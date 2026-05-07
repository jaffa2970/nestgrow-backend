import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, culle
from app.api import license as license_api
from app.api import messages as messages_api
from app.api import support as support_api
from app.database import AsyncSessionLocal, engine
from app.licensing import heartbeat
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

    client = await get_client()
    if client is None:
        return

    async with AsyncSessionLocal() as db:
        culle_result = await db.execute(
            select(Culla).where(Culla.attiva == True)
        )
        culle = culle_result.scalars().all()

        for culla in culle:
            device_id = culla.device_id or f"culla-{culla.id}"
            tank = latest_tank.get(device_id, {})
            tank_level = tank.get("livello", 100.0)

            if tank_level is not None and tank_level < 10.0:
                logger.warning(
                    "Serbatoio culla %d sotto 10%% (%.1f) — irrigazione bloccata",
                    culla.id,
                    tank_level,
                )
                continue

            zones_result = await db.execute(
                select(Zona).where(
                    Zona.culla_id == culla.id,
                    Zona.attiva == True,
                    Zona.irrigazione_auto == True,
                    Zona.umidita_soglia_min.is_not(None),
                )
            )
            zone = zones_result.scalars().all()

            for zona in zone:
                reading = latest_readings.get(zona.id, {})
                ts = reading.get("ts")
                if not ts or (datetime.now(timezone.utc) - ts) > timedelta(minutes=5):
                    continue

                umidita = reading.get("umidita_pct")
                if umidita is None:
                    continue

                state = pump_state.get(zona.id, {})

                # Safety: pump ON for > 5 minutes → force OFF
                if state.get("on") and state.get("since"):
                    elapsed = datetime.now(timezone.utc) - state["since"]
                    if elapsed > timedelta(minutes=5):
                        logger.warning(
                            "Safety: pompa culla %d zona %d on >5min → forzo OFF",
                            culla.id,
                            zona.numero_zona,
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

                # Trigger irrigation when humidity drops below zone threshold
                soglia = zona.umidita_soglia_min
                durata = zona.durata_irrigazione_sec or 20
                if umidita < soglia and not state.get("on"):
                    logger.info(
                        "Culla %d zona %d: umidità %.1f < soglia %.1f → irrigazione %ds",
                        culla.id,
                        zona.numero_zona,
                        umidita,
                        soglia,
                        durata,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.mqtt_client as mqtt_mod

    mqtt_task = asyncio.create_task(mqtt_mod.mqtt_loop(_mqtt_stop))

    _scheduler.add_job(heartbeat, "interval", minutes=60, id="license_heartbeat")
    _scheduler.add_job(_irrigation_tick, "interval", seconds=60, id="irrigation_tick")
    _scheduler.add_job(sync_messages, "interval", minutes=15, id="messages_sync")
    _scheduler.start()

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
app.include_router(culle.router)
app.include_router(license_api.router)
app.include_router(messages_api.router)
app.include_router(support_api.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nestgrow-backend", "version": "0.3.0"}
