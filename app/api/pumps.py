from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Zona
from app.mqtt_client import get_client, publish_pump_cmd
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["pumps"])


class PumpCmd(BaseModel):
    cmd: str  # "on" | "off"
    sec: int = 30


@router.post("/zones/{zona_id}/pump")
async def pump_command(
    zona_id: int,
    body: PumpCmd,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    if body.cmd not in ("on", "off"):
        raise HTTPException(status_code=400, detail="cmd deve essere 'on' o 'off'")

    zona = await db.get(Zona, zona_id)
    if not zona or not zona.attiva:
        raise HTTPException(status_code=404, detail="Zona non trovata o non attiva")

    client = await get_client()
    if client is None:
        raise HTTPException(status_code=503, detail="MQTT non connesso")

    await publish_pump_cmd(client, zona_id, body.cmd, body.sec)

    if body.cmd == "on":
        from datetime import datetime, timezone
        from app.database import AsyncSessionLocal
        from app.models import Irrigazione
        from app.mqtt_client import latest_readings

        reading = latest_readings.get(zona_id, {})
        async with AsyncSessionLocal() as session:
            irr = Irrigazione(
                zona_id=zona_id,
                ts_inizio=datetime.now(timezone.utc),
                umidita_pre=reading.get("umidita_pct"),
                trigger="manuale",
            )
            session.add(irr)
            await session.commit()

    return {"detail": f"Pompa zona {zona_id} → {body.cmd}"}
