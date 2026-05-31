#!/bin/bash
# NestGrow — Lista backup disponibili

echo "=== NestGrow — Backup disponibili ==="
echo ""

if ! ls ./backups/nestgrow_backup_*.sql.gz > /dev/null 2>&1; then
  echo "  Nessun backup trovato in ./backups/"
  echo ""
  echo "Totale: 0 backup"
  exit 0
fi

ls -lh ./backups/nestgrow_backup_*.sql.gz | \
  awk '{print $5, $9}' | \
  while read size path; do
    name=$(basename "$path" .sql.gz)
    date_part="${name#nestgrow_backup_}"
    echo "  📦 $date_part — $size"
  done

COUNT=$(ls ./backups/nestgrow_backup_*.sql.gz 2>/dev/null | wc -l)
echo ""
echo "Totale: $COUNT backup"
