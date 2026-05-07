from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.licensing import get_licenza, get_max_culle
from app.models import Culla, Irrigazione, Lettura, Zona
from app.mqtt_client import get_client, latest_readings, latest_tank, pump_state, publish_pump_cmd

router = APIRouter(prefix="/culle", tags=["culle"])


# ---------- Pydantic schemas ----------

class CullaCreate(BaseModel):
    nome: str
    device_id: Optional[str] = None


class CullaUpdate(BaseModel):
    nome: Optional[str] = None
    device_id: Optional[str] = None
    attiva: Optional[bool] = None


class ZonaUpdate(BaseModel):
    nome: Optional[str] = None
    pianta_id: Optional[int] = None


class PumpCmd(BaseModel):
    cmd: str   # "on" | "off"
    sec: int = 30


class ZonaOut(BaseModel):
    id: int
    numero_zona: int
    nome: Optional[str]
    pianta_id: Optional[int]
    attiva: bool
    ultima_umidita: Optional[float] = None
    ultima_lettura_ts: Optional[datetime] = None
    pompa_on: bool = False

    model_config = {"from_attributes": True}


class CullaOut(BaseModel):
    id: int
    nome: str
    device_id: Optional[str]
    attiva: bool
    creato_il: datetime
    zone: list[ZonaOut] = []

    model_config = {"from_attributes": True}


class LetturaOut(BaseModel):
    id: int
    ts: datetime
    zona_id: int
    umidita_pct: Optional[float]
    livello_serbatoio_pct: Optional[float]

    model_config = {"from_attributes": True}


class TankOut(BaseModel):
    livello_pct: Optional[float]
    ts: Optional[datetime]


# ---------- Helpers ----------

def _build_zona_out(zona: Zona) -> ZonaOut:
    reading = latest_readings.get(zona.id, {})
    state = pump_state.get(zona.id, {})
    return ZonaOut(
        id=zona.id,
        numero_zona=zona.numero_zona,
        nome=zona.nome,
        pianta_id=zona.pianta_id,
        attiva=zona.attiva,
        ultima_umidita=reading.get("umidita_pct"),
        ultima_lettura_ts=reading.get("ts"),
        pompa_on=state.get("on", False),
    )


async def _load_zone(culla_id: int, db: AsyncSession) -> list[Zona]:
    result = await db.execute(
        select(Zona).where(Zona.culla_id == culla_id).order_by(Zona.numero_zona)
    )
    return result.scalars().all()


def _build_culla_out(culla: Culla, zone: list[Zona]) -> CullaOut:
    return CullaOut(
        id=culla.id,
        nome=culla.nome,
        device_id=culla.device_id,
        attiva=culla.attiva,
        creato_il=culla.creato_il,
        zone=[_build_zona_out(z) for z in zone],
    )


# ---------- Culle endpoints ----------

@router.get("/", response_model=list[CullaOut])
async def list_culle(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(
        select(Culla).where(Culla.attiva == True).order_by(Culla.id)
    )
    culle = result.scalars().all()
    out = []
    for c in culle:
        zone = await _load_zone(c.id, db)
        out.append(_build_culla_out(c, zone))
    return out


@router.post("/", response_model=CullaOut, status_code=status.HTTP_201_CREATED)
async def create_culla(
    body: CullaCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    # License enforcement
    max_culle = await get_max_culle(db)
    count_result = await db.execute(
        select(func.count()).select_from(Culla).where(Culla.attiva == True)
    )
    culle_attive = count_result.scalar_one()

    if culle_attive >= max_culle:
        licenza = await get_licenza(db)
        piano = licenza.piano if licenza else "free"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Piano {piano.capitalize()}: massimo {max_culle} "
                f"{'culla' if max_culle == 1 else 'culle'}. "
                "Aggiorna su https://license.lake8.dev"
            ),
        )

    culla = Culla(nome=body.nome, device_id=body.device_id)
    db.add(culla)
    await db.flush()  # populate culla.id before creating zones

    for num in range(1, 5):
        db.add(Zona(culla_id=culla.id, numero_zona=num))

    await db.commit()
    await db.refresh(culla)
    zone = await _load_zone(culla.id, db)
    return _build_culla_out(culla, zone)


@router.get("/{culla_id}", response_model=CullaOut)
async def get_culla(
    culla_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    culla = await db.get(Culla, culla_id)
    if not culla:
        raise HTTPException(status_code=404, detail="Culla non trovata")
    zone = await _load_zone(culla_id, db)
    return _build_culla_out(culla, zone)


@router.put("/{culla_id}", response_model=CullaOut)
async def update_culla(
    culla_id: int,
    body: CullaUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    culla = await db.get(Culla, culla_id)
    if not culla:
        raise HTTPException(status_code=404, detail="Culla non trovata")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(culla, field, value)
    await db.commit()
    await db.refresh(culla)
    zone = await _load_zone(culla_id, db)
    return _build_culla_out(culla, zone)


@router.delete("/{culla_id}")
async def delete_culla(
    culla_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    culla = await db.get(Culla, culla_id)
    if not culla:
        raise HTTPException(status_code=404, detail="Culla non trovata")
    culla.attiva = False
    await db.commit()
    return {"detail": "Culla disattivata"}


# ---------- Zone sub-resource ----------

@router.get("/{culla_id}/zone", response_model=list[ZonaOut])
async def get_zone_culla(
    culla_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    if not await db.get(Culla, culla_id):
        raise HTTPException(status_code=404, detail="Culla non trovata")
    zone = await _load_zone(culla_id, db)
    return [_build_zona_out(z) for z in zone]


@router.put("/{culla_id}/zone/{numero_zona}", response_model=ZonaOut)
async def update_zona(
    culla_id: int,
    numero_zona: int,
    body: ZonaUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(
        select(Zona).where(
            Zona.culla_id == culla_id, Zona.numero_zona == numero_zona
        )
    )
    zona = result.scalar_one_or_none()
    if not zona:
        raise HTTPException(status_code=404, detail="Zona non trovata")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(zona, field, value)
    await db.commit()
    await db.refresh(zona)
    return _build_zona_out(zona)


# ---------- Pump command ----------

@router.post("/{culla_id}/zone/{numero_zona}/pump")
async def pump_command(
    culla_id: int,
    numero_zona: int,
    body: PumpCmd,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    if body.cmd not in ("on", "off"):
        raise HTTPException(status_code=400, detail="cmd deve essere 'on' o 'off'")

    culla = await db.get(Culla, culla_id)
    if not culla or not culla.attiva:
        raise HTTPException(status_code=404, detail="Culla non trovata o non attiva")

    result = await db.execute(
        select(Zona).where(
            Zona.culla_id == culla_id, Zona.numero_zona == numero_zona
        )
    )
    zona = result.scalar_one_or_none()
    if not zona:
        raise HTTPException(status_code=404, detail="Zona non trovata")

    client = await get_client()
    if client is None:
        raise HTTPException(status_code=503, detail="MQTT non connesso")

    device_id = culla.device_id or f"culla-{culla.id}"
    await publish_pump_cmd(client, device_id, numero_zona, body.cmd, body.sec)

    if body.cmd == "on":
        db.add(
            Irrigazione(
                zona_id=zona.id,
                ts_inizio=datetime.now(timezone.utc),
                umidita_pre=latest_readings.get(zona.id, {}).get("umidita_pct"),
                trigger="manuale",
            )
        )
        await db.commit()

    return {"detail": f"Pompa culla {culla_id} zona {numero_zona} → {body.cmd}"}


# ---------- Sensors ----------

@router.get("/{culla_id}/zone/{numero_zona}/readings", response_model=list[LetturaOut])
async def get_readings(
    culla_id: int,
    numero_zona: int,
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(
        select(Zona).where(
            Zona.culla_id == culla_id, Zona.numero_zona == numero_zona
        )
    )
    zona = result.scalar_one_or_none()
    if not zona:
        raise HTTPException(status_code=404, detail="Zona non trovata")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    letture = await db.execute(
        select(Lettura)
        .where(Lettura.zona_id == zona.id, Lettura.ts >= since)
        .order_by(Lettura.ts.desc())
        .limit(5000)
    )
    return letture.scalars().all()


@router.get("/{culla_id}/serbatoio", response_model=TankOut)
async def get_serbatoio(
    culla_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    culla = await db.get(Culla, culla_id)
    if not culla:
        raise HTTPException(status_code=404, detail="Culla non trovata")
    device_id = culla.device_id or f"culla-{culla.id}"
    tank = latest_tank.get(device_id, {})
    return TankOut(livello_pct=tank.get("livello"), ts=tank.get("ts"))
