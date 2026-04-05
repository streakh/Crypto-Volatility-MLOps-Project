#!/usr/bin/env python3
"""
Score a features Parquet file using the trained Logistic Regression model.
Outputs predictions alongside the original features.
"""

import argparse
import json
import logging
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("infer")

ARTIFACTS = Path("models/artifacts")


def load_artifacts():
    with open(ARTIFACTS / "metadata.json") as f:
        meta = json.load(f)

    with open(ARTIFACTS / "logistic_regression_model.pkl", "rb") as f:
        model = pickle.load(f)

    with open(ARTIFACTS / "logistic_regression_scaler.pkl", "rb") as f:
        scaler = pickle.load(f)

    return model, scaler, meta


def main():
    parser = argparse.ArgumentParser(description="Run inference on features")
    parser.add_argument(
        "--features", default="data/processed/features_test.parquet",
        help="Input Parquet file",
    )
    parser.add_argument(
        "--out", default="data/processed/predictions.parquet",
        help="Output Parquet file with predictions",
    )
    args = parser.parse_args()

    model, scaler, meta = load_artifacts()
    feature_cols = meta["feature_cols"]
    opt_threshold = meta.get("opt_threshold", 0.5)

    df = pd.read_parquet(args.features)
    logger.info("Loaded %d rows from %s", len(df), args.features)

    X = df[feature_cols]

    start = time.time()
    X_scaled = scaler.transform(X)
    probs = model.predict_proba(X_scaled)[:, 1]
    elapsed = time.time() - start

    df["pred_prob"] = probs
    df["pred_label"] = (probs >= opt_threshold).astype(int)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)

    logger.info("Scored %d rows in %.3f s (%.1fx real-time for 60s windows)",
                len(df), elapsed, 60.0 / max(elapsed, 0.001))
    logger.info("Predicted spikes: %d / %d (%.2f%%)",
                df["pred_label"].sum(), len(df),
                df["pred_label"].mean() * 100)
    logger.info("Saved predictions → %s", out)


if __name__ == "__main__":
    main()
