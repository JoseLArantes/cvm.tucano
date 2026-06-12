import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Paginacao


class CompanhiaResposta(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
                "cnpj_companhia": "08773135000100",
                "codigo_cvm": 25224,
                "denominacao_social": "2W ECOBANK S.A. - EM RECUPERACAO JUDICIAL",
                "denominacao_comercial": "2W ECOBANK S.A.",
                "situacao_registro": "SUSPENSO(A) - DECISAO ADM",
                "data_registro": "2020-10-29",
                "data_constituicao": "2007-03-23",
                "data_cancelamento": None,
                "motivo_cancelamento": None,
                "data_inicio_situacao": "2026-05-19",
                "setor_atividade": "Energia Eletrica",
                "tipo_mercado": None,
                "categoria_registro": "Categoria A",
                "data_inicio_categoria": "2020-10-29",
                "situacao_emissor": "EM RECUPERACAO JUDICIAL OU EQUIVALENTE",
                "data_inicio_situacao_emissor": "2025-04-23",
                "controle_acionario": "PRIVADO",
                "endereco": {
                    "tipo_endereco": "SEDE",
                    "logradouro": "Avenida Dr. Chucri Zaidan, 1550",
                    "complemento": "8 and-conj 815-sl 1",
                    "bairro": "Chacara Santo Antoni",
                    "municipio": "SAO PAULO",
                    "uf": "SP",
                    "pais": "BRASIL",
                    "cep": "4711130",
                    "ddd_telefone": "11",
                    "telefone": "39579400",
                    "ddd_fax": "11",
                    "fax": "39579499",
                    "email": "ri@2wecobank.com.br",
                },
                "responsavel": {
                    "tipo_responsavel": "DIRETOR DE RELACOES COM INVESTIDORES",
                    "nome_responsavel": "FERNANDO GUEDES VIEIRA",
                    "data_inicio_responsavel": "2026-04-22",
                    "logradouro": "AV DR. CHUCRI ZAIDAN, 1550",
                    "complemento": "8 AND-CONJ815-SL1",
                    "bairro": "CHACARA STO. ANTONIO",
                    "municipio": "SAO PAULO",
                    "uf": "SP",
                    "pais": None,
                    "cep": "4711130",
                    "ddd_telefone": "11",
                    "telefone": "39579400",
                    "ddd_fax": None,
                    "fax": None,
                    "email": "juridico@2wecobank.com.br",
                },
                "auditor": "GRANT THORNTON AUDITORES INDEPENDENTES LTDA.",
                "cnpj_auditor": "10830108000165",
                "criado_em": "2026-05-30T14:30:00Z",
                "sincronizado_em": "2026-05-30T14:30:00Z",
                "alterado_em": "2026-05-30T14:30:00Z",
            }
        },
    )

    id: uuid.UUID = Field(description="Identificador interno da companhia no sistema.")
    cnpj_companhia: str = Field(description="CNPJ normalizado da companhia com 14 digitos numericos.")
    codigo_cvm: int | None = Field(description="Codigo CVM da companhia, quando disponibilizado pela fonte.")
    denominacao_social: str | None = Field(description="Razao social cadastrada na CVM.")
    denominacao_comercial: str | None = Field(description="Nome comercial cadastrado na CVM.")
    situacao_registro: str | None = Field(description="Situacao do registro da companhia na CVM.")
    data_registro: date | None = Field(description="Data de registro da companhia na CVM.")
    data_constituicao: date | None = Field(description="Data de constituicao da companhia.")
    data_cancelamento: date | None = Field(description="Data de cancelamento do registro, quando houver.")
    motivo_cancelamento: str | None = Field(description="Motivo de cancelamento do registro, quando informado.")
    data_inicio_situacao: date | None = Field(description="Data de inicio da situacao atual do registro.")
    setor_atividade: str | None = Field(description="Setor de atividade informado pela CVM.")
    tipo_mercado: str | None = Field(description="Classificacao de mercado (ex.: Novo Mercado).")
    categoria_registro: str | None = Field(description="Categoria de registro do emissor.")
    data_inicio_categoria: date | None = Field(description="Data de inicio da categoria de registro atual.")
    situacao_emissor: str | None = Field(description="Situacao do emissor informada pela CVM.")
    data_inicio_situacao_emissor: date | None = Field(description="Data de inicio da situacao do emissor atual.")
    controle_acionario: str | None = Field(description="Tipo de controle acionario informado pela CVM.")
    endereco: dict[str, Any] = Field(description="Bloco estruturado com endereco da companhia.")
    responsavel: dict[str, Any] = Field(description="Bloco estruturado com dados do responsavel cadastral.")
    auditor: str | None = Field(description="Nome do auditor cadastral informado na base.")
    cnpj_auditor: str | None = Field(description="CNPJ do auditor com 14 digitos, quando informado.")
    criado_em: datetime = Field(description="Timestamp da primeira insercao do registro no sistema.")
    sincronizado_em: datetime = Field(
        description="Timestamp da ultima sincronizacao em que o registro foi encontrado na fonte."
    )
    alterado_em: datetime = Field(
        description="Timestamp da ultima alteracao real de campos de negocio apos normalizacao."
    )


class ListaCompanhiasResposta(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "dados": [],
                "paginacao": {"pagina": 1, "tamanho_pagina": 100, "total": 0},
            }
        }
    )

    dados: list[CompanhiaResposta] = Field(description="Lista paginada de companhias.")
    paginacao: Paginacao = Field(description="Metadados de paginacao da consulta.")
