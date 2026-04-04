#!/usr/bin/env python3
"""
Replay raw NDJSON tick files through the featurizer to regenerate
features offline.  Uses the same TickWindower / compute_features logic
as the live Kafka consumer so output is identical.
"""

import argparse
import glob
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from features.featurizer import featurize_ticks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("replay")


def load_raw_ticks(patterns: list[str]) -> list[dict]:
    """Load and merge ticks from one or more NDJSON file patterns."""
    paths: list[str] = []
    for pat in patterns:
        paths.extend(sorted(glob.glob(pat)))

    if not paths:
        raise FileNotFoundError(f"No files matched: {patterns}")

    ticks = []
    for p in paths:
        logger.info("Loading %s", p)
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    ticks.append(json.loads(line))

    logger.info("Loaded %d ticks from %d file(s)", len(ticks), len(paths))

    ticks.sort(key=lambda t: t.get("ws_timestamp", t.get("received_at", "")))
    return ticks


def main():
    parser = argparse.ArgumentParser(
        description="Replay raw NDJSON → features (offline featurizer)"
    )
    parser.add_argument(
        "--raw", nargs="+", required=True,
        help="Glob pattern(s) for raw NDJSON files, e.g. data/raw/*.ndjson",
    )
    parser.add_argument(
        "--out", default="data/processed/features.parquet",
        help="Output Parquet path",
    )
    args = parser.parse_args()

    ticks = load_raw_ticks(args.raw)
    features = featurize_ticks(ticks)

    if not features:
        logger.warning("No features produced — check your input data")
        return

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(features)
    df.to_parquet(out, index=False)
    logger.info("Wrote %d feature rows → %s", len(df), out)


if __name__ == "__main__":
    main()
