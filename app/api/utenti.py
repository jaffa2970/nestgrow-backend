from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_admin
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.models import Utente

router = APIRouter(prefix="/utenti", tags=["utenti"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class UtenteOut(BaseModel):
    id: int
    username: str
    ruolo: str
    attivo: bool
    creato_il: Optional[datetime] = None

    class Config:
        from_attributes = True


class UtenteCreate(BaseModel):
    username: str
    password: str
    ruolo: Literal["administrator", "user"] = "user"


class UtenteUpdate(BaseModel):
    username: Optional[str] = None
    ruolo: Optional[Literal["administrator", "user"]] = None
    attivo: Optional[bool] = None


class SetPasswordBody(BaseModel):
    password_attuale: Optional[str] = None
    nuova_password: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[UtenteOut])
async def list_utenti(
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Utente).order_by(Utente.id))
    return result.scalars().all()


@router.post("/", response_model=UtenteOut, status_code=201)
async def create_utente(
    body: UtenteCreate,
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="La password deve avere almeno 8 caratteri")
    existing = await db.execute(select(Utente).where(Utente.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username già in uso")
    utente = Utente(
        username=body.username,
        password_hash=hash_password(body.password),
        ruolo=body.ruolo,
        attivo=True,
    )
    db.add(utente)
    await db.commit()
    await db.refresh(utente)
    return utente


@router.put("/{utente_id}", response_model=UtenteOut)
async def update_utente(
    utente_id: int,
    body: UtenteUpdate,
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    utente = await db.get(Utente, utente_id)
    if not utente:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    if body.username is not None:
        existing = await db.execute(
            select(Utente).where(Utente.username == body.username, Utente.id != utente_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Username già in uso")
        utente.username = body.username

    if body.ruolo is not None:
        utente.ruolo = body.ruolo

    if body.attivo is not None:
        if not body.attivo:
            # Prevent disabling the last active administrator
            count = await db.execute(
                select(func.count()).select_from(Utente).where(
                    Utente.ruolo == "administrator",
                    Utente.attivo == True,
                    Utente.id != utente_id,
                )
            )
            if count.scalar_one() == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Impossibile disattivare l'ultimo amministratore",
                )
        utente.attivo = body.attivo

    await db.commit()
    await db.refresh(utente)
    return utente


@router.delete("/{utente_id}")
async def delete_utente(
    utente_id: int,
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    utente = await db.get(Utente, utente_id)
    if not utente:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if utente.ruolo == "administrator" and utente.attivo:
        count = await db.execute(
            select(func.count()).select_from(Utente).where(
                Utente.ruolo == "administrator",
                Utente.attivo == True,
                Utente.id != utente_id,
            )
        )
        if count.scalar_one() == 0:
            raise HTTPException(
                status_code=400,
                detail="Impossibile disattivare l'ultimo amministratore",
            )
    utente.attivo = False
    await db.commit()
    return {"detail": "Utente disattivato"}


@router.post("/{utente_id}/password")
async def set_password(
    utente_id: int,
    body: SetPasswordBody,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.get("ruolo") == "administrator"
    is_self = current_user.get("uid") == utente_id

    if not is_admin and not is_self:
        raise HTTPException(status_code=403, detail="Non autorizzato")

    if len(body.nuova_password) < 8:
        raise HTTPException(status_code=400, detail="La password deve avere almeno 8 caratteri")

    utente = await db.get(Utente, utente_id)
    if not utente:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    # Changing own password always requires current password, regardless of role
    if is_self:
        if not body.password_attuale or not verify_password(body.password_attuale, utente.password_hash):
            raise HTTPException(status_code=400, detail="Password attuale non corretta")

    utente.password_hash = hash_password(body.nuova_password)
    await db.commit()
    return {"detail": "Password aggiornata"}
