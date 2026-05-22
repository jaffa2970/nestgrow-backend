#!/bin/bash
set -e
echo "=== Compilazione Cython ==="

python setup.py build_ext --inplace

for f in app/licensing app/mqtt_client app/main app/models app/database; do
    if ls ${f}.cpython-*.so 1>/dev/null 2>&1; then
        echo "OK: ${f}.so"
    else
        echo "ERRORE: ${f}.so non trovato"
        exit 1
    fi
done

rm -f app/licensing.py
rm -f app/mqtt_client.py
rm -f app/main.py
rm -f app/models.py
rm -f app/database.py

find app/ -name "*.c" -delete
find build/ -type f -delete 2>/dev/null || true

echo "=== Build Cython completata ==="
ls -la app/*.so 2>/dev/null || echo "Nessun .so in app/"
