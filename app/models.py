from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PianoLimiti(Base):
    __tablename__ = "piano_limiti"

    piano: Mapped[str] = mapped_column(String(20), primary_key=True)
    max_culle: Mapped[int] = mapped_column(Integer, nullable=False)


class Pianta(Base):
    __tablename__ = "piante"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    umidita_min: Mapped[float] = mapped_column(Float, nullable=False)
    umidita_max: Mapped[float] = mapped_column(Float, nullable=False)
    durata_irrigazione_sec: Mapped[int] = mapped_column(Integer, default=30)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creato_il: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    zone: Mapped[list["Zona"]] = relationship("Zona", back_populates="pianta")


class Zona(Base):
    __tablename__ = "zone"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(50), nullable=False)
    pianta_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("piante.id"), nullable=True
    )
    attiva: Mapped[bool] = mapped_column(Boolean, default=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    creato_il: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    pianta: Mapped[Optional[Pianta]] = relationship("Pianta", back_populates="zone")
    letture: Mapped[list["Lettura"]] = relationship("Lettura", back_populates="zona")
    irrigazioni: Mapped[list["Irrigazione"]] = relationship(
        "Irrigazione", back_populates="zona"
    )


class Lettura(Base):
    __tablename__ = "letture"
    __table_args__ = (Index("idx_ts_zona", "ts", "zona_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(fsp=3), nullable=False, server_default=func.now(3))
    zona_id: Mapped[int] = mapped_column(Integer, ForeignKey("zone.id"), nullable=False)
    umidita_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    livello_serbatoio_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    zona: Mapped[Zona] = relationship("Zona", back_populates="letture")


class Irrigazione(Base):
    __tablename__ = "irrigazioni"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zona_id: Mapped[int] = mapped_column(Integer, ForeignKey("zone.id"), nullable=False)
    ts_inizio: Mapped[datetime] = mapped_column(DateTime(fsp=3), nullable=False)
    ts_fine: Mapped[Optional[datetime]] = mapped_column(DateTime(fsp=3), nullable=True)
    durata_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    umidita_pre: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    umidita_post: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trigger: Mapped[str] = mapped_column(
        Enum("ai", "manuale", "soglia"), default="soglia"
    )
    esito: Mapped[str] = mapped_column(
        Enum("ok", "serbatoio_vuoto", "timeout"), default="ok"
    )

    zona: Mapped[Zona] = relationship("Zona", back_populates="irrigazioni")


class LicenzaCache(Base):
    __tablename__ = "licenza_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    piano: Mapped[str] = mapped_column(String(20), nullable=False)
    valida_fino: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    features: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    aggiornato_il: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
