import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Companhia(Base):
    __tablename__ = "companhias"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), unique=True, index=True)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    denominacao_social: Mapped[str | None] = mapped_column(String(255))
    denominacao_comercial: Mapped[str | None] = mapped_column(String(255))
    situacao_registro: Mapped[str | None] = mapped_column(String(255))
    data_registro: Mapped[date | None] = mapped_column(Date)
    data_constituicao: Mapped[date | None] = mapped_column(Date)
    data_cancelamento: Mapped[date | None] = mapped_column(Date)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(255))
    data_inicio_situacao: Mapped[date | None] = mapped_column(Date)
    setor_atividade: Mapped[str | None] = mapped_column(String(255))
    tipo_mercado: Mapped[str | None] = mapped_column(String(255))
    categoria_registro: Mapped[str | None] = mapped_column(String(255))
    data_inicio_categoria: Mapped[date | None] = mapped_column(Date)
    situacao_emissor: Mapped[str | None] = mapped_column(String(255))
    data_inicio_situacao_emissor: Mapped[date | None] = mapped_column(Date)
    controle_acionario: Mapped[str | None] = mapped_column(String(255))
    endereco: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    responsavel: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    auditor: Mapped[str | None] = mapped_column(String(255))
    cnpj_auditor: Mapped[str | None] = mapped_column(String(14))

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
