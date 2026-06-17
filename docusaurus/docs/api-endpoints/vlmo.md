---
title: Valores Mobiliários Negociados e Detidos (VLMO)
sidebar_position: 12
---

# Valores Mobiliários Negociados e Detidos (VLMO)

## Visão Geral

O **VLMO** fornece informações sobre negociações e posições de **insiders** (administradores, conselheiros, controladores e pessoas vinculadas). É a fonte primária para monitoramento de **insider trading** e análise de concentração de capital.

## Endpoints Disponíveis

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/vlmo/documentos` | Listar documentos VLMO |
| `GET` | `/vlmo/consolidado` | Negociações e posições consolidadas |

---

## `GET /vlmo/documentos`

Retorna os cabeçalhos documentais do VLMO.

### Exemplo

```bash
curl -X GET "http://localhost:8007/vlmo/documentos?codigo_cvm=25224&ano_inicio=2025" \
  -H "Authorization: Bearer <token>"
```

### Filtros Adicionais

| Parâmetro | Descrição |
|-----------|-----------|
| `categoria` | Categoria do documento |
| `tipo` | Tipo do documento |

### Ordenação Permitida

`data_entrega`, `data_referencia`, `versao`, `cnpj_companhia`, `codigo_cvm`, `categoria`, `tipo`

---

## `GET /vlmo/consolidado`

Retorna posições consolidadas e movimentações detalhadas de valores mobiliários detidos por insiders.

### Query Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ com ou sem pontuação |
| `codigo_cvm` | integer | Código CVM da companhia |
| `data_referencia_inicio` / `data_referencia_fim` | date | Intervalo de data de referência |
| `data_movimentacao_inicio` / `data_movimentacao_fim` | date | Intervalo de data de movimentação |
| `ano_origem` / `ano_inicio` / `ano_fim` | integer | Filtros de ano |
| `versao` | integer | Versão específica |
| `tipo_empresa` | string | Tipo da empresa relacionada |
| `empresa` | string | Nome da empresa relacionada |
| `tipo_cargo` | string | Tipo de cargo (Diretor, Conselheiro, etc.) |
| `tipo_movimentacao` | string | Tipo de movimentação (Compra, Venda, etc.) |
| `tipo_operacao` | string | Tipo de operação |
| `tipo_ativo` | string | Tipo de ativo (Ação, Opção, Debênture, etc.) |
| `caracteristica_valor_mobiliario` | string | Característica do valor mobiliário |
| `intermediario` | string | Intermediário da operação |
| `ordenar_por` | string | Campo de ordenação |
| `pagina` / `tamanho_pagina` | integer | Paginação |

### Exemplo: Vendas de Diretores

```bash
curl -X GET "http://localhost:8007/vlmo/consolidado?codigo_cvm=25224&tipo_cargo=Diretor&tipo_movimentacao=Venda&ano_inicio=2025" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaVlmoConsolidadoResposta`

```json
{
  "dados": [
    {
      "id": "...",
      "cnpj_companhia": "08773135000100",
      "nome_companhia": "EMPRESA A",
      "data_referencia": "2026-05-31",
      "versao": 1,
      "tipo_empresa": "Controladora",
      "empresa": "EMPRESA A S.A.",
      "tipo_cargo": "Diretor",
      "tipo_movimentacao": "Venda",
      "descricao_movimentacao": "Venda de ações ordinárias",
      "tipo_operacao": "Mercado",
      "tipo_ativo": "Acao Ordinaria",
      "caracteristica_valor_mobiliario": "ON",
      "intermediario": "CORRETORA X",
      "data_movimentacao": "2026-05-15",
      "quantidade": 10000,
      "preco_unitario": "25.50",
      "volume": "255000.00",
      "indice_ocorrencia": 1,
      "arquivo_origem": "vlmo_cia_aberta_con_2026.csv",
      "ano_origem": 2026,
      "linha_origem": 100
    }
  ],
  "paginacao": { "pagina": 1, "tamanho_pagina": 100, "total": 1 }
}
```

### Ordenação Permitida

`data_referencia`, `data_movimentacao`, `versao`, `cnpj_companhia`, `tipo_ativo`, `tipo_operacao`, `tipo_movimentacao`, `empresa`

---

## Tipos de Cargo Comuns

- `Diretor`
- `Conselheiro de Administracao`
- `Conselheiro Fiscal`
- `Acionista Controlador`
- `Membro de Comitê`

## Tipos de Movimentação Comuns

- `Compra`
- `Venda`
- `Doacao`
- `Exercicio de Opcao`
- `Heranca`
- `Permuta`

## Tipos de Ativo Comuns

- `Acao Ordinaria`
- `Acao Preferencial`
- `Opcao de Compra`
- `Opcao de Venda`
- `Debenture`
- `Nota Comercial`

---

## Casos de Uso

### Caso 1: Monitorar Vendas de Insiders

```bash
# Vendas de diretores nos últimos 30 dias
GET /vlmo/consolidado?tipo_cargo=Diretor&tipo_movimentacao=Venda&data_movimentacao_inicio=2026-05-17
```

### Caso 2: Análise de Concentração por Cargo

```bash
# Volume total por tipo de cargo
GET /vlmo/consolidado?codigo_cvm=25224&ano_inicio=2025&ordenar_por=-data_movimentacao
```

### Caso 3: Python - Alertas de Insider Trading

```python
import httpx
from datetime import datetime, timedelta

def alertas_insider(base_url, token, codigos_cvm):
    """Gera alertas para vendas significativas de insiders."""
    headers = {"Authorization": f"Bearer {token}"}
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    alertas = []
    for codigo_cvm in codigos_cvm:
        response = httpx.get(
            f"{base_url}/vlmo/consolidado",
            params={
                "codigo_cvm": codigo_cvm,
                "tipo_movimentacao": "Venda",
                "data_movimentacao_inicio": ontem
            },
            headers=headers
        )
        vendas = response.json()["dados"]
        
        for venda in vendas:
            volume = float(venda["volume"])
            if volume > 1000000:  # Vendas > R$ 1M
                alertas.append({
                    "companhia": venda["nome_companhia"],
                    "cargo": venda["tipo_cargo"],
                    "volume": volume,
                    "data": venda["data_movimentacao"]
                })
    
    return alertas

# Uso
alertas = alertas_insider("http://localhost:8007", "seu-token", [25224, 1023])
for alerta in alertas:
    print(f"⚠️ {alerta['companhia']} - {alerta['cargo']}: R$ {alerta['volume']:,.2f}")
```

### Caso 4: JavaScript - Histórico de Movimentações

```javascript
async function historicoInsider(codigoCvm, token) {
  const response = await fetch(
    `http://localhost:8007/vlmo/consolidado?codigo_cvm=${codigoCvm}&ano_inicio=2025&ordenar_por=-data_movimentacao`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  
  const { dados } = await response.json();
  
  // Agrupar por tipo de cargo
  const porCargo = dados.reduce((acc, mov) => {
    const cargo = mov.tipo_cargo;
    if (!acc[cargo]) acc[cargo] = [];
    acc[cargo].push(mov);
    return acc;
  }, {});
  
  return porCargo;
}
```

---

## SLA de Reporte

A diferença entre `data_movimentacao` e `data_referencia` indica o SLA de reporte à CVM:

```python
from datetime import datetime

def calcular_sla(movimentacao):
    data_mov = datetime.strptime(movimentacao["data_movimentacao"], "%Y-%m-%d")
    data_ref = datetime.strptime(movimentacao["data_referencia"], "%Y-%m-%d")
    dias = (data_ref - data_mov).days
    return dias

# SLA típico: até 10 dias úteis
```

---

## Notas para Usuários

### Para Analistas Financeiros
- Use `/vlmo/consolidado` para analisar comportamento de insiders
- Cruze com `/ipe/documentos` (Fatos Relevantes) para validar timing
- `/analise/mercado-insiders` fornece visão consolidada

### Para Auditores
- Monitore `data_movimentacao` vs `data_referencia` para SLA de reporte
- Cruze com `/fre/posicao-acionaria` para validar concentrações
- Use `/fre/participacoes-sociedades` para entender estrutura de controle

### Para Operadores de Backoffice
- Use filtros por `tipo_cargo` e `tipo_movimentacao` para dashboards
- Monitore `volume` para identificar movimentações significativas
- Use `intermediario` para rastrear corretoras envolvidas

### Para Compliance
- **Insider Trading**: monitore vendas de insiders antes de fatos relevantes
- **Blackout Periods**: valide que não há negociações em períodos vedados
- **SLA de Reporte**: alerte para movimentações reportadas fora do prazo
- **Concentração**: use para monitorar mudanças de controle

---

## Próximos Passos

- [CGVN](./cgvn.md) - Código de Governança Corporativa
- [Ingestion](../ingestion/monitoring.md) - Monitoramento de sincronizações