---
title: Radar Informativo Tucano CVM
sidebar_position: 2
---

# Radar Informativo Tucano CVM

O Radar Informativo Tucano CVM publica um feed JSON estatico com novidades publicas da CVM. Ele nao cria endpoint FastAPI, nao consulta PostgreSQL durante leitura e nao dispara ingestao automaticamente.

## Consumo pelo frontend

O frontend deve consumir apenas a URL publica do artefato:

```text
{RADAR_CVM_PUBLIC_BASE_URL}/radar-cvm/latest.json
```

O arquivo e publicado no Cloudflare R2 e deve ser servido por custom domain publico com Cache Rule da Cloudflare. O bucket/prefixo deve permitir `GET` e `HEAD` para `http://cvm.companhias.tucano.beakcloud.com`.

## Arquivos publicados

| Arquivo | Descricao |
| --- | --- |
| `radar-cvm/latest.json` | Feed atual e URL estavel para o frontend. |
| `radar-cvm/history/YYYY/MM/DD/HHmmss.json` | Snapshot historico imutavel da execucao. |
| `radar-cvm/latest.json.sha256` | Checksum do `latest.json`. |
| `radar-cvm/state.json` | Estado operacional do coletor, incluindo `ETag` e `Last-Modified` por canal. |

## Contrato do feed

Datas usam ISO 8601 UTC. O schema e fechado: consumidores devem ignorar apenas campos futuros depois de uma nova versao de schema documentada.

Campos de topo:

- `schema_version`: versao do contrato, atualmente `1.0`;
- `generated_at`: instante UTC de geracao do feed;
- `window`: janela de retencao usada no feed;
- `summary`: totais e checksum;
- `channels`: status de cada canal monitorado;
- `items`: novidades normalizadas.

Cada item contem `id`, `channel`, `kind`, `title`, `summary`, `url`, `published_at`, `captured_at`, `tags`, `relevance`, `signals` e `source_hash`.

## Staleness e falhas parciais

O frontend deve usar:

- `generated_at` para idade global do feed;
- `channels[].last_success_at` para idade por canal;
- `channels[].status` para distinguir `success`, `not_modified`, `partial`, `failed` e `disabled`;
- `channels[].error` para exibir diagnostico simples sem depender de logs;
- `summary.channels_failed` para alertas de degradacao.

Atualizacao minima diaria e aceitavel. Falha total por mais de 24h deve ser tratada como feed obsoleto.

## Configuracao backend

Variaveis principais:

```bash
RADAR_CVM_ENABLED=false
RADAR_CVM_QUEUE_NAME=celery
RADAR_CVM_STORAGE_BACKEND=r2
RADAR_CVM_STORAGE_PREFIX=radar-cvm/
RADAR_CVM_PUBLIC_BASE_URL=
RADAR_CVM_RETENTION_DAYS=90
RADAR_CVM_MAX_ITEMS=500
RADAR_CVM_REQUEST_TIMEOUT_SECONDS=30
RADAR_CVM_USER_AGENT="Radar-Informativo-Tucano-CVM/1.0"
RADAR_CVM_CACHE_CONTROL="public, max-age=300, s-maxage=3600, stale-while-revalidate=86400"

RADAR_CVM_R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
RADAR_CVM_R2_BUCKET=tucano-radar
RADAR_CVM_R2_ACCESS_KEY_ID=
RADAR_CVM_R2_SECRET_ACCESS_KEY=
RADAR_CVM_R2_REGION=auto
```

`RADAR_CVM_ENABLED=false` e o padrao para evitar execucao acidental em ambientes sem R2. Em desenvolvimento, `RADAR_CVM_STORAGE_BACKEND=local` publica em `STORAGE_DIR/radar/`.

## Integração com Sistemas Frontend

Para que qualquer sistema frontend possa consumir e exibir os dados do Radar Informativo Tucano CVM como fonte, devem ser observadas as seguintes especificações de contrato, tipos de dados e diretrizes de integração.

### 1. URLs e Acesso aos Recursos

Os arquivos de feed são estáticos e estão hospedados em ambiente público (geralmente Cloudflare R2 servido sob CDN). O frontend deve buscar os dados diretamente das seguintes URLs:

*   **Feed Completo (Mais Recente):** `{RADAR_CVM_PUBLIC_BASE_URL}/radar-cvm/latest.json`
*   **Checksum SHA-256 (Verificação Rápida):** `{RADAR_CVM_PUBLIC_BASE_URL}/radar-cvm/latest.json.sha256`
*   **Snapshots Históricos (opcional):** `{RADAR_CVM_PUBLIC_BASE_URL}/radar-cvm/history/YYYY/MM/DD/HHmmss.json`

> [!NOTE]
> *   **CORS:** O bucket e a CDN estão configurados para permitir requisições do tipo `GET` e `HEAD` vindas da origem do frontend (ex: `http://cvm.companhias.tucano.beakcloud.com`).
> *   **Autenticação:** Não é necessária chave de API ou assinatura de URL para leitura. O acesso é totalmente público.
> *   **Headers de Cache:** O servidor responde com cabeçalhos de cache apropriados (ex: `Cache-Control: public, max-age=300, s-maxage=3600, stale-while-revalidate=86400`).

### 2. Definições de Tipos (TypeScript)

Para garantir a tipagem estrita no frontend, utilize as seguintes interfaces baseadas no contrato oficial do feed (`v1.0`):

```typescript
export type RadarChannelKey = "noticias" | "novidades_dados" | "normas" | "atos_declaratorios";

export type RadarItemKind = 
  | "noticia" 
  | "novidade_dados" 
  | "norma" 
  | "ato_declaratorio" 
  | "consulta_publica" 
  | "outro";

export type RadarRelevance = "baixa" | "media" | "alta" | "normal" | "desconhecida";

export type RadarChannelStatus = "success" | "not_modified" | "partial" | "failed" | "disabled";

export interface RadarWindow {
  days: number;       // Janela de retenção configurada (ex: 90 dias)
  started_at: string; // Instante UTC de início da janela (ISO 8601)
  ended_at: string;   // Instante UTC de fim da janela (ISO 8601)
}

export interface RadarSummary {
  total_items: number;
  channels_scanned: number;
  channels_failed: number;
  checksum_sha256: string;
}

export interface RadarChannel {
  key: RadarChannelKey;
  url: string;
  status: RadarChannelStatus;
  last_success_at: string | null; // Instante UTC da última coleta bem-sucedida (ISO 8601)
  items_count: number;
  error: string | null;           // Mensagem de erro amigável em caso de falha no canal
}

export interface RadarItem {
  id: string;               // Identificador único determinístico (ex: "noticias:2026-07-08:slug-do-titulo")
  channel: RadarChannelKey; // Canal de origem do item
  kind: RadarItemKind;      // Tipo/categoria de publicação
  title: string;            // Título original da publicação
  summary: string | null;   // Resumo simplificado da novidade (limite recomendado de 1.000 caracteres)
  url: string;              // Link canônico no portal da CVM
  published_at: string | null; // Data de publicação oficial pela CVM (ISO 8601, UTC)
  captured_at: string;      // Instante de captura pelo coletor (ISO 8601, UTC)
  tags: string[];           // Tags normalizadas em snake_case ASCII (ex: ["layout", "dados_abertos"])
  relevance: RadarRelevance;
  signals: string[];        // Sinais identificados que definiram a classificação (ex: ["layout_mudanca"])
  source_hash: string;      // Hash SHA-256 do conteúdo bruto para detecção de alteração
}

export interface RadarFeed {
  schema_version: "1.0";
  generated_at: string;     // Instante UTC de geração do arquivo (ISO 8601)
  window: RadarWindow;
  summary: RadarSummary;
  channels: RadarChannel[];
  items: RadarItem[];
}
```

### 3. Exemplo de Payload JSON Completo

Abaixo está um exemplo representativo de um feed completo retornado por `/radar-cvm/latest.json`:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-08T13:00:00Z",
  "window": {
    "days": 90,
    "started_at": "2026-04-09T00:00:00Z",
    "ended_at": "2026-07-08T13:00:00Z"
  },
  "summary": {
    "total_items": 2,
    "channels_scanned": 3,
    "channels_failed": 1,
    "checksum_sha256": "8f9b9f71c4c1a2e3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7"
  },
  "channels": [
    {
      "key": "noticias",
      "url": "https://www.gov.br/cvm/pt-br/assuntos/noticias",
      "status": "success",
      "last_success_at": "2026-07-08T13:00:00Z",
      "items_count": 1,
      "error": null
    },
    {
      "key": "novidades_dados",
      "url": "https://dados.cvm.gov.br/pages/novidades",
      "status": "success",
      "last_success_at": "2026-07-08T12:30:00Z",
      "items_count": 1,
      "error": null
    },
    {
      "key": "normas",
      "url": "https://www.gov.br/cvm/pt-br/assuntos/normas",
      "status": "failed",
      "last_success_at": "2026-07-07T06:00:00Z",
      "items_count": 0,
      "error": "Timeout de requisição após 30 segundos"
    }
  ],
  "items": [
    {
      "id": "noticias:2026-07-08:presidente-da-cvm-reuniao-abrasca",
      "channel": "noticias",
      "kind": "noticia",
      "title": "Presidente da CVM participa de reunião com representantes da ABRASCA",
      "summary": "Encontro teve como pauta o desenvolvimento do mercado de capitais no Brasil.",
      "url": "https://www.gov.br/cvm/pt-br/assuntos/noticias/presidente-da-cvm-participa-de-reuniao-com-representantes-da-abrasca",
      "published_at": "2026-07-08T11:45:00Z",
      "captured_at": "2026-07-08T13:00:00Z",
      "tags": ["mercado_capitais"],
      "relevance": "media",
      "signals": ["noticia_institucional"],
      "source_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    },
    {
      "id": "novidades_dados:2026-07-08:novo-layout-dfp-2026",
      "channel": "novidades_dados",
      "kind": "novidade_dados",
      "title": "Atualização de layout do conjunto de dados DFP",
      "summary": "Inclusão de novos campos de classificação de contas a partir do exercício financeiro de 2026.",
      "url": "https://dados.cvm.gov.br/pages/novidades#dfp-2026",
      "published_at": "2026-07-08T08:00:00Z",
      "captured_at": "2026-07-08T12:30:00Z",
      "tags": ["layout", "dados_abertos"],
      "relevance": "alta",
      "signals": ["layout_mudanca", "dados_abertos_atualizacao"],
      "source_hash": "7f83b1657ff1fc53b92dc18148a1d65dfcbd6dfa590a318371cc50040293a855"
    }
  ]
}
```

### 4. Boas Práticas e Diretrizes de Implementação UI/UX

Ao renderizar o Radar Informativo, o frontend deve implementar os seguintes comportamentos para uma melhor experiência e tolerância a falhas:

1.  **Monitoramento de Staleness (Feed Desatualizado):**
    *   Compare o campo `generated_at` com o horário atual do dispositivo do usuário.
    *   Se a diferença for **superior a 24 horas**, exiba um banner ou indicador de aviso (ex: "Radar desatualizado: dados coletados em [data/hora]").
2.  **Tratamento de Falhas de Canais:**
    *   Verifique se `summary.channels_failed > 0`.
    *   Caso haja canais falhos, verifique na lista `channels` quais possuem `status: "failed"` e exiba um alerta visual ou tooltip (utilizando a mensagem de erro contida em `error`) informando que o canal específico (ex: "Normas CVM") pode estar temporariamente sem novos itens.
3.  **Ordenação dos Itens:**
    *   Ordene a exibição dos itens na tela por data decrescente.
    *   Use preferencialmente `published_at` (quando disponível). Se `published_at` for nulo, utilize `captured_at` como fallback de ordenação.
4.  **Destaque de Relevância:**
    *   Itens com `relevance: "alta"` devem ter destaque visual destacado (ex: borda colorida, ícone de alerta vermelho/laranja) para chamar a atenção imediata do operador.
5.  **Filtros Rápidos:**
    *   Disponibilize filtros interativos para permitir ao usuário filtrar a lista por **Canal** (`channel`), **Tipo** (`kind`) e por **Tags** de classificação (como `layout`, `normativa`, `dados_abertos`, etc.).

