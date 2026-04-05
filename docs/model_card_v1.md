# Model Card v1 - Crypto Volatility Spike Detector

## Model Details

- **Model type:** Logistic Regression (scikit-learn)
- **Version:** 1.0
- **Training framework:** scikit-learn 1.7.2
- **Feature scaling:** StandardScaler
- **Class balancing:** class_weight="balanced"

## Intended Use

Detect short-term (60-second) volatility spikes in BTC-USD market data
streamed from the Coinbase Advanced Trade WebSocket API. This model is
intended for informational monitoring only - no trading decisions should
be made based on its output.

## Training Data

- **Source:** Coinbase Advanced Trade WebSocket, ticker channel
- **Pair:** BTC-USD
- **Collection period:** ~2 hours of continuous streaming
- **Split:** 60% train (10,349 rows) / 20% validation (3,450) / 20% test (3,450)
- **Split method:** Time-based (chronological, no shuffling)

## Label Definition

- **Target:** Binary spike indicator
- **Volatility proxy:** Rolling std of midprice log-returns over the next 60 seconds
- **Threshold:** 0.00001266 (90th percentile of BTC-USD sigma_future)
- **Positive rate:** ~10%

## Features

| Feature | Description |
|---|---|
| midprice_log_return | Tick-to-tick log-return of midprice |
| bid_ask_spread | best_ask - best_bid |
| spread_bps | Spread in basis points |
| rolling_volatility | Std dev of log-returns over 60s window |
| trade_intensity | Tick count in 60s window |
| order_book_imbalance | bid_qty / (bid_qty + ask_qty) |

## Performance

| Metric | Baseline (z-score) | Logistic Regression |
|---|---|---|
| Test PR-AUC | 0.1734 | 0.1758 |
| Test F1 | 0.2179 | 0.1771 |
| Inference speed | N/A | ~49,000x real-time |

- **Primary metric:** PR-AUC (chosen because spikes are rare; ROC-AUC would
  be misleadingly optimistic)
- The baseline uses z-scores of rolling_volatility as prediction scores.
  These are unbounded (not probabilities), which is valid for PR-AUC ranking
  but should not be interpreted as calibrated probabilities.

## Limitations

- Trained on ~2 hours of data from a single session. Performance may degrade
  in different market regimes (high news activity, weekends, etc.).
- BTC-USD only. Not validated on other trading pairs.
- PR-AUC of ~0.18 indicates modest predictive power above random (~0.10
  baseline for 10% positive rate). The model captures some signal but is
  far from production-ready.
- No external features (news, funding rates, order book depth) are included.

## Ethical Considerations

- This model uses only public market data. No personal or private data is involved.
- Not intended for automated trading. Misuse for trading could result in
  financial loss.

## Drift Monitoring

- Evidently reports are generated comparing training vs test feature distributions.
- Reports are stored in reports/evidently/ as HTML and JSON.
