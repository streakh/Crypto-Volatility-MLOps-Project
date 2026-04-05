# Model Evaluation Report

## Experiment Summary

- **Task:** Binary classification of 60-second volatility spikes in BTC-USD
- **Data:** ~17,250 ticks from 2-hour Coinbase WebSocket collection
- **Split:** Time-based 60/20/20 (train: 10,349 / val: 3,450 / test: 3,450)
- **Spike threshold:** 0.00001266 (P90 of sigma_future, ~10% positive rate)

## Models

### Baseline: Z-Score Rule

Predicts a spike when the z-score of rolling_volatility (computed on the training set) exceeds 1.0. No learned parameters.

### ML Model: Logistic Regression

StandardScaler + LogisticRegression with class_weight="balanced", solver="lbfgs", C=1.0. Optimal decision threshold (0.8157) selected on validation set by maximizing F1.

## Results

| Metric | Baseline (z-score) | Logistic Regression |
|---|---|---|
| Validation PR-AUC | 0.0619 | 0.0565 |
| Test PR-AUC | 0.1734 | 0.1758 |
| Test F1 | 0.2179 | 0.1771 |
| Inference latency | N/A | 0.001s for 3,450 rows (~49,000x real-time) |

## Analysis

- Both models achieve PR-AUC around 0.17 on the test set, modestly above the random baseline of ~0.10 (equal to the positive class rate).
- The baseline and LogReg perform similarly, suggesting that rolling_volatility is the dominant predictive signal. The additional features provide marginal lift.
- The gap between validation and test PR-AUC (both models perform better on test) suggests non-stationarity in the data: the test window may contain more pronounced volatility patterns than the validation window.
- Inference latency is well under the 2x real-time requirement.

## Drift Assessment

Evidently drift reports comparing training vs test feature distributions are available in reports/evidently/. Key observations should be reviewed in the HTML reports for any significant feature drift.

## MLflow Tracking

All runs are logged to the "crypto-volatility" experiment in MLflow, accessible at http://localhost:5001. Each run includes parameters, metrics, and model artifacts.
