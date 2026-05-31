# Architettura NestGrow

## Panoramica sistema

```
┌─────────────┐   WiFi/MQTT    ┌─────────────────┐   SQL    ┌───────────────┐
│   ESP32     │ ─────────────► │                 │ ────────► │   MariaDB 11  │
│  Firmware   │ ◄───────────── │  FastAPI        │          │   nestgrow_db │
│             │  pompa cmds    │  Backend        │          └───────────────┘
└─────────────┘                │                 │
                               │                 │   HTTPS   ┌───────────────────┐
┌─────────────┐                │                 │ ─────────► │  license.lake8.dev│
│  Vue 3      │   REST/JSON    │                 │ ◄───────── │  License Server   │
│  Dashboard  │ ◄────────────► │                 │           └───────────────────┘
└─────────────┘                └─────────────────┘
                                        ▲
                               ┌────────┴────────┐
                               │   Mosquitto 2   │
                               │   MQTT Broker   │
                               └─────────────────┘
```

**Flussi principali:**

1. `ESP32 → WiFi → MQTT (Mosquitto) → FastAPI → MariaDB` — letture sensori
2. `FastAPI → MQTT → ESP32` — comandi pompe
3. `FastAPI → License Server lake8.dev` — heartbeat ogni 60 minuti
4. `Vue 3 Dashboard ↔ FastAPI REST API` — interazione utente

---

## Componenti

### ESP32 Firmware (open source)

Repository: **https://github.com/lake8dev/nestgrow-esp32**

Funzionalità:
- Lettura sensori umidità capacitivi (fino a 4 zone per scheda)
- Lettura sensore livello serbatoio (ultrasonico o capacitivo)
- Controllo relè pompe (una per zona)
- Captive portal per configurazione WiFi iniziale (primo avvio)
- Riconfigurazione remota via MQTT (`nestgrow/device/{id}/cmd/reconfig`)
- Heartbeat periodico con stato sistema (uptime, RSSI, heap libero)

Il `device_id` è derivato dal MAC address dell'ESP32, nel formato `nestgrow-{4hex}` (es. `nestgrow-a4b2`).

---

### Backend FastAPI

| Modulo | Responsabilità |
|--------|----------------|
| `app/main.py` | Entry point, lifespan (MQTT task + scheduler), CORS, router registration |
| `app/database.py` | Engine SQLAlchemy async, session factory, `get_db` dependency |
| `app/models.py` | Tutti i modelli ORM mappati sulle tabelle MariaDB |
| `app/mqtt_client.py` | Loop MQTT asincrono, dispatcher topic, stato in-memory (letture, pompe, serbatoio) |
| `app/licensing.py` | Heartbeat License Server, lettura/scrittura `licenza_cache`, enforcement culle |
| `app/core/config.py` | `pydantic-settings` — lettura variabili d'ambiente / `.env` |
| `app/core/security.py` | JWT encode/decode, bcrypt hash/verify |
| `app/api/auth.py` | Endpoint autenticazione, dependency `get_current_user` |
| `app/api/zones.py` | CRUD zone con check limite licenza |
| `app/api/sensors.py` | Query letture storiche e stato serbatoio |
| `app/api/pumps.py` | Comando manuale pompa, pubblicazione MQTT, log irrigazione |
| `app/api/license.py` | Stato licenza, attivazione tramite License Server |

**Scheduler APScheduler (background, asyncio):**
- `license_heartbeat` — ogni 60 minuti → chiama `licensing.heartbeat()`
- `irrigation_tick` — ogni 60 secondi → controlla ogni zona attiva e attiva pompa se necessario

---

### Database MariaDB

| Tabella | Scopo |
|---------|-------|
| `piano_limiti` | Lookup statico: piano → max culle (seeded a migration) |
| `piante` | Profili piante configurabili (soglie umidità, durata irrigazione) |
| `zone` | Culle fisiche: ID manuale, device ESP32 associato, pianta assegnata |
| `letture` | Serie storica sensori — insert frequenti, index su `(ts, zona_id)` |
| `irrigazioni` | Log eventi irrigazione con trigger, esito, umidità pre/post |
| `licenza_cache` | Singleton (id=1): piano corrente, scadenza, features da License Server |

---

### License Server lake8.dev

- **Heartbeat:** `GET https://license.lake8.dev/api/v1/heartbeat?product=nestgrow`
  - Header `Authorization: Bearer {jwt_locale}` (opzionale per piano free)
  - Risposta: `{"plan": "pro", "valid_until": "2027-01-01T00:00:00", "features": {}}`
  - Salvata in `licenza_cache` (aggiornamento upsert sul singleton id=1)
- **Enforcement:** in `POST /zones`, prima di creare, si conta `zone.attiva == True`; se `>= max_culle` → HTTP 403

**Limiti per piano:**

| Piano | Max culle |
|-------|-----------|
| free | 1 |
| pro | 5 |
| enterprise | 20 |
| ultra | 9999 (illimitato) |

---

## Flusso irrigazione automatica

Lo scheduler `irrigation_tick` si esegue ogni 60 secondi:

```
Per ogni zona attiva con pianta assegnata:
│
├── Leggi ultima lettura in-memory (latest_readings[zona_id])
│   └── Se più vecchia di 5 minuti → skip (ESP32 offline o disconnesso)
│
├── Controlla livello serbatoio (latest_tank)
│   └── Se < 10% → blocca tutte le irrigazioni, log WARNING
│
├── Se pompa è già ON:
│   └── Se ON da > 5 minuti → forza OFF (publish MQTT) + esito="timeout"
│
└── Se umidità < pianta.umidita_min E pompa OFF:
    ├── Pubblica MQTT: nestgrow/zona/{id}/pompa {"cmd":"on","sec":N}
    └── Inserisce record in irrigazioni (ts_inizio, umidita_pre, trigger="soglia")
```

---

## Topic MQTT completi

| Topic | Direzione | Payload esempio | Descrizione |
|-------|-----------|-----------------|-------------|
| `nestgrow/zona/{id}/umidita` | ESP32 → Backend | `{"v": 67.3, "ts": 1234567890, "device_id": "nestgrow-a4b2"}` | Lettura umidità suolo (0-100%) |
| `nestgrow/serbatoio/livello` | ESP32 → Backend | `{"v": 82.0, "ts": 1234567890, "device_id": "nestgrow-a4b2"}` | Livello serbatoio (0-100%) |
| `nestgrow/zona/{id}/pompa` | Backend → ESP32 | `{"cmd": "on", "sec": 30}` oppure `{"cmd": "off"}` | Attivazione/disattivazione pompa |
| `nestgrow/device/{id}/heartbeat` | ESP32 → Backend | `{"uptime_sec": 3600, "wifi_rssi": -65, "free_heap": 180000, "firmware_version": "1.0.0", "ip": "192.168.1.45"}` | Stato dispositivo |
| `nestgrow/device/{id}/cmd/reconfig` | Backend → ESP32 | `{"ssid": "MyWifi", "password": "...", "mqtt_host": "192.168.1.10"}` | Riconfigurazione WiFi/MQTT remota |
