# Universal Biometric Integration Platform

FastAPI middleware that dynamically loads ZKTeco, Suprema, Hikvision, and OSDP drivers behind one normalized API.

## Run locally

### Ubuntu VM

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip redis-server
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000
```

In another shell, start the worker when background synchronization is needed:

```bash
source .venv/bin/activate
celery -A tasks.celery_app.celery_app worker --loglevel=info
```

The API is then available at `http://<VM-IP>:8000`; keep port 8000 restricted with UFW or a reverse proxy.

### Windows / macOS

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` values into your environment. The default database is local SQLite if `DATABASE_URL` is omitted.
4. Start Redis (and PostgreSQL when configured): `docker compose up -d`.
5. Start the API: `uvicorn main:app --reload`.
6. Start a worker: `celery -A tasks.celery_app.celery_app worker --loglevel=info`.

The API documentation is at `/docs`. Development credentials default to `admin` / `admin`; always override them in a deployed environment.

Device passwords and biometric templates are encrypted before storage. Manufacturer drivers are discovered dynamically by `core.plugin_loader`, so core services never import a concrete driver.
