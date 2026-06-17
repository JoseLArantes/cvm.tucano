---
title: Informações Periódicas e Eventuais (IPE)
sidebar_position: 11
---

# Informações Periódicas e Eventuais (IPE)

## Visão Geral

O **IPE** é a fonte primária para monitoramento de eventos corporativos: fatos relevantes, avisos aos acionistas, assembleias, alterações estatutárias, políticas corporativas e outros documentos regulatórios.

## Endpoints Disponíveis

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/ipe/documentos` | Listar documentos IPE |
| `GET` | `/ipe/documentos/agregados` | Contagem agrupada por ano/categoria/tipo |

---

## `GET /ipe/documentos`

Retorna documentos periódicos e eventuais com paginação e filtros.

### Query Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ com ou sem pontuação |
| `codigo_cvm` | integer | Código CVM da companhia |
| `data_referencia_inicio` | date | Data inicial do evento (YYYY-MM-DD) |
| `data_referencia_fim` | date | Data final do evento (YYYY-MM-DD) |
| `data_entrega_inicio` | date | Data inicial de entrega |
| `data_entrega_fim` | date | Data final de entrega |
| `categoria` | string | Categoria do documento |
| `tipo` | string | Tipo do documento |
| `especie` | string | Espécie do documento |
| `assunto` | string | Assunto do documento |
| `ano_origem` / `ano_inicio` / `ano_fim` | integer | Filtros de ano |
| `versao` | integer | Versão específica |
| `ordenar_por` | string | Campo de ordenação |
| `pagina` / `tamanho_pagina` | integer | Paginação |

### Categorias Comuns

- `Fato Relevante`
- `Aviso aos Acionistas`
- `Assembleia`
- `Estatuto Social`
- `Acordo de Acionistas`
- `Calendário de Eventos Corporativos`
- `Comunicado ao Mercado`
- `Política de Dividendos`
- `Política de Negociação`
- `Política de Sustentabilidade`
- `Regimento Interno`
- `Relatório de Sustentabilidade`
- `OPA - Edital de Oferta Pública de Ações`
- `Plano de Remuneração Baseada em Ações`

### Exemplo: Fatos Relevantes Recentes

```bash
curl -X GET "http://localhost:8007/ipe/documentos?categoria=Fato%20Relevante&data_entrega_inicio=2026-01-01&ordenar_por=-data_entrega" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaIpeDocumentosResposta`

```json
{
  "dados": [
    {
      "id": "...",
      "cnpj_companhia": "08773135000100",
      "codigo_cvm": 25224,
      "nome_companhia": "EMPRESA A",
      "data_referencia": "2026-05-15",
      "categoria": "Fato Relevante",
      "tipo": "Resultado",
      "especie": "Trimestral",
      "assunto": "Resultado do 1T26",
      "data_entrega": "2026-05-15",
      "tipo_apresentacao": "Consolidado",
      "protocolo_entrega": "123456",
      "versao": 1,
      "link_download": "https://dados.cvm.gov.br/...",
      "arquivo_origem": "ipe_cia_aberta_2026.csv",
      "ano_origem": 2026,
      "linha_origem": 100
    }
  ],
  "paginacao": { "pagina": 1, "tamanho_pagina": 100, "total": 1 }
}
```

### Ordenação Permitida

`data_entrega`, `data_referencia`, `versao`, `cnpj_companhia`, `codigo_cvm`, `categoria`

---

## `GET /ipe/documentos/agregados`

Retorna contagem de documentos IPE agrupados por dimensões específicas. Ideal para dashboards e análise de distribuição.

### Query Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `agrupar_por` | string | Campos separados por vírgula: `ano`, `categoria`, `tipo`, `especie` |
| (demais filtros) | - | Mesmos filtros do endpoint `/ipe/documentos` |

### Exemplo: Agrupar por Ano e Categoria

```bash
curl -X GET "http://localhost:8007/ipe/documentos/agregados?codigo_cvm=25224&agrupar_por=ano,categoria" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaIpeDocumentosAgregadosResposta`

```json
{
  "dados": [
    {
      "ano": 2026,
      "categoria": "Fato Relevante",
      "total": 45
    },
    {
      "ano": 2026,
      "categoria": "Aviso aos Acionistas",
      "total": 12
    },
    {
      "ano": 2025,
      "categoria": "Fato Relevante",
      "total": 38
    }
  ]
}
```

### Exemplo: Agrupar por Categoria e Tipo

```bash
GET /ipe/documentos/agregados?agrupar_por=categoria,tipo&ano_inicio=2025
```

---

## Casos de Uso

### Caso 1: Monitorar Fatos Relevantes em Tempo Real

```bash
# Fatos relevantes das últimas 24 horas
GET /ipe/documentos?categoria=Fato%20Relevante&data_entrega_inicio=2026-06-16&ordenar_por=-data_entrega
```

### Caso 2: Dashboard de Categorias

```bash
# Total de documentos por categoria no ano atual
GET /ipe/documentos/agregados?agrupar_por=categoria&ano_inicio=2026
```

### Caso 3: Python - Alertas de Fatos Relevantes

```python
import httpx
from datetime import datetime, timedelta

def verificar_fatos_relevantes(base_url, token, codigos_cvm):
    """Verifica fatos relevantes recentes para uma lista de companhias."""
    headers = {"Authorization": f"Bearer {token}"}
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    fatos = []
    for codigo_cvm in codigos_cvm:
        response = httpx.get(
            f"{base_url}/ipe/documentos",
            params={
                "codigo_cvm": codigo_cvm,
                "categoria": "Fato Relevante",
                "data_entrega_inicio": ontem,
                "ordenar_por": "-data_entrega"
            },
            headers=headers
        )
        fatos.extend(response.json()["dados"])
    
    return fatos

# Uso
fatos = verificar_fatos_relevantes("http://localhost:8007", "seu-token", [25224, 1023])
for fato in fatos:
    print(f"{fato['nome_companhia']}: {fato['assunto']} ({fato['data_entrega']})")
```

### Caso 4: JavaScript - Monitoramento de Assembleias

```javascript
async function monitorarAssembleias(codigoCvm, token) {
  const response = await fetch(
    `http://localhost:8007/ipe/documentos?codigo_cvm=${codigoCvm}&categoria=Assembleia&ordenar_por=-data_entrega`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  
  const { dados } = await response.json();
  
  const proximas = dados.filter(d => new Date(d.data_referencia) > new Date());
  console.log(`Próximas assembleias: ${proximas.length}`);
  
  return proximas;
}
```

---

## Diferença entre `data_referencia` e `data_entrega`

| Campo | Significado |
|-------|-------------|
| `data_referencia` | Data do fato/evento em si |
| `data_entrega` | Data de protocolo na CVM |

> **Importante para compliance:** A diferença entre `data_entrega` e `data_referencia` indica o SLA de divulgação. Fatos relevantes devem ser divulgados no mesmo dia do fato.

---

## Notas para Usuários

### Para Analistas Financeiros
- Use `/ipe/documentos` com `categoria=Fato Relevante` para monitorar eventos de mercado
- Cruze com `/dfp/documentos` para validar consistência de datas
- `/ipe/documentos/agregados` ajuda a identificar padrões de divulgação

### Para Auditores
- Use `categoria=Estatuto Social` para rastrear alterações estatutárias
- `categoria=Acordo de Acionistas` identifica mudanças de controle
- Cruze com `/fre/posicao-acionaria` para validar consistência

### Para Operadores de Backoffice
- Use `/ipe/documentos/agregados` para dashboards operacionais
- Monitore `data_entrega` para identificar atrasos de divulgação
- Use `protocolo_entrega` para rastrear entregas específicas

### Para Compliance
- **Fatos Relevantes**: monitore diariamente com `categoria=Fato Relevante`
- **SLA de Divulgação**: compare `data_referencia` vs `data_entrega`
- **OPA**: use `categoria=OPA` para monitorar ofertas públicas
- **Políticas**: use `categoria=Política de Negociação` para validar conformidade

---

## Próximos Passos

- [VLMO](./vlmo.md) - Valores Mobiliários Negociados e Detidos
- [CGVN](./cgvn.md) - Código de Governança Corporativa
- [Ingestion](../ingestion/monitoring.md) - Monitoramento de sincronizações