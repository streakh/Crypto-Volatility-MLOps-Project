# Crypto Volatility Spike Detection

Real-time pipeline that ingests Coinbase WebSocket market data, streams it through Kafka, computes features, and trains models to detect short-term BTC-USD volatility spikes.

## Quick Start

```bash
# Start Kafka + MLflow
cd docker && docker compose up -d && cd ..

# Install dependencies
pip install -r requirements.txt

# Ingest live data (15 min)
python scripts/ws_ingest.py --pair BTC-USD --minutes 15

# Verify Kafka stream
python scripts/kafka_consume_check.py --topic ticks.raw --min 100

# Generate features from raw data
python scripts/replay.py --raw "data/raw/*.ndjson" --out data/processed/features.parquet

# Train models + log to MLflow
python models/train.py --features data/processed/features.parquet

# Run inference
python models/infer.py --features data/processed/features_test.parquet

# Generate Evidently drift report
python scripts/generate_evidently.py
```

## Repository Layout

```
docker/              Compose + Dockerfile
scripts/             Ingest, replay, Kafka check, Evidently
features/            Featurizer (Kafka consumer + replay-compatible)
models/              Training, inference, artifacts
notebooks/           EDA
reports/             Evaluation + drift reports
docs/                Scoping brief, feature spec, model card, GenAI log
data/raw/            Captured raw ticks (gitignored)
data/processed/      Features + predictions (gitignored)
handoff/             Team handoff package
mlruns/              MLflow store (gitignored)
```

## Key Results

| Model | Test PR-AUC | Test F1 |
|---|---|---|
| Baseline (z-score) | 0.1734 | 0.2179 |
| Logistic Regression | 0.1758 | 0.1771 |

## Requirements

- Python 3.10+
- Docker (for Kafka and MLflow)
- Coinbase API credentials in `.env` (see `.env.example`)
