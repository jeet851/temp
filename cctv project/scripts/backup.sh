#!/bin/bash
# =====================================================================
# VisionGuard — Enterprise Production Backup & Recovery Automation Script
# =====================================================================

# Exit immediately if a command exits with a non-zero status
set -e

# Configuration
BACKUP_DIR="/var/backups/visionguard"
DATE_STR=$(date +%Y-%m-%d_%H%M%S)
POSTGRES_USER="vg_admin"
DATABASE_NAME="visionguard"
CONTAINER_NAME="visionguard_db"
MEDIA_DIR="./backend/media"
RETENTION_DAYS=30

echo "Starting automated database and file storage backup..."

# Ensure backup directories exist
mkdir -p "$BACKUP_DIR"

# ── 1. PostgreSQL Database Dump ──
echo "Dumping PostgreSQL database..."
docker exec "$CONTAINER_NAME" pg_dump -U "$POSTGRES_USER" "$DATABASE_NAME" > "$BACKUP_DIR/db_backup_$DATE_STR.sql"

# ── 2. Compress Media Assets (OCR Snapshots & Logs) ──
echo "Archiving environmental OCR camera snapshots..."
if [ -d "$MEDIA_DIR" ]; then
    tar -czf "$BACKUP_DIR/media_backup_$DATE_STR.tar.gz" "$MEDIA_DIR"
else
    echo "Warning: Media directory $MEDIA_DIR not found, skipping files archive."
fi

# ── 3. Compress Configuration Files ──
echo "Archiving environment config settings..."
tar -czf "$BACKUP_DIR/config_backup_$DATE_STR.tar.gz" ./backend/.env ./nginx/nginx.conf

# ── 4. File Compression & Housekeeping ──
echo "Compressing full backup archive..."
cd "$BACKUP_DIR"
tar -czf "visionguard_backup_$DATE_STR.tar.gz" "db_backup_$DATE_STR.sql" "media_backup_$DATE_STR.tar.gz" "config_backup_$DATE_STR.tar.gz"

# Remove intermediate files
rm "db_backup_$DATE_STR.sql" "media_backup_$DATE_STR.tar.gz" "config_backup_$DATE_STR.tar.gz"

# ── 5. Retention Policy (Delete backups older than retention period) ──
echo "Enforcing backup retention policy (deleting files older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -type f -name "visionguard_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "✓ Backup complete: $BACKUP_DIR/visionguard_backup_$DATE_STR.tar.gz"

# ── RECOVERY INSTRUCTIONS ─────────────────────────────────────────────
# To restore a backup:
#   1. Extract the tar.gz:
#      tar -xzf visionguard_backup_YYYY-MM-DD_HHMMSS.tar.gz
#   2. Restore the database:
#      docker exec -i visionguard_db psql -U vg_admin -d visionguard < db_backup_YYYY-MM-DD_HHMMSS.sql
#   3. Restore media assets:
#      tar -xzf media_backup_YYYY-MM-DD_HHMMSS.tar.gz -C /
# ──────────────────────────────────────────────────────────────────────
