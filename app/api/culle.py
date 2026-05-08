from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin, require_user
from app.database import get_db
from app.licensing import get_licenza, get_max_culle
from app.models import Culla, Irrigazione, Lettura, Zona
from app.mqtt_client import get_client, latest_readings, latest_tank, pump_state, publish_pump_cmd
import json
import logging

logger = logging.getLogger(__name__)

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
    descrizione_coltura: Optional[str] = None
    pianta_id: Optional[int] = None
    umidita_soglia_min: Optional[float] = None
    umidita_soglia_max: Optional[float] = None
    durata_irrigazione_sec: Optional[int] = None
    irrigazione_auto: Optional[bool] = None
    intervallo_lettura_sec: Optional[int] = None


class PumpCmd(BaseModel):
    cmd: str   # "on" | "off"
    sec: int = 30


class ZonaOut(BaseModel):
    id: int
    numero_zona: int
    nome: Optional[str]
    descrizione_coltura: Optional[str] = None
    pianta_id: Optional[int]
    attiva: bool
    umidita_soglia_min: Optional[float] = None
    umidita_soglia_max: Optional[float] = None
    durata_irrigazione_sec: Optional[int] = None
    irrigazione_auto: bool = True
    intervallo_lettura_sec: int = 60
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

def _is_pump_on(zona_id: int) -> bool:
    state = pump_state.get(zona_id, {})
    if not state.get("on"):
        return False
    # Auto-expire: if we passed expires_at the device has finished
    expires_at = state.get("expires_at")
    if expires_at and datetime.now(timezone.utc) > expires_at:
        return False
    return True


async def _get_latest_db_readings(
    db: AsyncSession, zone_ids: list[int]
) -> dict[int, dict]:
    """Query letture for the most recent row per zona_id (single round-trip)."""
    if not zone_ids:
        return {}
    subq = (
        select(Lettura.zona_id, func.max(Lettura.ts).label("max_ts"))
        .where(Lettura.zona_id.in_(zone_ids))
        .group_by(Lettura.zona_id)
        .subquery()
    )
    rows = await db.execute(
        select(Lettura).join(
            subq,
            (Lettura.zona_id == subq.c.zona_id) & (Lettura.ts == subq.c.max_ts),
        )
    )
    result: dict[int, dict] = {}
    for row in rows.scalars().all():
        result[row.zona_id] = {
            "umidita_pct": row.umidita_pct,
            "ts": row.ts,
        }
    return result


def _build_zona_out(zona: Zona, db_reading: dict | None = None) -> ZonaOut:
    # In-memory (live MQTT) takes priority; fall back to latest DB row
    reading = latest_readings.get(zona.id) or db_reading or {}
    return ZonaOut(
        id=zona.id,
        numero_zona=zona.numero_zona,
        nome=zona.nome,
        descrizione_coltura=zona.descrizione_coltura,
        pianta_id=zona.pianta_id,
        attiva=zona.attiva,
        umidita_soglia_min=zona.umidita_soglia_min,
        umidita_soglia_max=zona.umidita_soglia_max,
        durata_irrigazione_sec=zona.durata_irrigazione_sec,
        irrigazione_auto=zona.irrigazione_auto,
        intervallo_lettura_sec=zona.intervallo_lettura_sec,
        ultima_umidita=reading.get("umidita_pct"),
        ultima_lettura_ts=reading.get("ts"),
        pompa_on=_is_pump_on(zona.id),
    )


async def _load_zone(culla_id: int, db: AsyncSession) -> list[Zona]:
    result = await db.execute(
        select(Zona).where(Zona.culla_id == culla_id).order_by(Zona.numero_zona)
    )
    return result.scalars().all()


def _build_culla_out(
    culla: Culla, zone: list[Zona], db_readings: dict[int, dict] | None = None
) -> CullaOut:
    return CullaOut(
        id=culla.id,
        nome=culla.nome,
        device_id=culla.device_id,
        attiva=culla.attiva,
        creato_il=culla.creato_il,
        zone=[_build_zona_out(z, (db_readings or {}).get(z.id)) for z in zone],
    )


# ---------- Culle endpoints ----------

@router.get("/", response_model=list[CullaOut])
async def list_culle(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_user),
):
    result = await db.execute(
        select(Culla).where(Culla.attiva == True).order_by(Culla.id)
    )
    culle = result.scalars().all()
    zones_map: dict[int, list[Zona]] = {}
    for c in culle:
        zones_map[c.id] = await _load_zone(c.id, db)
    all_zone_ids = [z.id for zones in zones_map.values() for z in zones]
    db_readings = await _get_latest_db_readings(db, all_zone_ids)
    return [_build_culla_out(c, zones_map[c.id], db_readings) for c in culle]


@router.post("/", response_model=CullaOut, status_code=status.HTTP_201_CREATED)
async def create_culla(
    body: CullaCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
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
    # Invalidate device cache so new culla/zones are visible to mqtt_client
    from app.mqtt_client import _refresh_device_cache
    await _refresh_device_cache()
    zone = await _load_zone(culla.id, db)
    # No DB readings for a brand-new culla — pass empty dict
    return _build_culla_out(culla, zone, {})


@router.get("/{culla_id}", response_model=CullaOut)
async def get_culla(
    culla_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_user),
):
    culla = await db.get(Culla, culla_id)
    if not culla:
        raise HTTPException(status_code=404, detail="Culla non trovata")
    zone = await _load_zone(culla_id, db)
    db_readings = await _get_latest_db_readings(db, [z.id for z in zone])
    return _build_culla_out(culla, zone, db_readings)


@router.put("/{culla_id}", response_model=CullaOut)
async def update_culla(
    culla_id: int,
    body: CullaUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    culla = await db.get(Culla, culla_id)
    if not culla:
        raise HTTPException(status_code=404, detail="Culla non trovata")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(culla, field, value)
    await db.commit()
    await db.refresh(culla)
    zone = await _load_zone(culla_id, db)
    db_readings = await _get_latest_db_readings(db, [z.id for z in zone])
    return _build_culla_out(culla, zone, db_readings)


@router.delete("/{culla_id}")
async def delete_culla(
    culla_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
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
    _: dict = Depends(require_user),
):
    if not await db.get(Culla, culla_id):
        raise HTTPException(status_code=404, detail="Culla non trovata")
    zone = await _load_zone(culla_id, db)
    db_readings = await _get_latest_db_readings(db, [z.id for z in zone])
    return [_build_zona_out(z, db_readings.get(z.id)) for z in zone]


@router.put("/{culla_id}/zone/{numero_zona}", response_model=ZonaOut)
async def update_zona(
    culla_id: int,
    numero_zona: int,
    body: ZonaUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    result = await db.execute(
        select(Zona).where(
            Zona.culla_id == culla_id, Zona.numero_zona == numero_zona
        )
    )
    zona = result.scalar_one_or_none()
    if not zona:
        raise HTTPException(status_code=404, detail="Zona non trovata")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(zona, field, value)
    await db.commit()
    await db.refresh(zona)

    culla = await db.get(Culla, culla_id)
    if culla and culla.device_id:
        client = await get_client()
        if client is not None:
            logger.info("Intervallo ricevuto: %ss", zona.intervallo_lettura_sec)
            logger.info("MQTT intervallo_ms: %s", zona.intervallo_lettura_sec * 1000)
            topic = f"nestgrow/{culla.device_id}/cmd/config"
            payload = {
                "zona": numero_zona,
                "intervallo_ms": zona.intervallo_lettura_sec * 1000,
                "salva_nvs": True,
            }
            await client.publish(topic, json.dumps(payload))
            logger.info("MQTT config → %s: %s", topic, payload)

    return _build_zona_out(zona)


# ---------- Pump command ----------

@router.post("/{culla_id}/zone/{numero_zona}/pump")
async def pump_command(
    culla_id: int,
    numero_zona: int,
    body: PumpCmd,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
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

    # Keep pump_state in sync directly — publish_pump_cmd may miss it if device
    # cache hasn't refreshed yet (e.g. culla created after last cache refresh).
    now = datetime.now(timezone.utc)
    if body.cmd == "on":
        pump_state[zona.id] = {
            "on": True,
            "since": now,
            "expires_at": now + timedelta(seconds=body.sec + 5),
        }
        db.add(
            Irrigazione(
                zona_id=zona.id,
                ts_inizio=now,
                umidita_pre=latest_readings.get(zona.id, {}).get("umidita_pct"),
                trigger="manuale",
            )
        )
        await db.commit()
    else:
        pump_state[zona.id] = {"on": False, "since": None, "expires_at": None}

    return {"detail": f"Pompa culla {culla_id} zona {numero_zona} → {body.cmd}"}


# ---------- Sensors ----------

# ---------- Stats / Grafici ----------

@router.get("/{culla_id}/stats/irrigazioni")
async def get_culla_stats_irrigazioni(
    culla_id: int,
    giorni: int = 30,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_user),
):
    culla = await db.get(Culla, culla_id)
    if not culla or not culla.attiva:
        raise HTTPException(status_code=404, detail="Culla non trovata")

    zone = await _load_zone(culla_id, db)
    since = datetime.now(timezone.utc) - timedelta(days=giorni)

    per_zona = []
    for zona in zone:
        row = (await db.execute(
            select(
                func.count(Irrigazione.id).label("totale"),
                func.avg(Irrigazione.durata_sec).label("durata_media"),
                func.avg(Irrigazione.umidita_pre).label("umidita_media_pre"),
                func.avg(Irrigazione.umidita_post).label("umidita_media_post"),
            )
            .where(
                Irrigazione.zona_id == zona.id,
                Irrigazione.ts_inizio >= since,
            )
        )).one()
        per_zona.append({
            "zona": zona.numero_zona,
            "nome": zona.nome or f"Zona {zona.numero_zona}",
            "totale_irrigazioni": row.totale or 0,
            "durata_media_sec": round(float(row.durata_media), 1) if row.durata_media else 0.0,
            "umidita_media_pre": round(float(row.umidita_media_pre), 1) if row.umidita_media_pre else None,
            "umidita_media_post": round(float(row.umidita_media_post), 1) if row.umidita_media_post else None,
        })

    return {"per_zona": per_zona}


@router.get("/{culla_id}/stats")
async def get_culla_stats(
    culla_id: int,
    giorni: int = 7,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_user),
):
    culla = await db.get(Culla, culla_id)
    if not culla or not culla.attiva:
        raise HTTPException(status_code=404, detail="Culla non trovata")

    zone = await _load_zone(culla_id, db)
    zone_ids = [z.id for z in zone]
    since = datetime.now(timezone.utc) - timedelta(days=giorni)

    def _bucket(col):
        return func.from_unixtime(func.floor(func.unix_timestamp(col) / 900) * 900)

    zona_umidita = []
    for zona in zone:
        bucket = _bucket(Lettura.ts)
        rows = await db.execute(
            select(bucket.label("ts_bucket"), func.avg(Lettura.umidita_pct).label("v"))
            .where(
                Lettura.zona_id == zona.id,
                Lettura.ts >= since,
                Lettura.umidita_pct.is_not(None),
            )
            .group_by(bucket)
            .order_by(bucket)
        )
        dati = []
        for row in rows.all():
            if row.v is not None and row.ts_bucket is not None:
                ts_str = row.ts_bucket.isoformat() if hasattr(row.ts_bucket, "isoformat") else str(row.ts_bucket)
                dati.append({"ts": ts_str, "v": round(float(row.v), 1)})
        zona_umidita.append({
            "zona": zona.numero_zona,
            "zona_id": zona.id,
            "nome": zona.nome or f"Zona {zona.numero_zona}",
            "coltura": zona.descrizione_coltura or "",
            "umidita_soglia_min": zona.umidita_soglia_min,
            "umidita_soglia_max": zona.umidita_soglia_max,
            "dati": dati,
        })

    irr_result = await db.execute(
        select(Irrigazione, Zona.numero_zona)
        .join(Zona, Zona.id == Irrigazione.zona_id)
        .where(
            Irrigazione.zona_id.in_(zone_ids),
            Irrigazione.ts_inizio >= since,
        )
        .order_by(Irrigazione.ts_inizio)
    )
    irrigazioni = []
    for irr, num_zona in irr_result.all():
        irrigazioni.append({
            "zona": num_zona,
            "ts_inizio": irr.ts_inizio.isoformat(),
            "durata_sec": irr.durata_sec,
            "umidita_pre": irr.umidita_pre,
            "umidita_post": irr.umidita_post,
            "trigger": irr.trigger,
        })

    bucket = _bucket(Lettura.ts)
    serb_result = await db.execute(
        select(bucket.label("ts_bucket"), func.avg(Lettura.livello_serbatoio_pct).label("v"))
        .where(
            Lettura.zona_id.in_(zone_ids),
            Lettura.ts >= since,
            Lettura.livello_serbatoio_pct.is_not(None),
        )
        .group_by(bucket)
        .order_by(bucket)
    )
    serbatoio = []
    for row in serb_result.all():
        if row.v is not None and row.ts_bucket is not None:
            ts_str = row.ts_bucket.isoformat() if hasattr(row.ts_bucket, "isoformat") else str(row.ts_bucket)
            serbatoio.append({"ts": ts_str, "v": round(float(row.v), 1)})

    return {
        "zona_umidita": zona_umidita,
        "irrigazioni": irrigazioni,
        "serbatoio": serbatoio,
    }


@router.get("/{culla_id}/zone/{numero_zona}/readings", response_model=list[LetturaOut])
async def get_readings(
    culla_id: int,
    numero_zona: int,
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_user),
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
    _: dict = Depends(require_user),
):
    culla = await db.get(Culla, culla_id)
    if not culla:
        raise HTTPException(status_code=404, detail="Culla non trovata")
    device_id = culla.device_id or f"culla-{culla.id}"
    tank = latest_tank.get(device_id, {})
    return TankOut(livello_pct=tank.get("livello"), ts=tank.get("ts"))
