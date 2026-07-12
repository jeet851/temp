# 🛡️ VisionGuard — Enterprise Production Deployment Guide

## 🏗️ 1. Architecture Overview
VisionGuard is deployed as a fully containerized, microservices-structured system. The services are orchestrated via Docker Compose:

```
                  ┌──────────────────────┐
                  │   Nginx Gateway      │ (Port 80/443, SSL/TLS, Rate Limiting)
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────┐
│     Frontend UI       │         │      FastAPI API      │ (Gunicorn, Uvicorn, port 8000)
│   (Vite static serve) │         └──────────┬────────────┘
└───────────────────────┘                    │
                                    ┌────────┴────────┐
                                    ▼                 ▼
                         ┌─────────────────┐ ┌─────────────────┐
                         │   PostgreSQL    │ │     Redis       │ (AOF/RDB persistence)
                         │ (DB, port 5432) │ └────────┬────────┘
                         └─────────────────┘          │
                                             ┌────────┴────────┐
                                             ▼                 ▼
                                  ┌─────────────────┐ ┌─────────────────┐
                                  │  Celery Worker  │ │   Celery Beat   │ (Scheduler)
                                  └─────────────────┘ └─────────────────┘
```

---

## 🔑 2. Secrets Management & Environment Configuration
In production, all sensitive variables are loaded from environmental variables rather than being hardcoded in source control.

Copy the `.env` template to populate active production values:
```bash
# General config
APP_ENV=production
DEBUG=false
JWT_SECRET_KEY=highly-secure-random-string-256-bit
DATABASE_PASSWORD=strong-database-password-here
GRAFANA_PASSWORD=strong-grafana-password-here

# OCR settings
OCR_ENGINE=easyocr
OCR_GPU=false
OCR_CONFIDENCE_THRESHOLD=0.55
OCR_CAPTURE_INTERVAL=3600 # Grabs one snapshot per hour
```

---

## 🔒 3. Nginx Reverse Proxy & HTTPS Hardening
Nginx is configured as the main entry point to protect and load balance the internal services.

### Key Security Features Enabled:
* **HTTPS Redirect**: Directs all plain HTTP traffic (port 80) to HTTPS (port 443).
* **TLS 1.3 Termination**: Limits SSL protocols to TLS 1.2 and TLSv1.3 with high-security cipher suites.
* **Strict HTTP Headers**: Implements `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `Strict-Transport-Security` (HSTS).
* **Rate Limiting**: Protects API routes with a rate of `10 requests/sec` per IP to mitigate brute force attempts.
* **WebSocket Upgrades**: Specifically routes `/api/v1/ws` connection requests to sustain live CCTV update telemetry.

To rotate/renew certs:
1. Mount your Let's Encrypt certificates to `nginx/ssl/live/`.
2. Reload Nginx without downtime: `docker exec visionguard_nginx_gateway nginx -s reload`.

---

## 📊 4. Logging & Centralized Monitoring
Logs and metrics are scraped automatically inside the Docker network.

### Scraping Services:
1. **Loki**: Receives and aggregates system log dumps from Promtail.
2. **Promtail**: Scrapes logs from `/var/log/visionguard` (mounted directly from the backend log storage).
3. **Prometheus**: Polls endpoints every 15s to gather CPU, memory, database, and API execution latencies.
4. **Grafana**: Auto-provisions with Loki and Prometheus data sources. To customize dashboards, log in to `http://localhost:3000` (default user `admin` / password configured in `.env`).

---

## 💾 5. Enterprise Backup & Recovery Workflow
The platform features an automated shell script at `scripts/backup.sh` for backups and recovery.

### Running a Backup:
Make the script executable and configure a daily cron job:
```bash
chmod +x scripts/backup.sh
./scripts/backup.sh
```
The script will dump the PostgreSQL database, compress all snapshot media assets, package the environment variables, delete backups older than 30 days, and save the resulting `.tar.gz` archive to `/var/backups/visionguard/`.

### Restoring a Backup:
1. Extract the container backup:
   ```bash
   tar -xzf visionguard_backup_YYYY-MM-DD_HHMMSS.tar.gz
   ```
2. Restore the database dump:
   ```bash
   docker exec -i visionguard_db psql -U vg_admin -d visionguard < db_backup_YYYY-MM-DD_HHMMSS.sql
   ```
3. Restore files and environment files:
   ```bash
   tar -xzf media_backup_YYYY-MM-DD_HHMMSS.tar.gz -C /
   ```

---

## 🚀 6. How to Deploy the Stack
Deploying the entire VisionGuard production suite takes a single command:

```bash
# Generate self-signed test SSL certs (if production certs not ready)
python nginx/generate_certs.py

# Launch all 11 services in detached mode
docker-compose up -d --build
```
Verify the health checks are passing:
```bash
docker-compose ps
```
All containers will display `(healthy)` or `running` state.
