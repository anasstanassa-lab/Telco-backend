# 📡 TelcoPulse — Network Monitoring Backend

A production-ready network monitoring system built with **FastAPI**, **PostgreSQL**, **SQLAlchemy**, and **Docker**.  
It continuously probes registered URLs for availability and latency, stores historical results, and exposes a clean REST API.

---

## 🏗️ Architecture

```
telcopulse/
├── app/
│   ├── api/               # FastAPI routers (HTTP layer)
│   │   ├── health.py      #   GET /health
│   │   └── targets.py     #   CRUD + logs + uptime
│   ├── core/
│   │   ├── config.py      # Pydantic Settings (env-driven)
│   │   └── logging.py     # Structured stdout logger
│   ├── db/
│   │   └── base.py        # Async SQLAlchemy engine + session factory
│   ├── models/
│   │   ├── target.py      # ORM: Target table
│   │   └── check_log.py   # ORM: CheckLog table
│   ├── schemas/
│   │   ├── target.py      # Pydantic request/response schemas
│   │   └── check_log.py   # Pydantic log response schema
│   ├── services/
│   │   ├── monitor.py     # HTTP probe logic + retry + alerting
│   │   ├── scheduler.py   # asyncio background task manager
│   │   └── target_service.py  # CRUD + uptime business logic
│   └── main.py            # FastAPI app + lifespan + middleware
├── alembic/               # Database migrations
├── Dockerfile             # Multi-stage production image
├── docker-compose.yml     # Backend + PostgreSQL
├── requirements.txt
└── .env.example
```

---

## 🚀 Quick Start (Docker — recommended)

### 1. Clone and configure

```bash
git clone <repo-url>
cd telcopulse
cp .env.example .env          # edit passwords before production use
```

### 2. Build and start

```bash
docker compose up --build -d
```

### 3. Verify

```bash
curl http://localhost:8000/health
# → {"status":"ok","timestamp":"2026-05-06T..."}

curl http://localhost:8000/docs   # Swagger UI
```

The monitoring background worker starts automatically and runs every **60 seconds**.

---

## 🖥️ Local Development (without Docker)

### Prerequisites
- Python 3.12+
- A running PostgreSQL instance

### Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Point the app at your local database
export POSTGRES_HOST=localhost
export POSTGRES_USER=telcopulse
export POSTGRES_PASSWORD=telcopulse_secret
export POSTGRES_DB=telcopulse
```

### Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📖 API Reference

| Method   | Endpoint                          | Description                          |
|----------|-----------------------------------|--------------------------------------|
| `GET`    | `/health`                         | Liveness probe                       |
| `GET`    | `/api/targets`                    | List all monitored targets           |
| `POST`   | `/api/targets`                    | Register a new target                |
| `DELETE` | `/api/targets/{id}`               | Remove a target + all its logs       |
| `GET`    | `/api/targets/{id}/logs`          | Paginated probe history              |
| `GET`    | `/api/targets/{id}/uptime`        | Uptime % over a configurable window  |

Full interactive docs at **`/docs`** (Swagger) or **`/redoc`**.

### Add a target

```bash
curl -X POST http://localhost:8000/api/targets \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "name": "Example"}'
```

### List targets

```bash
curl http://localhost:8000/api/targets
```

### View logs (paginated)

```bash
curl "http://localhost:8000/api/targets/{id}/logs?limit=50&offset=0"
```

### Uptime over 7 days

```bash
curl "http://localhost:8000/api/targets/{id}/uptime?hours=168"
```

### Delete a target

```bash
curl -X DELETE http://localhost:8000/api/targets/{id}
```

---

## ⚙️ Configuration

All settings are driven by environment variables (see `.env.example`):

| Variable                    | Default          | Description                          |
|-----------------------------|------------------|--------------------------------------|
| `POSTGRES_USER`             | `telcopulse`     | DB username                          |
| `POSTGRES_PASSWORD`         | `telcopulse_secret` | DB password                       |
| `POSTGRES_DB`               | `telcopulse`     | Database name                        |
| `POSTGRES_HOST`             | `db`             | DB hostname (service name in Compose)|
| `POSTGRES_PORT`             | `5432`           | DB port                              |
| `MONITOR_INTERVAL_SECONDS`  | `60`             | Probe cycle interval                 |
| `HTTP_TIMEOUT_SECONDS`      | `10`             | Per-request HTTP timeout             |
| `HTTP_MAX_RETRIES`          | `2`              | Retry attempts before marking DOWN   |
| `HTTP_RETRY_WAIT_SECONDS`   | `2`              | Wait between retries                 |
| `RATE_LIMIT_PER_MINUTE`     | `60`             | Max API requests per IP/minute       |
| `DEBUG`                     | `false`          | Enable SQL query logging             |

---

## 🔄 Background Monitoring

The scheduler (`app/services/scheduler.py`) runs an asyncio task that:

1. Fetches all registered targets from the database.
2. Sends concurrent `GET` requests (via **httpx**) to every target.
3. Retries transient failures up to `HTTP_MAX_RETRIES` times.
4. Writes a `CheckLog` row for every probe.
5. Updates the `Target` row with the latest status and latency.
6. Logs **alerts** when a target transitions between UP ↔ DOWN.

All probes are non-blocking (`async/await`) so one slow target cannot stall others.

---

## 🗄️ Database Schema

```sql
-- Monitored endpoints
CREATE TABLE targets (
    id              VARCHAR(36) PRIMARY KEY,
    url             VARCHAR(2048) UNIQUE NOT NULL,
    name            VARCHAR(255) NOT NULL,
    status          target_status NOT NULL DEFAULT 'UNKNOWN',
    last_latency_ms FLOAT,
    last_checked_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL
);

-- Immutable probe history
CREATE TABLE check_logs (
    id          VARCHAR(36) PRIMARY KEY,
    target_id   VARCHAR(36) REFERENCES targets(id) ON DELETE CASCADE,
    status      target_status NOT NULL,
    latency_ms  FLOAT,
    error_msg   TEXT,
    checked_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX ON check_logs (target_id);
CREATE INDEX ON check_logs (checked_at);
```

---

## 🛡️ Reliability Features

| Feature              | Implementation                                           |
|----------------------|----------------------------------------------------------|
| Retry logic          | Up to N retries with configurable wait (tenacity-style)  |
| Timeout handling     | `httpx` timeouts, latency recorded even on failure       |
| Status transitions   | Alerts logged on UP→DOWN and DOWN→UP transitions         |
| Rate limiting        | Per-IP request throttling via `slowapi`                  |
| URL validation       | Pydantic `HttpUrl` + custom scheme validator             |
| Duplicate prevention | Unique constraint on `url` + service-layer check         |
| Graceful shutdown    | asyncio task cancellation on SIGTERM                     |
| DB resilience        | `pool_pre_ping=True`, connection pool sizing             |

---

## 🐳 Docker Commands

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f backend

# Stop
docker compose down

# Stop + delete DB volume (DESTRUCTIVE)
docker compose down -v

# Rebuild after code changes
docker compose up --build -d
```

---

## 📦 Scaling Considerations

- **Multiple workers**: Set `--workers N` in the Dockerfile CMD for CPU-bound scaling. Note: the background scheduler creates one asyncio task per worker — for production, consider moving the scheduler to a dedicated worker service or using a distributed task queue (Celery + Redis).
- **Database**: Add read replicas and connection pooling (PgBouncer) as load grows.
- **Alerting**: Replace the logger-based alerts in `monitor.py` with webhooks, PagerDuty, or a message queue.
- **Metrics**: Instrument with Prometheus (add `prometheus-fastapi-instrumentator`) for Grafana dashboards.
