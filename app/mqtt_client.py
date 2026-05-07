import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from aiomqtt import Client, MqttError

from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory sensor state keyed by zona.id (INT)
latest_readings: dict[int, dict] = {}   # zona_id → {umidita_pct, ts}
latest_tank: dict[str, dict] = {}        # device_id → {livello, ts}
pump_state: dict[int, dict] = {}         # zona_id → {on: bool, since: datetime | None}

# Device→zone cache: device_id → {numero_zona → zona_id}
_device_cache: dict[str, dict[int, int]] = {}
_cache_expires: datetime = datetime.min.replace(tzinfo=timezone.utc)
_CACHE_TTL = timedelta(seconds=60)


async def _refresh_device_cache() -> None:
    global _device_cache, _cache_expires
    from app.database import AsyncSessionLocal
    from app.models import Culla, Zona
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as db:
            rows = await db.execute(
                select(Culla.device_id, Zona.numero_zona, Zona.id)
                .join(Zona, Zona.culla_id == Culla.id)
                .where(Culla.attiva == True, Culla.device_id.is_not(None), Zona.attiva == True)
            )
            cache: dict[str, dict[int, int]] = {}
            for device_id, numero_zona, zona_id in rows:
                cache.setdefault(device_id, {})[numero_zona] = zona_id
            _device_cache = cache
            _cache_expires = datetime.now(timezone.utc) + _CACHE_TTL
    except Exception as exc:
        logger.warning("Device cache refresh failed: %s", exc)


async def _get_zona_id(device_id: str, numero_zona: int) -> int | None:
    if datetime.now(timezone.utc) >= _cache_expires:
        await _refresh_device_cache()
    return _device_cache.get(device_id, {}).get(numero_zona)


# ---------- Handlers ----------

async def handle_zona_umidita(device_id: str, numero_zona: int, payload: dict) -> None:
    zona_id = await _get_zona_id(device_id, numero_zona)
    if zona_id is None:
        logger.debug("device_id '%s' not in DB cache, discarding umidita", device_id)
        return

    latest_readings[zona_id] = {
        "umidita_pct": payload.get("v"),
        "ts": datetime.now(timezone.utc),
    }

    from app.database import AsyncSessionLocal
    from app.models import Lettura

    tank = latest_tank.get(device_id, {})
    async with AsyncSessionLocal() as db:
        db.add(
            Lettura(
                zona_id=zona_id,
                ts=datetime.now(timezone.utc),
                umidita_pct=payload.get("v"),
                livello_serbatoio_pct=tank.get("livello"),
            )
        )
        await db.commit()


async def handle_serbatoio(device_id: str, payload: dict) -> None:
    latest_tank[device_id] = {
        "livello": payload.get("v"),
        "ts": datetime.now(timezone.utc),
    }


async def handle_heartbeat(device_id: str, payload: dict) -> None:
    logger.debug("Heartbeat %s: uptime=%s rssi=%s", device_id,
                 payload.get("uptime_sec"), payload.get("wifi_rssi"))


# ---------- Dispatcher ----------

async def _dispatch(topic: str, payload_raw: bytes) -> None:
    try:
        payload = json.loads(payload_raw)
    except Exception:
        return

    parts = topic.split("/")
    if len(parts) < 2 or parts[0] != "nestgrow":
        return

    device_id = parts[1]

    # nestgrow/{device_id}/zona/{num}/umidita  → 5 parts
    if len(parts) == 5 and parts[2] == "zona" and parts[4] == "umidita":
        try:
            num = int(parts[3])
        except ValueError:
            return
        await handle_zona_umidita(device_id, num, payload)

    # nestgrow/{device_id}/serbatoio/livello   → 4 parts
    elif len(parts) == 4 and parts[2] == "serbatoio" and parts[3] == "livello":
        await handle_serbatoio(device_id, payload)

    # nestgrow/{device_id}/heartbeat           → 3 parts
    elif len(parts) == 3 and parts[2] == "heartbeat":
        await handle_heartbeat(device_id, payload)


# ---------- Publish ----------

async def publish_pump_cmd(
    mqtt_client: Client,
    device_id: str,
    numero_zona: int,
    cmd: str,
    sec: int = 30,
) -> None:
    payload: dict = {"cmd": cmd}
    if cmd == "on":
        payload["sec"] = sec
    await mqtt_client.publish(
        f"nestgrow/{device_id}/zona/{numero_zona}/pompa",
        json.dumps(payload),
    )
    zona_id = await _get_zona_id(device_id, numero_zona)
    if zona_id is not None:
        pump_state[zona_id] = {
            "on": cmd == "on",
            "since": datetime.now(timezone.utc) if cmd == "on" else None,
        }


# ---------- Main loop ----------

async def mqtt_loop(stop_event: asyncio.Event) -> None:
    # Pre-populate cache before entering the loop
    await _refresh_device_cache()

    while not stop_event.is_set():
        try:
            async with Client(settings.mqtt_host, port=settings.mqtt_port) as client:
                import app.mqtt_client as _self
                _self._client = client

                await client.subscribe("nestgrow/#")
                logger.info("MQTT connected to %s:%d", settings.mqtt_host, settings.mqtt_port)

                async for message in client.messages:
                    if stop_event.is_set():
                        break
                    asyncio.create_task(_dispatch(str(message.topic), message.payload))

        except MqttError as exc:
            if stop_event.is_set():
                break
            logger.warning("MQTT error: %s — reconnecting in 5s", exc)
            await asyncio.sleep(5)
        except Exception as exc:
            if stop_event.is_set():
                break
            logger.error("Unexpected MQTT error: %s", exc)
            await asyncio.sleep(5)


_client = None


async def get_client() -> Client:
    return _client
