import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompanhiaRegistroCvm(Base):
    __tablename__ = "companhia_registros_cvm"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True, nullable=False)
    fonte_cadastro: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    cnpj_companhia: Mapped[str | None] = mapped_column(String(14), index=True)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, index=True)
    denominacao_social: Mapped[str | None] = mapped_column(String(255))
    denominacao_comercial: Mapped[str | None] = mapped_column(String(255))
    pais_origem: Mapped[str | None] = mapped_column(String(100))
    situacao_registro: Mapped[str | None] = mapped_column(String(255))
    data_registro: Mapped[date | None] = mapped_column(Date)
    data_constituicao: Mapped[date | None] = mapped_column(Date)
    data_cancelamento: Mapped[date | None] = mapped_column(Date)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(255))
    data_inicio_situacao: Mapped[date | None] = mapped_column(Date)
    setor_atividade: Mapped[str | None] = mapped_column(String(255))
    categoria_registro: Mapped[str | None] = mapped_column(String(255))
    data_inicio_categoria: Mapped[date | None] = mapped_column(Date)
    situacao_emissor: Mapped[str | None] = mapped_column(String(255))
    data_inicio_situacao_emissor: Mapped[date | None] = mapped_column(Date)
    controle_acionario: Mapped[str | None] = mapped_column(String(255))
    endereco: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    responsavel: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    auditor: Mapped[str | None] = mapped_column(String(255))
    cnpj_auditor: Mapped[str | None] = mapped_column(String(14))
    source_ingestion_row_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("ingestion_rows.id"), index=True)
    hash_sem_mercado: Mapped[str] = mapped_column(String(64), nullable=False)
    hash_origem: Mapped[str] = mapped_column(String(64), nullable=False)
    arquivo_origem: Mapped[str] = mapped_column(String(255), nullable=False)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CompanhiaMercado(Base):
    __tablename__ = "companhia_mercados"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_registro_cvm_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companhia_registros_cvm.id"), index=True, nullable=False
    )
    tipo_mercado: Mapped[str | None] = mapped_column(String(255))
    source_ingestion_row_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("ingestion_rows.id"), index=True)
    arquivo_origem: Mapped[str] = mapped_column(String(255), nullable=False)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CompanhiaIdentificador(Base):
    __tablename__ = "companhia_identificadores"
    __table_args__ = (Index("ix_companhia_identificadores_tipo_valor_normalizado", "tipo", "valor_normalizado"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True, nullable=False)
    tipo: Mapped[str] = mapped_column(String(32), nullable=False)
    valor: Mapped[str] = mapped_column(String(255), nullable=False)
    valor_normalizado: Mapped[str] = mapped_column(String(255), nullable=False)
    fonte: Mapped[str] = mapped_column(String(64), nullable=False)
    confianca: Mapped[str] = mapped_column(String(16), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source_ingestion_row_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("ingestion_rows.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RepairRule(Base):
    __tablename__ = "repair_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    match_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    action_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
