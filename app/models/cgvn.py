import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CgvnDocumento(Base):
    __tablename__ = "cgvn_documentos"
    __table_args__ = (
        UniqueConstraint("id_documento", "versao", name="uq_cgvn_documentos_id_versao"),
        UniqueConstraint(
            "cnpj_companhia",
            "codigo_cvm",
            "data_referencia",
            "versao",
            name="uq_cgvn_documentos_chave_alternativa",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str | None] = mapped_column(String(14), index=True)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(String(255))
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    data_entrega: Mapped[date] = mapped_column(Date, index=True)
    data_inicio_exercicio_social: Mapped[date | None] = mapped_column(Date)
    data_fim_exercicio_social: Mapped[date | None] = mapped_column(Date)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    link_download: Mapped[str | None] = mapped_column(String(1000))
    categoria: Mapped[str | None] = mapped_column(String(50))
    motivo_reapresentacao: Mapped[str | None] = mapped_column(String(500))

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CgvnPratica(Base):
    __tablename__ = "cgvn_praticas"
    __table_args__ = (
        UniqueConstraint(
            "cnpj_companhia",
            "data_referencia",
            "versao",
            "id_item",
            "linha_origem",
            name="uq_cgvn_praticas_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str | None] = mapped_column(String(14), index=True)
    nome_companhia: Mapped[str | None] = mapped_column(String(255))
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_item: Mapped[str] = mapped_column(String(50), index=True)
    pratica_recomendada: Mapped[str | None] = mapped_column(String(2000))
    pratica_adotada: Mapped[str | None] = mapped_column(String(50), index=True)
    capitulo: Mapped[str | None] = mapped_column(String(255))
    principio: Mapped[str | None] = mapped_column(String(255))
    explicacao: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
