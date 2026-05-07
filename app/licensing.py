import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import LicenzaCache, PianoLimiti

logger = logging.getLogger(__name__)

PIANO_LIMITI_DEFAULT = {
    "free": 1,
    "pro": 5,
    "enterprise": 20,
    "ultra": 9999,
}


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


async def heartbeat(jwt_token: str | None = None) -> dict | None:
    from app.database import AsyncSessionLocal

    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.license_server_url}/api/v1/heartbeat",
                headers=headers,
                params={"product": "NESTGROW"},
            )
            if resp.status_code == 200:
                data = resp.json()
                async with AsyncSessionLocal() as db:
                    existing = await get_licenza(db)
                    valida_fino = datetime.fromisoformat(
                        data.get("valid_until", "2099-01-01T00:00:00")
                    )
                    if existing:
                        await db.execute(
                            update(LicenzaCache)
                            .where(LicenzaCache.id == 1)
                            .values(
                                piano=data.get("plan", "free"),
                                valida_fino=valida_fino,
                                features=data.get("features", {}),
                                aggiornato_il=datetime.now(timezone.utc),
                            )
                        )
                        await db.commit()
                return data
            logger.warning("License heartbeat returned %d", resp.status_code)
    except Exception as exc:
        logger.warning("License heartbeat failed: %s", exc)
    return None
