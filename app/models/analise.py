import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnaliseMaterializacaoCampanha(Base):
    __tablename__ = "analise_materializacao_campanhas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="post_ingestion")
    source_execucao_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("execucoes_sincronizacao.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="pending")
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    running_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnaliseMaterializacaoControle(Base):
    __tablename__ = "analise_materializacao_controle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AnaliseMaterializacaoChunkExecucao(Base):
    __tablename__ = "analise_materializacao_chunk_execucoes"
    __table_args__ = (
        Index("ix_analise_materializacao_chunk_execucoes_campanha_status", "campanha_id", "status"),
        Index("ix_analise_materializacao_chunk_execucoes_lease_expires_at", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    campanha_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("analise_materializacao_campanhas.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="queued")
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnaliseMaterializacaoCampanhaItem(Base):
    __tablename__ = "analise_materializacao_campanha_itens"
    __table_args__ = (
        Index("ix_analise_materializacao_campanha_itens_lookup", "codigo_cvm", "escopo", "status"),
        Index("ix_analise_materializacao_campanha_itens_campanha_status", "campanha_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    campanha_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("analise_materializacao_campanhas.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    codigo_cvm: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    escopo: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="pending")
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    materializacao_execucao_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("analise_materializacao_execucoes.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    chunk_execucao_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("analise_materializacao_chunk_execucoes.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalidated_from: Mapped[date | None] = mapped_column(Date, index=True)
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnaliseMaterializacaoExecucao(Base):
    __tablename__ = "analise_materializacao_execucoes"
    __table_args__ = (
        Index("ix_analise_materializacao_execucoes_lookup", "codigo_cvm", "escopo", "calculation_version", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    codigo_cvm: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    escopo: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    coverage_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="backfill")
    materialization_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    invalidated_from: Mapped[date | None] = mapped_column(Date, index=True)
    campanha_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("analise_materializacao_campanhas.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    campanha_item_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True, nullable=True)
    chunk_execucao_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("analise_materializacao_chunk_execucoes.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    queue_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position_in_chunk: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnaliseContextoRevision(Base):
    __tablename__ = "analise_contexto_revisions"
    __table_args__ = (
        Index(
            "ix_analise_contexto_revisions_lookup",
            "codigo_cvm",
            "escopo",
            "calculation_version",
            "known_from",
            "known_to",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execucao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("analise_materializacao_execucoes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    codigo_cvm: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    escopo: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    known_from: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    known_to: Mapped[date | None] = mapped_column(Date, index=True)
    default_period_id: Mapped[str] = mapped_column(String(32), nullable=False)
    periodos_disponiveis: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    qualidade: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnaliseFatoRevision(Base):
    __tablename__ = "analise_fato_revisions"
    __table_args__ = (
        Index(
            "ix_analise_fato_revisions_lookup",
            "codigo_cvm",
            "escopo",
            "calculation_version",
            "periodicidade",
            "base_periodo",
            "metric_id",
            "known_from",
            "known_to",
        ),
        Index(
            "ix_analise_fato_revisions_period",
            "codigo_cvm",
            "escopo",
            "calculation_version",
            "period_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execucao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("analise_materializacao_execucoes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    codigo_cvm: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    escopo: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    periodicidade: Mapped[str] = mapped_column(String(20), nullable=False)
    base_periodo: Mapped[str] = mapped_column(String(20), nullable=False)
    metric_id: Mapped[str] = mapped_column(String(64), nullable=False)
    period_id: Mapped[str] = mapped_column(String(32), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    known_from: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    known_to: Mapped[date | None] = mapped_column(Date, index=True)
    observation_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    unavailable_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
