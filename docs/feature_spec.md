# Feature Specification

## Target Definition

- **Target horizon:** 60 seconds
- **Volatility proxy:** Rolling standard deviation of midprice log-returns over the next 60s
- **Label definition:** 1 if sigma_future >= threshold; else 0
- **Chosen threshold:** 0.00001266 (90th percentile of sigma_future, BTC-USD only)
- **Justification:** P90 yields a ~10% positive rate, providing sufficient spike samples for training while keeping the label selective. Threshold is computed from BTC-USD data only to avoid scale confounding with ETH-USD. The percentile plot shows a smooth curve with a clear uptick above P90, indicating that the top decile captures meaningfully elevated volatility.
- **Note:** when filtered to BTC-USD only for modeling, the P90 threshold is 0.00001266 (see model_card_v1.md for model-specific details).

## Input Features

| Feature | Description | Source fields |
|---|---|---|
| midprice | (best_bid + best_ask) / 2 | best_bid, best_ask |
| midprice_log_return | log(mid_t / mid_{t-1}), tick-to-tick | best_bid, best_ask |
| bid_ask_spread | best_ask - best_bid | best_bid, best_ask |
| spread_bps | Spread in basis points: spread / midprice * 10,000 | best_bid, best_ask |
| rolling_volatility | Std dev of log-returns over 60s window (ddof=1) | best_bid, best_ask |
| trade_intensity | Count of ticks in the 60s window | ws_timestamp |
| order_book_imbalance | bid_qty / (bid_qty + ask_qty) | best_bid_qty, best_ask_qty |

## Window Configuration

- **Window size:** 60 seconds (rolling, per product)
- **Minimum ticks:** 2 (features are not emitted until at least 2 ticks in window)

## Data Source

- **Coinbase Advanced Trade WebSocket** ticker channel
- **Trading pairs:** BTC-USD, ETH-USD
- **Raw format:** NDJSON (one JSON object per line)
- **Processed format:** Parquet
