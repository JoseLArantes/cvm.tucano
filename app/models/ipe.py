import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IpeDocumento(Base):
    __tablename__ = "ipe_documentos"
    __table_args__ = (
        UniqueConstraint(
            "cnpj_companhia",
            "codigo_cvm",
            "data_referencia",
            "categoria",
            "tipo",
            "especie",
            "assunto",
            "data_entrega",
            "protocolo_entrega",
            "versao",
            name="uq_ipe_documentos_chave_alternativa",
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
    especie: Mapped[str | None] = mapped_column(String(255), index=True)
    assunto: Mapped[str | None] = mapped_column(String(1000), index=True)
    data_entrega: Mapped[date] = mapped_column(Date, index=True)
    tipo_apresentacao: Mapped[str | None] = mapped_column(String(255))
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
