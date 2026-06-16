import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Paginacao, PeriodicModel


class VlmoDocumentoResposta(PeriodicModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str | None
    codigo_cvm: int | None
    nome_companhia: str | None
    data_referencia: date
    categoria: str | None
    tipo: str | None
    data_entrega: date
    tipo_apresentacao: str | None
    motivo_reapresentacao: str | None
    protocolo_entrega: str | None
    versao: int
    link_download: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class ListaVlmoDocumentosResposta(BaseModel):
    dados: list[VlmoDocumentoResposta] = Field(description="Lista paginada de documentos VLMO.")
    paginacao: Paginacao


class VlmoConsolidadoResposta(PeriodicModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str | None
    nome_companhia: str | None
    data_referencia: date
    versao: int
    tipo_empresa: str | None
    empresa: str | None
    tipo_cargo: str | None
    tipo_movimentacao: str | None
    descricao_movimentacao: str | None
    tipo_operacao: str | None
    tipo_ativo: str | None
    caracteristica_valor_mobiliario: str | None
    intermediario: str | None
    data_movimentacao: date | None
    quantidade: int | None
    preco_unitario: Decimal | None
    volume: Decimal | None
    indice_ocorrencia: int
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class ListaVlmoConsolidadoResposta(BaseModel):
    dados: list[VlmoConsolidadoResposta] = Field(description="Lista paginada de linhas consolidadas VLMO.")
    paginacao: Paginacao
