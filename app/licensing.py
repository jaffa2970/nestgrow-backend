import base64
import json as _stdlib_json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import LicenzaCache, PianoLimiti

logger = logging.getLogger(__name__)

MACHINE_ID = "nestgrow-server"

PIANO_LIMITI_DEFAULT = {
    "free": 1,
    "pro": 5,
    "ai": 10,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without signature verification."""
    try:
        parts = token.split(".")
        pad = parts[1] + "=" * (-len(parts[1]) % 4)
        return _stdlib_json.loads(base64.urlsafe_b64decode(pad))
    except Exception:
        return {}


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def get_licenza(db: AsyncSession) -> LicenzaCache | None:
    result = await db.execute(select(LicenzaCache).where(LicenzaCache.id == 1))
    return result.scalar_one_or_none()


async def get_max_culle(db: AsyncSession) -> int:
    licenza = await get_licenza(db)
    if not licenza:
        return PIANO_LIMITI_DEFAULT["free"]
    result = await db.execute(
        select(PianoLimiti).where(PianoLimiti.piano == licenza.piano)
    )
    piano = result.scalar_one_or_none()
    return piano.max_culle if piano else PIANO_LIMITI_DEFAULT.get(licenza.piano, 1)


# ── JWT polling ────────────────────────────────────────────────────────────────

async def poll_pending_jwt_once() -> str | None:
    """Call /license/pending ONCE. Returns raw JWT string if delivered, else None.

    The License Server enforces a 60-second rate limit per machine_id, so this
    must NOT be called in a tight loop. Use poll_pending_jwt() from APScheduler.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{settings.license_server_url}/license/pending",
                params={"machine_id": MACHINE_ID, "product": "NESTGROW"},
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("trovato") and data.get("token"):
                    token = data["token"]
                    logger.info("JWT ricevuto dal License Server (piano=%s)", data.get("piano"))
                    # Acknowledge delivery
                    try:
                        await client.post(
                            f"{settings.license_server_url}/license/delivered",
                            json={"machine_id": MACHINE_ID, "product": "NESTGROW"},
                            timeout=5,
                        )
                    except Exception:
                        pass
                    return token
                logger.debug("poll_pending_jwt_once: trovato=False (approvazione admin in corso)")
            elif r.status_code == 429:
                logger.debug("poll_pending_jwt_once: rate limited (60s cooldown)")
            else:
                logger.debug("poll_pending_jwt_once: status=%d", r.status_code)
    except Exception as exc:
        logger.debug("poll_pending_jwt_once error: %s", exc)
    return None


async def poll_pending_jwt() -> None:
    """APScheduler job: poll /license/pending every 5 min until JWT arrives.

    Respects the server's 60-second rate limit (called at most once per run).
    Skips silently if a JWT is already stored.
    """
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        existing = await get_licenza(db)
        if not existing or existing.jwt_token or not existing.piva:
            return  # Nothing to do

    token = await poll_pending_jwt_once()
    if not token:
        return

    payload = _decode_jwt_payload(token)
    piano = payload.get("piano", "free")
    exp = payload.get("exp")
    valida_fino = (
        datetime.fromtimestamp(exp, tz=timezone.utc)
        if exp
        else datetime.fromisoformat("2099-01-01T00:00:00")
    )

    async with AsyncSessionLocal() as db:
        existing = await get_licenza(db)
        if existing and not existing.jwt_token:
            await db.execute(
                update(LicenzaCache)
                .where(LicenzaCache.id == 1)
                .values(
                    jwt_token=token,
                    piano=piano,
                    valida_fino=valida_fino,
                    aggiornato_il=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.info("JWT salvato in background (piano=%s)", piano)


# ── Heartbeat ──────────────────────────────────────────────────────────────────

async def heartbeat(jwt_token: str | None = None) -> dict | None:
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        existing = await get_licenza(db)
        token = jwt_token or (existing.jwt_token if existing else None)
        if not token:
            logger.debug("Heartbeat skipped: no JWT token available")
            return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.license_server_url}/heartbeat",
                json={
                    "token": token,
                    "prodotto_codice": "NESTGROW",
                    "sessioni_attive": 0,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                async with AsyncSessionLocal() as db:
                    existing = await get_licenza(db)
                    if existing:
                        await db.execute(
                            update(LicenzaCache)
                            .where(LicenzaCache.id == 1)
                            .values(
                                aggiornato_il=datetime.now(timezone.utc),
                            )
                        )
                        await db.commit()
                return data
            logger.warning("License heartbeat returned %d", resp.status_code)
    except Exception as exc:
        logger.warning("License heartbeat failed: %s", exc)
    return None
