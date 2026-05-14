import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, culle
from app.api import admin as admin_api
from app.api import export as export_api
from app.api import impostazioni as impostazioni_api
from app.api import license as license_api
from app.api import messages as messages_api
from app.api import support as support_api
from app.api import utenti as utenti_api
from app.database import AsyncSessionLocal, engine
from app.licensing import check_license_on_boot, heartbeat, poll_pending_jwt
from app.messaging import sync_messages

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_mqtt_stop = asyncio.Event()
_scheduler = AsyncIOScheduler()


async def _irrigation_tick() -> None:
    from app.models import Culla, Irrigazione, Zona
    from app.mqtt_client import (
        get_client,
        latest_readings,
        latest_tank,
        publish_pump_cmd,
        pump_state,
    )
    from sqlalchemy import select

    logger.info("=== IRRIGATION TICK ===")

    client = await get_client()
    if client is None:
        logger.warning("  MQTT non connesso — tick saltato")
        return

    async with AsyncSessionLocal() as db:
        culle_result = await db.execute(
            select(Culla).where(Culla.attiva == True)
        )
        culle = culle_result.scalars().all()
        logger.info("Culle attive: %d", len(culle))

        for culla in culle:
            device_id = culla.device_id or f"culla-{culla.id}"
            tank = latest_tank.get(device_id, {})
            tank_level = tank.get("livello", 100.0)
            logger.info("Culla %d — device_id: %s — serbatoio: %s%%",
                        culla.id, device_id,
                        f"{tank_level:.1f}" if tank_level is not None else "N/A")

            if tank_level is not None and tank_level < 10.0:
                logger.warning(
                    "  Culla %d: serbatoio vuoto (%.1f%%) — irrigazione bloccata",
                    culla.id, tank_level,
                )
                continue

            # Fetch all active zones (no pre-filter) so we can log skip reasons
            zones_result = await db.execute(
                select(Zona).where(Zona.culla_id == culla.id, Zona.attiva == True)
            )
            zone = zones_result.scalars().all()

            for zona in zone:
                logger.info("  Zona %d — nome: %s — auto: %s — soglia_min: %s",
                            zona.numero_zona, zona.nome or "—",
                            zona.irrigazione_auto, zona.umidita_soglia_min)

                if not zona.irrigazione_auto:
                    logger.info("  → SKIP: irrigazione_auto disabilitata")
                    continue
                if zona.umidita_soglia_min is None:
                    logger.info("  → SKIP: soglia_min non configurata")
                    continue

                reading = latest_readings.get(zona.id, {})
                ts = reading.get("ts")
                umidita = reading.get("umidita_pct")

                if not ts:
                    logger.info("  → SKIP: nessuna lettura MQTT in memoria (zona_id=%d)", zona.id)
                    continue

                age_sec = (datetime.now(timezone.utc) - ts).total_seconds()
                logger.info("  Ultima lettura MQTT: %s%% — ts: %s — età: %.0fs",
                            f"{umidita:.1f}" if umidita is not None else "None", ts, age_sec)

                if age_sec > 300:
                    logger.info("  → SKIP: lettura troppo vecchia (%.0fs > 300s)", age_sec)
                    continue

                if umidita is None:
                    logger.info("  → SKIP: umidità None nella lettura")
                    continue

                state = pump_state.get(zona.id, {})

                # Safety: pump ON for > 5 minutes → force OFF
                if state.get("on") and state.get("since"):
                    elapsed = datetime.now(timezone.utc) - state["since"]
                    if elapsed > timedelta(minutes=5):
                        logger.warning(
                            "  Safety: pompa culla %d zona %d on >5min → forzo OFF",
                            culla.id, zona.numero_zona,
                        )
                        await publish_pump_cmd(client, device_id, zona.numero_zona, "off")
                        irr_r = await db.execute(
                            select(Irrigazione)
                            .where(
                                Irrigazione.zona_id == zona.id,
                                Irrigazione.ts_fine.is_(None),
                            )
                            .order_by(Irrigazione.ts_inizio.desc())
                            .limit(1)
                        )
                        irr = irr_r.scalar_one_or_none()
                        if irr:
                            irr.ts_fine = datetime.now(timezone.utc)
                            irr.durata_sec = int(elapsed.total_seconds())
                            irr.esito = "timeout"
                        await db.commit()
                    continue

                soglia = zona.umidita_soglia_min
                durata = zona.durata_irrigazione_sec or 20
                if umidita < soglia and not state.get("on"):
                    logger.info(
                        "  → IRRIGAZIONE: %.1f%% < %.1f%% → pompa ON per %ds",
                        umidita, soglia, durata,
                    )
                    await publish_pump_cmd(client, device_id, zona.numero_zona, "on", durata)
                    db.add(
                        Irrigazione(
                            zona_id=zona.id,
                            ts_inizio=datetime.now(timezone.utc),
                            umidita_pre=umidita,
                            trigger="soglia",
                        )
                    )
                    await db.commit()
                else:
                    logger.info("  → OK: %.1f%% >= %.1f%% (nessuna azione)", umidita, soglia)


async def _cleanup_old_readings() -> None:
    from sqlalchemy import delete
    from app.models import Lettura
    from app.api.impostazioni import get_impostazione

    async with AsyncSessionLocal() as db:
        retention = await get_impostazione(db, "retention_giorni", "30")
        giorni = int(retention)
        cutoff = datetime.now(timezone.utc) - timedelta(days=giorni)
        result = await db.execute(delete(Lettura).where(Lettura.ts < cutoff))
        await db.commit()
        logger.info("Cleanup: eliminati %d letture più vecchie di %d giorni", result.rowcount, giorni)


async def _auto_backup() -> None:
    from app.api.admin import run_backup
    logger.info("=== Auto backup database ===")
    try:
        info = await run_backup()
        logger.info("Auto backup OK: %s (%d bytes)", info["filename"], info["size_bytes"])
    except Exception as exc:
        logger.error("Auto backup FAILED: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.mqtt_client as mqtt_mod

    mqtt_task = asyncio.create_task(mqtt_mod.mqtt_loop(_mqtt_stop))

    _scheduler.add_job(heartbeat, "interval", minutes=60, id="license_heartbeat")
    _scheduler.add_job(poll_pending_jwt, "interval", minutes=5, id="jwt_poll")
    _scheduler.add_job(_irrigation_tick, "interval", seconds=60, id="irrigation_tick")
    _scheduler.add_job(sync_messages, "interval", minutes=30, id="messages_sync")
    _scheduler.add_job(_auto_backup, "cron", hour=2, minute=0, id="auto_backup")
    _scheduler.add_job(_cleanup_old_readings, "cron", hour=3, minute=0, id="cleanup_readings")
    _scheduler.start()
    logger.info("Scheduler avviato — job registrati: %s", [j.id for j in _scheduler.get_jobs()])

    # Boot checks — run synchronously so logs appear immediately
    try:
        async with AsyncSessionLocal() as db:
            await check_license_on_boot(db)
    except Exception as exc:
        logger.error("check_license_on_boot ha fallito: %s", exc, exc_info=True)

    try:
        await sync_messages()
    except Exception as exc:
        logger.error("sync_messages al boot ha fallito: %s", exc, exc_info=True)

    logger.info("NestGrow backend avviato")
    yield

    _mqtt_stop.set()
    _scheduler.shutdown(wait=False)
    try:
        await asyncio.wait_for(mqtt_task, timeout=5.0)
    except asyncio.TimeoutError:
        pass
    await engine.dispose()
    logger.info("NestGrow backend fermato")


app = FastAPI(
    title="NestGrow API",
    version="0.3.0",
    description="Sistema gestione culle di accrescimento vegetale — lake8.dev",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin_api.router)
app.include_router(culle.router)
app.include_router(export_api.router)
app.include_router(impostazioni_api.router)
app.include_router(license_api.router)
app.include_router(messages_api.router)
app.include_router(support_api.router)
app.include_router(utenti_api.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nestgrow-backend", "version": "0.3.0"}
