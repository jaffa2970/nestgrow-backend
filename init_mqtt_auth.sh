#!/bin/bash
# NestGrow — Inizializza autenticazione MQTT
# Eseguire UNA VOLTA prima del primo avvio: ./init_mqtt_auth.sh

set -e

ENV_FILE="${1:-.env}"

if [ -f "$ENV_FILE" ]; then
  export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | xargs)
fi

MQTT_USER="${MQTT_USER:-nestgrow}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"

if [ -z "$MQTT_PASSWORD" ]; then
  echo "❌ MQTT_PASSWORD non impostata nel .env"
  echo "   Aggiungi: MQTT_PASSWORD=<password_sicura>"
  exit 1
fi

PASSWD_FILE="./mosquitto/config/passwd"

docker run --rm \
  -v "$(pwd)/mosquitto/config:/mosquitto/config" \
  eclipse-mosquitto:2 \
  mosquitto_passwd -b -c /mosquitto/config/passwd "$MQTT_USER" "$MQTT_PASSWORD"

echo "✅ File passwd MQTT creato: $PASSWD_FILE"
echo "   Utente: $MQTT_USER"
echo ""
echo "Ora avvia il sistema con: docker compose up -d"
