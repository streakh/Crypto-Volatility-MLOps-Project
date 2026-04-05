#!/usr/bin/env python3
"""
Generate Evidently data drift and data quality reports by comparing
the early and late halves of the feature dataset.
"""

import argparse
import logging
from pathlib import Path

import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset, DataSummaryPreset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("evidently_report")

FEATURE_COLS = [
    "midprice",
    "midprice_log_return",
    "bid_ask_spread",
    "spread_bps",
    "rolling_volatility",
    "trade_intensity",
    "order_book_imbalance",
]


def generate_reports(parquet_path: str, out_dir: str, reference_path: str = None):
    df = pd.read_parquet(parquet_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    if reference_path:
        ref = pd.read_parquet(reference_path)
        early = ref[FEATURE_COLS].reset_index(drop=True)
        late = df[FEATURE_COLS].reset_index(drop=True)
        logger.info("Reference: %d rows, Current: %d rows", len(early), len(late))
    else:
        midpoint = len(df) // 2
        early = df.iloc[:midpoint][FEATURE_COLS].reset_index(drop=True)
        late = df.iloc[midpoint:][FEATURE_COLS].reset_index(drop=True)
        logger.info("Early window: %d rows, Late window: %d rows", len(early), len(late))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    drift_report = Report([DataDriftPreset()])
    drift_result = drift_report.run(current_data=late, reference_data=early)
    drift_result.save_html(str(out / "data_drift.html"))
    drift_result.save_json(str(out / "data_drift.json"))
    logger.info("Saved data drift report → %s", out / "data_drift.html")

    quality_report = Report([DataSummaryPreset()])
    quality_result = quality_report.run(current_data=late, reference_data=early)
    quality_result.save_html(str(out / "data_quality.html"))
    quality_result.save_json(str(out / "data_quality.json"))
    logger.info("Saved data quality report → %s", out / "data_quality.html")


def main():
    parser = argparse.ArgumentParser(description="Generate Evidently reports")
    parser.add_argument(
        "--features", default="data/processed/features.parquet",
        help="Path to features Parquet file",
    )
    parser.add_argument(
        "--reference", default=None,
        help="Reference Parquet (e.g. training data). If omitted, splits input in half.",
    )
    parser.add_argument(
        "--out", default="reports/evidently",
        help="Output directory for reports",
    )
    args = parser.parse_args()
    generate_reports(args.features, args.out, args.reference)


if __name__ == "__main__":
    main()
