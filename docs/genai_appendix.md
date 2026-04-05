# GenAI Usage Appendix

| Prompt (summary) | Used in | Verification |
|---|---|---|
| Kafka KRaft dual-listener config for host and container access | `docker/compose.yaml` | Tested with `docker compose ps`; verified connectivity from both host scripts and ingestor container |
| Coinbase Advanced Trade WebSocket ticker response parsing (nested events/tickers structure) | `scripts/ws_ingest.py` | Compared against live WebSocket output; confirmed field mapping |
| Async reconnect loop with exponential backoff using websockets + asyncio | `scripts/ws_ingest.py` | Tested by running ingestor for multiple minutes; verified reconnect behavior |
| confluent-kafka Consumer setup with earliest offset and PARTITION_EOF handling | `scripts/kafka_consume_check.py` | Ran against live topic, confirmed correct message consumption |
| Draft scoping brief structure and risk table | `docs/scoping_brief.md` | Reviewed and edited content to match project specifics |
| Rolling window pruning with deque for per-product tick windows | `features/featurizer.py` | Verified window correctly drops ticks older than 60s; checked feature output against manual calculation |
| Forward-looking sigma_future computation with numpy datetime indexing | `notebooks/eda.ipynb` | Validated label counts match expected percentile rates |
| Evidently Report API for drift and data quality presets | `scripts/generate_evidently.py` | Fixed preset name (DataSummaryPreset); reviewed generated HTML reports |
| MLflow artifact logging with local SQLite backend | `models/train.py` | Debugged container artifact path issue; switched to direct SQLite URI; verified runs in MLflow UI |
| Model card structure and evaluation report writeup | `docs/model_card_v1.md`, `reports/model_eval.md` | Reviewed and edited to reflect correct metrics and model details |
| Pandoc commands for markdown to PDF conversion, fixing Unicode issues | `docs/scoping_brief.pdf`, `reports/model_eval.pdf` | Tested conversion; replaced Unicode characters that basictex couldn't handle |
| Concise readme for overall project | `README.md` | Reviewed and edited to reflect correct information |