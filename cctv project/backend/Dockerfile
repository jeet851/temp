# ============================================
# VisionGuard Backend — Production Dockerfile
# ============================================
FROM python:3.12-slim

# Set system env variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app

WORKDIR ${APP_HOME}

# Install system dependencies (including OpenCV dependencies for headless Linux)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port and start ASGI server via Gunicorn
EXPOSE 8000
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app.main:app"]
