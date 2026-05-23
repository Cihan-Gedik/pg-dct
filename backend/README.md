# PG-DCT API

FastAPI service for cluster inventory and Patroni discovery.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8080
```
