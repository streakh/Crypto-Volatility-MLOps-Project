# GenAI Usage Appendix

| Prompt (summary) | Used in | Verification |
|---|---|---|
| Kafka KRaft dual-listener config for host and container access | `docker/compose.yaml` | Tested with `docker compose ps`; verified connectivity from both host scripts and ingestor container |
| Coinbase Advanced Trade WebSocket ticker response parsing (nested events/tickers structure) | `scripts/ws_ingest.py` | Compared against live WebSocket output; confirmed field mapping |
| Async reconnect loop with exponential backoff using websockets + asyncio | `scripts/ws_ingest.py` | Tested by running ingestor for multiple minutes; verified reconnect behavior |
| confluent-kafka Consumer setup with earliest offset and PARTITION_EOF handling | `scripts/kafka_consume_check.py` | Ran against live topic, confirmed correct message consumption |
| Draft scoping brief structure and risk table | `docs/scoping_brief.md` | Reviewed and edited content to match project specifics |
