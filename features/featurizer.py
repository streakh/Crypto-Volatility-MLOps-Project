#!/usr/bin/env python3
"""
Kafka consumer that reads raw ticks and produces windowed features.

Reads:  ticks.raw
Writes: ticks.features (Kafka) + data/processed/features.parquet

Feature computation is factored into reusable functions so that
scripts/replay.py can produce identical output from saved NDJSON.
"""

import argparse
import json
import logging
import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from math import log
from pathlib import Path

import numpy as np
import pandas as pd
from confluent_kafka import Consumer, Producer, KafkaError
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("featurizer")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
WINDOW_SEC = 60


def parse_timestamp(ts_str: str) -> float:
    """Parse an ISO-8601 timestamp string to epoch seconds."""
    ts_str = ts_str.replace("Z", "+00:00")
    ts_str = re.sub(r"(\.\d{6})\d+", r"\1", ts_str)
    return datetime.fromisoformat(ts_str).timestamp()


def compute_features(window: list[dict], current: dict) -> dict | None:
    """
    Compute features from a rolling window of ticks.
    ``window`` must include ``current`` as its last element and contain
    at least two ticks.
    """
    if len(window) < 2:
        return None

    midprices = []
    for t in window:
        bid = float(t["best_bid"])
        ask = float(t["best_ask"])
        midprices.append((bid + ask) / 2.0)

    log_returns = []
    for i in range(1, len(midprices)):
        if midprices[i - 1] > 0:
            log_returns.append(log(midprices[i] / midprices[i - 1]))

    if not log_returns:
        return None

    cur_bid = float(current["best_bid"])
    cur_ask = float(current["best_ask"])
    cur_mid = midprices[-1]
    cur_bid_qty = float(current.get("best_bid_qty", 0))
    cur_ask_qty = float(current.get("best_ask_qty", 0))
    qty_sum = cur_bid_qty + cur_ask_qty

    return {
        "timestamp": current.get("ws_timestamp", current.get("received_at", "")),
        "received_at": current.get("received_at", ""),
        "product_id": current["product_id"],
        "midprice": cur_mid,
        "midprice_log_return": log_returns[-1],
        "bid_ask_spread": cur_ask - cur_bid,
        "spread_bps": (cur_ask - cur_bid) / cur_mid * 10_000 if cur_mid > 0 else 0.0,
        "rolling_volatility": float(np.std(log_returns, ddof=1)) if len(log_returns) > 1 else 0.0,
        "trade_intensity": len(window),
        "order_book_imbalance": cur_bid_qty / qty_sum if qty_sum > 0 else 0.5,
        "price": float(current.get("price", cur_mid)),
        "volume_24h": float(current.get("volume_24h", 0)),
    }


class TickWindower:
    """Maintains per-product rolling windows and emits features."""

    def __init__(self, window_sec: int = WINDOW_SEC):
        self.window_sec = window_sec
        self.windows: dict[str, deque] = {}

    def add_tick(self, tick: dict) -> dict | None:
        ts_str = tick.get("ws_timestamp") or tick.get("received_at", "")
        try:
            ts = parse_timestamp(ts_str)
        except (ValueError, TypeError):
            return None

        tick["_epoch"] = ts
        pid = tick["product_id"]

        if pid not in self.windows:
            self.windows[pid] = deque()

        win = self.windows[pid]
        win.append(tick)

        cutoff = ts - self.window_sec
        while win and win[0]["_epoch"] < cutoff:
            win.popleft()

        return compute_features(list(win), tick)


# ── public helper for replay.py ──────────────────────────────────────

def featurize_ticks(ticks: list[dict], window_sec: int = WINDOW_SEC) -> list[dict]:
    """Compute features from an ordered list of raw ticks (for replay)."""
    windower = TickWindower(window_sec=window_sec)
    results = []
    for tick in ticks:
        feat = windower.add_tick(tick)
        if feat is not None:
            results.append(feat)
    return results


# ── Kafka consumer/producer loop ─────────────────────────────────────

def run_kafka(topic_in: str, topic_out: str, parquet_path: str, timeout_sec: float):
    consumer = Consumer({
        "bootstrap.servers": KAFKA_BROKER,
        "group.id": "featurizer",
        "auto.offset.reset": "earliest",
    })
    producer = Producer({"bootstrap.servers": KAFKA_BROKER})
    consumer.subscribe([topic_in])

    windower = TickWindower()
    features_buf: list[dict] = []
    count = 0
    idle = 0
    max_idle = 10
    deadline = time.time() + timeout_sec if timeout_sec > 0 else float("inf")

    logger.info("Featurizer: %s → %s  (parquet: %s)", topic_in, topic_out, parquet_path)

    try:
        while time.time() < deadline:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                idle += 1
                if timeout_sec == 0 and idle >= max_idle:
                    logger.info("No new messages for %d s — stopping", max_idle)
                    break
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    idle += 1
                    if timeout_sec == 0 and idle >= max_idle:
                        logger.info("Reached end of partition, idle %d s — stopping", max_idle)
                        break
                    continue
                logger.error("Consumer error: %s", msg.error())
                break

            idle = 0
            tick = json.loads(msg.value().decode())
            feat = windower.add_tick(tick)
            if feat is None:
                continue

            payload = json.dumps(feat)
            producer.produce(topic_out, key=feat["product_id"], value=payload)
            features_buf.append(feat)
            count += 1

            if count % 500 == 0:
                logger.info("Computed %d feature rows", count)
                producer.flush()

        producer.flush()
    finally:
        consumer.close()

    if features_buf:
        out = Path(parquet_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(features_buf)
        df.to_parquet(out, index=False)
        logger.info("Saved %d rows → %s", len(df), out)
    else:
        logger.warning("No features computed")

    logger.info("Done. Total feature rows: %d", count)


def main():
    parser = argparse.ArgumentParser(description="Tick featurizer (Kafka consumer)")
    parser.add_argument("--topic_in", default="ticks.raw")
    parser.add_argument("--topic_out", default="ticks.features")
    parser.add_argument("--parquet", default="data/processed/features.parquet")
    parser.add_argument(
        "--timeout", type=float, default=0,
        help="Seconds to run (0 = stop after topic is drained)",
    )
    args = parser.parse_args()
    run_kafka(args.topic_in, args.topic_out, args.parquet, args.timeout)


if __name__ == "__main__":
    main()
