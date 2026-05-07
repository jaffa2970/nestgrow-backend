from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, decode_token, verify_password
from app.database import get_db
from app.models import Utente

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Login ──────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=Token)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Utente).where(Utente.username == form.username, Utente.attivo == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": user.username, "ruolo": user.ruolo, "uid": user.id})
    return Token(access_token=token)


@router.post("/logout")
async def logout():
    return {"detail": "Logout effettuato"}


# ── Dependencies ───────────────────────────────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Returns the decoded JWT payload: {sub, ruolo, uid, exp}."""
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("ruolo") != "administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso riservato agli amministratori",
        )
    return user


async def require_user(user: dict = Depends(get_current_user)) -> dict:
    return user


# ── Change own password ────────────────────────────────────────────────────────

class ChangePasswordBody(BaseModel):
    password_attuale: str
    nuova_password: str


@router.post("/change-password")
async def change_password(
    body: ChangePasswordBody,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(body.nuova_password) < 8:
        raise HTTPException(status_code=400, detail="La nuova password deve avere almeno 8 caratteri")
    result = await db.execute(select(Utente).where(Utente.id == user["uid"]))
    utente = result.scalar_one_or_none()
    if not utente or not verify_password(body.password_attuale, utente.password_hash):
        raise HTTPException(status_code=400, detail="Password attuale non corretta")
    from app.core.security import hash_password
    utente.password_hash = hash_password(body.nuova_password)
    await db.commit()
    return {"detail": "Password aggiornata"}
