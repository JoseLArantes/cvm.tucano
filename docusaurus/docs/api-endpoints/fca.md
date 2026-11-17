---
title: Formulário Cadastral (FCA)
sidebar_position: 10
---

# Formulário Cadastral (FCA)

## Visão Geral

O **Formulário Cadastral do Emissor (FCA)** reúne informações cadastrais completas das companhias abertas: dados gerais, endereços, DRI, auditores independentes, valores mobiliários emitidos e departamento de atendimento a acionistas.

## Endpoints Disponíveis

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/fca/documentos` | Listar documentos FCA |
| `GET` | `/fca/geral` | Dados gerais da companhia |
| `GET` | `/fca/enderecos` | Endereços (sede, correspondência) |
| `GET` | `/fca/dri` | Diretor de Relações com Investidores |
| `GET` | `/fca/auditores` | Auditores independentes |
| `GET` | `/fca/valores-mobiliarios` | Valores mobiliários emitidos |
| `GET` | `/fca/departamento-acionistas` | Departamento de atendimento a acionistas |

---

## Filtros Comuns

Todos os endpoints FCA aceitam:

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ com ou sem pontuação |
| `codigo_cvm` | integer | Código CVM da companhia |
| `data_referencia_inicio` | date | Data inicial (YYYY-MM-DD) |
| `data_referencia_fim` | date | Data final (YYYY-MM-DD) |
| `ano_origem` | integer | Ano do ZIP de origem |
| `ano_inicio` / `ano_fim` | integer | Intervalo de anos |
| `versao` | integer | Versão específica do documento |
| `ordenar_por` | string | Campo de ordenação (prefixe com `-` para desc.) |
| `pagina` / `tamanho_pagina` | integer | Paginação |

---

## `GET /fca/documentos`

Retorna os cabeçalhos documentais do FCA.

### Exemplo

```bash
curl -X GET "http://localhost:8007/fca/documentos?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaFcaDocumentosResposta`

```json
{
  "dados": [
    {
      "id": "...",
      "cnpj_companhia": "08773135000100",
      "codigo_cvm": 25224,
      "data_referencia": "2025-12-31",
      "versao": 1,
      "denominacao_companhia": "EMPRESA A",
      "categoria_documento": "FCA",
      "id_documento": 12345,
      "data_recebimento": "2026-03-31",
      "link_documento": "http://exemplo",
      "arquivo_origem": "fca_cia_aberta_2025.csv",
      "ano_origem": 2025,
      "linha_origem": 100
    }
  ],
  "paginacao": { "pagina": 1, "tamanho_pagina": 100, "total": 1 }
}
```

---

## `GET /fca/geral`

Retorna informações cadastrais gerais: denominação, constituição, exercício social, controle acionário, etc.

### Exemplo

```bash
curl -X GET "http://localhost:8007/fca/geral?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer <token>"
```

### Campos Principais

| Campo | Descrição |
|-------|-----------|
| `nome_empresarial` | Razão social atual |
| `nome_empresarial_anterior` | Razão social anterior |
| `data_constituicao` | Data de fundação |
| `data_registro_cvm` | Data de registro na CVM |
| `categoria_registro_cvm` | Categoria A ou B |
| `situacao_registro_cvm` | Situação atual |
| `especie_controle_acionario` | Tipo de controle |
| `dia_encerramento_exercicio_social` | Dia de encerramento |
| `mes_encerramento_exercicio_social` | Mês de encerramento |
| `setor_atividade` | Setor econômico |
| `descricao_atividade` | Descrição detalhada |
| `pagina_web` | Site da companhia |

### Ordenação Permitida

`data_referencia`, `versao`, `cnpj_companhia`, `codigo_cvm`, `nome_empresarial`

---

## `GET /fca/enderecos`

Retorna endereços da companhia (sede, correspondência, etc.).

### Exemplo

```bash
curl -X GET "http://localhost:8007/fca/enderecos?codigo_cvm=25224&tipo_endereco=SEDE" \
  -H "Authorization: Bearer <token>"
```

### Filtros Adicionais

| Parâmetro | Descrição |
|-----------|-----------|
| `tipo_endereco` | Filtrar por tipo (SEDE, CORRESPONDENCIA, etc.) |
| `pais` | Filtrar por país |

### Ordenação Permitida

`data_referencia`, `versao`, `cnpj_companhia`, `tipo_endereco`, `pais`

---

## `GET /fca/dri`

Retorna informações do Diretor de Relações com Investidores (DRI).

### Exemplo

```bash
curl -X GET "http://localhost:8007/fca/dri?codigo_cvm=25224" \
  -H "Authorization: Bearer <token>"
```

### Filtros Adicionais

| Parâmetro | Descrição |
|-----------|-----------|
| `nome_dri` | Filtrar por nome do DRI |
| `email_dri` | Filtrar por email do DRI |

### Campos Principais

| Campo | Descrição |
|-------|-----------|
| `nome_dri` | Nome do DRI |
| `email_dri` | Email de contato |
| `telefone` | Telefone de contato |
| `data_inicio_atuacao` | Início da atuação |
| `data_fim_atuacao` | Fim da atuação (se aplicável) |

### Ordenação Permitida

`data_referencia`, `versao`, `cnpj_companhia`, `nome_dri`, `email_dri`

---

## `GET /fca/auditores`

Retorna auditores independentes registrados no FCA.

### Exemplo

```bash
curl -X GET "http://localhost:8007/fca/auditores?codigo_cvm=25224&nome_auditor=Deloitte" \
  -H "Authorization: Bearer <token>"
```

### Filtros Adicionais

| Parâmetro | Descrição |
|-----------|-----------|
| `nome_auditor` | Filtrar por nome do auditor |
| `codigo_cvm_auditor` | Filtrar por código CVM do auditor |

### Campos Principais

| Campo | Descrição |
|-------|-----------|
| `nome_auditor` | Nome do auditor independente |
| `cpf_cnpj_auditor` | Documento do auditor |
| `codigo_cvm_auditor` | Código CVM do auditor |
| `data_inicio_atuacao_auditor` | Início da contratação |
| `data_fim_atuacao_auditor` | Fim da contratação |
| `responsavel_tecnico` | Nome do responsável técnico |
| `cpf_responsavel_tecnico` | CPF do responsável técnico |

### Ordenação Permitida

`data_referencia`, `versao`, `cnpj_companhia`, `nome_auditor`, `codigo_cvm_auditor`

---

## `GET /fca/valores-mobiliarios`

Retorna valores mobiliários emitidos pela companhia.

### Exemplo

```bash
curl -X GET "http://localhost:8007/fca/valores-mobiliarios?codigo_cvm=25224&tipo_valor_mobiliario=Acoes" \
  -H "Authorization: Bearer <token>"
```

### Filtros Adicionais

| Parâmetro | Descrição |
|-----------|-----------|
| `tipo_valor_mobiliario` | Filtrar por tipo (ações, debêntures, etc.) |
| `codigo_negociacao` | Código de negociação exato, sem diferenciar maiúsculas e minúsculas. |
| `current` | Quando `true`, seleciona o documento FCA e a versão mais recentes por CNPJ antes de filtrar pelo ticker. Padrão `false`. |

O filtro do ticker é uma igualdade exata, não uma busca por prefixo. Use `current=true` para resolver uma listagem corrente. Assim, um ticker presente apenas em uma versão FCA antiga não estabelece uma relação atual. Sem `codigo_negociacao` e `current`, a consulta mantém o comportamento histórico e retorna os documentos conforme os demais filtros.

```bash
curl -X GET "http://localhost:8007/fca/valores-mobiliarios?codigo_negociacao=bbas3&current=true" \
  -H "Authorization: Bearer <token>"
```

Na resposta paginada, cada linha preserva CNPJ do emissor, `id`, `id_documento`, versão, data de referência, tipo do valor mobiliário, ticker, mercado, datas de início/fim da negociação e datas de início/fim da listagem. O cliente deve validar ticker, mercado, classe e intervalo antes de associar um emissor a um instrumento.

### Campos Principais

| Campo | Descrição |
|-------|-----------|
| `tipo_valor_mobiliario` | Tipo do valor mobiliário |
| `sigla_classe_acao_preferencial` | Classe da ação PN (se aplicável) |
| `codigo_negociacao` | Código de negociação (ticker) |
| `mercado` | Mercado de listagem |
| `entidade_administradora` | Entidade administradora |
| `data_inicio_negociacao` | Início da negociação |
| `data_fim_negociacao` | Fim da negociação |
| `data_inicio_listagem` | Início da listagem |
| `data_fim_listagem` | Fim da listagem |
| `segmento` | Segmento de listagem |

### Ordenação Permitida

`data_referencia`, `versao`, `cnpj_companhia`, `tipo_valor_mobiliario`, `codigo_negociacao`

---

## `GET /fca/departamento-acionistas`

Retorna contatos e endereços do departamento de atendimento a acionistas.

### Exemplo

```bash
curl -X GET "http://localhost:8007/fca/departamento-acionistas?codigo_cvm=25224" \
  -H "Authorization: Bearer <token>"
```

### Filtros Adicionais

| Parâmetro | Descrição |
|-----------|-----------|
| `contato` | Filtrar por nome do contato |
| `email` | Filtrar por email |
| `tipo_endereco` | Filtrar por tipo de endereço |
| `sigla_uf` | Filtrar por UF |

### Ordenação Permitida

`data_referencia`, `versao`, `cnpj_companhia`, `contato`, `email`, `tipo_endereco`, `sigla_uf`

---

## Casos de Uso

### Caso 1: Identificar Auditor Atual

```bash
GET /fca/auditores?codigo_cvm=25224&ordenar_por=-data_inicio_atuacao_auditor&tamanho_pagina=1
```

### Caso 2: Listar Tickers Ativos

```bash
GET /fca/valores-mobiliarios?codigo_cvm=25224&tipo_valor_mobiliario=Acoes
```

### Caso 3: Encontrar DRI de Múltiplas Companhias

```bash
GET /fca/dri?nome_dri=Silva&ano_inicio=2025
```

### Caso 4: Python - Exportar Endereços de Companhias Ativas

```python
import httpx

def exportar_enderecos(base_url, token):
    """Exporta endereços de todas as companhias ativas."""
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Buscar companhias ativas
    response = httpx.get(
        f"{base_url}/companhias",
        params={"situacao_registro": "ATIVO", "tamanho_pagina": 500},
        headers=headers
    )
    companhias = response.json()["dados"]
    
    # 2. Para cada companhia, buscar endereço
    enderecos = []
    for comp in companhias:
        response = httpx.get(
            f"{base_url}/fca/enderecos",
            params={"codigo_cvm": comp["codigo_cvm"], "tipo_endereco": "SEDE"},
            headers=headers
        )
        enderecos.extend(response.json()["dados"])
    
    return enderecos
```

---

## Notas para Usuários

### Para Analistas Financeiros
- Use `/fca/geral` para validar dados cadastrais antes de análises
- `/fca/valores-mobiliarios` mapeia todos os tickers e classes de ações
- Cruze com `/fca/auditores` para avaliar qualidade da auditoria

### Para Auditores
- `/fca/auditores` é a fonte primária para verificar independência e rotatividade
- Compare `data_inicio_atuacao_auditor` com `data_fim_atuacao_auditor` para calcular tempo de mandato
- Cruze com `/fre/auditores` para validar consistência entre fontes

### Para Operadores de Backoffice
- Use `/fca/enderecos` para validar cadastros de correspondência
- `/fca/departamento-acionistas` fornece contatos oficiais para comunicações
- `/fca/dri` identifica o ponto de contato oficial para RI

### Para Compliance
- `/fca/valores-mobiliarios` mapeia todos os valores mobiliários emitidos
- `/fca/auditores` ajuda a monitorar rotatividade de auditores (regra de 5 anos)
- Use `data_inicio_atuacao_auditor` para alertas de mandato prolongado

---

## Próximos Passos

- [IPE](./ipe.md) - Informações Periódicas e Eventuais
- [VLMO](./vlmo.md) - Valores Mobiliários Negociados e Detidos
- [CGVN](./cgvn.md) - Código de Governança Corporativa
