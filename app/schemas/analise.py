import uuid
from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field


class AlertaOverview(BaseModel):
    tipo: str = Field(description="Tipo do alerta (ex: SITUACAO_REGISTRO, ATRASO_FILING)")
    descricao: str = Field(description="Descrição amigável do alerta")
    severidade: str = Field(description="Nível de severidade: INFO, WARNING, CRITICAL")


class OverviewAnaliseResposta(BaseModel):
    cnpj_companhia: str = Field(description="CNPJ da companhia")
    codigo_cvm: int = Field(description="Código CVM da companhia")
    denominacao_social: str = Field(description="Denominação social da companhia")
    situacao_registro: str = Field(description="Situação do registro atual na CVM")
    status_ativo: bool = Field(description="Indica se a companhia está ativa")
    data_freshness: datetime | None = Field(description="Timestamp da última sincronização geral de dados")
    cobertura: dict[str, list[str]] = Field(description="Mapeamento de ano para famílias de dados disponíveis")
    periodos_disponiveis: dict[str, list[str]] = Field(description="Períodos disponíveis por tipo documental (DFP, ITR)")
    alertas: list[AlertaOverview] = Field(description="Lista de alertas de conformidade ou operacionais")
    anos_comparacao_disponiveis: list[int] = Field(description="Anos com DFP disponível para comparação")


class ReferenciaProveniencia(BaseModel):
    fonte: str = Field(default="CVM", description="Fonte primária do dado")
    dataset: str = Field(description="Dataset / tabela de origem")
    documento_id: str | None = Field(None, description="ID do documento na origem")
    linha_id: str | None = Field(None, description="UUID da linha original no banco de dados")
    data_referencia: date | None = Field(None, description="Data de referência do documento original")
    data_entrega: date | None = Field(None, description="Data de entrega do documento à CVM")
    link_download: str | None = Field(None, description="Link para download do documento oficial")


class MetricaFinanceira(BaseModel):
    valor_normalizado: float | None = Field(None, description="Valor absoluto em reais")
    valor_original: str | None = Field(None, description="Valor exatamente como reportado originalmente")
    yoy: float | None = Field(None, description="Percentual de variação ano contra ano (YoY)")
    qoq: float | None = Field(None, description="Percentual de variação trimestre contra trimestre anterior (QoQ)")
    cagr: float | None = Field(None, description="Taxa de crescimento anual composta (CAGR)")
    proveniencia: ReferenciaProveniencia | None = Field(None, description="Metadados de proveniência do dado contábil")


class PeriodoFinanceiro(BaseModel):
    periodo_label: str = Field(description="Label amigável do período (ex: 2024 ou 2024-3T)")
    ano: int = Field(description="Ano do período")
    trimestre: int = Field(description="Trimestre do período (1 a 4)")
    periodo_tipo: str = Field(description="Tipo do período: ANUAL ou TRIMESTRAL")
    metrics: dict[str, MetricaFinanceira] = Field(description="Dicionário de métricas financeiras chave")


class FinanceiroAnaliseResposta(BaseModel):
    cnpj_companhia: str
    codigo_cvm: int
    dados: list[PeriodoFinanceiro] = Field(description="Lista ordenada de períodos financeiros e suas métricas")


class DeltaComparativo(BaseModel):
    valor_base: float | None = Field(None, description="Valor no período/ano base")
    valor_comparacao: float | None = Field(None, description="Valor no período/ano de comparação")
    delta_absoluto: float | None = Field(None, description="Diferença absoluta (Base - Comparação)")
    delta_percentual: float | None = Field(None, description="Variação percentual")


class ComparativoAnaliseResposta(BaseModel):
    ano_base: int
    ano_comparacao: int
    financeiro: dict[str, DeltaComparativo] = Field(description="Deltas contábeis")
    capital: dict[str, DeltaComparativo] = Field(description="Deltas de composição acionária e ações")
    governanca: dict[str, DeltaComparativo] = Field(description="Deltas de estrutura do conselho/diretoria")
    pessoas: dict[str, DeltaComparativo] = Field(description="Deltas de força de trabalho e média salarial")
    mercado: dict[str, DeltaComparativo] = Field(description="Deltas de insider trading e tesouraria")
    eventos_ipe: DeltaComparativo | None = Field(None, description="Delta do total de eventos IPE")


class EventoLinhaTempo(BaseModel):
    data_evento: date = Field(description="Data da publicação/entrega do evento")
    familia_evento: str = Field(description="Família de origem: IPE, FRE, VLMO, CGVN, FCA, FINANCEIRO")
    tipo_evento: str = Field(description="Tipo específico de evento (ex: Fato Relevante, Reapresentação)")
    severidade: str = Field(description="Severidade: INFO, WARNING, CRITICAL")
    titulo: str = Field(description="Título do evento")
    explicacao: str = Field(description="Explicação ou descrição resumida do ocorrido")
    link_documento: str | None = Field(None, description="Link direto para download do documento na CVM")
    periodo_afetado: str | None = Field(None, description="Período correspondente (ex: 2024, 2024-3T)")


class PessoasRemuneracaoAno(BaseModel):
    ano: int
    total_remuneracao_conselho: float | None = Field(None, description="Remuneração anual total do Conselho de Administração")
    membros_conselho: int | None = Field(None, description="Quantidade de membros no Conselho")
    remuneracao_media_conselho: float | None = Field(None, description="Remuneração média por membro do Conselho")
    total_remuneracao_diretoria: float | None = Field(None, description="Remuneração anual total da Diretoria Estatutária")
    membros_diretoria: int | None = Field(None, description="Quantidade de membros na Diretoria")
    remuneracao_media_diretoria: float | None = Field(None, description="Remuneração média por membro da Diretoria")
    yoy_remuneracao_total: float | None = Field(None, description="Variação YoY da remuneração total somada")
    proporcao_feminino_conselho: float | None = Field(None, description="Proporção de mulheres no Conselho de Administração")
    proporcao_feminino_diretoria: float | None = Field(None, description="Proporção de mulheres na Diretoria Estatutária")
    relacoes_familiares_total: int = Field(0, description="Quantidade de relações familiares reportadas entre administradores")


class PessoasRemuneracaoResposta(BaseModel):
    cnpj_companhia: str
    codigo_cvm: int
    dados: list[PessoasRemuneracaoAno]


class MercadoInsidersResposta(BaseModel):
    cnpj_companhia: str
    codigo_cvm: int
    movimentacoes: list[dict[str, Any]] = Field(description="Histórico de movimentações de insiders agrupadas por ano/mês")
    concentracao_cargo: dict[str, float] = Field(description="Porcentagem de volume financeiro de negociação por tipo de cargo")
    tesouraria: list[dict[str, Any]] = Field(description="Ações detidas em tesouraria ao longo do tempo")
    capital_alteracoes: list[dict[str, Any]] = Field(description="Aumentos, reduções ou splits de capital")
    governanca_resumo: dict[str, int] = Field(description="Contagem de práticas de governança por status (Adotada, Não Adotada, etc.)")


class AnaliseConsolidadaResposta(BaseModel):
    companhia: dict[str, Any] = Field(description="Dados gerais da companhia")
    periodos_disponiveis: dict[str, list[str]] = Field(description="Lista de períodos disponíveis por tipo")
    cobertura: dict[str, list[str]] = Field(description="Grade de cobertura anual de dados")
    financeiro: list[PeriodoFinanceiro] = Field(description="Métricas financeiras chave por período")
    eventos: list[EventoLinhaTempo] = Field(description="Timeline de eventos relevantes")
    governanca: dict[str, Any] = Field(description="Práticas e flags de governança")
    pessoas_remuneracao: list[PessoasRemuneracaoAno] = Field(description="Remuneração e composição do board")
    mercado_insiders: dict[str, Any] = Field(description="Movimentações de mercado e insider trading")
    proveniencia: dict[str, Any] = Field(description="Sumário de proveniência dos blocos")
