# DevTask

> High-performance team project & task management platform inspired by Linear and Trello, built with Django 5, Django REST Framework, Django Channels, PostgreSQL, and Redis.

---

## Table of Contents
- [Architecture & Tech Stack](#architecture--tech-stack)
- [Key Features](#key-features)
- [Security & Production Readiness Audit](#security--production-readiness-audit)
- [Local Development Setup](#local-development-setup)
- [Docker & Docker Compose Deployment](#docker--docker-compose-deployment)
- [Automated Tests & Quality Checks](#automated-tests--quality-checks)
- [Performance Benchmarking & Load Testing](#performance-benchmarking--load-testing)
- [Production Deployment Guide](#production-deployment-guide)
- [Health Check & Monitoring](#health-check--monitoring)
- [Troubleshooting & Unresolved Risks](#troubleshooting--unresolved-risks)

---

## Architecture & Tech Stack

- **Backend Framework**: Django 5.2 (Python 3.12+)
- **API Engine**: Django REST Framework (DRF) 3.18
- **API Documentation**: DRF Spectacular (OpenAPI 3.0 / Swagger UI & Redoc)
- **ASGI & WebSockets**: Daphne 4.2 + Django Channels 4.2
- **Channel Layer**: Redis (`channels-redis`) for multi-worker real-time synchronization; In-memory fallback for local single-process development
- **Database**: PostgreSQL 16 (production) / SQLite (zero-config local development)
- **Database Connection Pooling**: `dj-database-url` with connection health checks and `conn_max_age=600`
- **Static Assets**: WhiteNoise with gzip/Brotli compression and cache manifest (`CompressedManifestStaticFilesStorage`)
- **Frontend**: Vanilla JavaScript (ES6+), Bootstrap 5.3 (Sleek Dark Theme), native Drag & Drop Kanban, resilient WebSocket client with auth failure rejection handling

---

## Key Features

1. **Workspace & Project Management**:
   - Multi-tenant workspace isolation.
   - Role-based access control: `OWNER`, `MANAGER`, `MEMBER`.
   - Comprehensive project lifecycle management (creation, update, archiving, restoring, ownership transfer).
2. **Interactive Kanban Board**:
   - Drag-and-drop task movement across `TODO`, `IN_PROGRESS`, and `DONE` states.
   - Optimistic UI updates with automatic rollback on network failure.
   - Accessible keyboard/menu fallback controls.
   - Auto-computed position indexing and automatic completion timestamps (`completed_at`).
3. **Real-Time Synchronization**:
   - Bi-directional WebSockets via Daphne and Django Channels.
   - Project-scoped event channels (`project_<id>`) ensuring zero cross-project leakage.
   - WebSocket connection authentication and membership verification on handshake.
   - Intelligent reconnect logic that aborts retry storms upon `4001` (Unauthenticated) or `4003` (Forbidden) errors.
4. **Task Collaboration & History**:
   - Task assignment restricted strictly to confirmed project members.
   - Rich task descriptions and threaded comments.
   - Automatic audit logging (`ActivityLog`) capturing membership changes, task mutations, and comments.
5. **Search, Filtering, and Pagination**:
   - Full-text search across titles and descriptions.
   - Priority, assignee, and status filters.
   - Standardized paginated endpoints with custom page sizes and ordering.

---

## Security & Production Readiness Audit

DevTask has undergone rigorous security auditing and hardening:

| Security Vector | Implementation & Safeguards |
|---|---|
| **Secret Management** | Strict separation: `DJANGO_SECRET_KEY` is loaded exclusively from environment variables in production. Docker image builds use `BUILDING_IMAGE=1` so static asset collection never bakes credentials into container layers. |
| **Debug Mode** | `DEBUG = False` enforced unconditionally in `config.settings.production`. |
| **Object Permissions & IDOR** | All queries enforce `Project.objects.for_user(request.user)` and `is_project_member()`. Non-members cannot view, modify, or infer project existence. |
| **Mass-Assignment Defense** | Privileged fields (`owner`, `created_by`, `project_id`, `completed_at`, `role`) are marked `read_only` or managed via dedicated, validated action endpoints. |
| **Data Integrity** | Unique constraints prevent duplicate memberships (`project, user`). Foreign keys use `PROTECT` on project owners and `CASCADE` on project teardowns. Assignee membership is validated at both model and serializer layers. |
| **HTTPS & Secure Cookies** | `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `X_FRAME_OPTIONS = "DENY"`, `SECURE_CONTENT_TYPE_NOSNIFF`. |
| **CSRF & Origin Verification** | `CSRF_TRUSTED_ORIGINS` automatically populates from `DJANGO_ALLOWED_HOSTS` and supports explicit `DJANGO_CSRF_TRUSTED_ORIGINS` overrides for HTTPS ingress proxies. |
| **Information Disclosure** | Custom dark-theme error templates (`404.html`, `403.html`, `500.html`). DRF custom exception handler intercepts internal exceptions and returns sanitized JSON 500 error messages in production. Health check `/health/` masks database error details when `DEBUG=False`. |
| **API Throttling** | Built-in DRF throttles: `60/minute` for anonymous requests, `600/minute` for authenticated users. |

---

## Local Development Setup

### 1. Prerequisites
- Python 3.12 or later
- Git
- Redis (optional, required only for multi-worker WebSocket channel layer)

### 2. Clone and Setup Environment
```bash
git clone https://github.com/uddyalokb700-cmk/DevTask.git
cd DevTask

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the template configuration file:
```bash
cp .env.example .env
```
For local development, the default values in `.env` default to SQLite (`db.sqlite3`) and in-memory channel layers with `DEBUG=True`.

### 4. Database Migrations & Initial Setup
```bash
# Verify no pending unmigrated changes
python manage.py makemigrations --check --dry-run

# Apply database migrations
python manage.py migrate

# Create an administrative superuser
python manage.py createsuperuser
```

### 5. Launch Development Server
```bash
# Run with Daphne ASGI server (recommended for WebSockets)
daphne -b 127.0.0.1 -p 8000 config.asgi:application

# Or using Django's standard development server
python manage.py runserver 127.0.0.1:8000
```

### 6. Access DevTask
- **Web Application**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Interactive Swagger UI**: [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
- **ReDoc Documentation**: [http://127.0.0.1:8000/api/redoc/](http://127.0.0.1:8000/api/redoc/)
- **Health Check Endpoint**: [http://127.0.0.1:8000/health/](http://127.0.0.1:8000/health/)
- **Django Admin**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## Docker & Docker Compose Deployment

DevTask provides a multi-container Docker Compose configuration featuring Daphne ASGI, PostgreSQL 16, and Redis 7 with integrated health checks.

### 1. Configure Production Environment
Create your production `.env` file:
```bash
cp .env.example .env
```
Ensure strong secrets are defined:
```ini
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=generate-a-strong-random-secret-key-with-32-plus-chars
DJANGO_ALLOWED_HOSTS=yourdomain.com,app.yourdomain.com,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
POSTGRES_DB=devtask_db
POSTGRES_USER=devtask_user
POSTGRES_PASSWORD=your-secure-postgres-password
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
```

### 2. Build and Start Containers
```bash
docker compose up --build -d
```

### 3. Verify Container Health
```bash
docker compose ps
```
Both `devtask_db` and `devtask_redis` perform active health checks (`pg_isready` and `redis-cli ping`). The `web` container waits for dependencies, automatically applies migrations via `docker-entrypoint.sh`, and starts Daphne.

### 4. Create Production Superuser in Docker
```bash
docker compose exec web python manage.py createsuperuser
```

---

## Automated Tests & Quality Checks

The DevTask repository includes 50 automated tests covering authentication, project membership, IDOR security, task mutations, N+1 query budgets, and end-to-end deployment workflows.

### Run Test Suite
```bash
# Run complete pytest test suite
.venv/bin/pytest

# Run tests with verbose output
.venv/bin/pytest -v

# Run deployment and end-to-end integration tests specifically
.venv/bin/pytest tests/test_deployment.py -v
```

### Run Linter & Code Style Checks
```bash
.venv/bin/ruff check .
```

### Run Django Production Deployment Checks
Verify zero security warnings under production settings:
```bash
DJANGO_SECRET_KEY="temporary-secret-key-at-least-50-characters-long" \
DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1" \
.venv/bin/python manage.py check --deploy --settings=config.settings.production
```

### Run Database Migration Integrity Check
```bash
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py showmigrations
```

---

## Performance Benchmarking & Load Testing

DevTask is engineered to eliminate N+1 queries using targeted `select_related()`, `prefetch_related()`, and database-side aggregation.

### 1. Synthetic Data Seeding
Populate the database with synthetic projects and tasks for realistic load testing:
```bash
python manage.py seed_performance_data --projects 20 --tasks 500
```

### 2. Locust Load Testing
Locust test scenarios are located in `tests/locustfile.py` and test authenticated workflows including login, project listing, task filtering, board retrieval, and task status reordering.

```bash
# Headless benchmark (50 concurrent users, 10 spawn rate, 1 minute duration)
locust -f tests/locustfile.py \
       --headless \
       -u 50 \
       -r 10 \
       --run-time 1m \
       --host http://127.0.0.1:8000

# Or start the Locust Web UI at http://127.0.0.1:8089
locust -f tests/locustfile.py --host http://127.0.0.1:8000
```

---

## Production Deployment Guide

### Deployment Architecture
In a standard production environment, DevTask should be deployed behind a reverse proxy (Nginx, AWS ALB, Caddy, or Cloudflare):

```
Client (Browser)
       │  (HTTPS / WSS)
       ▼
Reverse Proxy (Nginx / Cloudflare)
       │  (HTTP / WS reverse proxy)
       ▼
Daphne ASGI Server (Port 8000)
    ├── Django REST Framework & Templates (WhiteNoise Static)
    ├── PostgreSQL 16 (Relational data & transactions)
    └── Redis 7 (Channel Layer & WebSocket PubSub)
```

### Sample Nginx Configuration
```nginx
upstream devtask_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 20M;

    # HTTP API and HTML views
    location / {
        proxy_pass http://devtask_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket Real-Time Channel proxying
    location /ws/ {
        proxy_pass http://devtask_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

### Static Files in Production
DevTask uses WhiteNoise. Static assets are collected during Docker image build or before starting Daphne:
```bash
python manage.py collectstatic --noinput
```
WhiteNoise serves files directly from memory and disk with persistent HTTP cache headers and content hashing.

---

## Health Check & Monitoring

DevTask provides a dedicated health check endpoint at `/health/`:
- **Success (HTTP 200)**:
  ```json
  {
    "status": "ok",
    "database": "healthy"
  }
  ```
- **Failure (HTTP 503)**:
  ```json
  {
    "status": "error",
    "database": "unhealthy"
  }
  ```
When `DEBUG=False`, internal database connection exception details are suppressed to prevent credential leakage.

Configure your container orchestrator (Kubernetes, AWS ECS, Docker Compose) or load balancer health check target to `/health/`.

---

## Troubleshooting & Unresolved Risks

1. **Direct Cloud Deployment Access**:
   - Automated code checks, container configurations, and migration scripts are verified. However, since direct cloud infrastructure credentials (e.g., AWS, GCP, Railway, Render) are not connected to this workspace, final production provisioning requires executing the container launch or deployment pipeline on your target hosting provider using the instructions above.
2. **PostgreSQL SSL Mode**:
   - In managed database environments (AWS RDS, Neon, Supabase), append `?sslmode=require` to your `DATABASE_URL` to ensure TLS encryption for all database network traffic.
3. **Redis Clustering / Sentinel**:
   - The default `channels_redis` configuration points to a single Redis instance. For multi-node high-availability clustering, configure Redis Sentinel or clustered endpoints via `REDIS_URL`.