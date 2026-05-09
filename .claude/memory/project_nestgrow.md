---
name: NestGrow project overview
description: Stack, structure, license server, plan limits, auth system, scheduler jobs, and key paths for NestGrow
type: project
originSessionId: 5c0ef111-b4c5-4ee2-83cd-505b4c18edbe
---
NestGrow is a plant growth crib (culla) management system with IoT control via ESP32.

**Product:** NestGrow by lake8.dev  
**License product code:** `"NESTGROW"` (uppercase — the License Server is case-sensitive)  
**License Server:** https://license.lake8.dev — local source at /home/tommy/Documenti/license-server/  
**Root path:** /home/tommy/Documenti/NestGrow/nestgrow-backend/  
**Git remote:** https://github.com/jaffa2970/nestgrow-backend  

**Why:** IoT-connected growing system with per-plan crib limits enforced at the API layer.

---

## Stack

- Python 3.13 + FastAPI + SQLAlchemy async (AsyncSession, Mapped[]) + Alembic + MariaDB (aiomysql)
- Vue 3 + Vite + Vue Router + Axios + **ECharts + vue-echarts** (no Pinia — reactive auth via module-level ref singleton `src/auth.js`)
- MQTT via asyncio-mqtt (eclipse-mosquitto:2)
- APScheduler AsyncIOScheduler
- Docker services: mosquitto / db (mariadb:11) / backend (:8000) / frontend (:3000 via nginx)

---

## Plan limits (PIANO_LIMITI_DEFAULT)

| Piano | Max culle | Note |
|-------|-----------|------|
| free  | 1         | |
| pro   | 5         | |
| ai    | 10        | "enterprise" and "ultra" map to "ai" on the LS |

Stored in `piano_limiti` table. `PIANO_LIMITI_DEFAULT` dict in `app/licensing.py` is the in-memory fallback.

---

## APScheduler jobs (app/main.py)

| Job ID | Function | Interval | Note |
|--------|----------|----------|------|
| license_heartbeat | heartbeat() | 60 min | POST /heartbeat to LS |
| jwt_poll | poll_pending_jwt() | 5 min | Collect pending JWT delivery |
| irrigation_tick | _irrigation_tick() | 60 sec | Auto-irrigation logic |
| messages_sync | sync_messages() | 30 min | Also called once at boot (await, not task) |

`sync_messages()` is also called with `await` at startup (before `yield`) so logs appear immediately on boot.

---

## Alembic migrations (in order)

- 0001 initial_schema
- 0002 culle_refactor
- 0003 zone_config_messages
- 0004 piano_limiti_ai
- 0005 jwt_token_support (adds jwt_token VARCHAR(500))
- 0006 jwt_token_text (widens to TEXT — RS256 JWTs are 800-1000+ chars)
- 0007 messaggi_tipo_varchar (ENUM → VARCHAR(50) for LS notification types)
- 0008 utenti (user management table, seeds admin from ADMIN_PASSWORD env)
- 0009 zona_intervallo_lettura (adds intervallo_lettura_sec INT NOT NULL default 60 to zone table)

---

## Auth system

- **DB-based** (utenti table) — NOT env-var hardcoded anymore
- Roles: `administrator`, `user`
- JWT claims: `sub` (username), `ruolo`, `uid` (user id)
- FastAPI deps: `get_current_user` → dict, `require_admin` → 403 if not administrator, `require_user` → any valid token
- Write endpoints (POST/PUT/DELETE culle, zone, pump, license/register, support/tickets POST) require `require_admin`
- Read endpoints use `require_user`
- Seed: migration 0008 inserts admin user hashed with bcrypt from `ADMIN_PASSWORD` env (default: "admin")

---

## Frontend auth (src/auth.js)

Module-level reactive ref singleton — the single source of truth for role/username. All components import from here. `localStorage.getItem()` in `computed()` is NOT reactive in Vue; this pattern fixes that.

```
setAuth(token)   — call after login; decodes JWT, updates refs + localStorage
clearAuth()      — call on logout/401; resets refs + clears localStorage keys
isAdmin          — computed(() => _ruolo.value === 'administrator')
```

localStorage keys: `ng_token`, `ng_ruolo`, `ng_username`

---

## License Server API (license.lake8.dev)

All endpoints are at root (no `/api/v1/` prefix — that was wrong):

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | /register | none | Body: prodotto_codice, ragione_sociale, piva, email, nome, cognome, piano, machine_id, version |
| POST | /heartbeat | Bearer JWT | Body: token, prodotto_codice, sessioni_attive |
| GET | /license/pending | none | Params: machine_id, product — 60s rate limit per machine_id |
| POST | /license/delivered | none | Acknowledges JWT pickup |
| GET | /notifications | Bearer JWT | Params: machine_id (optional). Returns list of {id, tipo, titolo, corpo, letto, data_creazione} |
| GET | /support/tickets | Bearer JWT | Returns TicketListOut list — filtered by licenza_id (our LS fix) |
| GET | /support/tickets/{id} | Bearer JWT | Returns TicketOut with messaggi array |
| POST | /support/tickets | Bearer JWT | Body JSON: oggetto, testo, priorita |

**JWT delivery flow:** POST /register → LS queues as pending → poll GET /license/pending (respects 60s rate limit) → if trovato=true, token returned → POST /license/delivered to acknowledge.

**MACHINE_ID:** `"nestgrow-server"` (fixed identifier in `app/licensing.py`)

---

## Key models (app/models.py)

- `LicenzaCache` — single row (id=1), stores piano, valida_fino, jwt_token (TEXT), piva, email
- `Utente` — username, password_hash (bcrypt), ruolo (administrator/user), attivo
- `MessaggioCache` — tipo is VARCHAR(50) (was ENUM — LS sends "aggiornamento", "comunicazione" etc.)
- `Culla`, `Zona`, `Lettura`, `Irrigazione`, `PianoLimiti`
- `Zona` fields of note: `umidita_soglia_min/max`, `durata_irrigazione_sec`, `irrigazione_auto`, `intervallo_lettura_sec` (INT, default 60 — seconds between sensor reads, synced to ESP32 via MQTT cmd/config)

---

## Zone config MQTT (PUT /culle/{id}/zone/{num})

After saving to DB, if `culla.device_id` is set and MQTT is connected, publishes:
- Topic: `nestgrow/{device_id}/cmd/config`
- Payload: `{"zona": numero_zona, "intervallo_ms": zona.intervallo_lettura_sec * 1000, "salva_nvs": true}`

Frontend zone modal (`saveZoneConfig` in Dashboard.vue) sends all zone fields including `intervallo_lettura_sec`. The field was missing from the frontend until migration 0009 + this fix.

**ESP32 BUG NOTE (firmware, not in this repo):** STATUS command must read `config.zona_interval[i]` (RAM) not `nvs.getInt(...)` — NVS lags behind until next reboot.

---

## Stats / Grafici API (app/api/culle.py)

- `GET /culle/{id}/stats?giorni=N` — humidity timeseries per zone (15-min buckets via `FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(ts)/900)*900)`), irrigation events with pre/post humidity, serbatoio level. Returns `{zona_umidita, irrigazioni, serbatoio}`.
- `GET /culle/{id}/stats/irrigazioni?giorni=N` — per-zone aggregates: totale_irrigazioni, durata_media_sec, umidita_media_pre/post. Returns `{per_zona}`.
- Both endpoints require `require_user`.

## Frontend grafici (src/components/CullaGrafici.vue)

Inline expandable section per ogni culla card (pulsante "📊 Grafici"):
- Selettore periodo: 24h / 7gg / 30gg
- Grafico 1: line chart umidità per zona (4 colori: #2d6a4f, #1d6fa4, #e07b00, #6b2d8b), soglie tratteggiate, marker rossi irrigazioni
- Grafico 2: area chart serbatoio con gradiente blu, linea rossa al 10%
- Grafico 3: bar chart orizzontale irrigazioni per zona con tooltip stats
- Grafico 4: scatter efficacia irrigazione (pre→post) con diagonale di riferimento
- Griglia 2 colonne desktop / 1 colonna mobile; "Nessun dato" se periodo vuoto

## Backup & Restore system

### Script host-side (backup/)
- `backup/backup.sh [dir]` — dumpa DB via `docker exec nestgrow-db mariadb-dump`, gzippa, mantiene ultimi 30
- `backup/restore.sh <file.sql.gz>` — chiede conferma "SI", ripristina via `docker exec -i nestgrow-db mariadb`
- `backup/list.sh` — lista backup in `./backups/`
- Default backup dir: `./backups/` (volume montato in docker-compose)

### API admin (app/api/admin.py) — require_admin
- `GET /admin/backup` → esegue backup su disco in `/app/backups/`, ritorna metadata
- `GET /admin/backup/download` → dump DB in memoria, StreamingResponse `.sql.gz` (no disk write) — usa `_dump_sql()` helper condiviso
- `GET /admin/backups` → lista file in `/app/backups/`
- `POST /admin/restore` → body `{"filename": "..."}`, ripristina da `/app/backups/`
- `POST /admin/restore/upload` → accetta UploadFile `.sql.gz`, decomprimi in memoria, ripristina via `mysql`

#### Bug fix: Invalid Date in lista backup
`Path.stem` rimuove solo l'ultima estensione: `file.sql.gz` → stem = `file.sql` (non `file`).
Fix: usare `f.name.replace("nestgrow_backup_","").replace(".sql.gz","")` invece di `f.stem`.
Frontend: `parseBackupDate(filename)` legge il timestamp direttamente dal nome file via regex `(\d{8})_(\d{6})` — non usa il campo `timestamp` dell'API.

### Scheduler
- `auto_backup` cron job alle 02:00 ogni giorno (APScheduler `"cron"`, `hour=2`, `minute=0`)

### Frontend
- Tab ⚙️ Sistema (solo admin) in Dashboard con:
  - Pulsante "💾 Salva su volume" → `doBackup()` — salva su `/app/backups/`
  - Pulsante "⬇️ Scarica backup" → `doDownload()` — `axios.get('/admin/backup/download', {responseType:'blob'})` + `<a>.click()` trick
  - Lista ultimi 5 backup con `parseBackupDate(filename)` per la data, pulsante "🔄 Restore" per ognuno con `window.confirm()`
  - Sezione "Restore da file locale": file picker `.sql.gz`, pulsante "🔄 Ripristina da file" → `doUploadRestore()` con FormData + `axios.post('/admin/restore/upload', formData)`

### ⚠️ PRIMO AVVIO — fix permessi obbligatorio
Docker crea `./backups/` come `root`. Prima di usare il backup bisogna:
```bash
docker exec nestgrow-backend chmod 777 /app/backups
```
oppure creare la directory manualmente PRIMA di `docker compose up`:
```bash
mkdir -p backups && chmod 777 backups
```

### Nota tecnica
- Container db (mariadb:11) usa `mariadb-dump` (non `mysqldump` — non in PATH)
- Container backend (python:3.13-slim + default-mysql-client) ha entrambi `mysqldump` e `mariadb-dump`
- I file `.sql.gz` sono in `.gitignore` — i backup non entrano nel repo

## Boot license recovery (app/licensing.py + app/main.py)

`check_license_on_boot(db)` is called once in lifespan before `sync_messages()`.

| DB state | LS response | Log |
|---|---|---|
| jwt_token present | (not called) | "Licenza presente al boot" |
| row exists, no jwt_token | pending JWT found | "JWT recuperato dal License Server" |
| row exists, no jwt_token | no pending JWT | "Licenza pending — attesa approvazione admin" |
| licenza_cache empty (after -v) | no pending JWT | "Nessuna licenza — registrazione necessaria" |

`_save_jwt_to_db(db, token)` — shared helper that does INSERT or UPDATE (handles fresh DB after -v).

`poll_pending_jwt()` (APScheduler 5 min) — old guard `not existing or ... or not existing.piva` blocked recovery on empty DB; now skips only when `existing and existing.jwt_token`.

---

## Pending / known issues

- License Server 500 on PRO upgrade under investigation — suspected VIES VAT validation failing for this P.IVA; full payload/response logging added to `app/api/license.py`
- The JWT consumed during VARCHAR(500) overflow (before migration 0006) was marked delivered on LS but not saved locally — if jwt_token is empty, admin needs to manually activate via `/license/activate`
