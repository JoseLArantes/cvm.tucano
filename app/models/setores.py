import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SetorTaxonomia(Base):
    __tablename__ = "setor_taxonomias"

    codigo: Mapped[str] = mapped_column(String(64), primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    fonte: Mapped[str] = mapped_column(String(255), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    versao_atual: Mapped[int | None] = mapped_column(Integer)
    checksum_atual: Mapped[str | None] = mapped_column(String(64))
    referencia_fonte_atual: Mapped[str | None] = mapped_column(String(255))
    publicada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alterada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SetorTaxonomiaVersao(Base):
    __tablename__ = "setor_taxonomia_versoes"
    __table_args__ = (
        UniqueConstraint("taxonomia", "versao", name="uq_setor_taxonomia_versao"),
        Index("ix_setor_taxonomia_versoes_publicada", "taxonomia", "publicada_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    taxonomia: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("setor_taxonomias.codigo", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_fonte: Mapped[str | None] = mapped_column(String(64))
    checksum_semantico: Mapped[str] = mapped_column(String(64), nullable=False)
    referencia_fonte: Mapped[str | None] = mapped_column(String(255))
    observada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resumo: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class Setor(Base):
    __tablename__ = "setores"
    __table_args__ = (
        UniqueConstraint("taxonomia", "chave_normalizada", name="uq_setores_taxonomia_chave"),
        Index("ix_setores_taxonomia_pai", "taxonomia", "setor_pai_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    taxonomia: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("setor_taxonomias.codigo", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    chave_normalizada: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    nivel: Mapped[str] = mapped_column(String(64), nullable=False, default="setor")
    setor_pai_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("setores.id", ondelete="RESTRICT"))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    alterado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SetorAlias(Base):
    __tablename__ = "setor_aliases"
    __table_args__ = (
        UniqueConstraint("taxonomia", "chave_normalizada", name="uq_setor_alias_taxonomia_chave"),
        Index("ix_setor_aliases_setor_id", "setor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    taxonomia: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    setor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("setores.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chave_normalizada: Mapped[str] = mapped_column(String(255), nullable=False)
    rotulo_origem: Mapped[str] = mapped_column(String(255), nullable=False)
    evidencias: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SetorClassificacaoCompanhia(Base):
    __tablename__ = "setor_classificacoes_companhia"
    __table_args__ = (
        Index(
            "ix_setor_classificacoes_taxonomia_setor_companhia_atual",
            "taxonomia",
            "setor_id",
            "companhia_id",
            sqlite_where=text("versao_fim IS NULL"),
            postgresql_where=text("versao_fim IS NULL"),
        ),
        Index(
            "ix_setor_classificacoes_companhia_taxonomia_atual",
            "companhia_id",
            "taxonomia",
            unique=True,
            sqlite_where=text("versao_fim IS NULL"),
            postgresql_where=text("versao_fim IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("companhias.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    taxonomia: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("setor_taxonomias.codigo", ondelete="RESTRICT"),
        nullable=False,
    )
    setor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("setores.id", ondelete="RESTRICT"), nullable=False)
    rotulo_origem: Mapped[str] = mapped_column(String(255), nullable=False)
    fonte: Mapped[str] = mapped_column(String(64), nullable=False)
    referencia_fonte: Mapped[str | None] = mapped_column(String(255))
    arquivo_origem: Mapped[str | None] = mapped_column(String(255))
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    versao_inicio: Mapped[int] = mapped_column(Integer, nullable=False)
    versao_fim: Mapped[int | None] = mapped_column(Integer)
    inicio_vigencia: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fim_vigencia: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SetorCorrespondencia(Base):
    __tablename__ = "setor_correspondencias"
    __table_args__ = (
        UniqueConstraint(
            "taxonomia_origem",
            "setor_origem_id",
            "taxonomia_destino",
            "setor_destino_id",
            "versao_mapeamento",
            name="uq_setor_correspondencia_versao",
        ),
        Index("ix_setor_correspondencias_origem", "taxonomia_origem", "setor_origem_id"),
        Index("ix_setor_correspondencias_destino", "taxonomia_destino", "setor_destino_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    taxonomia_origem: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("setor_taxonomias.codigo", ondelete="RESTRICT"),
        nullable=False,
    )
    setor_origem_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("setores.id", ondelete="RESTRICT"),
        nullable=False,
    )
    taxonomia_destino: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("setor_taxonomias.codigo", ondelete="RESTRICT"),
        nullable=False,
    )
    setor_destino_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("setores.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(32), nullable=False)
    versao_mapeamento: Mapped[int] = mapped_column(Integer, nullable=False)
    evidencias: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    justificativa: Mapped[str | None] = mapped_column(Text)
    revisado_por: Mapped[str | None] = mapped_column(String(128))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SetorTaxonomiaMudanca(Base):
    __tablename__ = "setor_taxonomia_mudancas"
    __table_args__ = (
        Index("ix_setor_taxonomia_mudancas_versao", "publicacao_id", "tipo"),
        Index("ix_setor_taxonomia_mudancas_companhia", "companhia_id", "criado_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    publicacao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("setor_taxonomia_versoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id", ondelete="SET NULL"))
    setor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("setores.id", ondelete="SET NULL"))
    antes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    depois: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
