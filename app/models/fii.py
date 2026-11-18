import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FiiInformeGeral(Base):
    __tablename__ = "fii_informes_gerais"
    __table_args__ = (
        UniqueConstraint(
            "cnpj",
            "tipo",
            "data_referencia",
            "versao",
            name="uq_fii_informes_gerais_chave",
        ),
        Index("ix_fii_informes_gerais_catalogo", "nome", "cnpj", "tipo"),
        Index("ix_fii_informes_gerais_atual", "consta_no_snapshot_atual", "data_referencia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cnpj: Mapped[str] = mapped_column(String(14), index=True)
    tipo: Mapped[str] = mapped_column(String(10), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    nome: Mapped[str | None] = mapped_column(String(255), index=True)
    codigo_isin: Mapped[str | None] = mapped_column(String(32), index=True)
    segmento_atuacao: Mapped[str | None] = mapped_column(String(255), index=True)
    publico_alvo: Mapped[str | None] = mapped_column(String(100))
    mandato: Mapped[str | None] = mapped_column(String(255))
    tipo_gestao: Mapped[str | None] = mapped_column(String(100))
    prazo_duracao: Mapped[str | None] = mapped_column(String(100))
    data_funcionamento: Mapped[date | None] = mapped_column(Date)
    data_prazo_duracao: Mapped[date | None] = mapped_column(Date)
    quantidade_cotas_emitidas: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    fundo_exclusivo: Mapped[bool | None] = mapped_column(Boolean)
    cotistas_vinculo_familiar: Mapped[bool | None] = mapped_column(Boolean)
    mercado_negociacao_bolsa: Mapped[bool | None] = mapped_column(Boolean, index=True)
    nome_administrador: Mapped[str | None] = mapped_column(String(255))
    cnpj_administrador: Mapped[str | None] = mapped_column(String(18), index=True)
    dados: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    linha_origem: Mapped[int] = mapped_column(Integer, nullable=False)
    hash_origem: Mapped[str] = mapped_column(String(64), nullable=False)
    arquivo_origem: Mapped[str] = mapped_column(String(255), nullable=False)
    ano_origem: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    execucao_sincronizacao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id"), index=True, nullable=False
    )
    consta_no_snapshot_atual: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FiiInformeComplemento(Base):
    __tablename__ = "fii_informes_complementos"
    __table_args__ = (
        UniqueConstraint("cnpj", "tipo", "data_referencia", "versao", "hash_variante", name="uq_fii_complementos_variante"),
        Index("ix_fii_complementos_fundo", "cnpj", "tipo", "data_referencia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cnpj: Mapped[str] = mapped_column(String(14), index=True)
    tipo: Mapped[str | None] = mapped_column(String(10), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    valor_ativo: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    patrimonio_liquido: Mapped[Decimal | None] = mapped_column(Numeric(50, 30), index=True)
    cotas_emitidas: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    valor_patrimonial_cotas: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    total_numero_cotistas: Mapped[int | None] = mapped_column(Integer)
    percentual_rentabilidade_efetiva_mes: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    percentual_rentabilidade_patrimonial_mes: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    percentual_dividend_yield_mes: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    percentual_amortizacao_cotas_mes: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    status_atribuicao: Mapped[str] = mapped_column(String(20), nullable=False)
    ocorrencias: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    dados: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    linha_origem: Mapped[int] = mapped_column(Integer, nullable=False)
    hash_variante: Mapped[str] = mapped_column(String(64), nullable=False)
    hash_origem: Mapped[str] = mapped_column(String(64), nullable=False)
    arquivo_origem: Mapped[str] = mapped_column(String(255), nullable=False)
    ano_origem: Mapped[int] = mapped_column(Integer, nullable=False)
    execucao_sincronizacao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id"), index=True, nullable=False
    )
    consta_no_snapshot_atual: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FiiInformeAtivoPassivo(Base):
    __tablename__ = "fii_informes_ativos_passivos"
    __table_args__ = (
        UniqueConstraint("cnpj", "tipo", "data_referencia", "versao", "hash_variante", name="uq_fii_ativos_passivos_variante"),
        Index("ix_fii_ativos_passivos_fundo", "cnpj", "tipo", "data_referencia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cnpj: Mapped[str] = mapped_column(String(14), index=True)
    tipo: Mapped[str | None] = mapped_column(String(10), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    total_necessidades_liquidez: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    disponibilidades: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    total_investido: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    direitos_bens_imoveis: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    valores_receber: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    total_passivo: Mapped[Decimal | None] = mapped_column(Numeric(50, 30))
    status_atribuicao: Mapped[str] = mapped_column(String(20), nullable=False)
    ocorrencias: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    dados: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    linha_origem: Mapped[int] = mapped_column(Integer, nullable=False)
    hash_variante: Mapped[str] = mapped_column(String(64), nullable=False)
    hash_origem: Mapped[str] = mapped_column(String(64), nullable=False)
    arquivo_origem: Mapped[str] = mapped_column(String(255), nullable=False)
    ano_origem: Mapped[int] = mapped_column(Integer, nullable=False)
    execucao_sincronizacao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id"), index=True, nullable=False
    )
    consta_no_snapshot_atual: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
