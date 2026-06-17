---
title: Formulário de Referência (FRE)
sidebar_position: 5
---

# Formulário de Referência (FRE)

## Visão Geral

Documento descritivo e analítico que complementa as demonstrações financeiras. Contém informações societárias, de governança, remuneração, auditoria e estrutura acionária.

## Metadados Técnicos

| Campo | Valor |
|-------|-------|
| **Fonte CVM** | `fre` |
| **Arquivo ZIP** | `fre_companhias_abertas_{ano}.zip` |
| **Periodicidade** | Anual/Eventual |
| **Desde** | 2010 |
| **Tabelas Alvo** | `fre_documentos`, `fre_auditores`, `fre_capital_social`, `fre_posicoes_acionarias`, `fre_remuneracoes_totais_orgaos`, `fre_empregados_posicao_genero`, `fre_responsaveis`, `fre_participacoes_sociedades`, `fre_relacoes_familiares` |
| **Chaves Naturais** | `(id_documento, versao, data_referencia)` |

## Estrutura de Subarquivos

```
fre_cia_aberta_{ano}.csv                  # Header
fre_cia_aberta_auditor_{ano}.csv          # Auditores
fre_cia_aberta_capital_{ano}.csv          # Capital Social
fre_cia_aberta_pos_acionaria_{ano}.csv    # Posição Acionária
fre_cia_aberta_remuneracao_{ano}.csv      # Remuneração
fre_cia_aberta_empregados_{ano}.csv       # Empregados por Gênero/Posição
fre_cia_aberta_resp_{ano}.csv             # Responsáveis
fre_cia_aberta_part_sociedades_{ano}.csv  # Participações em Sociedades
fre_cia_aberta_rel_familia_{ano}.csv      # Relações Familiares
```

## Endpoints Principais

### Listar Documentos
```bash
GET /fre/documentos?codigo_cvm=25224&ano_inicio=2020
```

### Posição Acionária
```bash
GET /fre/posicao-acionaria?codigo_cvm=25224&data_referencia_inicio=2024-01-01
```

### Remuneração por Órgão
```bash
GET /fre/remuneracao/total-por-orgao?codigo_cvm=25224&ano=2024
```

### Auditores
```bash
GET /fre/auditores?codigo_cvm=25224
```

## Campos Chave por Dataset

### `fre_posicoes_acionarias`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id_acionista` | String | Identificador interno |
| `nome_acionista` | String | Nome completo/razão social |
| `tipo_pessoa` | String | Física ou Jurídica |
| `cpf_cnpj` | String | Documento |
| `nacionalidade` | String | País |
| `quantidade_acoes_ordinarias` | Numeric | Ações ON |
| `quantidade_acoes_preferenciais` | Numeric | Ações PN |
| `percentual_capital_votante` | Numeric | % votante |
| `possui_acordo_acionarios` | Boolean | Sim/Não |
| `controla_companhia` | Boolean | Flag de controle |

### `fre_remuneracoes_totais_orgaos`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `orgao_administracao` | String | Diretoria, Conselho, etc. |
| `total_remuneracao` | Numeric | Soma bruta |
| `parcelas_fixas` | Numeric | Salários, pró-labore |
| `parcelas_variaveis` | Numeric | Bônus, PLR |
| `beneficios_pos_emprego` | Numeric | Previdência, etc. |
| `remuneracao_baseada_acoes` | Numeric | Stock options, etc. |
| `numero_membros` | Integer | Quantidade |
| `numero_membros_remunerados` | Integer | Quantos receberam |

## Regras de Processamento

1. **Promoção Seletiva**: O FRE possui ~48 datasets, mas apenas 9 são promovidos para tabelas de domínio por relevância regulatória
2. **Resolução de Acionistas**: CNPJs/CPFs são normalizados e vinculados a entidades quando possível
3. **Moeda**: Valores monetários são convertidos para escala base (R$) automaticamente
4. **Histórico**: Cada ano gera novo documento; não há sobrescrita

## Exemplo: Análise de Concentração

```bash
GET /fre/posicao-acionaria?codigo_cvm=25224&ordenar_por=-percentual_capital_votante
```

Use para identificar acionistas com >5% de participação (obrigação de comunicação CVM).

## Notas para Governança

- FRE é a fonte primária para análise de estrutura societária
- Use `fre_relacoes_familiares` para mapear controle familiar
- `fre_participacoes_sociedades` expõe holdings e coligadas
- Sempre verifique `versao` para garantir que está consultando a última atualização