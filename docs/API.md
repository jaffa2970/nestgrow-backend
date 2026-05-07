# API Reference

Base URL: `http://localhost:8000`
Documentazione interattiva: `http://localhost:8000/docs` (Swagger UI)

---

## Autenticazione

Tutte le API (eccetto `/auth/login`) richiedono l'header:

```
Authorization: Bearer {token}
```

Il token viene ottenuto con `POST /auth/login` e ha validità 8 ore.
Il frontend aggiunge automaticamente il token tramite Axios interceptor.

---

## Auth

### POST /auth/login

Autentica l'utente e restituisce un JWT.

**Content-Type:** `application/x-www-form-urlencoded`

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `username` | string | Nome utente (default: `admin`) |
| `password` | string | Password (configurabile via env `ADMIN_PASSWORD`) |

**Risposta 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Risposta 401:**
```json
{ "detail": "Credenziali non valide" }
```

---

### POST /auth/logout

Invalida la sessione lato client (il JWT è stateless, il client deve eliminare il token).

**Risposta 200:**
```json
{ "detail": "Logout effettuato" }
```

---

## Zones

### GET /zones/

Restituisce tutte le zone attive con stato corrente (ultima lettura umidità, stato pompa).

**Risposta 200:**
```json
[
  {
    "id": 1,
    "nome": "Zona Basilico",
    "pianta_id": 1,
    "attiva": true,
    "device_id": "nestgrow-a4b2",
    "creato_il": "2026-05-07T10:00:00",
    "ultima_umidita": 67.3,
    "ultima_lettura_ts": "2026-05-07T10:45:00Z",
    "pompa_on": false
  }
]
```

---

### POST /zones/

Crea una nuova zona. Verifica il limite di culle del piano licenza corrente.

**Body JSON:**
```json
{
  "id": 1,
  "nome": "Zona Basilico",
  "pianta_id": 1,
  "device_id": "nestgrow-a4b2"
}
```

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|:---:|-------------|
| `id` | int | Sì | ID zona (assegnato manualmente, 1-N) |
| `nome` | string | Sì | Nome descrittivo |
| `pianta_id` | int | No | ID profilo pianta associato |
| `device_id` | string | No | MAC-based ID ESP32 (es. `nestgrow-a4b2`) |

**Risposta 201:** oggetto zona creato

**Risposta 403 (limite piano raggiunto):**
```json
{
  "detail": "Piano Free: massimo 1 culla. Aggiorna su https://nestgrow.lake8.dev"
}
```

---

### GET /zones/{id}

Dettaglio zona con stato corrente.

**Risposta 200:** oggetto zona (stesso schema di GET /zones/)
**Risposta 404:** `{ "detail": "Zona non trovata" }`

---

### PUT /zones/{id}

Modifica una zona esistente. Tutti i campi sono opzionali.

**Body JSON:**
```json
{
  "nome": "Nuovo nome",
  "pianta_id": 2,
  "device_id": "nestgrow-b5c3",
  "attiva": true
}
```

**Risposta 200:** oggetto zona aggiornato

---

### DELETE /zones/{id}

Disattiva una zona (soft delete — imposta `attiva = false`).

**Risposta 200:**
```json
{ "detail": "Zona disattivata" }
```

---

## Sensors

### GET /zones/{id}/readings

Restituisce le letture della zona nell'ultimo intervallo di ore specificato.

**Query params:**

| Param | Tipo | Default | Descrizione |
|-------|------|---------|-------------|
| `hours` | int | 24 | Numero di ore da includere (max 5000 risultati) |

**Risposta 200:**
```json
[
  {
    "id": 1234,
    "ts": "2026-05-07T10:45:00.123Z",
    "zona_id": 1,
    "umidita_pct": 67.3,
    "livello_serbatoio_pct": 82.0
  }
]
```

Le letture sono in ordine decrescente (più recenti prima).

---

### GET /tank

Restituisce il livello attuale del serbatoio (dall'ultimo messaggio MQTT ricevuto).

**Risposta 200:**
```json
{
  "livello_pct": 82.0,
  "ts": "2026-05-07T10:45:00Z"
}
```

Se nessun messaggio serbatoio è ancora stato ricevuto, entrambi i campi sono `null`.

---

## Pumps

### POST /zones/{id}/pump

Invia un comando manuale alla pompa della zona tramite MQTT. Se il comando è `on`, crea anche un record in `irrigazioni` con `trigger = "manuale"`.

**Body JSON:**
```json
{ "cmd": "on", "sec": 30 }
```

oppure:

```json
{ "cmd": "off" }
```

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `cmd` | string | `"on"` oppure `"off"` |
| `sec` | int | Durata in secondi (solo per `cmd = "on"`, default 30) |

**Risposta 200:**
```json
{ "detail": "Pompa zona 1 → on" }
```

**Risposta 503:** MQTT non connesso
**Risposta 404:** Zona non trovata o non attiva

---

## License

### GET /license/

Restituisce lo stato della licenza corrente con conteggio culle.

**Risposta 200:**
```json
{
  "piano": "free",
  "valida_fino": "2099-01-01T00:00:00",
  "features": {},
  "aggiornato_il": "2026-05-07T10:00:00",
  "culle_usate": 1,
  "culle_disponibili": 0
}
```

---

### POST /license/activate

Attiva o aggiorna la licenza inviando un JWT al License Server lake8.dev. Il server valida il JWT e restituisce il piano associato, che viene salvato in `licenza_cache`.

**Body JSON:**
```json
{ "jwt_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." }
```

**Risposta 200:**
```json
{ "detail": "Licenza aggiornata", "piano": "pro" }
```

**Risposta 502:** License Server non raggiungibile o JWT non valido

---

## Codici di errore

| Codice | Significato |
|--------|-------------|
| 400 | Richiesta non valida (es. ID zona duplicato) |
| 401 | Token JWT mancante, non valido o scaduto |
| 403 | Limite culle del piano raggiunto |
| 404 | Risorsa non trovata |
| 503 | MQTT non connesso (broker offline o in riconnessione) |
| 502 | License Server non raggiungibile |
