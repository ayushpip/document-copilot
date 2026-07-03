# Backend

## Run the API

From the backend folder:

```bash
uv run uvicorn app.main:app --reload
```

## Check health

```bash
curl http://127.0.0.1:8000/health
```

## Useful notes

- The app entrypoint is `app/main.py`
- The health endpoint is `GET /health`
- Environment variables are loaded from `.env`
