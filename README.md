# Universal Biometric Integration Platform

FastAPI middleware and Vue/Vuetify console for ZKTeco, Suprema, Hikvision, and OSDP devices.

## Ubuntu deployment

```bash
git clone https://github.com/Brent-developer/AIO-Dashboard.git
cd AIO-Dashboard
cp .env.example .env
chmod 600 .env
nano .env
docker compose up --build -d
docker compose ps
curl http://127.0.0.1:8080/health/ready
```

Open `http://<VM-IP>:8080`. Keep PostgreSQL and Redis internal; only expose port 8080 through the VM firewall or reverse proxy.

Useful commands:

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose down
```

OpenAPI is available at `http://<VM-IP>:8080/docs`.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

In another shell:

```bash
source .venv/bin/activate
celery -A tasks.celery_app.celery_app worker --loglevel=info
```

The dashboard can be run separately with Node.js 22+:

```bash
cd frontend
npm install
npm run dev
```

## Security

Replace every placeholder secret before deployment. Use HTTPS at a reverse proxy, restrict device-network access, and never publish PostgreSQL or Redis ports. Back up the database and encryption key separately.

## Device workflow

1. Create a device through the authenticated API.
2. Connect over the vendor protocol.
3. Clone the live device profile into the sandbox.
4. Run controlled latency, offline, malformed-response, or healthy scenarios.
5. Run synchronization only after validating the device driver and credentials.
