---
title: Informações Periódicas e Eventuais (IPE)
sidebar_position: 7
---

# Informações Periódicas e Eventuais (IPE)

## Visão Geral

Comunicações obrigatórias de fatos relevantes, assembleias, alterações estatutárias, acordos de acionistas e outros eventos corporativos.

## Metadados Técnicos

| Campo | Valor |
|-------|-------|
| **Fonte CVM** | `ipe` |
| **Arquivo ZIP** | `ipe_companhias_abertas_{ano}.zip` |
| **Periodicidade** | Contínua/Eventual |
| **Desde** | 2003 |
| **Tabelas Alvo** | `ipe_documentos` |

## Endpoints Principais

```bash
GET /ipe/documentos?codigo_cvm=25224
GET /ipe/documentos?categoria=Fato%20Relevante
GET /ipe/documentos?assunto=Assembleia
GET /ipe/documentos?data_referencia_inicio=2025-01-01&data_referencia_fim=2025-06-30
```

## Campos Principais

| Campo | Descrição |
|-------|-----------|
| `categoria` | Fato Relevante, Aviso aos Acionistas, Estatuto, etc. |
| `tipo` | Subclassificação regulatória |
| `assunto` | Descrição resumida do evento |
| `data_referencia` | Data do fato |
| `data_entrega` | Data de protocolo na CVM |
| `link_download` | URL para PDF original |
| `status` | Publicado, Cancelado, Retificado |

## Regras de Processamento

1. **Granularidade**: IPE não possui subarquivos CSV estruturados; é tratado como documento metadata
2. **Categorização**: Baseada em taxonomia CVM oficial
3. **Link Direto**: `link_download` aponta para sistema oficial de download da CVM
4. **Histórico Completo**: Preserva todas as versões e retificações

## Exemplo: Monitoramento de Fatos Relevantes

```bash
curl -X GET "http://localhost:8007/ipe/documentos?codigo_cvm=25224&categoria=Fato%20Relevante&ordenar_por=-data_entrega&tamanho_pagina=50" \
  -H "Authorization: Bearer seu-token"
```

## Notas para Compliance

- IPE é a principal fonte para monitoramento de eventos corporativos
- Use filtros por `categoria` para alertas automatizados
- `data_entrega` vs `data_referencia` ajuda a identificar atrasos de divulgação
- Links expiram? Não, são mantidos no portal CVM, mas consulte periodicamente