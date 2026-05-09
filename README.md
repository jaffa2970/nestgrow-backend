# NestGrow 🌱
**by lake8.dev**

Sistema di gestione intelligente per culle di accrescimento vegetale. Controllo IoT via ESP32, irrigazione automatica con logica a soglie, dashboard real-time con grafici storici. Multi-tenant con licensing per piano.

---

## Features

- Gestione culle con limite dipendente dal piano licenza
- Controllo pompe indipendenti per zona via MQTT
- Sensori umidità suolo capacitivi per zona
- Sensore livello serbatoio centralizzato
- Logica irrigazione automatica a soglie
- **Grafici storici** per zona: umidità, serbatoio, irrigazioni, efficacia (ECharts)
- Configurazione zona con sincronizzazione MQTT verso ESP32 (soglie, intervallo lettura)
- Dashboard Vue 3 con aggiornamento real-time
- **Sistema backup/restore** database con download diretto via browser
- **Recupero automatico licenza** al boot: se il JWT non è in cache, tenta il recovery dal License Server
- Gestione utenti multi-ruolo (administrator / user)
- Messaggi e notifiche dal License Server
- Supporto ticket integrato con License Server
- Integrazione License Server lake8.dev

---

## Piani disponibili

| Piano | Culle | Note |
|-------|-------|------|
| Free | 1 | Hobbisti e test |
| Pro | 5 | Piccoli produttori |
| AI | 10 | Vivai e aziende agricole |

---

## Stack tecnico

| Componente | Tecnologia |
|------------|------------|
| Backend | Python 3.13 + FastAPI + SQLAlchemy async + Alembic |
| Database | MariaDB 11 (aiomysql) |
| Broker MQTT | Eclipse Mosquitto 2 |
| Scheduler | APScheduler AsyncIOScheduler |
| Frontend | Vue 3 + Vite + ECharts (vue-echarts) |
| Deploy | Docker Compose |
| License | lake8.dev License Server |

---

## Quick start

```bash
git clone https://github.com/jaffa2970/nestgrow-backend
cd nestgrow-backend
cp .env.example .env        # modifica le variabili

# Crea la cartella backups con i permessi corretti PRIMA di avviare
mkdir -p backups && chmod 777 backups

docker compose up --build
```

Accedi a:

- **Dashboard:** http://localhost:3000
- **API docs:** http://localhost:8000/docs
- **Credenziali default:** `admin` / `admin` _(cambia `ADMIN_PASSWORD` in `.env`)_

---

## Backup & Restore

NestGrow include un sistema completo di backup del database.

### Via Dashboard (tab ⚙️ Sistema — solo admin)

- **Salva su volume** — esegue un dump e lo salva in `/app/backups/` (volume persistente)
- **Scarica backup** — scarica direttamente nel browser un file `.sql.gz` senza salvare sul server
- **Restore da volume** — ripristina uno dei backup salvati sul server
- **Restore da file** — carica un file `.sql.gz` locale e ripristina il database

### Via script host (cartella `backup/`)

```bash
./backup/backup.sh              # crea backup in ./backups/
./backup/list.sh                # lista backup disponibili
./backup/restore.sh <file.sql.gz>  # ripristino interattivo (chiede conferma)
```

### Backup automatico

Il backend esegue automaticamente un backup ogni giorno alle 02:00 (APScheduler cron job).
Vengono mantenuti gli ultimi 30 file.

### Prima esecuzione — fix permessi

Se Docker crea la cartella `./backups` come `root`, il container backend non può scrivere.
Soluzione: crea la cartella manualmente prima di `docker compose up`:

```bash
mkdir -p backups && chmod 777 backups
```

Oppure, dopo il primo avvio:

```bash
docker exec nestgrow-backend chmod 777 /app/backups
```

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
| `nestgrow/device/{id}/cmd/config` | Backend → ESP32 | `{"zona": 1, "intervallo_ms": 30000, "salva_nvs": true}` | Intervallo lettura sensori zona |
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

## Scheduler jobs

| Job | Intervallo | Funzione |
|-----|-----------|---------|
| `irrigation_tick` | 60 sec | Logica irrigazione automatica a soglie |
| `jwt_poll` | 5 min | Ritiro JWT pendenti dal License Server (funziona anche con DB vuoto) |
| `messages_sync` | 30 min | Sincronizzazione messaggi/notifiche |
| `license_heartbeat` | 60 min | Heartbeat verso License Server |
| `auto_backup` | ogni giorno 02:00 | Backup automatico database (mantiene ultimi 30) |

All'avvio il backend esegue `check_license_on_boot()`: se nessun JWT è in cache prova automaticamente a recuperarlo dal License Server prima di avviare i job scheduler.

---

## Licenza

Copyright © 2026 lake8.dev — Tutti i diritti riservati.
Il codice sorgente di questo repository non è open source.
Per licenze commerciali: **https://nestgrow.lake8.dev**
