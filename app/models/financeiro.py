import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentoFinanceiro(Base):
    __tablename__ = "documentos_financeiros"
    __table_args__ = (
        UniqueConstraint(
            "tipo_formulario",
            "id_documento",
            "versao",
            "data_referencia",
            name="uq_documentos_financeiros_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    tipo_formulario: Mapped[str] = mapped_column(String(10), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    denominacao_companhia: Mapped[str | None] = mapped_column(String(255))
    categoria_documento: Mapped[str | None] = mapped_column(String(255))
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    data_recebimento: Mapped[date | None] = mapped_column(Date)
    link_documento: Mapped[str | None] = mapped_column(String(1000))

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    alterado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class DemonstracaoFinanceira(Base):
    __tablename__ = "demonstracoes_financeiras"
    __table_args__ = (
        UniqueConstraint(
            "tipo_formulario",
            "tipo_demonstracao",
            "escopo_demonstracao",
            "cnpj_companhia",
            "data_referencia",
            "versao",
            "grupo_demonstracao",
            "ordem_exercicio",
            "data_inicio_exercicio",
            "data_fim_exercicio",
            "codigo_conta",
            "coluna_df",
            name="uq_demonstracoes_financeiras_chave_natural",
        ),
        Index(
            "ix_demonstracoes_financeiras_lineage_scope_hash",
            "arquivo_origem",
            "ano_origem",
            "hash_origem",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    tipo_formulario: Mapped[str] = mapped_column(String(10), index=True)
    tipo_demonstracao: Mapped[str] = mapped_column(String(80), index=True)
    escopo_demonstracao: Mapped[str] = mapped_column(String(20), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    denominacao_companhia: Mapped[str | None] = mapped_column(String(255))
    grupo_demonstracao: Mapped[str | None] = mapped_column(String(255))
    moeda: Mapped[str | None] = mapped_column(String(20))
    escala_moeda: Mapped[str | None] = mapped_column(String(50))
    ordem_exercicio: Mapped[str | None] = mapped_column(String(20))
    data_inicio_exercicio: Mapped[date | None] = mapped_column(Date)
    data_fim_exercicio: Mapped[date | None] = mapped_column(Date)
    codigo_conta: Mapped[str | None] = mapped_column(String(40), index=True)
    coluna_df: Mapped[str] = mapped_column(Text, nullable=False, default="")
    descricao_conta: Mapped[str | None] = mapped_column(Text)
    valor_conta: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    conta_fixa: Mapped[bool | None] = mapped_column(Boolean)

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    alterado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ComposicaoCapital(Base):
    __tablename__ = "composicoes_capital"
    __table_args__ = (
        UniqueConstraint(
            "tipo_formulario",
            "cnpj_companhia",
            "data_referencia",
            "versao",
            name="uq_composicoes_capital_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    tipo_formulario: Mapped[str] = mapped_column(String(10), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    denominacao_companhia: Mapped[str | None] = mapped_column(String(255))
    quantidade_acoes_ordinarias_capital_integralizado: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_acoes_preferenciais_capital_integralizado: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_total_acoes_capital_integralizado: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_acoes_ordinarias_tesouraria: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_acoes_preferenciais_tesouraria: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_total_acoes_tesouraria: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    alterado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ParecerFinanceiro(Base):
    __tablename__ = "pareceres_financeiros"
    __table_args__ = (
        UniqueConstraint(
            "tipo_formulario",
            "cnpj_companhia",
            "data_referencia",
            "versao",
            "tipo_relatorio_auditor",
            "tipo_parecer_declaracao",
            "numero_item_parecer_declaracao",
            name="uq_pareceres_financeiros_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    tipo_formulario: Mapped[str] = mapped_column(String(10), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    denominacao_companhia: Mapped[str | None] = mapped_column(String(255))
    tipo_relatorio_auditor: Mapped[str | None] = mapped_column(String(255))
    tipo_parecer_declaracao: Mapped[str | None] = mapped_column(String(255))
    numero_item_parecer_declaracao: Mapped[str | None] = mapped_column(String(100))
    texto_parecer_declaracao: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    alterado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
