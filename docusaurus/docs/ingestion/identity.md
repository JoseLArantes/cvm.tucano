---
title: Identidade e Auditoria
sidebar_position: 5
---

# Identidade e Auditoria

## Visão Geral

Endpoints para reconstruir o grafo de identidade e auditar fontes CVM.

---

## `POST /ingestion/identity/rebuild`

Reprocessa o cadastro para reconstruir a malha de identidade usada por DFP, ITR e FRE.

### Exemplo

```bash
curl -X POST "http://localhost:8007/ingestion/identity/rebuild" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

```json
{
  "status": "sucesso",
  "detalhe": {...}
}
```

### Quando Usar

- Após sincronização do cadastro
- Quando há muitas linhas em quarentena com `companhia_nao_encontrada`
- Após aplicar novas regras de reparo
- Quando o grafo de identidade está desatualizado

### Fluxo Recomendado

```bash
# 1. Sincronizar cadastro
POST /ingestion/sincronizacoes/cadastro

# 2. Reconstruir grafo de identidade
POST /ingestion/identity/rebuild

# 3. Replay da quarentena
POST /ingestion/replay/quarentena
{
  "reason_code": "companhia_nao_encontrada"
}
```

---

## `GET /ingestion/fontes`

Retorna catálogo interno de fontes CVM suportadas.

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/fontes" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `ListaFontesResposta`

```json
{
  "dados": [
    {
      "fonte": "cadastro",
      "familia": "cadastro_cvm",
      "descricao": "Cadastro de companhias abertas",
      "tipo_distribuicao": "csv_unico",
      "status_suporte": "suportado",
      "dependencias": [],
      "primeiro_ano": null,
      "ultimo_ano": null,
      "total_datasets": 2,
      "datasets_obrigatorios": 2,
      "datasets_opcionais": 0
    },
    {
      "fonte": "dfp",
      "familia": "documentos_financeiros",
      "descricao": "Demonstrações Financeiras Padronizadas",
      "tipo_distribuicao": "zip_anual",
      "status_suporte": "suportado",
      "dependencias": ["cadastro"],
      "primeiro_ano": 2010,
      "ultimo_ano": 2026,
      "total_datasets": 15,
      "datasets_obrigatorios": 15,
      "datasets_opcionais": 0
    }
  ]
}
```

---

## `GET /ingestion/fontes/{fonte}`

Retorna detalhe dos datasets conhecidos para uma fonte específica.

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `fonte` | string | Chave canônica da fonte (ex: `dfp`, `fre`) |

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/fontes/fre" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `FonteDetalheResposta`

```json
{
  "fonte": "fre",
  "familia": "formulario_referencia",
  "descricao": "Formulário de Referência",
  "tipo_distribuicao": "zip_anual",
  "status_suporte": "suportado",
  "dependencias": ["cadastro"],
  "primeiro_ano": 2010,
  "ultimo_ano": 2026,
  "total_datasets": 48,
  "datasets_obrigatorios": 9,
  "datasets_opcionais": 39,
  "obrigatorio": true,
  "dataset_path_template": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_{ano}.zip",
  "arquivo_principal_template": "fre_cia_aberta_{ano}.csv",
  "datasets": [
    {
      "dataset": "documentos",
      "descricao": "Cabeçalho documental do FRE",
      "member_name_template": "fre_cia_aberta_{ano}.csv",
      "row_kind": "fre_documento",
      "destino_promovido": "fre_documentos",
      "obrigatorio": true,
      "status_suporte": "suportado",
      "normalizador": "normalizar_fre_row",
      "chaves_relacao": ["cnpj_companhia", "data_referencia", "versao"],
      "observacoes": null
    },
    {
      "dataset": "auditores",
      "descricao": "Auditores independentes",
      "member_name_template": "fre_cia_aberta_auditor_{ano}.csv",
      "row_kind": "fre_auditor",
      "destino_promovido": "fre_auditores",
      "obrigatorio": true,
      "status_suporte": "suportado",
      "normalizador": "normalizar_fre_row",
      "chaves_relacao": ["id_documento", "versao", "data_referencia"],
      "observacoes": null
    }
  ]
}
```

---

## `POST /ingestion/fontes/auditar`

Executa auditoria on-demand das fontes CVM registradas.

### Request Body

**Schema:** `AuditoriaFontesRequisicao`

```json
{
  "ano": 2025,
  "fontes": ["dfp", "itr", "fre"]
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `ano` | integer | Ano de referência (opcional) |
| `fontes` | array | Lista de fontes a auditar (opcional, padrão: todas implementadas) |

### Exemplo

```bash
curl -X POST "http://localhost:8007/ingestion/fontes/auditar" \
  -H "Authorization: Bearer <token-admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "ano": 2025,
    "fontes": ["dfp", "fre"]
  }'
```

### Response 200

**Schema:** `AuditoriaFontesResposta`

```json
{
  "ano": 2025,
  "fontes": [
    {
      "fonte": "dfp",
      "familia": "documentos_financeiros",
      "descricao": "Demonstrações Financeiras Padronizadas",
      "status_suporte": "suportado",
      "artifact_type": "annual_zip_replacement",
      "update_cadence": "semanal",
      "remote_probe_strategy": "ckan_head_sha",
      "version_semantics": "preserve_all",
      "reconcile_policy": "member_replace",
      "ano": 2025,
      "url": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip",
      "arquivo_principal": "dfp_cia_aberta_2025.zip",
      "acessivel": true,
      "sha256": "abc123...",
      "tamanho_bytes": 10485760,
      "datasets_esperados": 15,
      "datasets_encontrados": 15,
      "datasets_faltantes": 0,
      "drift_summary": {
        "member_added": [],
        "member_removed": [],
        "required_member_missing": [],
        "optional_member_missing": []
      },
      "datasets": [
        {
          "dataset": "documentos",
          "membro_esperado": "dfp_cia_aberta_2025.csv",
          "encontrado": true,
          "row_kind": "dfp_documento",
          "destino_promovido": "documentos_financeiros",
          "obrigatorio": true,
          "status_suporte": "suportado",
          "normalizador": "normalizar_financeiro_row",
          "chaves_relacao": ["cnpj_companhia", "data_referencia", "versao"],
          "observacoes": null
        }
      ],
      "observacoes": null
    }
  ],
  "total_fontes": 2,
  "total_fontes_acessiveis": 2,
  "total_datasets_faltantes": 0,
  "novidades": {
    "ultima_atualizacao": "2026-06-15",
    "mudancas_estruturais": []
  }
}
```

### Campos Importantes

| Campo | Descrição |
|-------|-----------|
| `acessivel` | Se o arquivo principal respondeu com sucesso |
| `datasets_esperados` | Quantidade de datasets esperados no registry |
| `datasets_encontrados` | Quantidade de datasets encontrados no payload |
| `datasets_faltantes` | Quantidade de datasets ausentes |
| `drift_summary` | Resumo de drift estrutural detectado |
| `novidades` | Resumo consultivo da página oficial de novidades |

---

## Casos de Uso

### Caso 1: Auditoria Completa de Fontes

```bash
# Auditar todas as fontes para 2025
POST /ingestion/fontes/auditar
{
  "ano": 2025
}
```

### Caso 2: Auditoria de Fonte Específica

```bash
# Auditar apenas DFP e FRE
POST /ingestion/fontes/auditar
{
  "ano": 2025,
  "fontes": ["dfp", "fre"]
}
```

### Caso 3: Python - Auditoria Automatizada

```python
import httpx

def auditar_fontes(base_url, token, ano):
    """Audita todas as fontes para um ano e reporta problemas."""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = httpx.post(
        f"{base_url}/ingestion/fontes/auditar",
        json={"ano": ano},
        headers=headers
    )
    response.raise_for_status()
    
    resultado = response.json()
    
    print(f"Auditoria {ano}:")
    print(f"  Fontes acessíveis: {resultado['total_fontes_acessiveis']}/{resultado['total_fontes']}")
    print(f"  Datasets faltantes: {resultado['total_datasets_faltantes']}")
    
    for fonte in resultado["fontes"]:
        if fonte["datasets_faltantes"] > 0:
            print(f"  ⚠️ {fonte['fonte']}: {fonte['datasets_faltantes']} datasets faltando")
    
    return resultado

# Uso
resultado = auditar_fontes("http://localhost:8007", "seu-token", 2025)
```

---

## Notas para Usuários

### Para Operadores de Backoffice

- Use `/fontes` para verificar cobertura de fontes
- Use `/fontes/{fonte}` para detalhar datasets
- Execute auditoria antes de sincronizações críticas

### Para Auditores

- Use `/fontes/auditar` para validar integridade de fontes
- Monitore `drift_summary` para detectar mudanças estruturais
- Documente auditorias para compliance

### Para Compliance

- Valide `acessivel` antes de依赖 dados de uma fonte
- Monitore `datasets_faltantes` para gaps de cobertura
- Use `novidades` para entender mudanças regulatórias

---

## Próximos Passos

- [Conceitos](../concepts/ingestion-pipeline.md) - Entenda o pipeline completo
- [Modelo de Dados](../concepts/data-model.md) - Tabelas do sistema