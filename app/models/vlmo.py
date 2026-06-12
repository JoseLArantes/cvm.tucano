import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VlmoDocumento(Base):
    __tablename__ = "vlmo_documentos"
    __table_args__ = (
        UniqueConstraint("protocolo_entrega", "versao", name="uq_vlmo_documentos_protocolo_versao"),
        UniqueConstraint(
            "cnpj_companhia",
            "codigo_cvm",
            "data_referencia",
            "categoria",
            "tipo",
            "data_entrega",
            "versao",
            name="uq_vlmo_documentos_chave_alternativa",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str | None] = mapped_column(String(14), index=True)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(String(255))
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    categoria: Mapped[str | None] = mapped_column(String(255), index=True)
    tipo: Mapped[str | None] = mapped_column(String(255), index=True)
    data_entrega: Mapped[date] = mapped_column(Date, index=True)
    tipo_apresentacao: Mapped[str | None] = mapped_column(String(255))
    motivo_reapresentacao: Mapped[str | None] = mapped_column(String(500))
    protocolo_entrega: Mapped[str | None] = mapped_column(String(255), index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    link_download: Mapped[str | None] = mapped_column(String(1000))
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VlmoConsolidado(Base):
    __tablename__ = "vlmo_consolidado"
    __table_args__ = (
        UniqueConstraint(
            "cnpj_companhia",
            "data_referencia",
            "versao",
            "linha_origem",
            name="uq_vlmo_consolidado_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str | None] = mapped_column(String(14), index=True)
    nome_companhia: Mapped[str | None] = mapped_column(String(255))
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    tipo_empresa: Mapped[str | None] = mapped_column(String(50), index=True)
    empresa: Mapped[str | None] = mapped_column(String(255), index=True)
    tipo_cargo: Mapped[str | None] = mapped_column(String(100), index=True)
    tipo_movimentacao: Mapped[str | None] = mapped_column(String(255), index=True)
    descricao_movimentacao: Mapped[str | None] = mapped_column(String(255))
    tipo_operacao: Mapped[str | None] = mapped_column(String(50), index=True)
    tipo_ativo: Mapped[str | None] = mapped_column(String(255), index=True)
    caracteristica_valor_mobiliario: Mapped[str | None] = mapped_column(String(100), index=True)
    intermediario: Mapped[str | None] = mapped_column(String(100), index=True)
    data_movimentacao: Mapped[date | None] = mapped_column(Date, index=True)
    quantidade: Mapped[int | None] = mapped_column(BigInteger)
    preco_unitario: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    indice_ocorrencia: Mapped[int] = mapped_column(Integer, index=True)
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
