---
title: Formulário Cadastral (FCA)
sidebar_position: 6
---

# Formulário Cadastral (FCA)

## Visão Geral

Documento de atualização cadastral obrigatório, focado em dados institucionais, endereços, DRI e emissões de valores mobiliários.

## Metadados Técnicos

| Campo | Valor |
|-------|-------|
| **Fonte CVM** | `fca` |
| **Arquivo ZIP** | `fca_companhias_abertas_{ano}.zip` |
| **Periodicidade** | Anual/Eventual |
| **Desde** | 2010 |
| **Tabelas Alvo** | `fca_documentos`, `fca_geral`, `fca_enderecos`, `fca_dri`, `fca_auditores`, `fca_valores_mobiliarios` |

## Endpoints Principais

```bash
GET /fca/documentos?codigo_cvm=25224
GET /fca/geral?codigo_cvm=25224
GET /fca/enderecos?codigo_cvm=25224
GET /fca/dri?codigo_cvm=25224
GET /fca/auditores?codigo_cvm=25224
GET /fca/valores-mobiliarios?codigo_cvm=25224
```

## Campos Principais

| Dataset | Finalidade |
|---------|------------|
| `fca_geral` | Razão social, CNPJ, código CVM, setor, situação |
| `fca_enderecos` | Sede, filiais, escritórios |
| `fca_dri` | Identificação e contatos do Diretor de Relações com Investidores |
| `fca_auditores` | Auditores independentes (diferente do FRE por foco cadastral) |
| `fca_valores_mobiliarios` | Ações, debêntures, CPRs, etc. em circulação |

## Diferença FRE vs FCA

| Aspecto | FRE | FCA |
|---------|-----|-----|
| **Foco** | Analítico/Societário/Governança | Cadastral/Institucional |
| **Detalhamento Acionário** | Completo por acionista | Geral |
| **Remuneração** | Detalhada por órgão/parte | Não incluída |
| **Endereços** | Não incluído | Completo |
| **DRI** | Breve | Completo com contatos |

## Notas para Backoffice

- FCA é essencial para validação de cadastros e comunicação oficial
- Use `fca_enderecos` para correspondência física/jurídica
- `fca_valores_mobiliarios` mapeia ISINs e códigos de negociação ativos