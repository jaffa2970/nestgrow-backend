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
    UniqueConstraint,
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


class Culla(Base):
    __tablename__ = "culle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    attiva: Mapped[bool] = mapped_column(Boolean, default=True)
    creato_il: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    zone: Mapped[list["Zona"]] = relationship(
        "Zona", back_populates="culla", cascade="all, delete-orphan"
    )


class Zona(Base):
    __tablename__ = "zone"
    __table_args__ = (UniqueConstraint("culla_id", "numero_zona", name="uq_culla_zona"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    culla_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("culle.id", ondelete="CASCADE"), nullable=False
    )
    numero_zona: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-4
    nome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    descrizione_coltura: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pianta_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("piante.id"), nullable=True
    )
    attiva: Mapped[bool] = mapped_column(Boolean, default=True)
    # Irrigation automation config (NULL = zone not yet configured)
    umidita_soglia_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    umidita_soglia_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    durata_irrigazione_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    irrigazione_auto: Mapped[bool] = mapped_column(Boolean, default=True)

    culla: Mapped["Culla"] = relationship("Culla", back_populates="zone")
    pianta: Mapped[Optional[Pianta]] = relationship("Pianta")
    letture: Mapped[list["Lettura"]] = relationship("Lettura", back_populates="zona")
    irrigazioni: Mapped[list["Irrigazione"]] = relationship(
        "Irrigazione", back_populates="zona"
    )


class Lettura(Base):
    __tablename__ = "letture"
    __table_args__ = (Index("idx_ts_zona", "ts", "zona_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    zona_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zone.id"), nullable=False
    )
    umidita_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    livello_serbatoio_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    zona: Mapped["Zona"] = relationship("Zona", back_populates="letture")


class Irrigazione(Base):
    __tablename__ = "irrigazioni"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zona_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zone.id"), nullable=False
    )
    ts_inizio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ts_fine: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    durata_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    umidita_pre: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    umidita_post: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trigger: Mapped[str] = mapped_column(
        Enum("ai", "manuale", "soglia"), default="soglia"
    )
    esito: Mapped[str] = mapped_column(
        Enum("ok", "serbatoio_vuoto", "timeout"), default="ok"
    )

    zona: Mapped["Zona"] = relationship("Zona", back_populates="irrigazioni")


class LicenzaCache(Base):
    __tablename__ = "licenza_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    piano: Mapped[str] = mapped_column(String(20), nullable=False)
    valida_fino: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    features: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    aggiornato_il: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    ragione_sociale: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    piva: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class MessaggioCache(Base):
    __tablename__ = "messaggi_cache"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tipo: Mapped[str] = mapped_column(
        Enum("info", "warning", "critical"), default="info"
    )
    titolo: Mapped[str] = mapped_column(String(200), nullable=False)
    corpo: Mapped[str] = mapped_column(Text, nullable=False)
    data_msg: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    letto: Mapped[bool] = mapped_column(Boolean, default=False)
    ricevuto_il: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
