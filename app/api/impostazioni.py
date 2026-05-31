import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.database import get_db
from app.models import Impostazioni, Lettura

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/impostazioni", tags=["impostazioni"])

_RETENTION_MIN = 7
_RETENTION_MAX = 365


async def get_impostazione(db: AsyncSession, chiave: str, default: str = "") -> str:
    result = await db.execute(select(Impostazioni).where(Impostazioni.chiave == chiave))
    row = result.scalar_one_or_none()
    return row.valore if row else default


class ImpostazioneUpdate(BaseModel):
    valore: str


@router.get("/")
async def list_impostazioni(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    result = await db.execute(select(Impostazioni).order_by(Impostazioni.chiave))
    rows = result.scalars().all()
    return {"impostazioni": [{"chiave": r.chiave, "valore": r.valore, "descrizione": r.descrizione} for r in rows]}


@router.put("/{chiave}")
async def update_impostazione(
    chiave: str,
    body: ImpostazioneUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    if chiave == "retention_giorni":
        try:
            v = int(body.valore)
        except ValueError:
            raise HTTPException(status_code=400, detail="Il valore deve essere un numero intero")
        if not (_RETENTION_MIN <= v <= _RETENTION_MAX):
            raise HTTPException(
                status_code=400,
                detail=f"retention_giorni deve essere tra {_RETENTION_MIN} e {_RETENTION_MAX}",
            )

    row = (await db.execute(select(Impostazioni).where(Impostazioni.chiave == chiave))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Impostazione '{chiave}' non trovata")

    row.valore = body.valore
    await db.commit()
    logger.info("Impostazione aggiornata: %s = %s", chiave, body.valore)
    return {"chiave": row.chiave, "valore": row.valore}


@router.post("/cleanup-now")
async def cleanup_now(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    retention = await get_impostazione(db, "retention_giorni", "30")
    giorni = int(retention)
    cutoff = datetime.now(timezone.utc) - timedelta(days=giorni)
    result = await db.execute(delete(Lettura).where(Lettura.ts < cutoff))
    await db.commit()
    deleted = result.rowcount
    logger.info("Cleanup manuale: eliminati %d letture più vecchie di %d giorni", deleted, giorni)
    return {"deleted": deleted, "giorni": giorni}
