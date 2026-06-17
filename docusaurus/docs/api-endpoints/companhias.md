---
title: Companhias
sidebar_position: 5
---

# Companhias

## Visão Geral

A entidade `companhia` é a **raiz do domínio** do Tucano CVM. Todos os dados financeiros (DFP, ITR), societários (FRE, FCA), eventos (IPE), negociações (VLMO) e governança (CGVN) se vinculam a uma companhia sempre que possível.

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/companhias` | Listar companhias com filtros |
| `GET` | `/companhias/codigo-cvm/{codigo_cvm}` | Obter companhia por código CVM |
| `GET` | `/companhias/{cnpj_companhia}` | Obter companhia por CNPJ |
| `GET` | `/companhias/mestre` | Consulta agregada (master endpoint) |
| `GET` | `/companhias/{codigo_cvm}/analise/*` | Endpoints de análise estratégica |

---

## `GET /companhias`

Lista paginada de companhias abertas normalizadas.

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `cnpj_companhia` | string | - | CNPJ com ou sem pontuação (ex: `08.773.135/0001-00` ou `08773135000100`) |
| `codigo_cvm` | integer | - | Código CVM da companhia |
| `nome` | string | - | Busca por nome (razão social ou comercial) |
| `situacao_registro` | string | - | Filtrar por situação (ex: `ATIVO`, `SUSPENSO(A) - DECISAO ADM`) |
| `ordenar` | string | `ativa_nome` | Ordenação: `ativa_nome`, `nome`, `codigo_cvm` |
| `pagina` | integer | `1` | Número da página (inicia em 1) |
| `tamanho_pagina` | integer | `100` | Itens por página (máx: 500) |

### Exemplo: Listar Companhias Ativas

```bash
curl -X GET "http://localhost:8007/companhias?situacao_registro=ATIVO&ordenar=ativa_nome&tamanho_pagina=50" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaCompanhiasResposta`

```json
{
  "dados": [
    {
      "id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
      "cnpj_companhia": "08773135000100",
      "codigo_cvm": 25224,
      "denominacao_social": "2W ECOBANK S.A. - EM RECUPERACAO JUDICIAL",
      "denominacao_comercial": "2W ECOBANK S.A.",
      "situacao_registro": "SUSPENSO(A) - DECISAO ADM",
      "data_registro": "2020-10-29",
      "data_constituicao": "2007-03-23",
      "data_cancelamento": null,
      "motivo_cancelamento": null,
      "data_inicio_situacao": "2026-05-19",
      "setor_atividade": "Energia Eletrica",
      "tipo_mercado": "Novo Mercado",
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
        "cep": "4711130",
        "pais": "BRASIL",
        "telefone": "39579400",
        "ddd_telefone": "11",
        "fax": "39579499",
        "ddd_fax": "11",
        "email": "ri@2wecobank.com.br"
      },
      "responsavel": {
        "nome_responsavel": "FERNANDO GUEDES VIEIRA",
        "tipo_responsavel": "DIRETOR DE RELACOES COM INVESTIDORES",
        "logradouro": "AV DR. CHUCRI ZAIDAN, 1550",
        "complemento": "8 AND-CONJ815-SL1",
        "bairro": "CHACARA STO. ANTONIO",
        "municipio": "SAO PAULO",
        "uf": "SP",
        "cep": "4711130",
        "telefone": "39579400",
        "ddd_telefone": "11",
        "email": "juridico@2wecobank.com.br",
        "data_inicio_responsavel": "2026-04-22"
      },
      "auditor": "GRANT THORNTON AUDITORES INDEPENDENTES LTDA.",
      "cnpj_auditor": "10830108000165",
      "criado_em": "2026-05-30T14:30:00Z",
      "sincronizado_em": "2026-05-30T14:30:00Z",
      "alterado_em": "2026-05-30T14:30:00Z"
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 50,
    "total": 1
  }
}
```

### Campos da Resposta

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID | Identificador interno estável |
| `cnpj_companhia` | string | CNPJ com 14 dígitos (sem pontuação) |
| `codigo_cvm` | integer | Código CVM da companhia |
| `denominacao_social` | string | Razão social completa |
| `denominacao_comercial` | string | Nome fantasia |
| `situacao_registro` | string | Situação atual (ATIVO, SUSPENSO, CANCELADO, etc.) |
| `data_registro` | date | Data de concessão do registro na CVM |
| `data_constituicao` | date | Data de fundação da companhia |
| `data_cancelamento` | date | Data de cancelamento (se houver) |
| `motivo_cancelamento` | string | Motivo do cancelamento |
| `data_inicio_situacao` | date | Data de início da situação atual |
| `setor_atividade` | string | Setor econômico |
| `tipo_mercado` | string | Segmento de listagem (Novo Mercado, Nível 2, etc.) |
| `categoria_registro` | string | Categoria A (ações) ou B (renda fixa) |
| `situacao_emissor` | string | Situação específica do emissor |
| `controle_acionario` | string | Tipo de controle (PRIVADO, ESTATAL, etc.) |
| `endereco` | object | Endereço estruturado |
| `responsavel` | object | Responsável cadastral |
| `auditor` | string | Nome do auditor independente |
| `cnpj_auditor` | string | CNPJ do auditor |
| `criado_em` | datetime | Timestamp da primeira inserção |
| `sincronizado_em` | datetime | Última vez que foi reencontrado na fonte |
| `alterado_em` | datetime | Última alteração real de negócio |

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `404` | Recurso não encontrado para os critérios informados |
| `422` | Parâmetro inválido |

---

## `GET /companhias/codigo-cvm/{codigo_cvm}`

Retorna uma companhia específica a partir do código CVM.

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `codigo_cvm` | integer | Código CVM da companhia (ex: `25224`) |

### Exemplo

```bash
curl -X GET "http://localhost:8007/companhias/codigo-cvm/25224" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `CompanhiaResposta` (mesmo formato do item da listagem)

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `404` | Companhia não encontrada |
| `422` | Parâmetro inválido |

---

## `GET /companhias/{cnpj_companhia}`

Retorna uma companhia específica a partir do CNPJ.

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ com ou sem pontuação (regex: `^[0-9./-]+$`) |

### Exemplos

```bash
# Com pontuação
curl -X GET "http://localhost:8007/companhias/08.773.135/0001-00" \
  -H "Authorization: Bearer <token>"

# Sem pontuação
curl -X GET "http://localhost:8007/companhias/08773135000100" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `CompanhiaResposta`

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `404` | Companhia não encontrada |
| `422` | Parâmetro inválido (CNPJ malformado) |

---

## `GET /companhias/mestre`

**Endpoint estratégico** que agrega a resposta de todos os grupos de endpoints de uma companhia em um único payload.

### Comportamento

Dado um `cnpj_companhia` ou `codigo_cvm`, o endpoint agrega:
- Cadastro da companhia
- Documentos DFP e ITR
- Composição de capital (DFP e ITR)
- Pareceres (DFP e ITR)
- Demonstrações financeiras (todas as combinações tipo/escopo)
- FRE (documentos, auditores, capital social, posição acionária, remuneração, empregados)
- IPE (documentos)

> **Importante:** Nas demonstrações financeiras agregadas, `valor_conta` já é entregue ajustado por `escala_moeda`, enquanto `valor_conta_reportado` preserva o número bruto do CSV da CVM.

### Query Parameters

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `cnpj_companhia` | string | Um dos dois | CNPJ da companhia |
| `codigo_cvm` | integer | Um dos dois | Código CVM da companhia |
| `limite_por_endpoint` | integer | Não (padrão: 100, máx: 500) | Máximo de itens por endpoint agregado |

### Exemplo

```bash
curl -X GET "http://localhost:8007/companhias/mestre?codigo_cvm=25224&limite_por_endpoint=50" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ConsultaCompanhiaMestreResposta`

```json
{
  "companhia": { "..." },
  "documentos_dfp": { "dados": [...], "paginacao": {...} },
  "documentos_itr": { "dados": [...], "paginacao": {...} },
  "composicao_capital_dfp": { "dados": [...], "paginacao": {...} },
  "composicao_capital_itr": { "dados": [...], "paginacao": {...} },
  "pareceres_dfp": { "dados": [...], "paginacao": {...} },
  "pareceres_itr": { "dados": [...], "paginacao": {...} },
  "demonstracoes": {
    "dfp_balanco_patrimonial_ativo_consolidado": {...},
    "dfp_balanco_patrimonial_ativo_individual": {...},
    "dfp_balanco_patrimonial_passivo_consolidado": {...},
    "dfp_demonstracao_resultado_consolidado": {...},
    "dfp_fluxo_caixa_metodo_direto_consolidado": {...},
    "dfp_fluxo_caixa_metodo_indireto_consolidado": {...},
    "dfp_mutacoes_patrimonio_liquido_consolidado": {...},
    "dfp_resultado_abrangente_consolidado": {...},
    "dfp_valor_adicionado_consolidado": {...},
    "itr_balanco_patrimonial_ativo_consolidado": {...}
  },
  "fre_documentos": {...},
  "fre_auditores": {...},
  "fre_capital_social": {...},
  "fre_posicao_acionaria": {...},
  "fre_remuneracao_total_orgao": {...},
  "fre_empregados_posicao_genero": {...},
  "ipe_documentos": {...}
}
```

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `404` | Companhia não encontrada |
| `422` | Filtro inválido (nenhum identificador informado) |

### Notas para Usuários

#### Para Analistas Financeiros
Use o endpoint mestre para obter uma visão completa da companhia em uma única chamada. Ideal para dashboards de análise fundamentalista.

#### Para Auditores
O endpoint mestre permite validar a consistência entre diferentes fontes (DFP vs FRE vs FCA) para a mesma companhia e período.

#### Para Operadores de Backoffice
Use `limite_por_endpoint` baixo (ex: 10) para previews rápidos, ou alto (500) para extrações completas.

---

## Casos de Uso Comuns

### Caso 1: Buscar Companhias por Setor

```bash
GET /companhias?setor_atividade=Energia&situacao_registro=ATIVO
```

### Caso 2: Buscar por Nome (Busca Parcial)

```bash
GET /companhias?nome=Petrobras
```

### Caso 3: Iterar Todas as Companhias

```python
import httpx

def todas_companhias(base_url, token):
    pagina = 1
    while True:
        response = httpx.get(
            f"{base_url}/companhias",
            params={"pagina": pagina, "tamanho_pagina": 500},
            headers={"Authorization": f"Bearer {token}"}
        )
        data = response.json()
        yield from data["dados"]
        if pagina * 500 >= data["paginacao"]["total"]:
            break
        pagina += 1
```

### Caso 4: Verificar Última Atualização

Compare `sincronizado_em` com a data atual para determinar o frescor dos dados:

```python
from datetime import datetime, timezone

companhia = response.json()
ultima_sync = datetime.fromisoformat(companhia["sincronizado_em"].replace("Z", "+00:00"))
idade_horas = (datetime.now(timezone.utc) - ultima_sync).total_seconds() / 3600

if idade_horas > 48:
    print(f"Dados desatualizados: {idade_horas:.1f} horas")
```

---

## Diferença entre `sincronizado_em` e `alterado_em`

| Campo | Quando Muda | Significado |
|-------|-------------|-------------|
| `sincronizado_em` | Toda sincronização | Registro foi reencontrado na fonte CVM |
| `alterado_em` | Apenas mudanças reais | Houve mudança em campos de negócio |

> **Importante para auditores:** Reapresentação regulatória não é igual a alteração econômica. A API diferencia esses dois conceitos.

---

## Próximos Passos

- [Fontes](./fontes.md) - Catálogo de fontes e datasets
- [Análise](./analise.md) - Endpoints estratégicos de análise