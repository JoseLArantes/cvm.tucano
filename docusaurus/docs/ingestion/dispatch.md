---
title: Disparo de Sincronizações
sidebar_position: 2
---

# Disparo de Sincronizações

## Visão Geral

Endpoints para disparar sincronizações administrativas de fontes CVM. Todos exigem permissão administrativa.

---

## `POST /ingestion/sincronizacoes/cadastro`

Dispara sincronização completa do cadastro de companhias abertas.

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `force_reimport` | boolean | `false` | Força reprocessamento mesmo se hash já existir |

### Exemplo

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/cadastro" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `RespostaAgendamentoSincronizacao`

```json
{
  "id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367",
  "status": "agendada"
}
```

---

## `POST /ingestion/sincronizacoes/dfp/{ano}`

Dispara sincronização DFP para um ano específico.

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `ano` | integer | Ano do pacote DFP (mín: 2010) |

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `force_reimport` | boolean | `false` | Força reprocessamento |

### Exemplo

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/dfp/2025" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

```json
{
  "id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367",
  "status": "agendada"
}
```

---

## Endpoints Similares para Outras Fontes

Os seguintes endpoints seguem o mesmo padrão do DFP:

| Endpoint | Ano Mínimo | Descrição |
|----------|------------|-----------|
| `POST /ingestion/sincronizacoes/itr/{ano}` | 2010 | Informações Trimestrais |
| `POST /ingestion/sincronizacoes/fre/{ano}` | 2010 | Formulário de Referência |
| `POST /ingestion/sincronizacoes/fca/{ano}` | 2010 | Formulário Cadastral |
| `POST /ingestion/sincronizacoes/ipe/{ano}` | 2003 | Informações Periódicas e Eventuais |
| `POST /ingestion/sincronizacoes/vlmo/{ano}` | 2018 | Valores Mobiliários |
| `POST /ingestion/sincronizacoes/cgvn/{ano}` | 2018 | Governança Corporativa |

### Exemplo: Sincronizar ITR 2024

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/itr/2024" \
  -H "Authorization: Bearer <token-admin>"
```

---

## `POST /ingestion/sincronizacoes/tudo/{ano}`

Dispara sincronização completa de todas as fontes para um ano específico.

### Comportamento

1. Dispara primeiro a sincronização de `cadastro`
2. Na sequência, agenda `dfp`, `itr`, `fre`, `fca`, `ipe`, `vlmo` e `cgvn` para o mesmo ano
3. **Não usa** `ANOS_INICIAIS_*` do ambiente: o ano processado é exclusivamente o argumento recebido

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `ano` | integer | Ano para todas as sincronizações (mín: 2003) |

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `force_reimport` | boolean | `false` | Força reprocessamento |

### Exemplo

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/tudo/2025" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `RespostaAgendamentoEmLote`

```json
{
  "status": "agendada",
  "tarefas": [
    {
      "tipo_fonte": "cadastro",
      "ano": null,
      "id_tarefa": "task-1-uuid"
    },
    {
      "tipo_fonte": "dfp",
      "ano": 2025,
      "id_tarefa": "task-2-uuid"
    },
    {
      "tipo_fonte": "itr",
      "ano": 2025,
      "id_tarefa": "task-3-uuid"
    }
  ]
}
```

---

## `POST /ingestion/sincronizacoes/reprocessar-arquivo`

Dispara reprocessamento seletivo por nome de arquivo CVM.

Use este endpoint para recuperacao cirurgica. No fluxo atual, um rerun anual normal da mesma fonte/ano ja tenta reaproveitar automaticamente members bem-sucedidos e inalterados por `member_sha256`, inclusive quando a execucao anual anterior terminou em `falha`. Portanto, o caso comum de "apenas 3 arquivos falharam dentro de 19" deve ser resolvido pelo rerun anual, nao por obrigacao de reprocessamento member a member.

### Request Body

```json
{
  "arquivo": "dfp_cia_aberta_2025.zip",
  "ano": 2025,
  "force_reimport": true
}
```

### Arquivos Aceitos

- `cad_cia_aberta.csv`
- `dfp_cia_aberta_*`
- `itr_cia_aberta_*`
- `fre_cia_aberta_*`
- `fca_cia_aberta_*`
- `ipe_cia_aberta_*`
- `vlmo_cia_aberta_*`
- `cgvn_cia_aberta_*`

A validacao do campo `arquivo` e case-insensitive. Isso inclui members com siglas em
maiusculas no nome do CSV, como `itr_cia_aberta_BPA_con_2026.csv`. Depois da validacao,
o backend preserva o nome canonico do arquivo ao gravar a execucao filha e ao extrair o
member do ZIP.

### Exemplo

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/reprocessar-arquivo" \
  -H "Authorization: Bearer <token-admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "arquivo": "fre_cia_aberta_2025.csv",
    "ano": 2025,
    "force_reimport": true
  }'
```

### Response 200

```json
{
  "status": "agendada",
  "tarefas": [...]
}
```

## Semantica de rerun anual

Nos endpoints anuais (`/ingestion/sincronizacoes/{fonte}/{ano}` e `/ingestion/sincronizacoes/tudo/{ano}`):

- o ZIP anual continua passando por probe remoto e, quando necessario, download
- se o ZIP mudou ou se a recuperacao exigir nova avaliacao, cada member e comparado por `member_sha256`
- members ja bem-sucedidos e inalterados sao reaproveitados e aparecem como `member_skipped` no inventario de snapshots
- members falhados, interrompidos, ausentes ou alterados seguem para processamento
- `force_reimport=true` desliga esse reaproveitamento e reprocessa tudo

---

## Execução em Duas Fases (Manual)

### `POST /ingestion/sincronizacoes/pre-processar/cadastro`

Executa apenas a **Fase 1** (download, extração e análise de metadados) do cadastro.

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/pre-processar/cadastro" \
  -H "Authorization: Bearer <token-admin>"
```

### `POST /ingestion/sincronizacoes/pre-processar/{tipo_fonte}/{ano}`

Executa apenas a **Fase 1** para uma fonte anual específica.

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/pre-processar/dfp/2025" \
  -H "Authorization: Bearer <token-admin>"
```

### `POST /ingestion/sincronizacoes/{id_execucao}/ingerir`

Dispara a **Fase 2** (ingestão dos dados) para uma execução que está no status `aguardando_ingestao`.

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/6a31c7f8-1c89-4f3d-87db-7e6a8e196999/ingerir" \
  -H "Authorization: Bearer <token-admin>"
```

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `400` | Execução não está no status `aguardando_ingestao` |
| `404` | Execução não encontrada |

---

## Casos de Uso

### Caso 1: Sincronização Diária Rotineira

```bash
# Sincronizar cadastro (diário)
POST /ingestion/sincronizacoes/cadastro

# Sincronizar DFP do ano corrente
POST /ingestion/sincronizacoes/dfp/2025
```

### Caso 2: Backfill de Anos Históricos

```bash
# Sincronizar todos os anos de 2010 a 2025
for ano in {2010..2025}; do
  curl -X POST "http://localhost:8007/ingestion/sincronizacoes/dfp/$ano" \
    -H "Authorization: Bearer <token-admin>"
done
```

### Caso 3: Reprocessamento Após Correção de Bug

```bash
# 1. Corrigir bug no normalizador
# 2. Deploy
# 3. Forçar reprocessamento
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/dfp/2025?force_reimport=true" \
  -H "Authorization: Bearer <token-admin>"
```

### Caso 4: Python - Sincronização Automatizada

```python
import httpx

def sincronizar_ano(base_url, token, ano):
    """Sincroniza todas as fontes para um ano."""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = httpx.post(
        f"{base_url}/ingestion/sincronizacoes/tudo/{ano}",
        headers=headers
    )
    response.raise_for_status()
    
    tarefas = response.json()["tarefas"]
    print(f"Disparadas {len(tarefas)} tarefas para {ano}")
    
    return tarefas

# Uso
tarefas = sincronizar_ano("http://localhost:8007", "seu-token", 2025)
```

---

## Notas para Usuários

### Para Operadores de Backoffice

- Use `/tudo/{ano}` para sincronizações completas
- Monitore o dashboard após o disparo
- Use `force_reimport=true` apenas quando necessário

### Para Auditores

- Prefira execução em duas fases para inspeção intermediária
- Use `/pre-processar` para validar metadados antes da ingestão
- Monitore `change_summary` para detectar drift estrutural

### Para Compliance

- Documente todos os disparos com `force_reimport=true`
- Use `/reprocessar-arquivo` para correções pontuais
- Monitore quarentena após reprocessamentos

---

## Próximos Passos

- [Monitoramento](./monitoring.md) - Acompanhar execuções
- [Quarentena e Replay](./quarantine.md) - Tratar erros
