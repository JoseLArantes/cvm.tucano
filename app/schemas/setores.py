from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.analise import AnaliseProvenienciaItem

_METRICAS_MARGEM_PADRAO: tuple[Literal["margem_bruta", "margem_ebit", "margem_liquida"], ...] = (
    "margem_bruta",
    "margem_ebit",
    "margem_liquida",
)
_ESTATISTICAS_PADRAO: tuple[Literal["media_simples", "mediana", "razao_das_somas"], ...] = (
    "media_simples",
    "mediana",
    "razao_das_somas",
)


class SetorTaxonomiaResposta(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    codigo: str
    nome: str
    fonte: str
    ativa: bool
    versao_atual: int | None
    checksum_atual: str | None
    referencia_fonte_atual: str | None
    publicada_em: datetime | None


class SetorVersaoResposta(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    versao: int = Field(description="Número sequencial da publicação dentro da taxonomia.")
    checksum_fonte: str | None = Field(
        description="SHA-256 dos bytes do arquivo importado; pode mudar sem gerar nova versão semântica."
    )
    checksum_semantico: str = Field(
        description="SHA-256 dos conceitos, nomes, níveis e relações hierárquicas publicados."
    )
    referencia_fonte: str | None = Field(description="URL ou referência informada para a origem da publicação.")
    observada_em: datetime | None = Field(
        description="Instante representado pela data da fonte, à meia-noite UTC; nulo se a data não foi informada."
    )
    publicada_em: datetime = Field(description="Instante UTC em que a versão foi publicada pelo sistema.")
    resumo: dict[str, object] = Field(description="Contagens e metadados operacionais da publicação.")


class SetorTaxonomiaImportacaoResumoResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    referencia_fonte: str | None = Field(
        default=None,
        description="URL ou identificador da fonte preenchido no multipart; usa a página da B3 quando omitido.",
    )
    observacao: str | None = Field(default=None, description="Nota operacional registrada pelo responsável.")
    setores: int | None = Field(default=None, ge=0, description="Quantidade de nós de nível setor reconhecidos.")
    subsetores: int | None = Field(default=None, ge=0, description="Quantidade de nós de nível subsetor reconhecidos.")
    segmentos: int | None = Field(default=None, ge=0, description="Quantidade de nós de nível segmento reconhecidos.")
    classificacoes_de_emissores_importadas: int | None = Field(
        default=None,
        ge=0,
        description="Classificações de emissores criadas pelo arquivo. Para esta operação, sempre zero.",
    )
    nos_publicados: int | None = Field(default=None, ge=0, description="Total de conceitos publicados na versão.")
    mudancas: int | None = Field(default=None, ge=0, description="Mudanças auditadas na versão publicada.")


class SetorTaxonomiaImportacaoResposta(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "0c8df70a-33c6-4c1a-b690-8dd2a49c615b",
                    "taxonomia": "b3",
                    "nome_arquivo": "ClassifSetorial.xlsx",
                    "checksum_sha256": "342a9966b1cafe0ee226de66b398a9288c5ad9ba93c40cbc2d2bc3354ba454aa",
                    "tamanho_bytes": 16149,
                    "data_atualizacao_fonte": "2026-11-10",
                    "importado_por": "token_sistema",
                    "status": "sucesso",
                    "versao_taxonomia": 1,
                    "resumo": {
                        "referencia_fonte": (
                            "https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/"
                            "acoes/consultas/classificacao-setorial/"
                        ),
                        "observacao": "Arquivo baixado e conferido manualmente",
                        "setores": 11,
                        "subsetores": 45,
                        "segmentos": 86,
                        "classificacoes_de_emissores_importadas": 0,
                        "nos_publicados": 142,
                        "mudancas": 142,
                    },
                    "erro": None,
                    "importada_em": "2026-11-10T12:00:00Z",
                    "concluida_em": "2026-11-10T12:00:01Z",
                }
            ]
        },
    )

    id: uuid.UUID = Field(description="UUID opaco da tentativa de importação para rastreamento e suporte.")
    taxonomia: str = Field(description="Identificador da taxonomia de destino; nesta operação, `b3`.")
    nome_arquivo: str = Field(description="Nome original recebido no upload, sem diretórios do cliente.")
    checksum_sha256: str = Field(
        pattern="^[a-f0-9]{64}$",
        description="SHA-256 hexadecimal dos bytes exatos do arquivo XLSX recebido.",
    )
    tamanho_bytes: int = Field(ge=0, description="Tamanho do arquivo original em bytes; limite da operação: 10 MiB.")
    data_atualizacao_fonte: date | None = Field(
        description="Data da atualização da classificação indicada manualmente; não é inferida pelo arquivo."
    )
    importado_por: str = Field(
        description="Usuário administrativo autenticado ou `token_sistema` quando usada a credencial de sistema."
    )
    status: Literal["processando", "sucesso", "sem_alteracao", "rejeitada"] = Field(
        description=(
            "Resultado: `sucesso` publicou uma versão; `sem_alteracao` registrou a tentativa sem nova versão; "
            "`rejeitada` indica XLSX/layout inválido; `processando` é reservado para execução assíncrona futura."
        )
    )
    versao_taxonomia: int | None = Field(
        description="Versão criada ou já vigente para esta importação; nulo quando o arquivo foi rejeitado."
    )
    resumo: SetorTaxonomiaImportacaoResumoResposta = Field(
        description="Contagens da hierarquia e metadados informados na requisição."
    )
    erro: str | None = Field(description="Motivo legível da rejeição; nulo quando a planilha foi aceita.")
    importada_em: datetime = Field(description="Instante UTC em que a tentativa foi registrada.")
    concluida_em: datetime | None = Field(description="Instante UTC de conclusão; nulo enquanto não concluída.")


class SetorResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    taxonomia: str
    nome: str
    chave_normalizada: str
    nivel: str
    setor_pai_id: uuid.UUID | None
    ativo: bool
    total_companhias: int | None = None


class SetorDetalheResposta(SetorResposta):
    versao_taxonomia: int
    aliases: list[str] = Field(default_factory=list)
    correspondencias: list[SetorCorrespondenciaResposta] = Field(default_factory=list)


class SetorCorrespondenciaResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomia_origem: str
    setor_origem_id: uuid.UUID
    setor_origem_nome: str
    taxonomia_destino: str
    setor_destino_id: uuid.UUID
    setor_destino_nome: str
    tipo: Literal["equivalente", "mais_amplo", "mais_estreito", "relacionado"]
    versao_mapeamento: int
    evidencias: dict[str, object]
    justificativa: str | None


class SetorAliasResposta(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    taxonomia: str
    setor_id: uuid.UUID
    chave_normalizada: str
    rotulo_origem: str
    evidencias: dict[str, object]


class SetorCompanhiaResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    cnpj_companhia: str
    codigo_cvm: int | None
    denominacao_social: str | None
    denominacao_comercial: str | None
    categoria_registro: str | None
    tipo_emissor: str | None
    situacao_registro: str | None
    setor_atividade: str | None
    setor_id: uuid.UUID | None
    taxonomia: str


class SetorPaginacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pagina: int
    tamanho_pagina: int
    total: int


class SetorAliasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomia: str
    setor_id: uuid.UUID
    rotulo_origem: str = Field(min_length=1, max_length=255)
    evidencias: dict[str, object] = Field(min_length=1)
    justificativa: str = Field(min_length=1, max_length=2000)
    revisado_por: str = Field(min_length=1, max_length=128)


class SetorCorrespondenciaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomia_origem: str
    setor_origem_id: uuid.UUID
    taxonomia_destino: str
    setor_destino_id: uuid.UUID
    tipo: Literal["equivalente", "mais_amplo", "mais_estreito", "relacionado"]
    evidencias: dict[str, object] = Field(min_length=1)
    justificativa: str = Field(min_length=1, max_length=2000)
    revisado_por: str = Field(min_length=1, max_length=128)


class SetorListaResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dados: list[SetorResposta]
    paginacao: SetorPaginacao
    taxonomia: str
    versao_taxonomia: int


class SetorCompanhiasResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dados: list[SetorCompanhiaResposta]
    paginacao: SetorPaginacao
    setor_id: uuid.UUID
    taxonomia: str
    versao_taxonomia: int


class AgregacaoSetorialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomia: str = Field(
        default="cvm_cadastro",
        description="Taxonomia usada para filtrar e agrupar pelo vínculo setorial atual.",
        examples=["cvm_cadastro"],
    )
    todas: bool = Field(
        default=False,
        description="Seleciona todo o cadastro; deve ser true sozinho quando nenhum outro filtro de universo for enviado.",
    )
    companhia_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=500,
        description="UUIDs internos de companhias. Em união com `codigos_cvm`; filtros cadastrais distintos são intersectados.",
    )
    codigos_cvm: list[int] = Field(
        default_factory=list,
        max_length=500,
        description="Códigos CVM de emissores. Em união com `companhia_ids`; a seleção explícita combinada é limitada a 500 identidades.",
    )
    setores: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=100,
        description="UUIDs de conceitos da taxonomia selecionada; união dentro da lista.",
    )
    categorias_registro: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Categorias de registro CVM aceitas em união dentro da lista.",
    )
    tipos_emissor: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Tipos de emissor cadastrados aceitos em união dentro da lista.",
    )
    situacoes_registro: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Situações de registro CVM aceitas em união dentro da lista.",
    )
    anos: list[int] = Field(
        min_length=1,
        max_length=10,
        description="Exercícios fiscais anuais FY, entre 1900 e 2100; máximo de dez itens.",
        examples=[[2023, 2024]],
    )
    escopo: Literal["consolidated", "individual"] = Field(
        default="consolidated",
        description="Escopo societário dos fatos financeiros canônicos.",
    )
    metricas: list[Literal["margem_bruta", "margem_ebit", "margem_liquida"]] = Field(
        default_factory=lambda: list(_METRICAS_MARGEM_PADRAO),
        min_length=1,
        max_length=3,
        description="Margens derivadas de lucro bruto, EBIT ou lucro líquido divididos pela receita líquida.",
    )
    estatisticas: list[Literal["media_simples", "mediana", "razao_das_somas"]] = Field(
        default_factory=lambda: list(_ESTATISTICAS_PADRAO),
        min_length=1,
        max_length=3,
        description="Estatísticas calculadas para a mesma amostra elegível; por padrão retorna as três.",
    )
    agrupar_por: list[Literal["setor", "categoria_registro", "tipo_emissor", "situacao_registro"]] = Field(
        default_factory=list,
        max_length=2,
        description="Dimensões de agrupamento; admite setor, categoria, tipo de emissor e situação cadastral.",
    )
    as_of: date | None = Field(
        default=None,
        description="Corte informacional. Seleciona revisões em que `known_from <= as_of < known_to`; nulo usa revisões vigentes.",
    )
    incluir_detalhamento: bool = Field(
        default=False,
        description="Inclui componentes por companhia elegível. Limitado a até 500 companhias selecionadas e não cacheado.",
    )

    @model_validator(mode="after")
    def validar_universo(self) -> AgregacaoSetorialRequest:
        possui_filtro = any(
            (
                self.companhia_ids,
                self.codigos_cvm,
                self.setores,
                self.categorias_registro,
                self.tipos_emissor,
                self.situacoes_registro,
            )
        )
        if self.todas and possui_filtro:
            raise ValueError("`todas=true` deve ser usado sozinho, sem outros filtros de universo.")
        if not self.todas and not possui_filtro:
            raise ValueError("Informe ao menos um filtro de universo ou use `todas=true`.")
        if len(set(self.agrupar_por)) != len(self.agrupar_por):
            raise ValueError("`agrupar_por` nao pode repetir dimensoes.")
        if any(ano < 1900 or ano > 2100 for ano in self.anos):
            raise ValueError("Cada ano deve estar entre 1900 e 2100.")
        self.anos = list(dict.fromkeys(self.anos))
        self.companhia_ids = list(dict.fromkeys(self.companhia_ids))
        self.codigos_cvm = list(dict.fromkeys(self.codigos_cvm))
        self.setores = list(dict.fromkeys(self.setores))
        self.categorias_registro = list(dict.fromkeys(self.categorias_registro))
        self.tipos_emissor = list(dict.fromkeys(self.tipos_emissor))
        self.situacoes_registro = list(dict.fromkeys(self.situacoes_registro))
        self.metricas = list(dict.fromkeys(self.metricas))
        self.estatisticas = list(dict.fromkeys(self.estatisticas))
        if any(codigo <= 0 for codigo in self.codigos_cvm):
            raise ValueError("Os códigos CVM devem ser positivos.")
        if len(self.companhia_ids) + len(self.codigos_cvm) > 500:
            raise ValueError("A seleção explícita aceita no máximo 500 identidades de companhia.")
        return self


class AgregacaoSetorialEstatisticas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_simples: Decimal | None = Field(description="Média aritmética das margens individuais, quando solicitada.")
    mediana: Decimal | None = Field(description="Mediana das margens individuais, quando solicitada.")
    razao_das_somas: Decimal | None = Field(description="Soma dos resultados dividida pela soma das receitas, quando solicitada.")


class AgregacaoSetorialCobertura(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selecionadas: int
    elegiveis: int
    excluidas: int
    motivos: dict[str, int]


class AgregacaoSetorialCelula(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grupo: dict[str, str | None]
    period_id: str
    metric_id: str
    unit: Literal["ratio"] = "ratio"
    status: Literal["disponivel", "parcial", "indisponivel"]
    estatisticas: AgregacaoSetorialEstatisticas
    cobertura: AgregacaoSetorialCobertura


class AgregacaoSetorialComponente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    companhia_id: uuid.UUID
    codigo_cvm: int | None
    denominacao_social: str | None
    grupo: dict[str, str | None]
    period_id: str
    metric_id: str
    numerador: Decimal
    denominador: Decimal
    margem: Decimal
    proveniencia_numerador: list[AnaliseProvenienciaItem]
    proveniencia_denominador: list[AnaliseProvenienciaItem]


class AgregacaoSetorialResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomia: str
    versao_taxonomia: int
    classificacao: Literal["atual"] = "atual"
    escopo: Literal["consolidated", "individual"]
    calculation_version: str
    as_of: date | None
    resolution_mode: Literal["canonical"] = "canonical"
    atualidade: Literal["atual", "pendente", "falha", "indeterminada"] = "indeterminada"
    atualidade_motivo: str = "LINHAGEM_DE_ENTRADA_NAO_COMPROVADA"
    geracao_financeira: str | None
    fingerprint: str
    selecionadas: int
    celulas: list[AgregacaoSetorialCelula]
    detalhamento: list[AgregacaoSetorialComponente] | None = None
