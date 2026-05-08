import asyncio
import gzip
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from pydantic import BaseModel

from app.api.auth import require_admin
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

BACKUP_DIR = Path("/app/backups")
_FILENAME_RE = re.compile(r"^nestgrow_backup_\d{8}_\d{6}\.sql\.gz$")


def _parse_db_url():
    url = urlparse(settings.db_url.replace("mysql+aiomysql://", "mysql://"))
    return url.hostname, url.username, url.password, url.path.lstrip("/")


async def run_backup() -> dict:
    """Core backup logic — runs mysqldump inside the container and gzips the output."""
    BACKUP_DIR.mkdir(exist_ok=True)
    host, user, password, db = _parse_db_url()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nestgrow_backup_{timestamp}.sql.gz"
    filepath = BACKUP_DIR / filename

    proc = await asyncio.create_subprocess_exec(
        "mysqldump",
        f"-h{host}",
        f"-u{user}",
        f"-p{password}",
        "--single-transaction",
        "--routines",
        "--triggers",
        db,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"mysqldump failed: {stderr.decode().strip()}")

    with gzip.open(filepath, "wb") as f:
        f.write(stdout)

    size_bytes = filepath.stat().st_size

    # Keep only the last 30 backups
    existing = sorted(BACKUP_DIR.glob("nestgrow_backup_*.sql.gz"), reverse=True)
    for old in existing[30:]:
        old.unlink(missing_ok=True)

    return {"filename": filename, "size_bytes": size_bytes, "timestamp": timestamp}


def _list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    files = sorted(BACKUP_DIR.glob("nestgrow_backup_*.sql.gz"), reverse=True)
    result = []
    for f in files:
        ts_raw = f.stem.replace("nestgrow_backup_", "")  # 20260507_020000
        try:
            dt = datetime.strptime(ts_raw, "%Y%m%d_%H%M%S")
            ts_iso = dt.isoformat()
        except ValueError:
            ts_iso = ts_raw
        result.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "timestamp": ts_iso,
        })
    return result


# ---------- Endpoints ----------

@router.get("/backup")
async def backup_now(_: dict = Depends(require_admin)):
    try:
        info = await run_backup()
        logger.info("Manual backup OK: %s (%d bytes)", info["filename"], info["size_bytes"])
        return {"ok": True, **info}
    except Exception as exc:
        logger.error("Manual backup failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/backups")
async def list_backups(_: dict = Depends(require_admin)):
    return {"backups": _list_backups()}


class RestoreBody(BaseModel):
    filename: str


@router.post("/restore")
async def restore_backup(body: RestoreBody, _: dict = Depends(require_admin)):
    if not _FILENAME_RE.match(body.filename):
        raise HTTPException(status_code=400, detail="Nome file non valido")

    filepath = BACKUP_DIR / body.filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"File non trovato: {body.filename}")

    host, user, password, db = _parse_db_url()

    try:
        with gzip.open(filepath, "rb") as f:
            sql_data = f.read()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Errore lettura backup: {exc}")

    proc = await asyncio.create_subprocess_exec(
        "mysql",
        f"-h{host}",
        f"-u{user}",
        f"-p{password}",
        db,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate(input=sql_data)

    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Restore fallito: {stderr.decode().strip()}")

    logger.info("Restore completato: %s", body.filename)
    return {"ok": True, "filename": body.filename}
