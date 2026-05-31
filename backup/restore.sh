#!/bin/bash
# NestGrow — Restore database
# Uso: ./backup/restore.sh <file_backup.sql.gz>

BACKUP_FILE=$1
CONTAINER="nestgrow-db"
DB="nestgrow_db"
USER="nestgrow"
PASS="${DB_PASSWORD:-$(cat /run/secrets/db_password 2>/dev/null)}"
if [ -z "$PASS" ]; then
  echo "❌ DB_PASSWORD non impostata"
  exit 1
fi

if [ -z "$BACKUP_FILE" ]; then
  echo "Uso: ./backup/restore.sh <file_backup.sql.gz>"
  echo ""
  echo "Backup disponibili:"
  ls -lh ./backups/nestgrow_backup_*.sql.gz 2>/dev/null || \
    echo "Nessun backup trovato in ./backups/"
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "❌ File non trovato: $BACKUP_FILE"
  exit 1
fi

echo "=== NestGrow Restore ==="
echo "File: $BACKUP_FILE"
echo ""
echo "⚠️  ATTENZIONE: questa operazione sovrascrive"
echo "   tutti i dati attuali del database."
echo ""
read -p "Confermi il restore? (scrivi 'SI' per confermare): " CONFIRM

if [ "$CONFIRM" != "SI" ]; then
  echo "Restore annullato."
  exit 0
fi

echo "Restore in corso..."

gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER" \
  mariadb -u"$USER" -p"$PASS" "$DB"

if [ $? -eq 0 ]; then
  echo "✅ Restore completato"
  echo "Riavvia il backend per applicare le modifiche:"
  echo "  docker compose restart backend"
else
  echo "❌ Restore fallito"
  exit 1
fi
