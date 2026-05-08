#!/bin/bash
# NestGrow — Backup database
# Uso: ./backup/backup.sh [cartella_destinazione]

BACKUP_DIR=${1:-./backups}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="nestgrow_backup_${TIMESTAMP}.sql.gz"
CONTAINER="nestgrow-db"
DB="nestgrow_db"
USER="nestgrow"
PASS="nestgrow"

mkdir -p "$BACKUP_DIR"

echo "=== NestGrow Backup ==="
echo "Data: $(date)"
echo "File: ${BACKUP_DIR}/${FILENAME}"

docker exec "$CONTAINER" mariadb-dump \
  -u"$USER" -p"$PASS" \
  --single-transaction \
  --routines \
  --triggers \
  "$DB" | gzip > "${BACKUP_DIR}/${FILENAME}"

if [ $? -eq 0 ]; then
  SIZE=$(du -sh "${BACKUP_DIR}/${FILENAME}" | cut -f1)
  echo "✅ Backup completato — ${SIZE}"

  # Mantieni solo gli ultimi 30 backup
  ls -t "${BACKUP_DIR}"/nestgrow_backup_*.sql.gz 2>/dev/null | \
    tail -n +31 | xargs rm -f 2>/dev/null

  echo "Backup disponibili: $(ls "${BACKUP_DIR}"/nestgrow_backup_*.sql.gz 2>/dev/null | wc -l)"
else
  echo "❌ Backup fallito"
  exit 1
fi
