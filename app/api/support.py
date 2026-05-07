from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import settings
from app.database import get_db
from app.licensing import get_licenza

router = APIRouter(prefix="/support", tags=["support"])


class TicketCreate(BaseModel):
    oggetto: str
    testo: str
    priorita: Optional[str] = "normale"


async def _get_licenza_or_fail(db: AsyncSession):
    licenza = await get_licenza(db)
    if not licenza or not licenza.piva:
        raise HTTPException(status_code=400, detail="Licenza non registrata")
    return licenza


@router.get("/tickets")
async def list_tickets(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    licenza = await _get_licenza_or_fail(db)
    if not licenza.jwt_token:
        # JWT not yet delivered by admin — return empty list with pending flag
        return {"jwt_pending": True, "tickets": []}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{settings.license_server_url}/support/tickets",
                headers={"Authorization": f"Bearer {licenza.jwt_token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"License Server non raggiungibile: {exc}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    # Normalise: server may return a list or {"tickets": [...]}
    tickets = data if isinstance(data, list) else data.get("tickets", data)
    return {"jwt_pending": False, "tickets": tickets}


@router.post("/tickets")
async def create_ticket(
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    licenza = await _get_licenza_or_fail(db)
    if not licenza.jwt_token:
        raise HTTPException(
            status_code=400,
            detail="Attivazione in corso — la licenza non è ancora stata approvata. Riprova tra qualche minuto.",
        )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.license_server_url}/support/tickets",
                data={
                    "token": licenza.jwt_token,
                    "oggetto": payload.oggetto,
                    "testo": payload.testo,
                    "priorita": payload.priorita or "normale",
                },
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"License Server non raggiungibile: {exc}")
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()
