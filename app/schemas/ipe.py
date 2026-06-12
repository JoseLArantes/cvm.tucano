import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Paginacao


class IpeDocumentoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str | None
    codigo_cvm: int | None
    nome_companhia: str | None
    data_referencia: date
    categoria: str | None
    tipo: str | None
    especie: str | None
    assunto: str | None
    data_entrega: date
    tipo_apresentacao: str | None
    protocolo_entrega: str | None
    versao: int
    link_download: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class ListaIpeDocumentosResposta(BaseModel):
    dados: list[IpeDocumentoResposta] = Field(description="Lista paginada de documentos IPE.")
    paginacao: Paginacao
