# Handoff Package

## Selection Note

**Selected-base** — This individual submission is provided as the base model
for the team project. The Logistic Regression model trained on BTC-USD ticker
data can be used directly or extended with additional features/pairs.

## Contents

| File | Description |
|---|---|
| `raw_10min_slice.ndjson` | 10-minute sample of raw BTC-USD/ETH-USD tick data |
| `features_slice.parquet` | Features computed from the raw slice |
| `predictions.parquet` | Model predictions on the test set |

## Reproduction Steps

```bash
# 1. Start infrastructure
cd docker && docker compose up -d && cd ..

# 2. Install dependencies
pip install -r requirements.txt

# 3. Ingest live data (15 min)
python scripts/ws_ingest.py --pair BTC-USD --minutes 15

# 4. Generate features
python scripts/replay.py --raw "data/raw/*.ndjson" --out data/processed/features.parquet

# 5. Train models
python models/train.py --features data/processed/features.parquet

# 6. Run inference
python models/infer.py --features data/processed/features_test.parquet
```

## Key Files from Main Repo

- `docker/compose.yaml` — Kafka + MLflow
- `docker/Dockerfile.ingestor` — Containerized ingestor
- `.env.example` — Required environment variables
- `docs/feature_spec.md` — Feature definitions and threshold
- `docs/model_card_v1.md` — Model documentation
- `models/artifacts/` — Trained model and scaler
- `requirements.txt` — Python dependencies
- `reports/model_eval.pdf` — Evaluation with PR-AUC
- `reports/evidently/` — Drift and quality reports
