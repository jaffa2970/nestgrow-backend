# Deployment Guide

## Requisiti

- **Docker** >= 24.0
- **Docker Compose** >= 2.0
- Porte disponibili: `1883` (MQTT), `8000` (API), `3000` (Frontend)
- Connessione a internet per l'attivazione licenza (https://license.lake8.dev)

---

## Installazione standard

### 1. Clone repository

```bash
git clone https://github.com/lake8dev/nestgrow-backend
cd nestgrow-backend
```

### 2. Configura le variabili d'ambiente

```bash
cp .env.example .env
```

Modifica `.env` con i tuoi valori. Genera un `JWT_SECRET` sicuro:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Avvia lo stack

```bash
docker-compose up --build -d
```

### 4. Verifica i container

```bash
docker-compose ps
```

Tutti e 4 i servizi devono essere `Up`:
- `nestgrow-mqtt`
- `nestgrow-db` (con health check `healthy`)
- `nestgrow-backend`
- `nestgrow-frontend`

### 5. Accedi all'applicazione

- **Dashboard:** http://localhost:3000
- **API docs (Swagger):** http://localhost:8000/docs
- **Credenziali default:** `admin` / `admin`

> **Cambia subito la password admin** modificando `ADMIN_PASSWORD` in `.env` e riavviando il backend:
> ```bash
> docker-compose restart backend
> ```

---

## Configurazione produzione

### Reverse proxy con nginx

Esempio di configurazione nginx per esporre NestGrow su dominio con SSL (Let's Encrypt):

```nginx
server {
    listen 80;
    server_name nestgrow.tuodominio.it;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name nestgrow.tuodominio.it;

    ssl_certificate     /etc/letsencrypt/live/nestgrow.tuodominio.it/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nestgrow.tuodominio.it/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API diretta (opzionale — il frontend già fa proxy interno)
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### ESP32 in produzione

Quando il broker MQTT non è `localhost`, imposta `MQTT_HOST` nell'`.env` con l'IP o hostname raggiungibile dagli ESP32 sulla rete locale. Il valore `mosquitto` funziona solo dentro la rete Docker.

```env
MQTT_HOST=192.168.1.100   # IP della macchina host, raggiungibile dagli ESP32
```

### Sicurezza Mosquitto

Per ambienti esposti, abilita l'autenticazione MQTT modificando `mosquitto/config/mosquitto.conf`:

```
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd
```

Genera il file password con:
```bash
docker exec nestgrow-mqtt mosquitto_passwd -c /mosquitto/config/passwd nestgrow
```

---

## Backup database

```bash
# Dump completo
docker exec nestgrow-db \
  mysqldump -unestgrow -pnestgrow nestgrow_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
docker exec -i nestgrow-db \
  mysql -unestgrow -pnestgrow nestgrow_db < backup_20260507_120000.sql
```

Aggiungi a crontab per backup notturno automatico:
```
0 2 * * * /usr/bin/docker exec nestgrow-db mysqldump -unestgrow -pnestgrow nestgrow_db > /backup/nestgrow_$(date +\%Y\%m\%d).sql
```

---

## Aggiornamento

```bash
# 1. Aggiorna il codice
git pull origin main

# 2. Ricostruisci e riavvia
docker-compose up --build -d

# 3. Le migration Alembic vengono eseguite automaticamente all'avvio del backend
# 4. Verifica
docker-compose ps
docker-compose logs --tail=50 backend
```

---

## Troubleshooting

### Container `backend` non si avvia

```bash
docker-compose logs backend
```

**Causa più comune:** MariaDB non ancora pronta. Il backend attende il health check di MariaDB prima di avviarsi. Se il timeout viene superato, riavvia:
```bash
docker-compose restart backend
```

### ESP32 non si connette al broker MQTT

1. Verifica che la porta 1883 sia raggiungibile dall'ESP32:
   ```bash
   # Da un altro dispositivo sulla stessa rete
   nc -zv <IP_HOST> 1883
   ```
2. Controlla che `MQTT_HOST` in `.env` sia l'IP della macchina host (non `mosquitto`)
3. Verifica i log di Mosquitto:
   ```bash
   docker-compose logs mosquitto
   ```

### Letture MQTT non appaiono nelle API

Verifica che il backend stia ricevendo i messaggi:
```bash
docker-compose logs backend | grep "zona\|mqtt\|MQTT"
```

Pubblica un messaggio di test:
```bash
docker exec nestgrow-mqtt \
  mosquitto_pub -h localhost -t "nestgrow/zona/1/umidita" \
  -m '{"v": 55.0, "ts": 1234567890, "device_id": "test"}'
```

### Licenza non valida o errore heartbeat

```bash
docker-compose logs backend | grep -i "license\|licenza"
```

Verifica connettività verso il License Server:
```bash
docker exec nestgrow-backend curl -s https://license.lake8.dev/api/v1/heartbeat?product=nestgrow
```

### Errore "max culle raggiunto" quando ci sono ancora slot disponibili

La cache licenza potrebbe essere corrotta. Resetta:
```bash
docker exec nestgrow-db \
  mysql -unestgrow -pnestgrow nestgrow_db \
  -e "UPDATE licenza_cache SET piano='free' WHERE id=1;"
docker-compose restart backend
```
