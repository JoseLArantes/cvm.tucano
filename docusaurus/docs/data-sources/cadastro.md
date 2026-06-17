---
title: Cadastro de Companhias Abertas
sidebar_position: 2
---

# Cadastro de Companhias Abertas

## Visão Geral

Fonte primária de identificação dos emissores. Todas as outras fontes dependem da resolução de identidade vinculada a esta base.

## Metadados Técnicos

| Campo | Valor |
|-------|-------|
| **Fonte CVM** | `cadastro` |
| **Arquivo ZIP** | `cadastral_companhias_abertas.zip` |
| **Membros CSV** | `cadastro.csv` |
| **Periodicidade** | Diária (oficial) / Sincronização configurável |
| **Tabela Alvo** | `companhias` |
| **Chaves Naturais** | `cnpj_companhia`, `codigo_cvm` |

## Estrutura de Arquivo

```
cadastro.csv
├── CNPJ_COMPANHIA (14 dígitos, sem máscara)
├── COD_CVM (inteiro)
├── DENOM_SOCIAL (razão social)
├── DENOM_COMERC (nome fantasia, se houver)
├── SIT_REG (ATIVO, SUSPENSO, CANCELADO)
├── SIT_REG_DESC (descrição textual da situação)
├── DT_REG (data de registro na CVM)
├── DT_CONST (data de constituição jurídica)
├── DT_CANC (data de cancelamento, se aplicável)
├── MOTIVO_REG (motivo da situação)
├── SIT_EMITOR (emissor autorizado, autorizado não listado, etc.)
├── CATEG_REG (categoria de registro)
├── CONTROLE_ACIONARIO
├── DT_INICIO_SIT
├── DT_FIM_SIT
├── TIPO_MERCADO (Novo Mercado, Nível 2, Tradicional, etc.)
├── SETOR_ATIVIDADE
├── CNPJ_RESPONSAVEL
├── NOME_RESPONSAVEL
├── EMAIL_RESPONSAVEL
├── TELEFONE_RESPONSAVEL
├── LOGRADOURO_RESPONSAVEL
├── NUMERO_RESPONSAVEL
├── COMPLEMENTO_RESPONSAVEL
├── BAIRRO_RESPONSAVEL
├── CIDADE_RESPONSAVEL
├── UF_RESPONSAVEL
├── CEP_RESPONSAVEL
├── PAIS_RESPONSAVEL
```

## Mapeamento para Modelo

| Campo CVM | Tabela | Campo | Tipo | Transformação |
|-----------|--------|-------|------|---------------|
| `CNPJ_COMPANHIA` | `companhias` | `cnpj_companhia` | String | Remove máscara, valida 14 dígitos |
| `COD_CVM` | `companhias` | `codigo_cvm` | Integer | Cast direto |
| `DENOM_SOCIAL` | `companhias` | `denominacao_social` | String | Trim + UTF-8 sanitization |
| `SIT_REG` | `companhias` | `situacao_registro` | String | Mapeamento para enum interno |
| `DT_REG` | `companhias` | `data_registro` | Date | `YYYY-MM-DD` |
| `TIPO_MERCADO` | `companhias` | `tipo_mercado` | String | Normalização de case |
| `SETOR_ATIVIDADE` | `companhias` | `setor_atividade` | String | Mantido como informado |
| `*RESPONSAVEL` | `companhias` | `responsavel` | JSON | Agrupado em objeto estruturado |
| `LOGRADOURO_*` a `PAIS_*` | `companhias` | `endereco` | JSON | Agrupado em objeto estruturado |

## Endpoints Principais

### Listar Companhias
```bash
GET /companhias?pagina=1&tamanho_pagina=100&situacao_registro=ATIVO
```

### Buscar por Código CVM
```bash
GET /companhias/codigo-cvm/{codigo_cvm}
```

### Buscar por CNPJ
```bash
GET /companhias/{cnpj}
```

### Filtros Avançados
```bash
GET /companhias?nome=Petrobras&ordenar=ativa_nome&setor_atividade=Energia
```

## Regras de Negócio e Tratamento

1. **Deduplicação**: Se múltiplos registros compartilham CNPJ, prevalece o mais recente por `DT_REG`
2. **Status Registros**: Mapeamento automático:
   - `ATIVO` → `ativo: true`
   - `SUSPENSO(A) - DECISAO ADM` → `ativo: false`, `motivo: suspensao_admin`
   - `CANCELADO` → `ativo: false`, `motivo: cancelamento`
3. **Identificadores Históricos**: CNPJs antigos são preservados em `companhia_identificadores` para resolução retroativa
4. **Sincronização**: Atualiza `sincronizado_em` mesmo sem alteração material; `alterado_em` só muda se houver mudança em campos de negócio

## Exemplo de Consulta

```bash
curl -X GET "http://localhost:8007/companhias/codigo-cvm/25224" \
  -H "Authorization: Bearer seu-token"
```

**Resposta:**
```json
{
  "id": "f4f6a9d8-...",
  "cnpj_companhia": "08773135000100",
  "codigo_cvm": 25224,
  "denominacao_social": "2W ECOBANK S.A. - EM RECUPERACAO JUDICIAL",
  "denominacao_comercial": "2W ECOBANK S.A.",
  "situacao_registro": "SUSPENSO(A) - DECISAO ADM",
  "data_registro": "2020-10-29",
  "setor_atividade": "Energia Eletrica",
  "tipo_mercado": "Novo Mercado",
  "endereco": { ... },
  "responsavel": { ... },
  "criado_em": "2026-05-30T14:30:00Z",
  "sincronizado_em": "2026-06-15T08:00:00Z",
  "alterado_em": "2026-05-30T14:30:00Z"
}
```

## Notas para Auditores

- O campo `situacao_registro` reflete o status oficial no momento da última sincronização
- Para auditoria histórica, consulte `companhia_identificadores` e `historico_alteracoes_campos`
- CNPJs extintos são mantidos com `ativo=false` para preservar vínculos com DFP/ITR históricos