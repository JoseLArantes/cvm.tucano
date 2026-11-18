from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import BrazilianDate, CanonicalDecimal, Paginacao

UnidadeFii = Literal[
    "BRL",
    "BRL/cota",
    "cotas",
    "contagens",
    "versao",
    "percentual CVM",
    "data",
    "booleano",
    "texto",
    "identificador",
]


class FiiVarianteProveniencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arquivo_csv: str
    arquivo_zip: str
    linha: int
    hash_origem: str
    execucao_sincronizacao_id: str
    ocorrencias: int
    consta_no_snapshot_atual: bool


class FiiVarianteResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dados: dict[str, str | int | bool | None]
    unidades: dict[str, UnidadeFii]
    proveniencia: FiiVarianteProveniencia


class FiiSecaoResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["disponivel", "ambiguo", "ausente"] = Field(
        description="Disponibilidade da secao para o fundo ou classe solicitado."
    )
    dados: dict[str, str | int | bool | None] | None = Field(
        description="Campos normalizados declarados pela CVM. Valores monetarios usam BRL, quantidades usam cotas ou contagens e percentuais preservam o decimal da fonte."
    )
    unidades: dict[str, UnidadeFii] = Field(
        description="Unidade de cada campo presente em dados. Valores decimais sao strings canonicas e mantem exatamente o decimal publicado pela CVM."
    )
    variantes: list[FiiVarianteResposta] = Field(
        default_factory=list,
        description="Valores distintos observados quando a secao nao pode ser atribuida com seguranca a fundo ou classe. Cada variante inclui proveniencia.",
    )
    proveniencia: FiiVarianteProveniencia | None = Field(
        description="Origem da secao quando disponivel. Variantes ambiguas trazem proveniencia individual em cada item."
    )
    consta_no_snapshot_atual: bool | None = Field(
        description="Indica se esta secao consta no ZIP anual atualmente publicado. Nulo quando a secao nao foi encontrada."
    )


class FiiInformeResumoResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cnpj: str = Field(description="CNPJ canonico de 14 caracteres, sem pontuacao.")
    tipo: Literal["fundo", "classe"]
    competencia: str = Field(description="Competencia do informe no formato AAAA-MM.")
    versao: int = Field(ge=1, description="Versao declarada pela CVM.")
    data_entrega: BrazilianDate | None = Field(description="Data de entrega do informe a CVM.")
    nome: str | None
    codigo_isin: str | None
    segmento_atuacao: str | None
    patrimonio_liquido_brl: CanonicalDecimal | None = Field(description="Patrimonio liquido reportado em reais.")
    valor_ativo_brl: CanonicalDecimal | None = Field(description="Valor do ativo reportado em reais.")
    valor_patrimonial_cota_brl: CanonicalDecimal | None = Field(description="Valor patrimonial por cota em reais.")
    cotistas_total: int | None = Field(description="Numero de cotistas informado no complemento.")
    dividend_yield_mes_percentual_cvm: CanonicalDecimal | None = Field(
        description="Percentual de dividend yield do mes conforme reportado pela CVM, usando a base de calculo do Suplemento I."
    )
    disponibilidade_secoes: dict[str, Literal["disponivel", "ambiguo", "ausente"]]
    consta_no_snapshot_atual: bool


class ListaFiisResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dados: list[FiiInformeResumoResposta]
    paginacao: Paginacao


class FiiInformeCompletoResposta(FiiInformeResumoResposta):
    geral: FiiSecaoResposta
    complemento: FiiSecaoResposta
    ativo_passivo: FiiSecaoResposta
    proveniencia: dict[str, str | int | None] = Field(
        description="Arquivo anual, arquivo membro, linha de origem, hash normalizado e execucao que promoveu a secao geral."
    )


class FiiPerfilResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identidade: dict[str, str | None]
    informe_atual: FiiInformeCompletoResposta
