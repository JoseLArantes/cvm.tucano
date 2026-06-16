import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Paginacao, PeriodicModel


class CgvnDocumentoResposta(PeriodicModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str | None
    codigo_cvm: int | None
    nome_companhia: str | None
    data_referencia: date
    data_entrega: date
    data_inicio_exercicio_social: date | None
    data_fim_exercicio_social: date | None
    id_documento: int
    versao: int
    link_download: str | None
    categoria: str | None
    motivo_reapresentacao: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class ListaCgvnDocumentosResposta(BaseModel):
    dados: list[CgvnDocumentoResposta] = Field(description="Lista paginada de documentos CGVN.")
    paginacao: Paginacao


class CgvnPraticaResposta(PeriodicModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str | None
    nome_companhia: str | None
    data_referencia: date
    id_documento: int
    versao: int
    id_item: str
    pratica_recomendada: str | None
    pratica_adotada: str | None
    capitulo: str | None
    principio: str | None
    explicacao: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class ListaCgvnPraticasResposta(BaseModel):
    dados: list[CgvnPraticaResposta] = Field(description="Lista paginada de práticas CGVN.")
    paginacao: Paginacao
