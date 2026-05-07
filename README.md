# NestGrow 🌱
**by lake8.dev**

Sistema di gestione intelligente per culle di accrescimento vegetale. Controllo IoT via ESP32, irrigazione automatica con logica a soglie, dashboard real-time. Multi-tenant con licensing per piano.

---

## Features

- Gestione fino a N culle (dipende dal piano licenza)
- Controllo pompe indipendenti per zona via MQTT
- Sensori umidità suolo capacitivi per zona
- Sensore livello serbatoio centralizzato
- Logica irrigazione automatica a soglie (livello 1)
- ML predittivo sui cicli storici (livello 2 — roadmap)
- Dashboard Vue 3 con aggiornamento real-time
- Integrazione License Server lake8.dev

---

## Piani disponibili

| Piano | Culle | Target |
|-------|-------|--------|
| Free | 1 | Hobbisti e test |
| Pro | 5 | Piccoli produttori |
| Enterprise | 20 | Vivai e aziende agricole |
| Ultra | Illimitato | Grandi impianti |

---

## Stack tecnico

| Componente | Tecnologia |
|------------|------------|
| Backend | Python 3.13 + FastAPI + SQLAlchemy async + Alembic |
| Database | MariaDB 11 |
| Broker MQTT | Eclipse Mosquitto 2 |
| Frontend | Vue 3 + Vite |
| Deploy | Docker Compose |
| License | lake8.dev License Server |

---

## Quick start

```bash
git clone https://github.com/lake8dev/nestgrow-backend
cd nestgrow-backend
cp .env.example .env        # modifica le variabili
docker-compose up --build
```

Accedi a:

- **Dashboard:** http://localhost:3000
- **API docs:** http://localhost:8000/docs
- **Credenziali default:** `admin` / `admin` _(cambia subito in `.env`)_

---

## Firmware ESP32

Il firmware open source per ESP32 è disponibile su:
**https://github.com/lake8dev/nestgrow-esp32**

---

## Topic MQTT

| Topic | Direzione | Payload | Descrizione |
|-------|-----------|---------|-------------|
| `nestgrow/zona/{id}/umidita` | ESP32 → Backend | `{"v": 67.3, "ts": 1234567890}` | Lettura umidità suolo |
| `nestgrow/serbatoio/livello` | ESP32 → Backend | `{"v": 82.0, "ts": 1234567890}` | Livello serbatoio (%) |
| `nestgrow/zona/{id}/pompa` | Backend → ESP32 | `{"cmd": "on", "sec": 30}` | Comando attivazione pompa |
| `nestgrow/device/{id}/heartbeat` | ESP32 → Backend | `{"uptime_sec": 3600, "wifi_rssi": -65, ...}` | Stato dispositivo |
| `nestgrow/device/{id}/cmd/reconfig` | Backend → ESP32 | `{"ssid": "...", "password": "...", "mqtt_host": "..."}` | Riconfigurazione WiFi remota |

---

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `DB_URL` | `mysql+aiomysql://nestgrow:nestgrow@db/nestgrow_db` | Connection string MariaDB |
| `MQTT_HOST` | `mosquitto` | Hostname broker MQTT |
| `MQTT_PORT` | `1883` | Porta broker MQTT |
| `LICENSE_SERVER_URL` | `https://license.lake8.dev` | URL License Server |
| `JWT_SECRET` | `changeme` | Segreto JWT (**CAMBIA in produzione**) |
| `ADMIN_PASSWORD` | `admin` | Password admin dashboard (**CAMBIA in produzione**) |

---

## Licenza

Copyright © 2026 lake8.dev — Tutti i diritti riservati.
Il codice sorgente di questo repository non è open source.
Per licenze commerciali: **https://nestgrow.lake8.dev**
