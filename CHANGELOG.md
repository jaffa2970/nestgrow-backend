# Changelog

Tutti i cambiamenti notevoli al progetto sono documentati in questo file.
Formato: [Semantic Versioning](https://semver.org/lang/it/)

---

## [0.3.1] — 2026-06-02

### Aggiunto

- **Ping telemetria anonimo** ogni 6 ore verso il License Server (`/telemetry/ping`): invia prodotto, versione, `machine_id` e stato registrazione — nessun dato personale
- Flag `TELEMETRY_ENABLED=true` in `.env.example`; impostare a `false` per disabilitare il ping
- Campo `registrato` nel payload aggiornato automaticamente a `true` quando è presente un JWT di licenza valido (al boot o dopo attivazione)
- Job APScheduler `ping_anonimo` con intervallo di 6 ore
- Chiamata `ping_anonimo()` eseguita anche all'avvio del backend, subito dopo il check della licenza

---

## [0.1.1] — 2026-05-15

### Sicurezza

- Pulsante ON pompa disabilitato in dashboard quando `livello_serbatoio_pct == 0` (tooltip "Serbatoio vuoto — ricarica il serbatoio")
- Backend `POST /culle/{id}/zone/{n}/pump`: rifiuta comando `on` con HTTP 403 se serbatoio è a 0 — doppia protezione frontend + API

### Bug fix

- **`_irrigation_tick` non riavviava mai la pompa** — `expires_at` era calcolato in `pump_state` ma non veniva mai letto nel tick; il `continue` era fuori dal blocco `if elapsed > 5min` e scattava sempre quando la pompa risultava "on", bloccando ogni ciclo successivo. Fix: aggiunto caso `expires_at` per riconoscere l'auto-stop normale dell'ESP32, chiudere il record `Irrigazione` con `esito="ok"` e ri-valutare l'umidità nello stesso tick

### Miglioramenti

- Grafici culla: polling automatico ogni 60 secondi quando la sezione è aperta; indicatore "🔄 Aggiornamento..." durante il refresh e "Aggiornato alle HH:MM:SS" dopo ogni fetch riuscito; cambio periodo resetta e ricrea il timer
- Log `_irrigation_tick` migliorato: aggiunto `CHECK: X% < Y% = True/False` prima di ogni decisione irrigazione; log `SKIP: pompa ON da Xs (scade tra Ys)` e `Auto-stop: pompa off dopo Xs` per visibilità completa del ciclo

---

## [0.1.0] — 2026-05-07

### Aggiunto

- Infrastruttura Docker Compose completa (Mosquitto, MariaDB, FastAPI, Vue 3 + nginx)
- Schema DB completo con Alembic migration `0001_initial_schema` (6 tabelle)
- Seed iniziale: piani licenza (`free`, `pro`, `enterprise`, `ultra`) e pianta `Basilico` di esempio
- Client MQTT asincrono (`asyncio-mqtt`) con dispatcher per tutti i topic `nestgrow/#`
- Persistenza letture sensori in tabella `letture` ad ogni messaggio MQTT ricevuto
- API REST completa:
  - `POST /auth/login` — autenticazione JWT con form OAuth2
  - `GET/POST /zones` — lista e creazione zone con enforcement piano licenza
  - `GET/PUT/DELETE /zones/{id}` — dettaglio, modifica e disattivazione zona
  - `GET /zones/{id}/readings` — serie storica letture per range orario
  - `GET /tank` — livello serbatoio corrente
  - `POST /zones/{id}/pump` — comando manuale pompa ON/OFF via MQTT
  - `GET /license` — stato licenza con conteggio culle usate/disponibili
  - `POST /license/activate` — attivazione licenza tramite License Server
- Integrazione License Server `https://license.lake8.dev`:
  - Heartbeat automatico ogni 60 minuti via APScheduler
  - Enforcement limite culle per piano (HTTP 403 con messaggio esplicito)
  - Cache locale in tabella `licenza_cache` (singleton row)
- Logica irrigazione automatica a soglie (scheduler ogni 60 secondi):
  - Trigger se `umidità < pianta.umidita_min` e lettura fresca (< 5 min)
  - Blocco se `livello_serbatoio < 10%`
  - Safety timeout: pompa ON da > 5 minuti → forza OFF con esito `timeout`
  - Log eventi irrigazione in tabella `irrigazioni`
- Dashboard Vue 3:
  - Login con autenticazione JWT e redirect automatico
  - Griglia zone con umidità real-time, stato pompa, badge piano licenza
  - Controllo manuale pompa ON/OFF per zona
  - Modal creazione nuova zona con validazione limite piano
  - Polling automatico ogni 10 secondi
- Autenticazione JWT con interceptor Axios (attach token + redirect su 401)
- Graceful shutdown: chiusura MQTT, scheduler, engine DB al termine del processo
- `test_mqtt.py`: script locale per pubblicare letture MQTT di test
