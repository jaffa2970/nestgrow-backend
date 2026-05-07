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

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{settings.license_server_url}/api/v1/messages",
                    params={"prodotto": "NESTGROW", "piva": licenza.piva},
                )
                if resp.status_code != 200:
                    logger.debug("Messages sync: server returned %d", resp.status_code)
                    return
                messages = resp.json()
        except Exception as exc:
            logger.debug("Messages sync failed: %s", exc)
            return

        new_count = 0
        for m in messages:
            existing = await db.get(MessaggioCache, m["id"])
            if not existing:
                db.add(
                    MessaggioCache(
                        id=m["id"],
                        tipo=m.get("tipo", "info"),
                        titolo=m["titolo"],
                        corpo=m["corpo"],
                        data_msg=datetime.fromisoformat(m["data"]),
                        letto=m.get("letto", False),
                    )
                )
                new_count += 1

        if new_count:
            await db.commit()
            logger.info("Messages sync: %d nuovi messaggi salvati", new_count)

        # Warn on unread criticals
        result = await db.execute(
            select(MessaggioCache).where(
                MessaggioCache.letto == False,
                MessaggioCache.tipo == "critical",
            )
        )
        for msg in result.scalars().all():
            logger.warning("MESSAGGIO CRITICO non letto: %s", msg.titolo)
