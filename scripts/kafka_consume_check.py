#!/usr/bin/env python3
"""
Kafka consumer sanity check.

Reads messages from a Kafka topic and prints summary stats to verify
the stream is healthy.
"""

import argparse
import json
import os
import sys
import time

from confluent_kafka import Consumer, KafkaError
from dotenv import load_dotenv

load_dotenv()

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")


def consume_check(topic: str, min_messages: int, timeout: float):
    consumer = Consumer({
        "bootstrap.servers": KAFKA_BROKER,
        "group.id": "consume-check",
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([topic])

    count = 0
    pairs_seen: dict[str, int] = {}
    first_ts = None
    last_ts = None
    deadline = time.time() + timeout

    print(f"Reading from '{topic}' (timeout {timeout}s, need ≥{min_messages}) …\n")

    try:
        while time.time() < deadline:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"Consumer error: {msg.error()}", file=sys.stderr)
                break

            data = json.loads(msg.value().decode())
            count += 1
            pid = data.get("product_id", "unknown")
            pairs_seen[pid] = pairs_seen.get(pid, 0) + 1
            ts = data.get("ws_timestamp", "")
            if first_ts is None:
                first_ts = ts
            last_ts = ts

            if count <= 3:
                print(f"  sample {count}: {json.dumps(data, indent=2)}\n")

            if count >= min_messages:
                break
    finally:
        consumer.close()

    print("=" * 50)
    print(f"Messages read : {count}")
    print(f"Pairs seen    : {pairs_seen}")
    print(f"First ts      : {first_ts}")
    print(f"Last ts       : {last_ts}")
    print("=" * 50)

    if count >= min_messages:
        print(f"\n✓ PASS — got {count} messages (≥{min_messages})")
        sys.exit(0)
    else:
        print(f"\n✗ FAIL — only {count} messages (need ≥{min_messages})")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Kafka consumer sanity check")
    parser.add_argument("--topic", default="ticks.raw", help="Topic to read")
    parser.add_argument("--min", type=int, default=100, help="Minimum messages expected")
    parser.add_argument("--timeout", type=float, default=30, help="Max seconds to wait")
    args = parser.parse_args()

    consume_check(args.topic, args.min, args.timeout)


if __name__ == "__main__":
    main()
