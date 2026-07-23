# Contexto do Radar Informativo

O Radar Informativo monitora superfícies públicas da CVM e produz uma linha do tempo estática de publicações, sem participar da ingestão canônica de dados de companhias.

## Linguagem

**Fonte monitorada**:
Superfície oficial usada para descobrir ou detectar mudanças, como sitemap, RSS ou página índice. Não é um item da linha do tempo.
_Evitar_: notícia fonte, item de navegação

**Publicação**:
Conteúdo individual da CVM com identidade e data editorial próprias, exibido em `items[]`.
_Evitar_: captura, observação, página índice

**Observação**:
Resultado operacional de inspecionar uma fonte ou publicação em uma execução. Pode atualizar `last_seen_at`, mas não redefine a data editorial.
_Evitar_: publicação nova

**Data editorial**:
Data oficial em que a CVM publicou o conteúdo, representada por `published_at`.
_Evitar_: data da coleta, data de captura

**Mudança semântica**:
Alteração no título, resumo, corpo relevante ou links de uma publicação, desconsiderando navegação, rodapé, scripts e variações de espaço.
_Evitar_: qualquer mudança de HTML

**Projeção v1**:
Representação compatível derivada do feed canônico v2 para consumidores ainda ligados a `radar-cvm/latest.json`.
_Evitar_: feed canônico
