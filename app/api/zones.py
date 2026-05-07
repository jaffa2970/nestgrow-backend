from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.database import get_db
from app.licensing import get_licenza, get_max_culle
from app.models import Lettura, Zona
from app.mqtt_client import latest_readings, pump_state

router = APIRouter(prefix="/zones", tags=["zones"])


class ZonaCreate(BaseModel):
    id: int
    nome: str
    pianta_id: Optional[int] = None
    device_id: Optional[str] = None


class ZonaUpdate(BaseModel):
    nome: Optional[str] = None
    pianta_id: Optional[int] = None
    device_id: Optional[str] = None
    attiva: Optional[bool] = None


class ZonaOut(BaseModel):
    id: int
    nome: str
    pianta_id: Optional[int]
    attiva: bool
    device_id: Optional[str]
    creato_il: datetime
    ultima_umidita: Optional[float] = None
    ultima_lettura_ts: Optional[datetime] = None
    pompa_on: bool = False

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[ZonaOut])
async def list_zones(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(
        select(Zona).where(Zona.attiva == True).order_by(Zona.id)
    )
    zone = result.scalars().all()
    out = []
    for z in zone:
        reading = latest_readings.get(z.id, {})
        state = pump_state.get(z.id, {})
        out.append(
            ZonaOut(
                id=z.id,
                nome=z.nome,
                pianta_id=z.pianta_id,
                attiva=z.attiva,
                device_id=z.device_id,
                creato_il=z.creato_il,
                ultima_umidita=reading.get("umidita_pct"),
                ultima_lettura_ts=reading.get("ts"),
                pompa_on=state.get("on", False),
            )
        )
    return out


@router.post("/", response_model=ZonaOut, status_code=status.HTTP_201_CREATED)
async def create_zone(
    body: ZonaCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    # License check
    max_culle = await get_max_culle(db)
    count_result = await db.execute(
        select(func.count()).select_from(Zona).where(Zona.attiva == True)
    )
    zone_attive = count_result.scalar_one()

    if zone_attive >= max_culle:
        licenza = await get_licenza(db)
        piano = licenza.piano if licenza else "free"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Piano {piano.capitalize()}: massimo {max_culle} "
                f"{'culla' if max_culle == 1 else 'culle'}. "
                "Aggiorna su https://nestgrow.lake8.dev"
            ),
        )

    # Check duplicate ID
    existing = await db.get(Zona, body.id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Zona con id {body.id} già esistente")

    zona = Zona(
        id=body.id,
        nome=body.nome,
        pianta_id=body.pianta_id,
        device_id=body.device_id,
    )
    db.add(zona)
    await db.commit()
    await db.refresh(zona)
    return ZonaOut(
        id=zona.id,
        nome=zona.nome,
        pianta_id=zona.pianta_id,
        attiva=zona.attiva,
        device_id=zona.device_id,
        creato_il=zona.creato_il,
    )


@router.get("/{zona_id}", response_model=ZonaOut)
async def get_zone(
    zona_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    zona = await db.get(Zona, zona_id)
    if not zona:
        raise HTTPException(status_code=404, detail="Zona non trovata")
    reading = latest_readings.get(zona_id, {})
    state = pump_state.get(zona_id, {})
    return ZonaOut(
        id=zona.id,
        nome=zona.nome,
        pianta_id=zona.pianta_id,
        attiva=zona.attiva,
        device_id=zona.device_id,
        creato_il=zona.creato_il,
        ultima_umidita=reading.get("umidita_pct"),
        ultima_lettura_ts=reading.get("ts"),
        pompa_on=state.get("on", False),
    )


@router.put("/{zona_id}", response_model=ZonaOut)
async def update_zone(
    zona_id: int,
    body: ZonaUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    zona = await db.get(Zona, zona_id)
    if not zona:
        raise HTTPException(status_code=404, detail="Zona non trovata")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(zona, field, value)
    await db.commit()
    await db.refresh(zona)
    return ZonaOut(
        id=zona.id,
        nome=zona.nome,
        pianta_id=zona.pianta_id,
        attiva=zona.attiva,
        device_id=zona.device_id,
        creato_il=zona.creato_il,
    )


@router.delete("/{zona_id}")
async def delete_zone(
    zona_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    zona = await db.get(Zona, zona_id)
    if not zona:
        raise HTTPException(status_code=404, detail="Zona non trovata")
    zona.attiva = False
    await db.commit()
    return {"detail": "Zona disattivata"}
