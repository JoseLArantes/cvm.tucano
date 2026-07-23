# PRD: Radar Informativo Tucano CVM

**Versão:** 2.0
**Data:** 2026-07-23
**Status:** Implementado

## 1. Objetivo

O Radar Informativo Tucano CVM monitora superfícies públicas da CVM, identifica publicações individuais e produz uma linha do tempo JSON estática para o `tucano-cvm-frontend`.

O Radar é consultivo. Ele não substitui a ingestão canônica, não dispara o `updates-service`, não cria endpoint FastAPI e não consulta PostgreSQL durante a leitura. O feed público é servido pelo Cloudflare R2/CDN para absorver volume sem transferir carga ao backend.

## 2. Modelo

O serviço distingue:

- **fonte monitorada**: sitemap, RSS ou página índice usada para descoberta e detecção de mudanças;
- **publicação**: conteúdo individual da CVM com identidade e data editorial próprias;
- **observação**: resultado operacional de uma coleta, sem efeito sobre a data editorial.

Fontes aparecem em `sources[]`. Publicações aparecem em `items[]`. Uma observação atualiza estado e `last_seen_at`, mas nunca cria uma publicação apenas porque a coleta ocorreu.

## 3. Escopo

### 3.1 Notícias

- descoberta primária: `https://www.gov.br/cvm/sitemap.xml`;
- fallback: `https://www.gov.br/cvm/pt-br/assuntos/noticias`;
- detalhe: páginas individuais sob `/cvm/pt-br/assuntos/noticias/...`;
- metadados: `NewsArticle`, `h1.documentFirstHeading`, `.documentDescription` e `[property="rnews:articleBody"]`.

A listagem, arquivos anuais, paginação, anexos, navegação e links de acessibilidade não são itens.

### 3.2 Normas e consultas

Índices monitorados:

- `https://conteudo.cvm.gov.br/legislacao/resolucoes.html`;
- `https://conteudo.cvm.gov.br/legislacao/deliberacoes.html`;
- `https://conteudo.cvm.gov.br/legislacao/pareceres-orientacao.html`;
- `https://conteudo.cvm.gov.br/audiencias_publicas/index.html`.

Sinais complementares:

- `https://conteudo.cvm.gov.br/feed/legislacao.xml`;
- `https://conteudo.cvm.gov.br/feed/audiencias.xml`.

Somente links que correspondem a documentos individuais geram itens. O `pubDate` do RSS não é data original da norma. Publicação no DOU define `published_at`; retificação, revogação e alteração podem definir `updated_at`, sem mover a publicação na linha do tempo.

Aliases `www.cvm.gov.br` e `cvm.gov.br` são canonicalizados para `https://conteudo.cvm.gov.br`.

### 3.3 Novidades de dados

`https://dados.cvm.gov.br/pages/novidades` é uma fonte mutável. Seu conteúdo é dividido em blocos separados por `<hr>`, com um item por novidade.

- `Aviso publicado em`: data inicial;
- cabeçalho do bloco: fallback da data inicial;
- `Atualizado em`: data de atualização.

Blocos distintos podem compartilhar a mesma URL. A identidade combina data inicial e link principal; sem link, usa uma assinatura estável do texto.

### 3.4 Fora do escopo

- endpoints FastAPI;
- tabelas PostgreSQL e migrações Alembic;
- worker/container exclusivo;
- ingestão automática;
- armazenamento de PDFs ou documentos integrais;
- `atos_declaratorios`, que permanece desabilitado.

## 4. Contrato público

### 4.1 Artefatos

| Chave | Uso |
| --- | --- |
| `radar-cvm/v2/latest.json` | Feed canônico v2 |
| `radar-cvm/v2/latest.json.sha256` | Checksum do feed v2 |
| `radar-cvm/v2/history/YYYY/MM/DD/HHmmss.json` | Snapshot histórico v2 |
| `radar-cvm/v2/state.json` | Estado operacional privado do coletor |
| `radar-cvm/latest.json` | Projeção compatível v1 |
| `radar-cvm/latest.json.sha256` | Checksum da projeção v1 |

Novas integrações usam v2. O frontend acessa `{RADAR_CVM_PUBLIC_BASE_URL}/radar-cvm/v2/latest.json` sem autenticação ou URL assinada.

### 4.2 Feed v2

O schema fechado contém:

- `schema_version="2.0"`;
- `generated_at` e `window`;
- `summary`;
- `channels[]`;
- `sources[]`;
- `items[]`.

`summary` expõe `total_items`, totais de canais e fontes, `items_new`, `items_changed`, `items_without_published_at` e checksum.

Cada fonte contém:

- `id`, `channel`, `title`, `url`, `source_type` e `role`;
- `status`, `last_checked_at`, `last_success_at` e `last_changed_at`;
- `content_hash`, `discovered_count` e `error`.

Cada publicação contém:

- `id`, `source_ids`, `channel`, `kind`, `title`, `summary` e `url`;
- `published_at`, `published_at_precision` e `published_at_source`;
- `updated_at`, `first_seen_at`, `last_seen_at` e `content_changed_at`;
- `tags`, `relevance`, `signals` e `content_hash`.

Datas usam ISO 8601 UTC.

## 5. Regras temporais

O ID é `channel + SHA-256(identity_key)[:24]` e não inclui data. A linha do tempo é ordenada por `published_at ?? first_seen_at`.

Para notícias, a precedência de `published_at` é:

1. JSON-LD `NewsArticle.datePublished`;
2. texto visível `Publicado em`;
3. card da listagem;
4. sitemap;
5. data previamente verificada.

Uma observação incompleta nunca apaga título, resumo, hash ou data existentes. Notícias novas sem data oficial ficam pendentes no estado e fora do feed.

`updated_at` só é preenchido com evidência oficial. Uma atualização preserva `published_at`, `first_seen_at`, ID e posição original.

## 6. Detecção de mudanças

O hash de publicação considera a representação canônica de título, resumo, corpo relevante e URL. Menus, rodapés, scripts, compartilhamento e variações de espaço são excluídos pelos seletores específicos.

O hash de uma fonte índice é calculado a partir do conjunto ordenado de identidades e hashes dos registros. Mudanças de layout que preservam os registros não mudam o hash.

- hash igual: atualizar apenas `last_seen_at`;
- hash diferente: atualizar conteúdo e `content_changed_at`;
- data oficial de atualização: também atualizar `updated_at`;
- queda superior a 50% em fonte com ao menos quatro registros: marcar `partial` e preservar snapshot anterior;
- desaparecimento temporário: manter publicação até a política de retenção.

`ETag` e `Last-Modified` são otimizações. O hash semântico é a autoridade.

## 7. Estado e migração

`state.json` v2 mantém validadores HTTP e estado por fonte, além da última versão conhecida de cada item e itens pendentes.

Na ausência de estado v2, o coletor lê snapshots v1 disponíveis:

- recupera o menor `captured_at` como `first_seen_at`;
- canonicaliza URLs;
- cria IDs estáveis;
- descarta índices e navegação;
- revalida notícias retidas para corrigir datas;
- não publica notícias ainda sem data oficial.

## 8. Execução

- a cada quatro horas: notícias em modo `incremental`;
- diariamente: todos os canais em modo `full`;
- fila Celery padrão configurável por `RADAR_CVM_QUEUE_NAME`;
- nenhuma task usa `ingestion` ou `ingestion_control`;
- lock Redis com TTL padrão de 30 minutos;
- cliente HTTP com três tentativas para timeout, `429` e `5xx`;
- `Retry-After` respeitado;
- limite padrão de duas requisições por segundo por host.

Publicação no R2:

1. history v2;
2. state v2;
3. checksums;
4. projeção v1;
5. `v2/latest.json`.

Em storage local, cada arquivo usa temporário e `os.replace`.

## 9. Configuração

```bash
RADAR_CVM_ENABLED=false
RADAR_CVM_QUEUE_NAME=celery
RADAR_CVM_STORAGE_BACKEND=r2
RADAR_CVM_STORAGE_PREFIX=radar-cvm/
RADAR_CVM_PUBLIC_BASE_URL=
RADAR_CVM_RETENTION_DAYS=90
RADAR_CVM_MAX_ITEMS=500
RADAR_CVM_REQUEST_TIMEOUT_SECONDS=30
RADAR_CVM_REQUESTS_PER_SECOND=2
RADAR_CVM_LOCK_TTL_SECONDS=1800
RADAR_CVM_USER_AGENT="Radar-Informativo-Tucano-CVM/1.0"
RADAR_CVM_CACHE_CONTROL="public, max-age=300, s-maxage=3600, stale-while-revalidate=86400"

RADAR_CVM_R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
RADAR_CVM_R2_BUCKET=tucano-radar
RADAR_CVM_R2_ACCESS_KEY_ID=
RADAR_CVM_R2_SECRET_ACCESS_KEY=
RADAR_CVM_R2_REGION=auto

RADAR_CVM_NOTICIAS_ENABLED=true
RADAR_CVM_NOVIDADES_DADOS_ENABLED=true
RADAR_CVM_NORMAS_ENABLED=true
RADAR_CVM_ATOS_DECLARATORIOS_ENABLED=false
```

O bucket e a CDN permitem `GET` e `HEAD` para `http://cvm.companhias.tucano.beakcloud.com`. Credenciais R2 nunca são expostas ao frontend.

## 10. Critérios de aceite

- 100% das notícias emitidas possuem data oficial;
- zero URLs de índice em `items[]`;
- nenhum item regride de data oficial para `null`;
- IDs não mudam após correção de data;
- duas execuções sem mudança produzem `items_new=0` e `items_changed=0`;
- menu ou rodapé não altera `content_hash`;
- mudança de corpo altera `content_hash` e `content_changed_at`, sem alterar a data editorial;
- blocos distintos de novidades coexistem na mesma URL;
- falha de detalhe preserva metadados conhecidos;
- queda anormal de índice resulta em `partial` e preserva o snapshot;
- falhas parciais continuam visíveis em `channels[]`, `sources[]` e `summary`;
- primeira execução totalmente falha não publica `latest.json`.

## 11. Decisões registradas

1. O feed é público.
2. Cloudflare R2 é o storage de produção.
3. O parsing HTML usa `selectolax`/Lexbor.
4. O canal normativo cobre resoluções, deliberações, pareceres e audiências/consultas.
5. O frontend inicial é `tucano-cvm-frontend`.
6. Atualização mínima diária é aceitável.
7. O feed v2 separa fontes, publicações e observações conforme ADR 0008.
