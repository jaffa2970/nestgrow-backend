import logging
from datetime import datetime, timezone
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_admin
from app.core.config import settings
from app.database import get_db
from app.licensing import (
    MACHINE_ID,
    PIANO_LIMITI_DEFAULT,
    _decode_jwt_payload,
    get_licenza,
    get_max_culle,
    poll_pending_jwt_once,
)
from app.models import Culla, LicenzaCache

logger = logging.getLogger(__name__)
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
    jwt_attivo: bool = False


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
        jwt_attivo=bool(licenza.jwt_token),
    )


# ---------- POST /license/register (PUBLIC — no auth) ----------

@router.post("/register")
async def register_license(
    payload: RegisterPayload,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    _PIANO_MAP = {"enterprise": "ai", "ultra": "ai"}
    piano_server = _PIANO_MAP.get(payload.piano, payload.piano)

    # ── Step 1: try License Server registration ──────────────────────────────
    server_ok = False
    _reg_body = {
        "prodotto_codice": "NESTGROW",
        "ragione_sociale": payload.ragione_sociale,
        "piva": payload.piva,
        "email": str(payload.email),
        "nome": "",
        "cognome": "",
        "piano": piano_server,
        "machine_id": MACHINE_ID,
        "version": "0.3.0",
    }
    logger.info("=== REGISTER PAYLOAD ===")
    logger.info("  prodotto_codice : %r", _reg_body["prodotto_codice"])
    logger.info("  ragione_sociale : %r", _reg_body["ragione_sociale"])
    logger.info("  piva            : %r  (len=%d)", _reg_body["piva"], len(_reg_body["piva"]))
    logger.info("  email           : %r", _reg_body["email"])
    logger.info("  piano           : %r  (input=%r)", _reg_body["piano"], payload.piano)
    logger.info("  machine_id      : %r", _reg_body["machine_id"])
    logger.info("  version         : %r", _reg_body["version"])
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.license_server_url}/register",
                json=_reg_body,
            )
        logger.info("=== REGISTER RESPONSE %d ===", resp.status_code)
        logger.info("Headers: %s", dict(resp.headers))
        logger.info("Body: %s", resp.text)
        if resp.status_code in (200, 201):
            server_ok = True
            logger.info("Registrazione OK sul License Server (piano=%s)", piano_server)
        elif resp.status_code == 409:
            # Already registered — still try JWT polling (might be pending)
            server_ok = True
            logger.info("Registrazione già presente sul License Server — polling JWT")
        elif resp.status_code >= 500:
            logger.error("License Server %d — body completo: %s", resp.status_code, resp.text)
            if piano_server != "free":
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            logger.warning("License Server 500 — fallback free plan")
        elif piano_server != "free":
            logger.error("License Server %d — body: %s", resp.status_code, resp.text)
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        else:
            logger.warning(
                "License Server ha rifiutato la registrazione free (%d): %s",
                resp.status_code, resp.text,
            )
    except httpx.RequestError as exc:
        if piano_server != "free":
            raise HTTPException(
                status_code=502,
                detail=f"License Server non raggiungibile: {exc}",
            )
        logger.warning("License Server non raggiungibile (offline fallback): %s", exc)

    # ── Step 2: try to collect JWT immediately ───────────────────────────────
    jwt_token: str | None = None
    piano = piano_server
    valida_fino = datetime.fromisoformat("2099-01-01T00:00:00")

    if server_ok:
        jwt_token = await poll_pending_jwt_once()
        if jwt_token:
            jwt_payload = _decode_jwt_payload(jwt_token)
            piano = jwt_payload.get("piano", piano_server)
            exp = jwt_payload.get("exp")
            if exp:
                valida_fino = datetime.fromtimestamp(exp, tz=timezone.utc)

    # ── Step 3: save / update licenza_cache ──────────────────────────────────
    existing = await get_licenza(db)
    base_values = dict(
        piano=piano,
        valida_fino=valida_fino,
        features={},
        aggiornato_il=datetime.now(timezone.utc),
        ragione_sociale=payload.ragione_sociale,
        piva=payload.piva,
        email=str(payload.email),
    )
    if jwt_token:
        base_values["jwt_token"] = jwt_token

    if existing:
        await db.execute(
            update(LicenzaCache).where(LicenzaCache.id == 1).values(**base_values)
        )
    else:
        db.add(LicenzaCache(id=1, **base_values))
    await db.commit()

    pending_approval = server_ok and jwt_token is None
    if pending_approval:
        logger.info("JWT non ancora disponibile — il background job riproverà ogni 5 min")

    return {
        "success": True,
        "piano": piano,
        "max_culle": PIANO_LIMITI_DEFAULT.get(piano, 1),
        "jwt_attivo": jwt_token is not None,
        "pending_approval": pending_approval,
    }


# ---------- GET /license/check-pending (requires auth) ──────────────────────

@router.get("/check-pending")
async def check_pending(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Manually trigger a JWT poll. Respects the server's 60s rate limit."""
    from app.licensing import poll_pending_jwt
    await poll_pending_jwt()
    licenza = await get_licenza(db)
    return {"jwt_attivo": bool(licenza and licenza.jwt_token)}


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
