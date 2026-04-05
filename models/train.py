#!/usr/bin/env python3
"""
Train a baseline z-score model and a Logistic Regression model for
volatility spike detection.  Logs parameters, metrics, and artifacts
to MLflow.
"""

import argparse
import json
import logging
import os
import pickle
import sys
from math import log
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    f1_score,
    precision_recall_curve,
)
from sklearn.preprocessing import StandardScaler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("train")

FEATURE_COLS = [
    "midprice_log_return",
    "bid_ask_spread",
    "spread_bps",
    "rolling_volatility",
    "trade_intensity",
    "order_book_imbalance",
]

HORIZON = 60
THRESHOLD_PERCENTILE = 90
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlruns/mlflow.db")


def compute_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Compute forward-looking volatility and binary spike label."""
    ts = df["timestamp"].values
    returns = df["midprice_log_return"].values
    sigma_future = np.full(len(df), np.nan)

    for i in range(len(df)):
        t0 = ts[i]
        horizon_end = t0 + np.timedelta64(HORIZON, "s")
        mask = (ts > t0) & (ts <= horizon_end)
        future_rets = returns[mask]
        if len(future_rets) >= 2:
            sigma_future[i] = np.std(future_rets, ddof=1)

    df["sigma_future"] = sigma_future
    df = df.dropna(subset=["sigma_future"]).copy()

    threshold = np.percentile(df["sigma_future"], THRESHOLD_PERCENTILE)
    df["label"] = (df["sigma_future"] >= threshold).astype(int)
    logger.info(
        "Threshold (P%d): %.8f — positive rate: %.2f%%",
        THRESHOLD_PERCENTILE, threshold, df["label"].mean() * 100,
    )
    return df, threshold


def time_split(df: pd.DataFrame):
    """60/20/20 time-based split."""
    n = len(df)
    train_end = int(n * 0.6)
    val_end = int(n * 0.8)
    return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]


def best_f1_threshold(y_true, y_prob):
    """Find the probability threshold that maximizes F1."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    f1_scores = 2 * precision * recall / (precision + recall + 1e-8)
    best_idx = np.argmax(f1_scores)
    return thresholds[min(best_idx, len(thresholds) - 1)], f1_scores[best_idx]


# ── Baseline: z-score rule ───────────────────────────────────────────

def train_baseline(train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame):
    """
    Baseline: predict spike if rolling_volatility z-score > 1.0.
    Uses train set to compute mean/std, evaluates on val and test.
    """
    col = "rolling_volatility"
    mu = train[col].mean()
    sigma = train[col].std()

    def predict(df):
        z = (df[col] - mu) / sigma
        return (z > 1.0).astype(int), z.values

    y_train_pred, _ = predict(train)
    y_val_pred, z_val = predict(val)
    y_test_pred, z_test = predict(test)

    val_pr_auc = average_precision_score(val["label"], z_val)
    test_pr_auc = average_precision_score(test["label"], z_test)
    val_f1 = f1_score(val["label"], y_val_pred, zero_division=0)
    test_f1 = f1_score(test["label"], y_test_pred, zero_division=0)

    logger.info("Baseline — val PR-AUC: %.4f, test PR-AUC: %.4f", val_pr_auc, test_pr_auc)

    return {
        "model_name": "baseline_zscore",
        "params": {"feature": col, "z_threshold": 1.0, "mu": mu, "sigma": sigma},
        "val_pr_auc": val_pr_auc,
        "test_pr_auc": test_pr_auc,
        "val_f1": val_f1,
        "test_f1": test_f1,
        "test_preds": z_test,
    }


# ── ML model: Logistic Regression ───────────────────────────────────

def train_logreg(train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame):
    """Logistic Regression with StandardScaler."""
    scaler = StandardScaler()
    X_train = scaler.fit_transform(train[FEATURE_COLS])
    X_val = scaler.transform(val[FEATURE_COLS])
    X_test = scaler.transform(test[FEATURE_COLS])
    y_train = train["label"].values
    y_val = val["label"].values
    y_test = test["label"].values

    model = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        solver="lbfgs",
        C=1.0,
    )
    model.fit(X_train, y_train)

    val_prob = model.predict_proba(X_val)[:, 1]
    test_prob = model.predict_proba(X_test)[:, 1]

    val_pr_auc = average_precision_score(y_val, val_prob)
    test_pr_auc = average_precision_score(y_test, test_prob)

    opt_thresh, opt_f1 = best_f1_threshold(y_val, val_prob)
    test_pred = (test_prob >= opt_thresh).astype(int)
    test_f1 = f1_score(y_test, test_pred, zero_division=0)

    logger.info("LogReg — val PR-AUC: %.4f, test PR-AUC: %.4f", val_pr_auc, test_pr_auc)
    logger.info("LogReg — optimal threshold: %.4f, test F1: %.4f", opt_thresh, test_f1)

    return {
        "model_name": "logistic_regression",
        "model": model,
        "scaler": scaler,
        "params": {
            "C": 1.0,
            "solver": "lbfgs",
            "class_weight": "balanced",
            "features": FEATURE_COLS,
            "opt_threshold": float(opt_thresh),
        },
        "val_pr_auc": val_pr_auc,
        "test_pr_auc": test_pr_auc,
        "val_f1": float(opt_f1),
        "test_f1": test_f1,
        "test_preds": test_prob,
    }


# ── MLflow logging ──────────────────────────────────────────────────

def log_run(result: dict, threshold: float, artifacts_dir: Path):
    """Log a single model run to MLflow."""
    with mlflow.start_run(run_name=result["model_name"]):
        mlflow.log_param("model_name", result["model_name"])
        mlflow.log_param("spike_threshold", threshold)
        mlflow.log_param("horizon_sec", HORIZON)
        mlflow.log_param("threshold_percentile", THRESHOLD_PERCENTILE)
        for k, v in result["params"].items():
            mlflow.log_param(k, v)

        mlflow.log_metric("val_pr_auc", result["val_pr_auc"])
        mlflow.log_metric("test_pr_auc", result["test_pr_auc"])
        mlflow.log_metric("val_f1", result["val_f1"])
        mlflow.log_metric("test_f1", result["test_f1"])

        if "model" in result:
            mlflow.sklearn.log_model(result["model"], "model")
            model_path = artifacts_dir / f"{result['model_name']}_model.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(result["model"], f)

        if "scaler" in result:
            scaler_path = artifacts_dir / f"{result['model_name']}_scaler.pkl"
            with open(scaler_path, "wb") as f:
                pickle.dump(result["scaler"], f)
            mlflow.log_artifact(str(scaler_path))

        mlflow.log_artifact(str(artifacts_dir / "metadata.json"))

    logger.info("Logged %s to MLflow", result["model_name"])


def main():
    parser = argparse.ArgumentParser(description="Train volatility models")
    parser.add_argument(
        "--features", default="data/processed/features.parquet",
        help="Path to features Parquet",
    )
    args = parser.parse_args()

    mlflow.set_tracking_uri(MLFLOW_URI)
    experiment = mlflow.get_experiment_by_name("crypto-volatility")
    if experiment is None:
        mlflow.create_experiment(
            "crypto-volatility",
            artifact_location="mlruns/artifacts",
        )
    mlflow.set_experiment("crypto-volatility")

    df = pd.read_parquet(args.features)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    df = df[df["product_id"] == "BTC-USD"].copy()
    logger.info("Filtered to BTC-USD: %d rows", len(df))

    df, threshold = compute_labels(df)

    train, val, test = time_split(df)
    logger.info("Split — train: %d, val: %d, test: %d", len(train), len(val), len(test))

    artifacts_dir = Path("models/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    train.to_parquet("data/processed/features_train.parquet", index=False)
    val.to_parquet("data/processed/features_val.parquet", index=False)
    test.to_parquet("data/processed/features_test.parquet", index=False)

    baseline = train_baseline(train, val, test)
    logreg = train_logreg(train, val, test)

    metadata = {
        "feature_cols": FEATURE_COLS,
        "threshold": float(threshold),
        "threshold_percentile": THRESHOLD_PERCENTILE,
        "horizon_sec": HORIZON,
        "train_rows": len(train),
        "val_rows": len(val),
        "test_rows": len(test),
        "opt_threshold": logreg["params"]["opt_threshold"],
    }
    with open(artifacts_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    log_run(baseline, threshold, artifacts_dir)
    log_run(logreg, threshold, artifacts_dir)

    logger.info("=== Results ===")
    logger.info("Baseline  — test PR-AUC: %.4f, test F1: %.4f", baseline["test_pr_auc"], baseline["test_f1"])
    logger.info("LogReg    — test PR-AUC: %.4f, test F1: %.4f", logreg["test_pr_auc"], logreg["test_f1"])


if __name__ == "__main__":
    main()
