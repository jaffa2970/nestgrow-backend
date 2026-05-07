from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.licensing import ensure_default_licenza, get_licenza, get_max_culle, heartbeat
from app.models import Zona

router = APIRouter(prefix="/license", tags=["license"])


class LicenzaOut(BaseModel):
    piano: str
    valida_fino: datetime
    features: dict | None
    aggiornato_il: datetime
    culle_usate: int
    culle_disponibili: int


class ActivateBody(BaseModel):
    jwt_token: str


@router.get("/", response_model=LicenzaOut)
async def get_license_status(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    await ensure_default_licenza(db)
    licenza = await get_licenza(db)
    max_culle = await get_max_culle(db)

    count_result = await db.execute(
        select(func.count()).select_from(Zona).where(Zona.attiva == True)
    )
    culle_usate = count_result.scalar_one()

    return LicenzaOut(
        piano=licenza.piano,
        valida_fino=licenza.valida_fino,
        features=licenza.features or {},
        aggiornato_il=licenza.aggiornato_il,
        culle_usate=culle_usate,
        culle_disponibili=max(0, max_culle - culle_usate),
    )


@router.post("/activate")
async def activate_license(
    body: ActivateBody,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await heartbeat(jwt_token=body.jwt_token)
    if result is None:
        raise HTTPException(
            status_code=502,
            detail="Impossibile contattare il License Server o licenza non valida",
        )
    return {"detail": "Licenza aggiornata", "piano": result.get("plan")}
