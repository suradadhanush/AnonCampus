# AnonCampus

**Anonymous Grievance Intelligence Platform for Higher Education Institutions**

AnonCampus converts raw anonymous student complaints into structured, clustered, and mathematically-scored signals. Institutions get ranked, evidence-backed issue intelligence — not a noisy complaint board.

---

## What It Is

AnonCampus is a **signal processing system**, not a forum.

Students submit grievances anonymously. The system:
1. **Moderates** content (strips PII, names, accusations)
2. **Classifies** by category and estimated severity
3. **Clusters** similar issues using semantic embeddings
4. **Scores** each cluster using a confidence formula gated by diversity rules
5. **Escalates** only when evidence meets governance thresholds
6. **Surfaces** ranked, explainable decisions to administrators

**Core guarantee:** No student identity is ever exposed, stored in responses, or logged.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI (Python 3.11) |
| Database | PostgreSQL 15 |
| Cache / Queue | Redis 7 |
| Async tasks | Celery + Celery Beat |
| NLP | sentence-transformers (`all-MiniLM-L6-v2`) |
| Frontend | Next.js 14, React 18, Tailwind CSS |
| Auth | JWT (access: 15 min, refresh: 7 days, DB-backed + revocable) |
| Reverse proxy | Nginx |
| Containers | Docker + Docker Compose |
| Migrations | Alembic |

---

## Project Structure

```
anoncampus/
├── backend/
│   ├── app/
│   │   ├── api/routes/         # auth.py, issues.py, admin.py
│   │   ├── core/               # config.py, security.py
│   │   ├── db/                 # session.py (async SQLAlchemy)
│   │   ├── middleware/         # rate_limit.py (Redis sliding window)
│   │   ├── models/             # user, cluster, issue, report, event_log...
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── services/           # scoring, clustering, moderation, issue_service
│   │   ├── tasks/              # Celery: score_tasks, cluster_tasks, trust_tasks
│   │   ├── tests/
│   │   │   ├── unit/           # test_scoring, test_moderation, test_clustering, test_state_machine
│   │   │   └── integration/    # test_api (full flow)
│   │   ├── utils/              # observability.py (structured JSON logging)
│   │   └── main.py             # FastAPI app entrypoint
│   ├── alembic/
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── alembic.ini
│   ├── pytest.ini
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx                # Landing page
│       │   ├── auth/login/page.tsx
│       │   ├── auth/register/page.tsx
│       │   ├── dashboard/page.tsx      # Student feed
│       │   ├── admin/page.tsx          # Admin dashboard
│       │   └── issues/[id]/page.tsx    # Issue detail + explainability
│       ├── components/
│       │   ├── admin/AdminTable.tsx    # Status updates, rejection reasons
│       │   ├── dashboard/ClusterCard.tsx
│       │   ├── dashboard/SubmitModal.tsx
│       │   └── ui/                     # ScoreBar, StatusBadge, ErrorBoundary
│       ├── hooks/useAuth.ts            # Token refresh + route protection
│       ├── lib/                        # api.ts, store.ts (Zustand), utils.ts
│       └── types/index.ts
│
├── docker/
│   ├── Dockerfile.backend
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Quick Start — Local Development

### Prerequisites

- Docker Desktop ≥ 24.x
- Docker Compose ≥ 2.x
- Git

### Step 1 — Clone the repository

```bash
git clone https://github.com/your-org/anoncampus.git
cd anoncampus
```

### Step 2 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```env
SECRET_KEY=your-random-32-char-secret-here
POSTGRES_PASSWORD=your-db-password
```

> **Generate a secure SECRET_KEY:**
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### Step 3 — Start all services

```bash
docker-compose up --build
```

This starts: PostgreSQL, Redis, FastAPI backend, Celery worker, Celery beat, and Nginx.

First startup takes 2–3 minutes while Docker builds images and the NLP model downloads.

### Step 4 — Run database migrations

In a second terminal:

```bash
docker-compose exec backend alembic upgrade head
```

This creates all tables, indexes, enums, and the partial unique index on `system_config`.

### Step 5 — Access the system

| Service | URL |
|---|---|
| Frontend (via Nginx) | http://localhost |
| Backend API | http://localhost:8000 |
| API Docs (dev only) | http://localhost:8000/api/docs |
| Health check | http://localhost:8000/health |
| Readiness check | http://localhost:8000/ready |

### Default development credentials

| Role | Email | Password |
|---|---|---|
| Super Admin | admin@nsrit.edu.in | Admin1234 |

> These credentials are seeded automatically in development mode only. They do **not** exist in production.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | Async PostgreSQL URL (asyncpg driver). Format: `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `SYNC_DATABASE_URL` | ✅ | Sync PostgreSQL URL (psycopg2 driver, used by Celery). Same credentials, no `+asyncpg`. |
| `POSTGRES_PASSWORD` | ✅ | Password for the PostgreSQL `anoncampus` user. Must match credentials in the DB URLs. |
| `REDIS_URL` | ✅ | Redis connection string. Used for Celery broker, rate limiting, and distributed locks. |
| `SECRET_KEY` | ✅ | JWT signing secret. **Minimum 32 characters. Must be random. Never reuse across environments.** |
| `ALGORITHM` | — | JWT algorithm. Default: `HS256`. Do not change without understanding the implications. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | Lifetime of access tokens in minutes. Default: `15`. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | — | Lifetime of refresh tokens in days. Default: `7`. |
| `ENVIRONMENT` | ✅ | `development` or `production`. Controls: docs visibility, seeding, log level, CORS strictness. |
| `ALLOWED_ORIGINS` | ✅ | JSON array of allowed frontend origins. Example: `["https://app.yourdomain.com"]`. Never use `*`. |

---

## Services Overview

| Service | Role |
|---|---|
| **backend** | FastAPI application server. Handles all HTTP requests. 2 Uvicorn workers. |
| **postgres** | Primary data store. Stores all users, issues, clusters, event logs, tokens. |
| **redis** | Broker for Celery task queue. Also used for rate limiting (sliding window) and distributed locks (`lock:cluster:{id}`). |
| **celery_worker** | Processes async tasks: score recomputation, spike detection, cluster maintenance. |
| **celery_beat** | Scheduler for periodic tasks: daily trust decay, hourly dormant cluster checks, daily cleanup jobs. |
| **nginx** | Reverse proxy. Handles rate limiting, security headers, SSL termination. Routes all traffic to the backend. |

---

## Database Setup

### Run migrations

```bash
# Inside Docker
docker-compose exec backend alembic upgrade head

# Or locally (with virtual environment)
cd backend
alembic upgrade head
```

### Check migration status

```bash
docker-compose exec backend alembic current
docker-compose exec backend alembic history
```

### Create a new migration after model changes

```bash
docker-compose exec backend alembic revision --autogenerate -m "describe_your_change"
docker-compose exec backend alembic upgrade head
```

---

## Running Tests

Tests use an in-memory SQLite database — no external services required.

```bash
# Inside Docker
docker-compose exec backend pytest

# Or locally
cd backend
pip install -r requirements.txt
pytest

# With verbose output and coverage
pytest -v --tb=short

# Run only unit tests
pytest app/tests/unit/

# Run only integration tests
pytest app/tests/integration/
```

**Coverage targets (≥80% on core modules):**

| Module | Tests |
|---|---|
| `services/scoring.py` | 28 unit tests |
| `services/moderation.py` | 9 unit tests |
| `services/clustering.py` | 14 unit tests |
| `models/cluster.py` (state machine) | 13 unit tests |
| Full API flow | Integration test suite |

---

## Database Backup and Restore

### Create a backup

```bash
# Backup to local file
docker-compose exec postgres pg_dump -U anoncampus anoncampus > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
docker-compose exec postgres pg_dump -U anoncampus -Fc anoncampus > backup_$(date +%Y%m%d_%H%M%S).dump
```

### Restore from backup

```bash
# Restore from plain SQL
cat backup.sql | docker-compose exec -T postgres psql -U anoncampus -d anoncampus

# Restore from compressed dump
docker-compose exec postgres pg_restore -U anoncampus -d anoncampus /path/to/backup.dump
```

### Automated daily backup (production recommendation)

Add to your server's crontab:

```bash
# Run backup every day at 2:00 AM, keep last 30 days
0 2 * * * docker-compose -f /path/to/anoncampus/docker-compose.yml exec -T postgres \
  pg_dump -U anoncampus anoncampus | gzip > /backups/anoncampus_$(date +\%Y\%m\%d).sql.gz && \
  find /backups -name "anoncampus_*.sql.gz" -mtime +30 -delete
```

---

## Production Deployment

### Step 1 — Provision a server

Minimum recommended specs:
- 2 vCPU, 4 GB RAM (for all services on one machine)
- Ubuntu 22.04 LTS
- Docker + Docker Compose installed

### Step 2 — Clone and configure

```bash
git clone https://github.com/your-org/anoncampus.git /opt/anoncampus
cd /opt/anoncampus
cp .env.example .env
```

Edit `.env` for production:

```env
SECRET_KEY=<generate-with: python -c "import secrets; print(secrets.token_hex(32))">
POSTGRES_PASSWORD=<strong-random-password>
DATABASE_URL=postgresql+asyncpg://anoncampus:<password>@postgres:5432/anoncampus
SYNC_DATABASE_URL=postgresql://anoncampus:<password>@postgres:5432/anoncampus
REDIS_URL=redis://redis:6379/0
ENVIRONMENT=production
ALLOWED_ORIGINS=["https://app.yourdomain.com"]
```

### Step 3 — Build and start containers

```bash
docker-compose up --build -d
```

### Step 4 — Run migrations

```bash
docker-compose exec backend alembic upgrade head
```

### Step 5 — Verify health

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"anoncampus-api","env":"production"}

curl http://localhost:8000/ready
# Expected: {"status":"ready","checks":{"db":true,"redis":true}}
```

---

## Nginx + Domain + SSL Setup

### Step 1 — Point your domain

In your DNS provider, create an A record:

```
app.yourdomain.com → <your-server-IP>
```

### Step 2 — Install Certbot on the host

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx -y
```

### Step 3 — Obtain SSL certificate

```bash
# Stop nginx container temporarily
docker-compose stop nginx

# Obtain certificate (port 80 must be free)
sudo certbot certonly --standalone -d app.yourdomain.com

# Restart nginx
docker-compose start nginx
```

### Step 4 — Configure nginx for SSL

In `docker/nginx.conf`:

1. In the HTTP server block, **comment out** the development proxy locations and **uncomment** the HTTPS redirect:
   ```nginx
   return 301 https://$host$request_uri;
   ```

2. **Uncomment** the entire HTTPS server block and replace `yourdomain.com` with your actual domain.

3. Mount the Let's Encrypt certificates into the nginx container. Add to `docker-compose.yml` under the `nginx` service:
   ```yaml
   volumes:
     - ./docker/nginx.conf:/etc/nginx/nginx.conf:ro
     - /etc/letsencrypt:/etc/letsencrypt:ro
   ```

4. Restart nginx:
   ```bash
   docker-compose restart nginx
   ```

### Step 5 — Auto-renew SSL certificates

```bash
# Test renewal
sudo certbot renew --dry-run

# Add to crontab for automatic renewal
echo "0 3 * * * certbot renew --quiet && docker-compose -f /opt/anoncampus/docker-compose.yml restart nginx" | sudo crontab -
```

---

## Scaling Notes

### Horizontal backend scaling

To run multiple backend instances behind Nginx, update `docker-compose.yml`:

```yaml
backend:
  deploy:
    replicas: 3
```

And update `docker/nginx.conf` upstream:

```nginx
upstream backend {
    server backend:8000;   # Docker Compose load-balances automatically
    keepalive 64;
}
```

### Celery worker scaling

To increase task throughput, increase worker concurrency or add more worker containers:

```bash
# Increase concurrency
command: celery -A app.tasks.celery_app worker --concurrency=8

# Or add a second worker service in docker-compose.yml
celery_worker_2:
  extends:
    service: celery_worker
```

### Redis high availability

For production Redis, consider:
- Redis Sentinel for automatic failover
- Redis Cluster for horizontal scaling
- Managed Redis (AWS ElastiCache, Upstash, Redis Cloud)

Update `REDIS_URL` in `.env` accordingly.

---

## Health Checks

| Endpoint | Method | Purpose | Expected Response |
|---|---|---|---|
| `/health` | `GET` | Liveness probe — is the process alive? | `{"status":"ok"}` — always 200 if the server is running |
| `/ready` | `GET` | Readiness probe — are DB and Redis reachable? | `{"status":"ready","checks":{"db":true,"redis":true}}` — 200 if all healthy, 503 if any fail |

Both endpoints are excluded from rate limiting and authentication. Used by Docker HEALTHCHECK, Nginx upstream checks, and Kubernetes liveness/readiness probes.

---

## Security Notes

### Authentication
- **Access tokens** expire in 15 minutes. Short lifetime limits exposure if a token is compromised.
- **Refresh tokens** are stored hashed (SHA-256) in the database, never in plain text. They support revocation on logout and detect reuse attacks via token family rotation.
- On suspicious refresh token reuse, the **entire token family** is revoked (all sessions for that user).

### Identity protection
- `student_id` is stored in the database but **never returned in any API response**.
- All log records are passed through `StudentIDMaskingFilter`, which replaces uppercase alphanumeric tokens matching the student ID pattern with `****`.
- Public user identity uses `anon_id` (UUID), which cannot be reversed to the real student.

### CORS
- `ALLOWED_ORIGINS` must be explicitly set. The value `*` (wildcard) is never used.
- In production, only list your exact frontend domain(s).

### Login protection
- After 10 failed login attempts from the same IP within 15 minutes, the IP is locked out for 15 minutes.
- Successful login clears the failure counter.

### Rate limiting (per user)
| Action | Limit |
|---|---|
| Issue submission | 3 per day |
| Support signal | 3 per day |
| Feedback | 5 per day |
| Login attempts | 10 per 15 min per IP |
| Registration | 5 per hour per IP |

---

## Troubleshooting

### Containers not starting

```bash
# Check logs for a specific service
docker-compose logs backend
docker-compose logs postgres
docker-compose logs celery_worker
```

### Database connection refused

Ensure PostgreSQL is healthy before the backend starts:
```bash
docker-compose ps   # Check all services are "Up (healthy)"
```

If postgres is not healthy:
```bash
docker-compose restart postgres
docker-compose restart backend
```

### Celery tasks not running

```bash
# Check worker is connected
docker-compose exec celery_worker celery -A app.tasks.celery_app inspect ping

# Check task queue
docker-compose exec celery_worker celery -A app.tasks.celery_app inspect active
```

### NLP model download fails on first run

The `sentence-transformers` model (`all-MiniLM-L6-v2`) downloads on first use (~90 MB). If it fails:
```bash
# Rebuild with no cache to force fresh download
docker-compose build --no-cache backend
```

The system falls back to TF-IDF similarity automatically if the model is unavailable.

### Migrations not applying

```bash
# Check current state
docker-compose exec backend alembic current

# Re-run
docker-compose exec backend alembic upgrade head
```

---

## API Reference

Interactive API documentation (development only):

- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc

### Key endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | — | Register with college email + student ID |
| `POST` | `/api/auth/login` | — | Login, receive access + refresh tokens |
| `POST` | `/api/auth/refresh` | — | Rotate refresh token, get new access token |
| `POST` | `/api/auth/logout` | ✅ | Revoke refresh token |
| `GET` | `/api/auth/me` | ✅ | Get current user profile |
| `POST` | `/api/issues` | ✅ Student | Submit anonymous issue |
| `GET` | `/api/issues/clusters` | ✅ Student | List clusters (student feed) |
| `GET` | `/api/issues/{id}` | ✅ Student | Get issue detail |
| `POST` | `/api/issues/{id}/support` | ✅ Student | Add support signal |
| `POST` | `/api/issues/{id}/feedback` | ✅ Student | Submit resolution feedback |
| `GET` | `/api/admin/stats` | ✅ Admin | Dashboard summary statistics |
| `GET` | `/api/admin/issues` | ✅ Admin | List clusters (admin view) |
| `GET` | `/api/admin/clusters/{id}` | ✅ Admin | Cluster detail with explainability |
| `POST` | `/api/admin/update-status` | ✅ Admin | Update cluster status (state machine) |
| `GET` | `/api/admin/audit-log` | ✅ Admin | Full admin action history |

---

*AnonCampus — Built for signal clarity, not complaint volume.*
