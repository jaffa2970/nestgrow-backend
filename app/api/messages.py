from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import settings
from app.database import get_db
from app.licensing import get_licenza
from app.models import MessaggioCache

router = APIRouter(prefix="/messages", tags=["messages"])


class MessaggioOut(BaseModel):
    id: str
    tipo: str
    titolo: str
    corpo: str
    data_msg: datetime
    letto: bool
    ricevuto_il: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[MessaggioOut])
async def list_messages(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(
        select(MessaggioCache).order_by(
            MessaggioCache.letto,           # unread first
            MessaggioCache.data_msg.desc(),
        )
    )
    return result.scalars().all()


@router.post("/{msg_id}/read")
async def mark_read(
    msg_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    msg = await db.get(MessaggioCache, msg_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Messaggio non trovato")

    msg.letto = True
    await db.commit()

    # Best-effort: notify License Server
    licenza = await get_licenza(db)
    if licenza and licenza.piva:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"{settings.license_server_url}/api/v1/messages/{msg_id}/read",
                    params={"prodotto": "nestgrow", "piva": licenza.piva},
                )
        except Exception:
            pass

    return {"detail": "ok"}
