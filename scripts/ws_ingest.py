#!/usr/bin/env python3
"""
Coinbase Advanced Trade WebSocket → Kafka ingestor.

Connects to the public market-data WebSocket, subscribes to the ticker
channel for one or more trading pairs, and publishes each tick to the
Kafka topic `ticks.raw`.  Raw messages are also mirrored to data/raw/
as NDJSON for replay.
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("ws_ingest")

WS_URL = "wss://advanced-trade-ws.coinbase.com"
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "ticks.raw"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def _subscribe_msg(pairs: list[str], channel: str) -> str:
    return json.dumps({
        "type": "subscribe",
        "product_ids": pairs,
        "channel": channel,
    })


def _delivery_cb(err, msg):
    if err:
        log.error("Kafka delivery failed: %s", err)


def _make_producer() -> Producer:
    return Producer({
        "bootstrap.servers": KAFKA_BROKER,
        "linger.ms": 50,
        "batch.num.messages": 100,
    })


async def ingest(pairs: list[str], minutes: float, mirror: bool, stop: asyncio.Event):
    producer = _make_producer()

    ndjson_fh = None
    if mirror:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ndjson_path = RAW_DIR / f"ticks_{ts}.ndjson"
        ndjson_fh = open(ndjson_path, "a")
        log.info("Mirroring raw data → %s", ndjson_path)

    deadline = time.time() + minutes * 60 if minutes > 0 else float("inf")
    msg_count = 0
    backoff = 1

    while time.time() < deadline and not stop.is_set():
        try:
            async with websockets.connect(
                WS_URL, ping_interval=20, ping_timeout=10
            ) as ws:
                await ws.send(_subscribe_msg(pairs, "ticker"))
                await ws.send(_subscribe_msg(pairs, "heartbeats"))
                log.info("Connected & subscribed: %s", pairs)
                backoff = 1

                while time.time() < deadline and not stop.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    except asyncio.TimeoutError:
                        log.warning("No message for 30 s — reconnecting")
                        break

                    data = json.loads(raw)
                    channel = data.get("channel", "")

                    if channel == "heartbeats":
                        continue
                    if channel == "subscriptions":
                        log.info("Subscription confirmed: %s",
                                 [e.get("subscriptions", {}) for e in data.get("events", [])])
                        continue

                    if channel != "ticker":
                        continue

                    for event in data.get("events", []):
                        for ticker in event.get("tickers", []):
                            tick = {
                                "product_id": ticker.get("product_id"),
                                "price": ticker.get("price"),
                                "best_bid": ticker.get("best_bid"),
                                "best_bid_qty": ticker.get("best_bid_quantity"),
                                "best_ask": ticker.get("best_ask"),
                                "best_ask_qty": ticker.get("best_ask_quantity"),
                                "volume_24h": ticker.get("volume_24_h"),
                                "low_24h": ticker.get("low_24_h"),
                                "high_24h": ticker.get("high_24_h"),
                                "price_pct_chg_24h": ticker.get("price_percent_chg_24_h"),
                                "ws_timestamp": data.get("timestamp"),
                                "sequence_num": data.get("sequence_num"),
                                "event_type": event.get("type"),
                                "received_at": datetime.now(timezone.utc).isoformat(),
                            }

                            payload = json.dumps(tick)
                            producer.produce(
                                KAFKA_TOPIC,
                                key=tick["product_id"],
                                value=payload,
                                callback=_delivery_cb,
                            )

                            if ndjson_fh:
                                ndjson_fh.write(payload + "\n")

                            msg_count += 1
                            if msg_count % 100 == 0:
                                log.info("Published %d ticks so far", msg_count)
                                producer.flush()
                                if ndjson_fh:
                                    ndjson_fh.flush()

                    producer.poll(0)

        except (websockets.ConnectionClosed, ConnectionError, OSError) as exc:
            log.warning("Connection lost (%s) — reconnecting in %d s", exc, backoff)
            await asyncio.sleep(min(backoff, deadline - time.time()))
            backoff = min(backoff * 2, 30)
        except Exception:
            log.exception("Unexpected error — reconnecting in %d s", backoff)
            await asyncio.sleep(min(backoff, deadline - time.time()))
            backoff = min(backoff * 2, 30)

    producer.flush()
    if ndjson_fh:
        ndjson_fh.close()
    log.info("Finished. Total ticks published: %d", msg_count)


def main():
    parser = argparse.ArgumentParser(
        description="Coinbase WebSocket → Kafka ingestor"
    )
    parser.add_argument(
        "--pair", nargs="+", default=["BTC-USD"],
        help="Trading pair(s), e.g. BTC-USD ETH-USD",
    )
    parser.add_argument(
        "--minutes", type=float, default=15,
        help="How long to run (0 = indefinite)",
    )
    parser.add_argument(
        "--no-mirror", action="store_true",
        help="Skip writing NDJSON to data/raw/",
    )
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    stop = asyncio.Event()

    def on_signal():
        log.info("Shutdown signal received")
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, on_signal)

    try:
        loop.run_until_complete(
            ingest(args.pair, args.minutes, mirror=not args.no_mirror, stop=stop)
        )
    finally:
        loop.close()


if __name__ == "__main__":
    main()
