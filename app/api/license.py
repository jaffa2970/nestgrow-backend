from datetime import datetime, timezone
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import settings
from app.database import get_db
from app.licensing import PIANO_LIMITI_DEFAULT, get_licenza, get_max_culle
from app.models import Culla, LicenzaCache

router = APIRouter(prefix="/license", tags=["license"])


# ---------- Schemas ----------

class LicenzaOut(BaseModel):
    registrato: bool
    piano: Optional[str] = None
    valida_fino: Optional[datetime] = None
    features: Optional[dict] = None
    aggiornato_il: Optional[datetime] = None
    culle_usate: int = 0
    culle_disponibili: int = 0
    max_culle: int = 0
    ragione_sociale: Optional[str] = None
    piva: Optional[str] = None
    email: Optional[str] = None


class RegisterPayload(BaseModel):
    ragione_sociale: str
    piva: str
    email: EmailStr
    piano: Literal["free", "pro", "enterprise", "ultra", "ai"]
    tos_accettato: bool

    @field_validator("tos_accettato")
    @classmethod
    def must_accept(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Devi accettare i Termini di Servizio")
        return v

    @field_validator("piva")
    @classmethod
    def validate_piva(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) == 11 and v.isdigit():
            return v          # P.IVA
        if len(v) == 16 and v.isalnum():
            return v          # Codice Fiscale
        raise ValueError(
            "Inserisci una P.IVA valida (11 cifre) "
            "o un Codice Fiscale valido (16 caratteri alfanumerici)"
        )


class ActivateBody(BaseModel):
    jwt_token: str


# ---------- GET /license (requires auth) ----------

@router.get("/", response_model=LicenzaOut)
async def get_license_status(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    licenza = await get_licenza(db)
    if not licenza:
        return LicenzaOut(registrato=False)

    max_culle = await get_max_culle(db)
    count_result = await db.execute(
        select(func.count()).select_from(Culla).where(Culla.attiva == True)
    )
    culle_usate = count_result.scalar_one()

    return LicenzaOut(
        registrato=True,
        piano=licenza.piano,
        valida_fino=licenza.valida_fino,
        features=licenza.features or {},
        aggiornato_il=licenza.aggiornato_il,
        culle_usate=culle_usate,
        culle_disponibili=max(0, max_culle - culle_usate),
        max_culle=max_culle,
        ragione_sociale=licenza.ragione_sociale,
        piva=licenza.piva,
        email=licenza.email,
    )


# ---------- POST /license/register (PUBLIC — no auth) ----------

@router.post("/register")
async def register_license(
    payload: RegisterPayload,
    db: AsyncSession = Depends(get_db),
):
    # enterprise and ultra both map to the "ai" plan on the License Server
    _PIANO_MAP = {"enterprise": "ai", "ultra": "ai"}
    piano_server = _PIANO_MAP.get(payload.piano, payload.piano)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.license_server_url}/register",
                json={
                    "prodotto_codice": "NESTGROW",
                    "ragione_sociale": payload.ragione_sociale,
                    "piva": payload.piva,
                    "email": str(payload.email),
                    "nome": "",
                    "cognome": "",
                    "piano": piano_server,
                    "machine_id": "nestgrow-server",
                    "version": "0.3.0",
                },
            )
    except httpx.RequestError as exc:
        if piano_server == "free":
            data = {"plan": "free", "valid_until": "2099-01-01T00:00:00", "features": {}}
        else:
            raise HTTPException(
                status_code=502,
                detail=f"License Server non raggiungibile: {exc}",
            )
    else:
        if resp.status_code not in (200, 201):
            if piano_server == "free":
                data = {"plan": "free", "valid_until": "2099-01-01T00:00:00", "features": {}}
            else:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
        else:
            data = resp.json()

    valida_fino = datetime.fromisoformat(
        data.get("valid_until", "2099-01-01T00:00:00")
    )
    piano = data.get("plan", payload.piano)

    jwt_token = data.get("jwt_token") or data.get("token")

    existing = await get_licenza(db)
    if existing:
        values = dict(
            piano=piano,
            valida_fino=valida_fino,
            features=data.get("features", {}),
            aggiornato_il=datetime.now(timezone.utc),
            ragione_sociale=payload.ragione_sociale,
            piva=payload.piva,
            email=str(payload.email),
        )
        if jwt_token:
            values["jwt_token"] = jwt_token
        await db.execute(
            update(LicenzaCache).where(LicenzaCache.id == 1).values(**values)
        )
    else:
        db.add(
            LicenzaCache(
                id=1,
                piano=piano,
                valida_fino=valida_fino,
                features=data.get("features", {}),
                ragione_sociale=payload.ragione_sociale,
                piva=payload.piva,
                email=str(payload.email),
                jwt_token=jwt_token,
            )
        )
    await db.commit()

    return {
        "success": True,
        "piano": piano,
        "max_culle": PIANO_LIMITI_DEFAULT.get(piano, 1),
    }


# ---------- POST /license/activate (requires auth) ----------

@router.post("/activate")
async def activate_license(
    body: ActivateBody,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    from app.licensing import heartbeat
    result = await heartbeat(jwt_token=body.jwt_token)
    if result is None:
        raise HTTPException(
            status_code=502,
            detail="Impossibile contattare il License Server o licenza non valida",
        )
    return {"detail": "Licenza aggiornata", "piano": result.get("plan")}
