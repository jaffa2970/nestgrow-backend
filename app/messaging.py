import logging
from datetime import datetime

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.licensing import get_licenza
from app.models import MessaggioCache

logger = logging.getLogger(__name__)


async def sync_messages() -> None:
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        licenza = await get_licenza(db)
        if not licenza or not licenza.piva:
            return

        headers = {}
        if licenza.jwt_token:
            headers["Authorization"] = f"Bearer {licenza.jwt_token}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{settings.license_server_url}/notifications",
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.debug("Messages sync: server returned %d", resp.status_code)
                    return
                messages = resp.json()
        except Exception as exc:
            logger.debug("Messages sync failed: %s", exc)
            return

        if not isinstance(messages, list):
            logger.debug("Messages sync: unexpected response format")
            return

        new_count = 0
        for m in messages:
            msg_id = str(m.get("id", ""))
            if not msg_id:
                continue
            existing = await db.get(MessaggioCache, msg_id)
            if not existing:
                data_raw = m.get("data_creazione") or m.get("data")
                try:
                    data_msg = datetime.fromisoformat(str(data_raw)) if data_raw else datetime.utcnow()
                except ValueError:
                    data_msg = datetime.utcnow()
                db.add(
                    MessaggioCache(
                        id=msg_id,
                        tipo=m.get("tipo", "info"),
                        titolo=m.get("titolo", ""),
                        corpo=m.get("corpo") or "",
                        data_msg=data_msg,
                        letto=m.get("letto", False),
                    )
                )
                new_count += 1

        if new_count:
            await db.commit()
            logger.info("Messages sync: %d nuovi messaggi salvati", new_count)

        result = await db.execute(
            select(MessaggioCache).where(
                MessaggioCache.letto == False,
                MessaggioCache.tipo == "critical",
            )
        )
        for msg in result.scalars().all():
            logger.warning("MESSAGGIO CRITICO non letto: %s", msg.titolo)
