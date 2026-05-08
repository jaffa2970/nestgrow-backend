import asyncio
import gzip
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.params import Depends
from fastapi.responses import StreamingResponse
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
    """Dump DB, gzip to disk, return metadata. Keeps last 30 files."""
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nestgrow_backup_{timestamp}.sql.gz"
    filepath = BACKUP_DIR / filename

    sql_data = await _dump_sql()

    with gzip.open(filepath, "wb") as f:
        f.write(sql_data)

    size_bytes = filepath.stat().st_size

    existing = sorted(BACKUP_DIR.glob("nestgrow_backup_*.sql.gz"), reverse=True)
    for old in existing[30:]:
        old.unlink(missing_ok=True)

    return {"filename": filename, "size_bytes": size_bytes, "timestamp": timestamp}


async def _dump_sql() -> bytes:
    """Run mysqldump inside the container and return raw SQL bytes."""
    host, user, password, db = _parse_db_url()
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
    return stdout


def _list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    files = sorted(BACKUP_DIR.glob("nestgrow_backup_*.sql.gz"), reverse=True)
    result = []
    for f in files:
        # f.name = "nestgrow_backup_20260507_020000.sql.gz"
        # f.stem = "nestgrow_backup_20260507_020000.sql"  ← wrong, strip .sql.gz manually
        ts_raw = f.name.replace("nestgrow_backup_", "").replace(".sql.gz", "")
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


@router.get("/backup/download")
async def download_backup(_: dict = Depends(require_admin)):
    """Dump DB in memory, stream as .sql.gz — no disk write."""
    import io
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nestgrow_backup_{timestamp}.sql.gz"
    try:
        sql_data = await _dump_sql()
    except Exception as exc:
        logger.error("Download backup failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    compressed = gzip.compress(sql_data)
    return StreamingResponse(
        io.BytesIO(compressed),
        media_type="application/gzip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/restore/upload")
async def restore_from_upload(
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
):
    """Accept an uploaded .sql.gz, decompress in memory, restore to DB."""
    if not file.filename or not file.filename.endswith(".sql.gz"):
        raise HTTPException(status_code=400, detail="Il file deve essere .sql.gz")

    raw = await file.read()
    try:
        sql_data = gzip.decompress(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="File non valido o corrotto")

    host, user, password, db = _parse_db_url()
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

    logger.info("Restore da upload completato: %s", file.filename)
    return {"ok": True, "filename": file.filename}


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
