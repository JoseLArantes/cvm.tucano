---
title: Schemas de Ingestion
sidebar_position: 6
---

# Schemas de Ingestion (Pipeline de Dados)

## `IngestionRunResumo`

Resumo de uma run do pipeline de ingestão.

### Schema

```python
class IngestionRunResumo(BaseModel):
    id: str
    execucao_sincronizacao_id: Optional[str]
    tipo_fonte: str
    ano: Optional[int]
    status: str
    phase: str
    remote_probe: Optional[Dict[str, Any]]
    change_summary: Optional[Dict[str, Any]]
    quality_summary: Optional[Dict[str, Any]]
    artifact_snapshot: Optional[Dict[str, Any]]
    member_snapshot_summary: Optional[Dict[str, Any]]
    delivery_snapshot_summary: Optional[Dict[str, Any]]
    reconcile_summary: Optional[Dict[str, Any]]
    rows_reconciled_deleted: Optional[int]
    lifecycle_decision: Optional[Dict[str, Any]]
```

### Status Possíveis

| Status | Descrição |
|--------|-----------|
| `em_execucao` | Run ativa |
| `sucesso` | Processamento completo sem alerta |
| `sucesso_com_alerta` | Concluída com drift estrutural ou alerta operacional |
| `falha` | Erro impeditivo |
| `sem_alteracao` | Recurso CVM igual à referência anterior |
| `skipped` | Reaproveitamento administrativo legado |
| `cancelada` | Interrupção administrativa |

### Fases (`phase`)

| Fase | Descrição |
|------|-----------|
| `acquire` | Preflight remoto + download |
| `stage` | Extração de membros, headers, contagem |
| `promote` | Normalização, resolução, escrita |
| `reconcile` | Remoção de linhas obsoletas |
| `complete` | Encerramento da run |

### Exemplo JSON

```json
{
  "id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
  "execucao_sincronizacao_id": "02be26d3-8db8-48a1-bcd0-4737b8157116",
  "tipo_fonte": "dfp",
  "ano": 2025,
  "status": "sucesso_com_alerta",
  "phase": "complete",
  "remote_probe": {
    "dataset_url": "https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp",
    "decision": "changed",
    "decision_reason": "metadata_changed:resource_last_modified",
    "probe_sources": ["ckan", "head"],
    "resource_last_modified": "Mon, 09 Jun 2026 08:03:41 GMT"
  },
  "change_summary": {
    "member_added": [],
    "member_removed": ["dfp_cia_aberta_DVA_ind_2025.csv"],
    "header_changed": [
      {
        "member_name": "dfp_cia_aberta_DRE_ind_2025.csv",
        "before": ["CNPJ_CIA", "DT_REFER", "VERSAO"],
        "after": ["CNPJ_CIA", "DT_REFER", "VERSAO", "COLUNA_DF"]
      }
    ]
  },
  "quality_summary": {
    "members_total": 14,
    "members_processados": 13,
    "members_skipped": 1,
    "row_status_counts": {"valid": 1200, "invalid": 3},
    "reason_counts": {"companhia_nao_encontrada": 2, "schema_inesperado": 1},
    "quarantine_total": 3,
    "staged_rows_purged": 1197,
    "reconciled_deleted": 4
  },
  "rows_reconciled_deleted": 4
}
```

---

## `ExecucaoSincronizacaoDetalhe`

Detalhamento completo de uma execução.

### Schema

```python
class ExecucaoSincronizacaoDetalhe(BaseModel):
    id_tarefa: Optional[str]
    tipo_fonte: str
    ano: Optional[int]
    arquivo: str
    url: str
    hash_arquivo: Optional[str]
    status: str
    iniciada_em: datetime
    finalizada_em: Optional[datetime]
    total_linhas_lidas: int
    total_inseridos: int
    total_atualizados: int
    total_inalterados: int
    total_rejeitados: int
    mensagem_erro: Optional[str]
    analise_arquivos: Optional[List[AnaliseArquivo]]
    id_execucao_pai: Optional[str]
    tipo_execucao: Optional[str]
    arquivo_principal: Optional[str]
    filhos_total: Optional[int]
    filhos_concluidos: Optional[int]
    filhos_falha: Optional[int]
    filhos_em_andamento: Optional[int]
    execucoes_filhas: Optional[List[ExecucaoSincronizacaoResumo]]
```

### `AnaliseArquivo`

```python
class AnaliseArquivo(BaseModel):
    file_name: str
    file_size: str  # "2.5 MB"
    rows_count: int
    columns_count: int
    header_columns: List[str]
    encoding: Optional[str]
    delimiter: str
```

---

## `QuarantineItemResposta`

Item na fila de reparo da quarentena.

### Schema

```python
class QuarantineItemResposta(BaseModel):
    id: str
    ingestion_run_id: Optional[str]
    ingestion_row_id: str
    arquivo_origem: str
    ano_origem: Optional[int]
    linha_origem: Optional[int]
    row_kind: str
    status: str  # pendente, resolvido_auto, resolvido_manual, ignorado
    motivo_codigo: str
    severidade: str  # error, warning
    reparavel: bool
    tentativas_reprocessamento: int
    diagnostico: Optional[Dict[str, Any]]
```

Consultas à fila de reparo usam `status=pendente` como padrão implícito. Use `status=all` para listar também itens já resolvidos.

### Códigos de Motivo (`motivo_codigo`)

| Código | Descrição | Reparável |
|--------|-----------|-----------|
| `normalizacao_invalida` | Erro de conversão/parse ou falha de BD | Não |
| `companhia_nao_encontrada` | Empresa não encontrada no grafo | Sim |
| `companhia_ambigua` | CNPJ e CVM conflitantes | Sim |
| `chave_natural_duplicada_conflitante` | Chave duplicada com dados divergentes | Sim |
| `schema_inesperado` | Colunas obrigatórias ausentes | Sim* |
| `denominacao_social_ausente` | Não foi possível extrair denominação | Não |
| `identidade_ausente` | Nem CNPJ nem CVM disponíveis | Não |

*`schema_inesperado` é tratado em nível de membro, não explode em milhares de itens.

### Exemplo JSON

```json
{
  "id": "0ebc5c67-25a4-4e0c-ab25-66eaf4af4ced",
  "ingestion_run_id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
  "ingestion_row_id": "9b3a4f45-b7ab-4de6-a93d-95f85913df71",
  "arquivo_origem": "itr_cia_aberta_2021.csv",
  "ano_origem": 2021,
  "linha_origem": 1692,
  "row_kind": "itr_documento",
  "status": "pendente",
  "motivo_codigo": "companhia_nao_encontrada",
  "severidade": "error",
  "reparavel": true,
  "tentativas_reprocessamento": 1,
  "diagnostico": {
    "codigo_cvm": 3,
    "denominacao_companhia": "EMPRESA FINANCEIRA",
    "resolution_method": "none"
  }
}
```

---

## `QuarentenaResumoResposta`

Resumo analítico da quarentena.

### Schema

```python
class QuarentenaResumoResposta(BaseModel):
    total: int
    por_status: Dict[str, int]
    por_erro: List[ErroQuantidade]
    por_arquivo: List[ArquivoQuantidade]
    por_arquivo_e_erro: List[ArquivoErroQuantidade]
```

### Schemas Auxiliares

```python
class ErroQuantidade(BaseModel):
    motivo_codigo: str
    quantidade: int

class ArquivoQuantidade(BaseModel):
    arquivo_origem: str
    quantidade: int

class ArquivoErroQuantidade(BaseModel):
    arquivo_origem: str
    motivo_codigo: str
    quantidade: int
```

### Exemplo JSON

```json
{
  "total": 42,
  "por_status": {
    "pendente": 35,
    "resolvido_auto": 5,
    "resolvido_manual": 2
  },
  "por_erro": [
    {"motivo_codigo": "companhia_nao_encontrada", "quantidade": 28},
    {"motivo_codigo": "normalizacao_invalida", "quantidade": 10}
  ],
  "por_arquivo": [
    {"arquivo_origem": "itr_cia_aberta_2021.csv", "quantidade": 15},
    {"arquivo_origem": "dfp_cia_aberta_2022.csv", "quantidade": 12}
  ],
  "por_arquivo_e_erro": [
    {
      "arquivo_origem": "itr_cia_aberta_2021.csv",
      "motivo_codigo": "companhia_nao_encontrada",
      "quantidade": 10
    }
  ]
}
```

---

## `ReplayQuarantineRequisicao`

Request body para `POST /ingestion/replay/quarentena`.

### Schema

```python
class ReplayQuarantineRequisicao(BaseModel):
    reason_code: Optional[str] = Field(
        description="Filtra replay por motivo estável de quarentena."
    )
    arquivo_origem: Optional[str] = Field(
        description="Restringe o replay a um arquivo de origem específico."
    )
    ano: Optional[int] = Field(
        description="Restringe o replay a um ano de origem específico."
    )
```

### Exemplo JSON

```json
{
  "reason_code": "companhia_nao_encontrada",
  "arquivo_origem": "itr_cia_aberta_2021.csv",
  "ano": 2021
}
```

---

## `ReplayResposta`

Response para endpoints de replay.

### Schema

```python
class ReplayResposta(BaseModel):
    status: str  # "sucesso"
    detalhe: Optional[Dict[str, Any]]
```

### Exemplo JSON

```json
{
  "status": "sucesso",
  "detalhe": {
    "total": 10,
    "promovidos": 8,
    "inalterados": 1,
    "falhas": 1,
    "items": [
      {"row_id": "...", "status": "promovido"},
      {"row_id": "...", "status": "falha", "erro": "..."}
    ]
  }
}
```

---

## `RespostaAgendamentoSincronizacao`

Response para endpoints de disparo de sincronização.

### Schema

```python
class RespostaAgendamentoSincronizacao(BaseModel):
    id_tarefa: str = Field(description="Identificador da task assíncrona (Celery).")
    status: str = Field(description="Estado inicial. Valor esperado: 'agendada'.")
```

### Exemplo JSON

```json
{
  "id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367",
  "status": "agendada"
}
```

---

## `RespostaAgendamentoEmLote`

Response para `POST /ingestion/sincronizacoes/tudo/{ano}`.

### Schema

```python
class RespostaAgendamentoEmLote(BaseModel):
    status: str
    tarefas: List[TarefaAgendadaResumo]

class TarefaAgendadaResumo(BaseModel):
    tipo_fonte: str
    ano: Optional[int]
    id_tarefa: str
```

### Exemplo JSON

```json
{
  "status": "agendada",
  "tarefas": [
    {"tipo_fonte": "cadastro", "ano": null, "id_tarefa": "task-1-uuid"},
    {"tipo_fonte": "dfp", "ano": 2025, "id_tarefa": "task-2-uuid"},
    {"tipo_fonte": "itr", "ano": 2025, "id_tarefa": "task-3-uuid"}
  ]
}
```

---

## `DashboardExecucoesResposta`

Response para `GET /ingestion/dashboard`.

### Schema

```python
class DashboardExecucoesResposta(BaseModel):
    total_execucoes: int
    total_sucesso: int
    total_sem_alteracao: int
    total_falha: int
    total_rejeitados: int
    ultimas_execucoes: List[ExecucaoSincronizacaoResumo]
```

### Exemplo JSON

```json
{
  "total_execucoes": 150,
  "total_sucesso": 145,
  "total_sem_alteracao": 3,
  "total_falha": 2,
  "total_rejeitados": 42,
  "ultimas_execucoes": [...]
}
```

---

## `SolicitacaoCancelamentoSincronizacao`

Request body para `POST /ingestion/sincronizacoes/cancelar`.

### Schema

```python
class SolicitacaoCancelamentoSincronizacao(BaseModel):
    id_execucao: Optional[str] = Field(
        description="ID da execução registrada. Use este seletor quando a sincronização já aparece em /ingestion/sincronizacoes."
    )
    id_tarefa: Optional[str] = Field(
        description="ID da task Celery retornado no disparo. Use este seletor quando a execução ainda não apareceu na listagem."
    )
    terminar_imediatamente: bool = Field(
        default=True,
        description="Quando true, envia revogação com terminate=True e sinal SIGTERM ao worker Celery."
    )
    motivo: Optional[str] = Field(
        max_length=1000,
        description="Motivo livre para auditoria operacional."
    )
```

### Validação

**Importante:** Envie **exatamente um** seletor: `id_execucao` **ou** `id_tarefa`. Se ambos forem enviados, a API rejeita com `422`.

### Exemplo JSON

```json
{
  "id_execucao": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
  "terminar_imediatamente": true,
  "motivo": "Execução duplicada do mesmo ano."
}
```

---

## `RespostaCancelamentoSincronizacao`

Response para `POST /ingestion/sincronizacoes/cancelar`.

### Schema

```python
class RespostaCancelamentoSincronizacao(BaseModel):
    id_execucao: Optional[str]
    id_tarefa: Optional[str]
    execucao_encontrada: bool
    status_execucao: Optional[str]
    revogacao_solicitada: bool
    terminar_imediatamente: bool
    mensagem: str
```

### Exemplo JSON

```json
{
  "id_execucao": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
  "id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367",
  "execucao_encontrada": true,
  "status_execucao": "cancelada",
  "revogacao_solicitada": true,
  "terminar_imediatamente": true,
  "mensagem": "Sincronização cancelada com sucesso."
}
```
