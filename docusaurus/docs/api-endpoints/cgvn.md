---
title: Código de Governança Corporativa (CGVN)
sidebar_position: 13
---

# Código de Governança Corporativa (CGVN)

## Visão Geral

O **CGVN** (Informe sobre o Código Brasileiro de Governança Corporativa - ICBGC) documenta a adesão das companhias às práticas recomendadas de governança corporativa, seguindo o modelo **"pratique ou explique"**.

## Endpoints Disponíveis

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/cgvn/documentos` | Listar documentos CGVN |
| `GET` | `/cgvn/praticas` | Listar práticas adotadas |

---

## `GET /cgvn/documentos`

Retorna os cabeçalhos documentais do CGVN.

### Exemplo

```bash
curl -X GET "http://localhost:8007/cgvn/documentos?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer <token>"
```

### Filtros Adicionais

| Parâmetro | Descrição |
|-----------|-----------|
| `id_documento` | Filtrar por ID do documento |
| `categoria` | Filtrar por categoria |

### Ordenação Permitida

`data_entrega`, `data_referencia`, `versao`, `cnpj_companhia`, `codigo_cvm`, `id_documento`, `categoria`

---

## `GET /cgvn/praticas`

Retorna práticas de governança declaradas pelas companhias.

### Query Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ com ou sem pontuação |
| `codigo_cvm` | integer | Código CVM da companhia |
| `data_referencia_inicio` / `data_referencia_fim` | date | Intervalo de datas |
| `ano_origem` / `ano_inicio` / `ano_fim` | integer | Filtros de ano |
| `versao` | integer | Versão específica |
| `id_documento` | integer | ID do documento |
| `id_item` | string | ID da prática (ex: `1.1.1`) |
| `pratica_adotada` | string | Status: `Sim`, `Não`, `Parcialmente`, `Não se Aplica` |
| `ordenar_por` | string | Campo de ordenação |
| `pagina` / `tamanho_pagina` | integer | Paginação |

### Exemplo: Práticas Não Adotadas

```bash
curl -X GET "http://localhost:8007/cgvn/praticas?codigo_cvm=25224&pratica_adotada=Nao&ano_inicio=2025" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaCgvnPraticasResposta`

```json
{
  "dados": [
    {
      "id": "...",
      "cnpj_companhia": "08773135000100",
      "nome_companhia": "EMPRESA A",
      "data_referencia": "2025-12-31",
      "id_documento": 12345,
      "versao": 1,
      "id_item": "1.1.1",
      "pratica_recomendada": "O Conselho de Administração deve ser composto por maioria de membros independentes",
      "pratica_adotada": "Sim",
      "capitulo": "Conselho de Administração",
      "principio": "Independência",
      "explicacao": null,
      "arquivo_origem": "cgvn_cia_aberta_praticas_2025.csv",
      "ano_origem": 2025,
      "linha_origem": 100
    },
    {
      "id": "...",
      "id_item": "2.3.4",
      "pratica_recomendada": "A companhia deve possuir comitê de auditoria",
      "pratica_adotada": "Não",
      "capitulo": "Comitês",
      "principio": "Transparência",
      "explicacao": "A companhia não possui comitê de auditoria devido ao seu porte reduzido",
      "arquivo_origem": "cgvn_cia_aberta_praticas_2025.csv",
      "ano_origem": 2025,
      "linha_origem": 101
    }
  ],
  "paginacao": { "pagina": 1, "tamanho_pagina": 100, "total": 2 }
}
```

### Ordenação Permitida

`data_referencia`, `versao`, `cnpj_companhia`, `id_documento`, `id_item`, `pratica_adotada`

---

## Estrutura das Práticas

As práticas são organizadas hierarquicamente:

| Campo | Descrição |
|-------|-----------|
| `id_item` | Código hierárquico (ex: `1.1.1`, `2.3.4`) |
| `capitulo` | Tema principal (Conselho, Auditoria, Remuneração, etc.) |
| `principio` | Princípio de governança associado |
| `pratica_recomendada` | Texto da prática recomendada |
| `pratica_adotada` | Status de adoção |
| `explicacao` | Justificativa quando não adotada |

## Status de Adoção

| Valor | Significado |
|-------|-------------|
| `Sim` | Prática totalmente adotada |
| `Não` | Prática não adotada (deve haver explicação) |
| `Parcialmente` | Prática parcialmente adotada |
| `Não se Aplica` | Prática não aplicável à companhia |

---

## Casos de Uso

### Caso 1: Calcular Score de Governança

```python
import httpx

def calcular_score_governanca(base_url, token, codigo_cvm, ano):
    """Calcula score de governança baseado nas práticas adotadas."""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = httpx.get(
        f"{base_url}/cgvn/praticas",
        params={"codigo_cvm": codigo_cvm, "ano_inicio": ano, "ano_fim": ano},
        headers=headers
    )
    praticas = response.json()["dados"]
    
    total = len(praticas)
    nao_aplica = sum(1 for p in praticas if p["pratica_adotada"] == "Não se Aplica")
    adotadas = sum(1 for p in praticas if p["pratica_adotada"] == "Sim")
    parcialmente = sum(1 for p in praticas if p["pratica_adotada"] == "Parcialmente")
    
    score = (adotadas + parcialmente * 0.5) / (total - nao_aplica) * 100
    
    return {
        "score": round(score, 2),
        "total_praticas": total,
        "adotadas": adotadas,
        "parcialmente": parcialmente,
        "nao_adotadas": total - adotadas - parcialmente - nao_aplica,
        "nao_aplica": nao_aplica
    }

# Uso
score = calcular_score_governanca("http://localhost:8007", "seu-token", 25224, 2025)
print(f"Score de Governança: {score['score']}%")
```

### Caso 2: Comparar Adoção entre Companhias

```bash
# Práticas de Conselho de Administração
GET /cgvn/praticas?id_item=1.1.1&ano_inicio=2025&ordenar_por=pratica_adotada
```

### Caso 3: Identificar Práticas Não Adotadas com Explicação

```bash
GET /cgvn/praticas?pratica_adotada=Nao&ano_inicio=2025
```

### Caso 4: JavaScript - Dashboard de Governança

```javascript
async function dashboardGovernanca(codigoCvm, token) {
  const response = await fetch(
    `http://localhost:8007/cgvn/praticas?codigo_cvm=${codigoCvm}&ano_inicio=2025`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  
  const { dados } = await response.json();
  
  // Agrupar por capítulo
  const porCapitulo = dados.reduce((acc, pratica) => {
    const cap = pratica.capitulo || 'Sem Capítulo';
    if (!acc[cap]) acc[cap] = { total: 0, adotadas: 0 };
    acc[cap].total++;
    if (pratica.pratica_adotada === 'Sim') acc[cap].adotadas++;
    return acc;
  }, {});
  
  return porCapitulo;
}
```

---

## Notas para Usuários

### Para Analistas Financeiros
- Use `/cgvn/praticas` para calcular scores de governança
- Cruze com `/fre/remuneracao/total-por-orgao` para avaliar qualidade da gestão
- `/analise/mercado-insiders` fornece visão consolidada de governança

### Para Auditores
- Use `pratica_adotada=Não` para identificar áreas de risco
- Valide `explicacao` para práticas não adotadas
- Cruze com `/fre/auditores` para avaliar independência

### Para Operadores de Backoffice
- Use `/cgvn/documentos` para monitorar entregas
- Use `/cgvn/praticas` com filtros por `id_item` para análises específicas
- Monitore `versao` para identificar reapresentações

### Para Compliance
- **Score de Governança**: calcule periodicamente para benchmarking
- **Práticas Não Adotadas**: monitore explicações para identificar riscos
- **Evolução Temporal**: compare scores entre anos para avaliar maturidade
- **Setor**: compare scores dentro do mesmo setor para benchmarking competitivo

---

## Próximos Passos

- [Ingestion](../ingestion/monitoring.md) - Monitoramento de sincronizações
- [Padroes Transversais](./common-patterns.md) - Padroes transversais da API
