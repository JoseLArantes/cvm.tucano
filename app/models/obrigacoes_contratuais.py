import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ObrigacaoContratualRegistro(Base):
    __tablename__ = "obrigacoes_contratuais_registros"
    __table_args__ = (
        UniqueConstraint("codigo_cvm", "tipo_registro", "registro_id", "revisao", name="uq_obrigacao_contratual_revisao"),
        Index("ix_obrigacao_contratual_corte", "codigo_cvm", "disponivel_em", "tipo_registro"),
        Index("ix_obrigacao_contratual_acordo", "codigo_cvm", "acordo_id", "disponivel_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    codigo_cvm: Mapped[int] = mapped_column(ForeignKey("companhias.codigo_cvm", ondelete="CASCADE"), index=True)
    tipo_registro: Mapped[str] = mapped_column(String(32), index=True)
    registro_id: Mapped[str] = mapped_column(String(200), index=True)
    revisao: Mapped[int] = mapped_column(Integer)
    acordo_id: Mapped[str | None] = mapped_column(String(200), index=True)
    disponivel_em: Mapped[date] = mapped_column(Date, index=True)
    efetivo_em: Mapped[date | None] = mapped_column(Date)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidencias: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    revisor_id: Mapped[str | None] = mapped_column(String(200))
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    registrado_por: Mapped[str] = mapped_column(String(200), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
