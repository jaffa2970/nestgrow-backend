# Changelog

Tutti i cambiamenti notevoli al progetto sono documentati in questo file.
Formato: [Semantic Versioning](https://semver.org/lang/it/)

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
