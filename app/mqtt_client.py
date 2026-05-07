import asyncio
import json
import logging
from datetime import datetime, timezone

from asyncio_mqtt import Client, MqttError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Shared state — populated by MQTT callbacks, read by API
latest_readings: dict[int, dict] = {}  # zona_id → {umidita, ts}
latest_tank: dict = {}                  # {livello, ts}
pump_state: dict[int, dict] = {}        # zona_id → {on: bool, since: datetime}


async def handle_zona_umidita(zona_id: int, payload: dict) -> None:
    from app.database import AsyncSessionLocal
    from app.models import Lettura

    latest_readings[zona_id] = {
        "umidita_pct": payload.get("v"),
        "ts": datetime.now(timezone.utc),
        "device_id": payload.get("device_id"),
    }
    async with AsyncSessionLocal() as session:
        lettura = Lettura(
            zona_id=zona_id,
            ts=datetime.now(timezone.utc),
            umidita_pct=payload.get("v"),
            livello_serbatoio_pct=latest_tank.get("livello"),
        )
        session.add(lettura)
        await session.commit()


async def handle_serbatoio(payload: dict) -> None:
    latest_tank["livello"] = payload.get("v")
    latest_tank["ts"] = datetime.now(timezone.utc)


async def handle_device_heartbeat(device_id: str, payload: dict) -> None:
    logger.debug("Heartbeat from %s: %s", device_id, payload)


async def _dispatch(topic: str, payload_raw: bytes) -> None:
    try:
        payload = json.loads(payload_raw)
    except Exception:
        return

    parts = topic.split("/")

    if len(parts) == 4 and parts[0] == "nestgrow" and parts[1] == "zona" and parts[3] == "umidita":
        try:
            zona_id = int(parts[2])
        except ValueError:
            return
        await handle_zona_umidita(zona_id, payload)

    elif topic == "nestgrow/serbatoio/livello":
        await handle_serbatoio(payload)

    elif len(parts) == 4 and parts[0] == "nestgrow" and parts[1] == "device" and parts[3] == "heartbeat":
        await handle_device_heartbeat(parts[2], payload)


async def publish_pump_cmd(mqtt_client: Client, zona_id: int, cmd: str, sec: int = 30) -> None:
    payload: dict = {"cmd": cmd}
    if cmd == "on":
        payload["sec"] = sec
    await mqtt_client.publish(
        f"nestgrow/zona/{zona_id}/pompa",
        json.dumps(payload),
    )
    if cmd == "on":
        pump_state[zona_id] = {"on": True, "since": datetime.now(timezone.utc)}
    else:
        pump_state[zona_id] = {"on": False, "since": None}


async def mqtt_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with Client(settings.mqtt_host, port=settings.mqtt_port) as client:
                # Store client reference for use by other modules
                import app.mqtt_client as _self
                _self._client = client

                await client.subscribe("nestgrow/#")
                logger.info("MQTT connected to %s:%d", settings.mqtt_host, settings.mqtt_port)
                async with client.messages() as messages:
                    async for message in messages:
                        if stop_event.is_set():
                            break
                        asyncio.create_task(
                            _dispatch(str(message.topic), message.payload)
                        )
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


# Module-level client reference set by mqtt_loop
_client = None


async def get_client() -> Client:
    return _client
