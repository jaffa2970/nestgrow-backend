# NestGrow 🌱
**by lake8.dev**

Sistema IoT per la gestione automatizzata di celle di coltivazione orticola.
ESP32 firmware + Docker backend + dashboard Vue 3.

---

## Caratteristiche principali / Key Features

### 🇮🇹 Italiano

**Gestione culle**
- Fino a 4 zone indipendenti per culla con sensori umidità capacitivi
- Irrigazione automatica a soglie configurabili (min/max per zona)
- Irrigazione manuale dalla dashboard
- Cooldown 10 minuti tra irrigazioni consecutive
- Safety: timeout valvola 5 min, blocco automatico con serbatoio vuoto

**Monitoraggio**
- Grafici ECharts in tempo reale: umidità per zona, livello serbatoio, irrigazioni, efficacia
- Aggiornamento automatico ogni 60 secondi con indicatore timestamp
- Export Excel: letture, irrigazioni, riepilogo per zona (3 sheet)
- Backup automatico notturno alle 02:00 con download diretto da browser
- Retention dati configurabile (default 30 giorni)

**Simulatore ESP32**
- Simulatore integrato per testare il sistema senza hardware fisico
- Scenari rapidi: terreno secco / normale / dopo irrigazione
- Sliders per umidità iniziale per zona, velocità evaporazione, livello serbatoio
- Perfetto per provare NestGrow prima di flashare una ESP32

**Piani e licenze**
- FREE: 1 culla (simulatore incluso, gratuito per sempre)
- PRO: 5 culle
- ENTERPRISE: 10 culle
- ULTRA: illimitato
- Le culle oltre il limite del piano restano **visibili in read-only**: grafici e dati accessibili, controlli disabilitati
- Badge "Piano insufficiente" sulle culle bloccate con link diretto all'upgrade

**Multilingua**
- Interfaccia disponibile in Italiano, English, Deutsch
- Toggle lingua nella navbar

**Gestione utenti**
- Ruolo Administrator (lettura/scrittura completa)
- Ruolo User (solo lettura)

**Supporto tecnico**
- Ticket bidirezionali integrati nella dashboard
- Messaggi e comunicazioni dal team lake8.dev

---

### 🇬🇧 English

**Cell management**
- Up to 4 independent zones per cell with capacitive moisture sensors
- Automatic irrigation with configurable thresholds (min/max per zone)
- Manual irrigation from the dashboard
- 10-minute cooldown between consecutive irrigations
- Safety: 5-min valve timeout, automatic lock when tank is empty

**Monitoring**
- Real-time ECharts graphs: moisture per zone, tank level, irrigations, effectiveness
- Auto-refresh every 60 seconds with timestamp indicator
- Excel export: readings, irrigations, per-zone summary (3 sheets)
- Automatic nightly backup at 02:00 with direct browser download
- Configurable data retention (default 30 days)

**ESP32 Simulator**
- Built-in simulator to test the system without physical hardware
- Quick scenarios: dry soil / normal / after irrigation
- Sliders for per-zone initial moisture, evaporation speed, tank level
- Perfect for trying NestGrow before flashing an ESP32

**Plans & licensing**
- FREE: 1 cell (simulator included, free forever)
- PRO: 5 cells
- ENTERPRISE: 10 cells
- ULTRA: unlimited
- Cells beyond plan limit remain **visible in read-only**: data and graphs accessible, controls disabled
- "Insufficient plan" badge on blocked cells with direct upgrade link

**Multilingual**
- Interface available in Italian, English, Deutsch
- Language toggle in navbar

**User management**
- Administrator role (full read/write)
- User role (read-only)

**Technical support**
- Bidirectional tickets integrated in the dashboard
- Messages and communications from the lake8.dev team

---

## Piani disponibili / Available Plans

| Piano / Plan | Culle / Cells | Note |
|---|---|---|
| **Free** | 1 | Hobbisti e test / Hobbyists and testing |
| **Pro** | 5 | Piccoli produttori / Small producers |
| **Enterprise** | 10 | Vivai e aziende agricole / Nurseries and farms |
| **Ultra** | ∞ | Illimitato / Unlimited |

Le culle oltre il limite del piano attivo rimangono visibili con grafici e letture storiche accessibili, ma tutti i controlli (irrigazione manuale, modifica configurazione, simulatore) vengono disabilitati finché non si effettua l'upgrade.

---

## Stack tecnico / Tech Stack

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
cp .env.example .env        # modifica le variabili (vedi sotto)

# Crea la cartella backups con i permessi corretti PRIMA di avviare
mkdir -p backups && chmod 777 backups

# Genera il file di autenticazione MQTT (obbligatorio)
./init_mqtt_auth.sh

docker compose up --build
```

Accedi a:

- **Dashboard:** http://localhost:3001
- **API docs:** http://localhost:8000/docs

---

## 🔑 Primo accesso

Dopo `docker compose up -d` apri il browser su:

**http://localhost:3001**

### Credenziali dashboard

| Campo | Valore |
|---|---|
| **Username** | `admin` |
| **Password** | il valore di `ADMIN_PASSWORD` nel tuo `.env` |

> ⚠️ **Importante**: la password admin è quella che hai impostato nel file `.env` prima di avviare il sistema.
> Se non ricordi quale hai impostato:
> ```bash
> cat .env | grep ADMIN_PASSWORD
> ```

### Al primo avvio

La dashboard mostra la schermata di **registrazione licenza**.
Inserisci i tuoi dati e scegli il piano:

| Piano | Culle | Costo |
|-------|-------|-------|
| **Free** | 1 | Gratuito per sempre |
| **Pro** | 5 | Gratuito durante la beta |

Dopo la registrazione riceverai conferma via email e potrai accedere alla dashboard completa.

---

## Backup & Restore

NestGrow include un sistema completo di backup del database.

### Via Dashboard (tab ⚙️ Sistema — solo admin)

- **Salva su volume** — esegue un dump e lo salva in `/app/backups/` (volume persistente)
- **Scarica backup** — scarica direttamente nel browser un file `.sql.gz` senza salvare sul server
- **Restore da volume** — ripristina uno dei backup salvati sul server
- **Restore da file** — carica un file `.sql.gz` locale e ripristina il database

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
**https://github.com/jaffa2970/nestgrow-esp32**

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

| Variabile | Obbligatoria | Descrizione |
|-----------|-------------|-------------|
| `DB_URL` | ✅ | Connection string MariaDB |
| `DB_PASSWORD` | ✅ | Password utente DB (usata anche nel compose) |
| `DB_ROOT_PASSWORD` | ✅ | Password root MariaDB |
| `JWT_SECRET` | ✅ | Segreto JWT — genera con `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_PASSWORD` | ✅ | Password admin dashboard |
| `MQTT_USER` | — | Utente MQTT (default: `nestgrow`) |
| `MQTT_PASSWORD` | ✅ | Password broker MQTT |
| `MQTT_HOST` | — | Hostname broker MQTT (default: `mosquitto`) |
| `MQTT_PORT` | — | Porta broker MQTT (default: `1883`) |
| `LICENSE_SERVER_URL` | — | URL License Server (default: `https://license.lake8.dev`) |

---

## Scheduler jobs

| Job | Intervallo | Funzione |
|-----|-----------|---------|
| `irrigation_tick` | 60 sec | Logica irrigazione automatica a soglie (salta culle bloccate dal piano) |
| `jwt_poll` | 5 min | Ritiro JWT pendenti dal License Server |
| `license_status_check` | 30 min | Verifica stato licenza sul License Server |
| `messages_sync` | 30 min | Sincronizzazione messaggi/notifiche |
| `license_heartbeat` | 60 min | Heartbeat verso License Server |
| `auto_backup` | ogni giorno 02:00 | Backup automatico database (mantiene ultimi 30) |
| `cleanup_readings` | ogni giorno 03:00 | Elimina letture più vecchie di `retention_giorni` (default 30) |

All'avvio il backend esegue `check_license_on_boot()`: se nessun JWT è in cache prova automaticamente a recuperarlo dal License Server prima di avviare i job scheduler.

---

## Export dati

NestGrow supporta l'export dei dati storici in formato Excel (`.xlsx`).

| Endpoint | Sheet | Contenuto |
|---|---|---|
| `GET /export/letture?giorni=N` | Letture umidità | Data/Ora, Culla, Zona, Coltura, Umidità %, Serbatoio % |
| `GET /export/irrigazioni?giorni=N` | Irrigazioni | Inizio/fine, Culla, Zona, Durata, pre/post %, Trigger, Esito |
| `GET /export/completo?giorni=N` | Tutti e 3 | Letture + Irrigazioni + Riepilogo aggregato per zona |

`giorni=0` esporta tutto il database senza filtro temporale.

Dalla dashboard (tab ⚙️ Sistema) è disponibile un selettore periodo (7gg / 30gg / 90gg / Tutto) con pulsanti di download diretto.

---

## Licenza

Copyright © 2026 lake8.dev — Tutti i diritti riservati.
Il codice sorgente di questo repository non è open source.
Per licenze commerciali: **https://nestgrow.lake8.dev**
