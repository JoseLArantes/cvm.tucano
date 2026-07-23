---
title: Radar Informativo Tucano CVM
sidebar_position: 2
---

# Radar Informativo Tucano CVM

O Radar coleta publicações públicas da CVM de forma assíncrona e entrega arquivos JSON estáticos. A leitura não passa pelo FastAPI ou pelo PostgreSQL: o frontend acessa diretamente o Cloudflare R2 por domínio público e CDN.

## URLs públicas

| Recurso | URL |
| --- | --- |
| Feed canônico v2 | `{RADAR_CVM_PUBLIC_BASE_URL}/radar-cvm/v2/latest.json` |
| Checksum v2 | `{RADAR_CVM_PUBLIC_BASE_URL}/radar-cvm/v2/latest.json.sha256` |
| Projeção compatível v1 | `{RADAR_CVM_PUBLIC_BASE_URL}/radar-cvm/latest.json` |
| Checksum v1 | `{RADAR_CVM_PUBLIC_BASE_URL}/radar-cvm/latest.json.sha256` |

Novas integrações devem usar v2. A URL v1 continua publicada como projeção temporária para consumidores existentes.

## Modelo

O contrato distingue:

- **fonte monitorada**: sitemap, RSS ou página índice usada para descoberta; aparece em `sources[]`, nunca em `items[]`;
- **publicação**: notícia, novidade de dados, norma ou consulta individual exibida em `items[]`;
- **observação**: inspeção operacional que atualiza `last_seen_at`, sem redefinir a data ou a posição da publicação.

Landing pages, arquivos anuais, paginação, navegação, anexos e links de acessibilidade não são publicações.

## Datas e identidade

`published_at` é a data editorial oficial da CVM. A precedência para notícias é:

1. `NewsArticle.datePublished`;
2. texto visível `Publicado em`;
3. card da listagem;
4. sitemap oficial;
5. valor previamente verificado.

Para normas, a data rotulada de publicação no DOU tem precedência. `pubDate` dos RSS de legislação e audiências funciona apenas como sinal de descoberta ou alteração. Em novidades de dados, `Aviso publicado em` define `published_at`, o cabeçalho do bloco é o fallback e `Atualizado em` define `updated_at`.

O ID é `channel` mais um hash da identidade canônica e não contém data. Corrigir `published_at` não altera o ID. O feed já vem ordenado por `published_at ?? first_seen_at`; `last_seen_at`, `updated_at` e `generated_at` não promovem um item na linha do tempo.

## Contrato TypeScript

```typescript
export type RadarChannelKey =
  | "noticias"
  | "novidades_dados"
  | "normas"
  | "atos_declaratorios";

export type RadarItemKind =
  | "noticia"
  | "novidade_dados"
  | "norma"
  | "ato_declaratorio"
  | "consulta_publica"
  | "outro";

export type RadarStatus =
  | "success"
  | "not_modified"
  | "partial"
  | "failed"
  | "disabled";

export type RadarSourceType = "sitemap" | "rss" | "index" | "mutable_page";
export type RadarSourceRole = "primary" | "fallback" | "signal" | "catalog";
export type RadarDatePrecision = "date" | "datetime";
export type RadarPublishedAtSource =
  | "json_ld"
  | "visible_label"
  | "listing"
  | "sitemap"
  | "dou_text"
  | "block_heading"
  | "previous_verified";

export interface RadarSource {
  id: string;
  channel: RadarChannelKey;
  title: string;
  url: string;
  source_type: RadarSourceType;
  role: RadarSourceRole;
  status: RadarStatus;
  last_checked_at: string;
  last_success_at: string | null;
  last_changed_at: string | null;
  content_hash: string | null;
  discovered_count: number;
  error: string | null;
}

export interface RadarItemV2 {
  id: string;
  source_ids: string[];
  channel: RadarChannelKey;
  kind: RadarItemKind;
  title: string;
  summary: string | null;
  url: string;
  published_at: string | null;
  published_at_precision: RadarDatePrecision | null;
  published_at_source: RadarPublishedAtSource | null;
  updated_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  content_changed_at: string;
  tags: string[];
  relevance: "baixa" | "media" | "alta" | "normal" | "desconhecida";
  signals: string[];
  content_hash: string;
}

export interface RadarFeedV2 {
  schema_version: "2.0";
  generated_at: string;
  window: {
    days: number;
    started_at: string;
    ended_at: string;
  };
  summary: {
    total_items: number;
    channels_scanned: number;
    channels_failed: number;
    sources_scanned: number;
    sources_failed: number;
    items_new: number;
    items_changed: number;
    items_without_published_at: number;
    checksum_sha256: string;
  };
  channels: Array<{
    key: RadarChannelKey;
    url: string;
    status: RadarStatus;
    last_success_at: string | null;
    items_count: number;
    error: string | null;
  }>;
  sources: RadarSource[];
  items: RadarItemV2[];
}
```

## Coleta

- a cada quatro horas: sitemap e listagem de notícias, com detalhes apenas de URLs novas ou sem data;
- diariamente: todas as fontes e revalidação semântica das notícias dentro da retenção;
- até três tentativas para timeout, `429` e `5xx`, respeitando `Retry-After`;
- limite padrão de duas requisições por segundo por host;
- lock Redis de 30 minutos impede sobreposição entre execução agendada e manual;
- `ETag` e `Last-Modified` evitam transferências quando confiáveis, mas o hash semântico decide se houve mudança.

Uma queda superior a 50% em uma fonte que possuía pelo menos quatro registros gera `partial` e preserva o snapshot anterior. Falhas temporárias e desaparecimento de links também não removem imediatamente publicações retidas.

## Publicação

A ordem é:

1. `radar-cvm/v2/history/YYYY/MM/DD/HHmmss.json`;
2. `radar-cvm/v2/state.json`;
3. checksums;
4. projeção `radar-cvm/latest.json`;
5. ponteiro canônico `radar-cvm/v2/latest.json`.

O último passo evita que consumidores vejam um feed v2 antes do estado e do histórico correspondente.

## Configuração

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
```

`RADAR_CVM_ENABLED=false` é o padrão. O backend mantém as credenciais; o frontend recebe somente a URL pública. Em desenvolvimento, `RADAR_CVM_STORAGE_BACKEND=local` grava em `STORAGE_DIR/radar-cvm/`.

O bucket/CDN deve permitir `GET` e `HEAD` para a origem do frontend e aplicar cache ao `latest.json`.

## Operação no Kubernetes

Confirmar o schedule carregado:

```bash
kubectl exec deploy/tucano-cvm-beat -- \
  celery -A app.worker.celery_app:celery_app inspect conf
```

Disparar uma execução completa na fila configurada:

```bash
kubectl exec deploy/tucano-cvm-worker -- \
  celery -A app.worker.celery_app:celery_app call \
  app.radar.tasks.run_radar_collection_task \
  --args='[["noticias","novidades_dados","normas"],"full"]' \
  --queue=celery
```

Uma segunda execução concorrente retorna `status=skipped` e `reason=collection_already_running`.

## Consumo no frontend

- tratar `generated_at` superior a 24 horas como feed obsoleto;
- mostrar degradação usando `channels[].status`, `sources[].status` e os campos `error`;
- criar a seção “Fontes da CVM” a partir de `sources[]`;
- usar a ordem recebida ou ordenar por `published_at ?? first_seen_at`;
- nunca usar `last_seen_at` como data editorial;
- usar `updated_at` apenas como indicação de atualização do conteúdo.
