import multiprocessing
import os

# ============================================
# VisionGuard Backend — Gunicorn Config File
# ============================================

# Network Binding
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Worker Configuration
workers_per_core = 2
cores = multiprocessing.cpu_count()
default_workers = (cores * workers_per_core) + 1
workers = int(os.getenv("WEB_CONCURRENCY", default_workers))

# Ensure worker class is set to high-concurrency Uvicorn
worker_class = "uvicorn.workers.UvicornWorker"

# Timeouts & Keep-Alives
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
graceful_timeout = 30

# Logging Setup
loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = "-"  # Access logs to stdout
errorlog = "-"   # Error logs to stderr

# Connection Pooling / Backlog
backlog = 2048
