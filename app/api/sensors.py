from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Lettura, Zona
from app.mqtt_client import latest_tank

router = APIRouter(tags=["sensors"])


class LetturaOut(BaseModel):
    id: int
    ts: datetime
    zona_id: int
    umidita_pct: float | None
    livello_serbatoio_pct: float | None

    model_config = {"from_attributes": True}


class TankOut(BaseModel):
    livello_pct: float | None
    ts: datetime | None


@router.get("/zones/{zona_id}/readings", response_model=list[LetturaOut])
async def get_readings(
    zona_id: int,
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    zona = await db.get(Zona, zona_id)
    if not zona:
        raise HTTPException(status_code=404, detail="Zona non trovata")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(Lettura)
        .where(Lettura.zona_id == zona_id, Lettura.ts >= since)
        .order_by(Lettura.ts.desc())
        .limit(5000)
    )
    return result.scalars().all()


@router.get("/tank", response_model=TankOut)
async def get_tank(_: str = Depends(get_current_user)):
    return TankOut(
        livello_pct=latest_tank.get("livello"),
        ts=latest_tank.get("ts"),
    )
