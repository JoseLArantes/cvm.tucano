import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import BrazilianDate, BrazilianDateTime, Paginacao, PeriodicModel


class CgvnDocumentoResposta(PeriodicModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str | None
    codigo_cvm: int | None
    nome_companhia: str | None
    data_referencia: BrazilianDate
    data_entrega: BrazilianDate
    data_inicio_exercicio_social: BrazilianDate | None
    data_fim_exercicio_social: BrazilianDate | None
    id_documento: int
    versao: int
    link_download: str | None
    categoria: str | None
    motivo_reapresentacao: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaCgvnDocumentosResposta(BaseModel):
    dados: list[CgvnDocumentoResposta] = Field(description="Lista paginada de documentos CGVN.")
    paginacao: Paginacao


class CgvnPraticaResposta(PeriodicModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str | None
    nome_companhia: str | None
    data_referencia: BrazilianDate
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
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaCgvnPraticasResposta(BaseModel):
    dados: list[CgvnPraticaResposta] = Field(description="Lista paginada de práticas CGVN.")
    paginacao: Paginacao
