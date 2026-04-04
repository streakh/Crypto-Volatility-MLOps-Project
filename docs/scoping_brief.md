# Scoping Brief - Crypto Volatility Spike Detection

## Use Case

Cryptocurrency markets exhibit frequent, short-lived volatility spikes driven by large trades, liquidations, and sentiment shifts. This project builds a real-time pipeline that ingests Coinbase Advanced Trade WebSocket data for BTC-USD and detects whether a volatility spike is likely in the next 60 seconds. The system is intended for informational monitoring — no trades are placed.

## Prediction Goal

Given the most recent window of tick-level market data (price, bid, ask, spread, volume), predict whether the rolling standard deviation of midprice log-returns over the **next 60 seconds** will exceed a threshold.

- **Target horizon:** 60 seconds into the future
- **Volatility proxy:** Rolling standard deviation of midprice log-returns over the next 60 s
- **Label:** 1 if sigma_future >= threshold; 0 otherwise
- **Threshold:** To be determined empirically via percentile analysis in Milestone 2 EDA

## Success Metric

- **Primary:** PR-AUC (Precision-Recall Area Under Curve), chosen because the positive class (spike) is expected to be rare, making ROC-AUC misleadingly optimistic.
- **Secondary:** F1 score at the chosen decision threshold.

## Data Source

- **Coinbase Advanced Trade WebSocket** — ticker channel (public, no auth required)
- **Trading pair:** BTC-USD (primary); ETH-USD (optional second pair)
- **Fields per tick:** price, best_bid, best_ask, bid/ask quantities, 24h volume, timestamp, sequence number

## Risk Assumptions

| Risk | Mitigation |
|------|-----------|
| WebSocket disconnects or data gaps | Exponential-backoff reconnect; heartbeat channel subscription; sequence number gap detection |
| Label imbalance (spikes are rare) | Use PR-AUC as primary metric; stratified or time-aware splits; consider oversampling |
| Look-ahead bias in features | Strict time-based train/validation/test split; replay script to verify feature consistency |
| Non-stationarity of crypto markets | Monitor with Evidently drift reports; retrain cadence awareness |
| Latency requirements for real-time use | Target inference under 2x real-time; lightweight models (logistic regression, small XGBoost) |
| Overfitting on short data windows | Collect sufficient data (several hours minimum); regularization; simple model baselines |
