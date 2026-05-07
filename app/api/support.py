import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_admin, require_user
from app.core.config import settings
from app.database import get_db
from app.licensing import _decode_jwt_payload, get_licenza

logger = logging.getLogger(__name__)
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


def _auth_headers(jwt_token: str) -> dict:
    return {"Authorization": f"Bearer {jwt_token}"}


@router.get("/tickets")
async def list_tickets(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_user),
):
    licenza = await _get_licenza_or_fail(db)
    if not licenza.jwt_token:
        return {"jwt_pending": True, "tickets": []}

    url = f"{settings.license_server_url}/support/tickets"
    logger.info("GET tickets URL: %s", url)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=_auth_headers(licenza.jwt_token))
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"License Server non raggiungibile: {exc}")

    logger.info("GET tickets → %d  body: %s", resp.status_code, resp.text[:2000])
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    all_tickets = data if isinstance(data, list) else data.get("tickets", [])

    # Decode our own JWT to extract lid (license ID for this NestGrow installation).
    # Filter to only tickets whose licenza_id matches our license — this prevents
    # tickets from other products (MRP, Lagotto) with the same P.IVA from appearing.
    jwt_claims = _decode_jwt_payload(licenza.jwt_token)
    our_lid = jwt_claims.get("lid") or jwt_claims.get("iid")
    logger.info("GET tickets: jwt lid=%s, ticket licenza_ids=%s",
                our_lid, [t.get("licenza_id") for t in all_tickets])

    if our_lid is not None:
        tickets = [t for t in all_tickets if t.get("licenza_id") == our_lid]
        logger.info("GET tickets: filtrati %d/%d (licenza_id=%s)",
                    len(tickets), len(all_tickets), our_lid)
    else:
        # JWT doesn't have lid — can't filter precisely, return all
        tickets = all_tickets
        logger.warning("GET tickets: lid non trovato nel JWT, filtro disabilitato")

    return {"jwt_pending": False, "tickets": tickets}


@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_user),
):
    licenza = await _get_licenza_or_fail(db)
    if not licenza.jwt_token:
        raise HTTPException(status_code=400, detail="Licenza non ancora attivata")

    url = f"{settings.license_server_url}/support/tickets/{ticket_id}"
    logger.debug("GET ticket detail URL: %s", url)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=_auth_headers(licenza.jwt_token))
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"License Server non raggiungibile: {exc}")

    logger.debug("GET ticket/%d → %d  body: %s", ticket_id, resp.status_code, resp.text[:500])
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/tickets")
async def create_ticket(
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    licenza = await _get_licenza_or_fail(db)
    if not licenza.jwt_token:
        raise HTTPException(
            status_code=400,
            detail="Attivazione in corso — la licenza non è ancora stata approvata. Riprova tra qualche minuto.",
        )

    url = f"{settings.license_server_url}/support/tickets"
    body = {
        "oggetto": payload.oggetto,
        "testo": payload.testo,
        "priorita": payload.priorita or "normale",
    }
    logger.debug("POST tickets URL: %s body=%s", url, body)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=body, headers=_auth_headers(licenza.jwt_token))
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"License Server non raggiungibile: {exc}")

    logger.info("POST tickets → %d  body: %s", resp.status_code, resp.text[:300])
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()
