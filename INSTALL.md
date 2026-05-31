# NestGrow — Guida all'installazione

## Requisiti

- Docker >= 24.0
- Docker Compose >= 2.0
- Porte disponibili: `1883` (MQTT), `8000` (API), `3001` (Dashboard)

---

## Installazione

### 1. Scarica il progetto

```bash
git clone https://github.com/jaffa2970/nestgrow-backend
cd nestgrow-backend
```

### 2. Configura le variabili d'ambiente

```bash
cp .env.example .env
```

Modifica `.env` con i tuoi valori:

| Variabile | Cosa inserire |
|-----------|--------------|
| `DB_PASSWORD` | Una password sicura per il database |
| `DB_ROOT_PASSWORD` | Una password sicura per root MariaDB |
| `JWT_SECRET` | Stringa random lunga — genera con il comando sotto |
| `ADMIN_PASSWORD` | La password che userai per accedere alla dashboard |
| `MQTT_PASSWORD` | Una password sicura per il broker MQTT |

Per generare un `JWT_SECRET` sicuro:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Crea la cartella backups

```bash
mkdir -p backups && chmod 777 backups
```

### 4. Inizializza l'autenticazione MQTT

```bash
./init_mqtt_auth.sh
```

Questo script legge `MQTT_USER` e `MQTT_PASSWORD` dal `.env` e genera il file di autenticazione per il broker MQTT.

### 5. Avvia il sistema

```bash
docker compose up -d
```

---

## 🔑 Primo accesso

Apri il browser su:

**http://localhost:3001**

### Credenziali dashboard

| Campo | Valore |
|---|---|
| **Username** | `admin` |
| **Password** | il valore di `ADMIN_PASSWORD` nel tuo `.env` |

> ⚠️ **Importante**: la password admin è quella che hai impostato nel file `.env` prima di avviare.
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

## Comandi utili

```bash
# Ferma il sistema
docker compose down

# Visualizza i log
docker compose logs -f

# Riavvia solo il backend
docker compose restart backend

# Backup manuale del database
./backup/backup.sh

# Lista backup disponibili
./backup/list.sh

# Restore da backup
./backup/restore.sh ./backups/nestgrow_backup_YYYYMMDD_HHMMSS.sql.gz
```

---

## Firmware ESP32

Il firmware open source per ESP32 è disponibile su:
**https://github.com/jaffa2970/nestgrow-esp32**

---

## Supporto

**https://nestgrow.lake8.dev**
