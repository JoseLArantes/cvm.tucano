---
title: Formulário de Referência (FRE)
sidebar_position: 9
---

# Formulário de Referência (FRE)

## Visão Geral

O **Formulário de Referência (FRE)** é o documento mais rico em informações societárias, de governança e de recursos humanos. A API expõe os **quadros públicos ativos** do FRE organizados em grupos temáticos.

## Endpoints Disponíveis

### Documentos e Cabeçalhos

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/fre/documentos` | Listar documentos FRE |
| `GET` | `/fre/responsaveis` | Responsáveis pelo FRE |
| `GET` | `/fre/auditores` | Auditores independentes |

### Capital Social e Estrutura Acionária

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/fre/capital-social` | Capital social |
| `GET` | `/fre/capital-social-classes-acoes` | Classes de ações do capital |
| `GET` | `/fre/capital-social-titulos-conversiveis` | Títulos conversíveis |
| `GET` | `/fre/distribuicao-capital` | Distribuição de capital |
| `GET` | `/fre/distribuicao-capital-classes-acoes` | Classes na distribuição |
| `GET` | `/fre/posicao-acionaria` | Posição acionária |
| `GET` | `/fre/posicoes-acionarias-classes-acoes` | Classes na posição acionária |

### Endpoints removidos por descontinuação explícita da CVM

Os endpoints abaixo foram removidos da API porque a própria CVM descontinuou esses detalhamentos no FRE e orienta a consulta dos quadros ativos de capital social e distribuição:

- `/fre/capital-social/aumentos`
- `/fre/capital-social/aumentos-classes-acoes`
- `/fre/capital-social/desdobramentos`
- `/fre/capital-social/desdobramentos-classes-acoes`
- `/fre/capital-social/reducoes`
- `/fre/capital-social/reducoes-classes-acoes`
- `/fre/direitos-acoes`

Para exercícios a partir de 2024, use principalmente:

- `/fre/capital-social`
- `/fre/capital-social-classes-acoes`
- `/fre/distribuicao-capital`
- `/fre/distribuicao-capital-classes-acoes`
- `/fre/posicao-acionaria`

### Remuneração

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/fre/remuneracao/total-por-orgao` | Remuneração total por órgão |
| `GET` | `/fre/remuneracoes-maximas-minimas-medias` | Remunerações máx/mín/média |
| `GET` | `/fre/remuneracoes-variaveis` | Remuneração variável |
| `GET` | `/fre/remuneracoes-acoes` | Remuneração baseada em ações |
| `GET` | `/fre/acoes-entregues` | Ações entregues como remuneração |

### Empregados e Diversidade

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/fre/empregados/posicao-genero` | Empregados por posição e gênero |
| `GET` | `/fre/empregados/posicao-local` | Empregados por posição e local |
| `GET` | `/fre/empregados/posicao-faixa-etaria` | Empregados por posição e faixa etária |
| `GET` | `/fre/empregados/posicao-declaracao-raca` | Empregados por posição e raça |
| `GET` | `/fre/empregados/pcd` | Empregados PCD |
| `GET` | `/fre/empregados/local-faixa-etaria` | Empregados por local e faixa etária |
| `GET` | `/fre/empregados/local-declaracao-raca` | Empregados por local e raça |
| `GET` | `/fre/empregados/local-declaracao-genero` | Empregados por local e gênero |

### Administradores e Diversidade

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/fre/administradores/declaracao-genero` | Gênero dos administradores |
| `GET` | `/fre/administradores/declaracao-raca` | Raça dos administradores |
| `GET` | `/fre/administradores/pcd` | Administradores PCD |
| `GET` | `/fre/relacoes-familiares` | Relações familiares |

### Valores Mobiliários e Mercado

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/fre/volume-valor-mobiliario` | Volume de negociação |
| `GET` | `/fre/outro-valor-mobiliario` | Outros valores mobiliários |
| `GET` | `/fre/titular-valor-mobiliario` | Titulares de valores mobiliários |
| `GET` | `/fre/mercado-estrangeiro` | Mercados estrangeiros |
| `GET` | `/fre/titulo-exterior` | Títulos no exterior |

### Tesouraria e Recompra

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/fre/valor-mobiliario-tesouraria-movimentacao` | Movimentações em tesouraria |
| `GET` | `/fre/valor-mobiliario-tesouraria-ultimo-exercicio` | Saldos em tesouraria |
| `GET` | `/fre/plano-recompra` | Planos de recompra |
| `GET` | `/fre/plano-recompra-classes-acoes` | Classes em planos de recompra |

### Observação de layout para `/fre/plano-recompra-classes-acoes`

O campo `tipo_classe_acao_preferencial` pode vir vazio no dado oficial da CVM. O contrato atual expõe:

- `especie_acao`: espécie da ação no plano de recompra;
- `tipo_classe_acao_preferencial`: subtipo da preferencial, quando informado pela fonte.

Na prática, o backend não rejeita mais a linha apenas porque `tipo_classe_acao_preferencial` veio vazio.

### Participações e Estrutura

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/fre/participacoes-sociedades` | Participações em sociedades |

---

## `GET /fre/documentos`

Retorna os documentos principais do FRE.

### Exemplo

```bash
curl -X GET "http://localhost:8007/fre/documentos?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaFreDocumentosResposta`

```json
{
  "dados": [
    {
      "id": "...",
      "cnpj_companhia": "08773135000100",
      "codigo_cvm": 25224,
      "data_referencia": "31/12/2025",
      "versao": 1,
      "denominacao_companhia": "EMPRESA A",
      "categoria_documento": "FRE",
      "id_documento": 12345,
      "data_recebimento": "30/04/2026",
      "link_documento": "http://exemplo",
      "arquivo_origem": "fre_cia_aberta_2025.csv",
      "ano_origem": 2025,
      "linha_origem": 100,
      "criado_em": "30/05/2026 14:30:00",
      "sincronizado_em": "30/05/2026 14:30:00",
      "alterado_em": "30/05/2026 14:30:00"
    }
  ],
  "paginacao": { "pagina": 1, "tamanho_pagina": 100, "total": 1 }
}
```

---

## `GET /fre/posicao-acionaria`

Retorna a posição acionária detalhada.

### Exemplo

```bash
curl -X GET "http://localhost:8007/fre/posicao-acionaria?codigo_cvm=25224&ano_inicio=2024&ordenar_por=-data_referencia" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaFrePosicaoAcionariaResposta`

```json
{
  "dados": [
    {
      "id": "...",
      "cnpj_companhia": "08773135000100",
      "data_referencia": "31/12/2025",
      "versao": 1,
      "id_documento": 12345,
      "nome_companhia": "EMPRESA A",
      "id_acionista": 1,
      "acionista": "FUNDO DE INVESTIMENTO X",
      "tipo_pessoa_acionista": "PESSOA JURIDICA",
      "cpf_cnpj_acionista": "12345678000199",
      "quantidade_acao_ordinaria_circulacao": 100000000,
      "percentual_acao_ordinaria_circulacao": 12.5,
      "quantidade_acao_preferencial_circulacao": 50000000,
      "percentual_acao_preferencial_circulacao": 6.25,
      "quantidade_total_acoes_circulacao": 150000000,
      "percentual_total_acoes_circulacao": 10.0,
      "nacionalidade": "BRASIL",
      "sigla_uf": "SP",
      "residente_exterior": false,
      "acionista_controlador": false,
      "participante_acordo_acionistas": true,
      "arquivo_origem": "fre_cia_aberta_posicao_acionaria_2025.csv",
      "ano_origem": 2025,
      "linha_origem": 50,
      "criado_em": "30/05/2026 14:30:00",
      "sincronizado_em": "30/05/2026 14:30:00",
      "alterado_em": "30/05/2026 14:30:00"
    }
  ],
  "paginacao": { "pagina": 1, "tamanho_pagina": 100, "total": 1 }
}
```

### Filtros Adicionais

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `id_acionista` | integer | Filtrar por ID do acionista |

---

## `GET /fre/remuneracao/total-por-orgao`

Retorna remuneração total por órgão de administração.

### Exemplo

```bash
curl -X GET "http://localhost:8007/fre/remuneracao/total-por-orgao?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaFreRemuneracaoTotalOrgaoResposta`

```json
{
  "dados": [
    {
      "id": "...",
      "cnpj_companhia": "08773135000100",
      "data_referencia": "2025-12-31",
      "versao": 1,
      "id_documento": 12345,
      "nome_companhia": "EMPRESA A",
      "data_inicio_exercicio_social": "2025-01-01",
      "data_fim_exercicio_social": "2025-12-31",
      "total_remuneracao": 10500000.0,
      "orgao_administracao": "CONSELHO DE ADMINISTRACAO",
      "numero_membros": 7,
      "total_remuneracao_orgao": 2500000.0,
      "numero_membros_remunerados": 7,
      "salario": 1000000.0,
      "beneficios_diretos_indiretos": 500000.0,
      "participacoes_comites": 300000.0,
      "outros_valores_fixos": 200000.0,
      "bonus": 200000.0,
      "participacao_resultados": 150000.0,
      "participacao_reunioes": 100000.0,
      "outros_valores_variaveis": 50000.0,
      "pos_emprego": 0.0,
      "cessacao_cargo": 0.0,
      "baseada_acoes": 0.0,
      "observacao": null,
      "arquivo_origem": "fre_cia_aberta_remuneracao_total_orgao_2025.csv",
      "ano_origem": 2025,
      "linha_origem": 10,
      "criado_em": "2026-05-30T14:30:00Z",
      "sincronizado_em": "2026-05-30T14:30:00Z",
      "alterado_em": "2026-05-30T14:30:00Z"
    }
  ],
  "paginacao": { "pagina": 1, "tamanho_pagina": 100, "total": 1 }
}
```

### Filtros Adicionais

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `orgao_administracao` | string | Filtrar por órgão (ex: `Conselho`) |

---

## `GET /fre/empregados/posicao-genero`

Retorna distribuição de empregados por posição e gênero.

### Exemplo

```bash
curl -X GET "http://localhost:8007/fre/empregados/posicao-genero?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaFreEmpregadoPosicaoGeneroResposta`

```json
{
  "dados": [
    {
      "id": "...",
      "cnpj_companhia": "08773135000100",
      "data_referencia": "2025-12-31",
      "versao": 1,
      "id_documento": 12345,
      "nome_companhia": "EMPRESA A",
      "posicao": "CONSELHO DE ADMINISTRACAO",
      "quantidade_feminino": 2,
      "quantidade_masculino": 5,
      "quantidade_nao_binario": 0,
      "quantidade_outros": 0,
      "quantidade_sem_resposta": 0,
      "arquivo_origem": "fre_cia_aberta_empregado_posicao_declaracao_genero_2025.csv",
      "ano_origem": 2025,
      "linha_origem": 100,
      "criado_em": "2026-05-30T14:30:00Z",
      "sincronizado_em": "2026-05-30T14:30:00Z",
      "alterado_em": "2026-05-30T14:30:00Z"
    }
  ],
  "paginacao": { "pagina": 1, "tamanho_pagina": 100, "total": 1 }
}
```

---

## Casos de Uso

### Caso 1: Análise de Concentração Acionária

```bash
GET /fre/posicao-acionaria?codigo_cvm=25224&ano_inicio=2024&ordenar_por=-percentual_total_acoes_circulacao
```

### Caso 2: Comparação de Remuneração entre Órgãos

```bash
GET /fre/remuneracao/total-por-orgao?codigo_cvm=25224&ano_inicio=2024
```

### Caso 3: Análise de Diversidade de Gênero

```bash
GET /fre/empregados/posicao-genero?codigo_cvm=25224&ano_inicio=2024
```

### Caso 4: Identificar Relações Familiares

```bash
GET /fre/relacoes-familiares?codigo_cvm=25224&ano_inicio=2024
```

### Caso 5: Python - Exportar Posição Acionária

```python
import httpx

def exportar_posicao_acionaria(codigo_cvm, ano, token):
    response = httpx.get(
        "http://localhost:8007/exportacoes/fre/posicao_acionaria",
        params={"codigo_cvm": codigo_cvm, "ano_inicio": ano, "formato": "json"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=300.0
    )
    response.raise_for_status()
    return response.json()
```

---

## Notas Importantes

### Para Analistas de Governança

- **`/fre/posicao-acionaria`** é a fonte primária para análise de controle e concentração
- **`/fre/remuneracao/total-por-orgao`** permite benchmarking de remuneração executiva
- **`/fre/relacoes-familiares`** identifica potenciais conflitos de interesse
- **`/fre/participacoes-sociedades`** mapeia holdings e coligadas

### Para Analistas de ESG/Diversidade

- **`/fre/empregados/posicao-genero`** e **`/fre/empregados/posicao-declaracao-raca`** fornecem dados de diversidade
- **`/fre/administradores/declaracao-genero`** e **`/fre/administradores/declaracao-raca`** focam em gestão
- **`/fre/empregados/pcd`** e **`/fre/administradores/pcd`** rastreiam inclusão de PCDs

### Para Auditores

- **`/fre/auditores`** identifica auditores independentes e remuneração
- **`/fre/capital-social`** e sub-endpoints rastreiam alterações de capital
- **`/fre/valor-mobiliario-tesouraria-movimentacao`** monitora ações em tesouraria

### Regras de Negócio

1. **Promoção Seletiva**: O FRE possui ~48 datasets, mas apenas 9 são promovidos para tabelas de domínio por relevância regulatória
2. **Resolução de Acionistas**: CNPJs/CPFs são normalizados e vinculados a entidades quando possível
3. **Moeda**: Valores monetários são convertidos para escala base (R$) automaticamente
4. **Histórico**: Cada ano gera novo documento; não há sobrescrita

---

## Próximos Passos

- [FCA](./fca.md) - Formulário Cadastral
- [IPE](./ipe.md) - Informações Periódicas e Eventuais
- [Ingestion](../ingestion/monitoring.md) - Monitoramento de sincronizações
