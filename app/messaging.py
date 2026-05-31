import logging
from datetime import datetime

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.licensing import MACHINE_ID, get_licenza
from app.models import MessaggioCache

logger = logging.getLogger(__name__)

_TIPO_MAP: dict[str, str] = {
    "info":           "info",
    "warning":        "warning",
    "critical":       "critical",
    "aggiornamento":  "aggiornamento",
    "comunicazione":  "info",
    "alert":          "warning",
}


async def sync_messages() -> None:
    from app.database import AsyncSessionLocal

    logger.info("=== SYNC MESSAGES START ===")

    async with AsyncSessionLocal() as db:
        licenza = await get_licenza(db)
        if not licenza or not licenza.piva:
            logger.info("SYNC MESSAGES: nessuna licenza registrata, skip")
            logger.info("=== SYNC MESSAGES END ===")
            return

        if not licenza.jwt_token:
            logger.info("SYNC MESSAGES: jwt_token assente, skip (licenza in attesa di approvazione)")
            logger.info("=== SYNC MESSAGES END ===")
            return

        url = f"{settings.license_server_url}/notifications"
        params = {"machine_id": MACHINE_ID}
        jwt_preview = licenza.jwt_token[:20] if licenza.jwt_token else ""
        logger.info("URL: %s params=%s", url, params)
        logger.info("Headers: Authorization: Bearer %s...", jwt_preview)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params, headers={"Authorization": f"Bearer {licenza.jwt_token}"})
            logger.info("Response status: %d", resp.status_code)
            logger.info("Response body: %s", resp.text[:1000])
            if resp.status_code != 200:
                logger.info("=== SYNC MESSAGES END (non-200) ===")
                return
            messages = resp.json()
        except Exception as exc:
            logger.warning("SYNC MESSAGES: request failed: %s", exc)
            logger.info("=== SYNC MESSAGES END (exception) ===")
            return

        if not isinstance(messages, list):
            logger.info("SYNC MESSAGES: risposta non è lista — type=%s value=%r", type(messages).__name__, messages)
            logger.info("=== SYNC MESSAGES END ===")
            return

        logger.info("SYNC MESSAGES: ricevuti %d messaggi dal server", len(messages))

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
                raw_tipo = m.get("tipo", "info")
                tipo = _TIPO_MAP.get(raw_tipo, "info")
                db.add(
                    MessaggioCache(
                        id=msg_id,
                        tipo=tipo,
                        titolo=m.get("titolo", ""),
                        corpo=m.get("corpo") or "",
                        data_msg=data_msg,
                        letto=m.get("letto", False),
                    )
                )
                new_count += 1

        if new_count:
            await db.commit()
            logger.info("SYNC MESSAGES: %d nuovi messaggi salvati", new_count)
        else:
            logger.info("SYNC MESSAGES: nessun nuovo messaggio")

        result = await db.execute(
            select(MessaggioCache).where(
                MessaggioCache.letto == False,
                MessaggioCache.tipo == "critical",
            )
        )
        for msg in result.scalars().all():
            logger.warning("MESSAGGIO CRITICO non letto: %s", msg.titolo)

    logger.info("=== SYNC MESSAGES END ===")
