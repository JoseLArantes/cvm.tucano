# PRD: Radar Informativo Tucano CVM - feed estatico de novidades institucionais e regulatorias

**Versao:** 1.0  
**Data:** 2026-07-08  
**Status:** Draft revisado  
**Autor:** Arquitetura Tucano CVM  

---

## 1. Visao geral

### 1.1 Objetivo

Criar o **Radar Informativo Tucano CVM**, um servico assíncrono de baixa prioridade que monitora canais publicos da CVM, normaliza novidades institucionais/regulatorias e publica um feed JSON estatico para consumo por frontend, automacoes e operadores.

O Radar Informativo nao substitui a ingestao canonica de dados de companhias, nem o `updates-service`. Ele e uma camada informativa para responder: "o que mudou ou foi publicado pela CVM que pode exigir atencao humana ou tecnica?".

### 1.2 Problema a resolver

A plataforma ja possui:

- ingestao canonica de fontes estruturadas da CVM (`cadastro`, `dfp`, `itr`, `fre`, `fca`, `ipe`, `vlmo`, `cgvn`);
- `updates-service` para detectar alteracoes em artefatos de dados e preparar atualizacoes pendentes;
- auditoria pontual da pagina `https://dados.cvm.gov.br/pages/novidades` no diagnostico operacional de ingestao.

Ainda falta uma superficie leve e desacoplada para exibir novidades institucionais e regulatorias que nao pertencem diretamente ao modelo canonico de companhias. Hoje, um consumidor teria de consultar o site da CVM, fazer scraping proprio ou depender de leitura operacional interna.

### 1.3 Solucao proposta

Um pipeline periodico coleta paginas publicas da CVM, extrai itens recentes, aplica uma classificacao deterministica simples e publica um artefato JSON fechado e versionado.

O consumo de leitura deve preferir arquivo estatico servido por filesystem publico, CDN ou object storage. O backend FastAPI nao deve servir o feed em tempo real nem consultar PostgreSQL para cada leitura.

Na primeira entrega, o alvo de publicacao de producao sera o Cloudflare R2, usando a API S3-compatible via `boto3`. O artefato sera publico para leitura; credenciais existem apenas no lado do publicador.

Tambem deve existir um `LocalRadarPublisher` gravando em `STORAGE_DIR/radar/` para desenvolvimento local e testes sem dependencia externa.

---

## 2. Escopo e limites

### 2.1 Canais monitorados

Use **canal monitorado** para evitar confusao com `Source`/`fonte` da ingestao, que no projeto significa dataset estruturado como `dfp`, `itr` ou `fre`.

| Canal monitorado | URL base validada em 2026-07-08 | Tipo | Prioridade | Frequencia sugerida |
| --- | --- | --- | --- | --- |
| Noticias CVM | `https://www.gov.br/cvm/pt-br/assuntos/noticias` | HTML gov.br | MVP | A cada 4 horas |
| Novidades do Portal de Dados | `https://dados.cvm.gov.br/pages/novidades` | HTML estatico | MVP | Diaria, 06:30 |
| Normas CVM | `https://www.gov.br/cvm/pt-br/assuntos/normas` e subpaginas como `/resolucoes`, `/deliberacoes`, `/pareceres-de-orientacao`, `/audiencias-publicas` | HTML gov.br | MVP | Diaria, 06:00 |
| Atos Declaratorios | pagina gov.br historicamente exposta sob caminho de legislacao/treinamento | HTML gov.br | Candidato | Semanal, apos validacao manual do seletor |

Notas de revisao:

- o caminho `https://www.gov.br/cvm/pt-br/assuntos/legislacao/normas-da-cvm` nao deve ser usado como fonte primaria; a navegacao atual da CVM aponta para `assuntos/normas` e subpaginas;
- atos declaratorios devem entrar apenas depois de validacao do caminho e do layout, porque o resultado publico atual aparece em URL historica menos estavel;
- o canal de normas deve cobrir resolucoes, deliberacoes, pareceres de orientacao e audiencias/consultas publicas;
- qualquer canal novo deve ter teste de snapshot HTML antes de entrar no schedule padrao.

### 2.2 Fora do escopo

- Servir o feed por endpoint FastAPI no MVP.
- Consultar PostgreSQL durante leitura do feed.
- Persistir os itens do Radar Informativo em tabelas relacionais no MVP.
- Disparar ingestao automaticamente quando uma novidade for detectada.
- Armazenar PDFs ou documentos originais; o feed guarda metadados, resumo curto e link canonico.
- Monitorar documentos de companhias especificas; isso continua no pipeline de ingestao e nos endpoints de dominio.
- Enviar notificacoes push, email, Slack ou WhatsApp; outros servicos podem consumir o JSON e decidir alertas.

---

## 3. Relacao com a plataforma existente

### 3.1 Ingestao canonica

O Radar Informativo e consultivo. Ele pode indicar que a CVM publicou uma noticia ou alterou uma pagina, mas nao deve promover dados, criar `IngestionRun`, alterar `ExecucaoSincronizacao` nem inserir linhas em tabelas de dominio.

Quando o Radar Informativo identificar uma novidade sobre layout ou dados abertos, o comportamento aceito no MVP e apenas expor um item classificado como `dados_abertos` ou `layout`. A decisao de rodar o `updates-service` ou a ingestao permanece operacional e explicita.

### 3.2 Updates service

O `updates-service` existente ja detecta mudancas em artefatos CSV/ZIP da CVM e usa PostgreSQL para controlar `pending_updates`, membros, sessoes e disparos manuais. O Radar Informativo nao deve duplicar esse ciclo de vida.

| Dimensao | `updates-service` | Radar Informativo Tucano CVM |
| --- | --- | --- |
| Pergunta respondida | "Ha artefato de dados pronto para analisar/ingerir?" | "Que novidade publica da CVM merece atencao?" |
| Fonte principal | Artefatos em `dados.cvm.gov.br/dados/...` | Paginas publicas gov.br e portal de dados |
| Estado canonico | PostgreSQL operacional | Artefato JSON estatico |
| Acao | Preparar e disparar ingestao manualmente | Informar, classificar e linkar |
| Consumidor | Operador/backend/frontend operacional | Frontend, operador, automacoes read-only |

### 3.3 Filas e prioridade

Ingestao tem prioridade operacional sobre qualquer trabalho do Radar Informativo. Tasks do Radar Informativo nao podem ser roteadas para `ingestion` nem `ingestion_control`.

No MVP, o Radar Informativo usa a fila existente `celery` para evitar novo worker/container e reduzir custo operacional. Tasks do Radar Informativo continuam proibidas nas filas `ingestion` e `ingestion_control`.

Uma fila dedicada `radar` pode ser introduzida em versao futura se o volume crescer. Nesse caso, `app.worker.celery_app` deve declarar a queue e `docker-compose.workers.yml` deve ganhar worker explicito.

---

## 4. Contrato do artefato JSON

### 4.1 Localizacao

Chaves no R2:

- `radar-cvm/latest.json`: ponteiro estavel para o feed mais recente;
- `radar-cvm/history/YYYY/MM/DD/HHmmss.json`: snapshots historicos opcionais;
- `radar-cvm/latest.json.sha256`: checksum opcional para consumidores simples.

O bucket deve expor leitura publica para o prefixo publicado. O frontend `tucano-cvm-frontend` consumira o arquivo diretamente pela URL publica configurada em `RADAR_CVM_PUBLIC_BASE_URL`; nao ha URL assinada no contrato do MVP.

No filesystem local, a publicacao de `latest.json` deve usar escrita em arquivo temporario e `os.replace`. Em R2/S3-compatible, nao existe rename atomico universal; a implementacao deve publicar primeiro o snapshot imutavel e atualizar `latest.json` por ultimo. Objetos JSON devem ser gravados com `Content-Type: application/json; charset=utf-8`, `Cache-Control` explicito e metadata de checksum quando suportado pelo adapter.

### 4.2 Schema fechado

Datas do artefato estatico usam ISO 8601 UTC. Isso difere dos schemas FastAPI atuais que serializam varias datas em formato brasileiro; a diferenca deve ser explicita porque o Radar Informativo nao e um schema Pydantic de endpoint.

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
    "total_items": 42,
    "channels_scanned": 3,
    "channels_failed": 0,
    "checksum_sha256": "abc123..."
  },
  "channels": [
    {
      "key": "noticias",
      "url": "https://www.gov.br/cvm/pt-br/assuntos/noticias",
      "status": "success",
      "last_success_at": "2026-07-08T13:00:00Z",
      "items_count": 20,
      "error": null
    }
  ],
  "items": [
    {
      "id": "noticias:2026-07-08:presidente-da-cvm-participa-de-reuniao-com-representantes-da-abrasca",
      "channel": "noticias",
      "kind": "noticia",
      "title": "Presidente da CVM participa de reuniao com representantes da Abrasca",
      "summary": "Reuniao abordou temas relacionados ao mercado de capitais.",
      "url": "https://www.gov.br/cvm/pt-br/assuntos/noticias/...",
      "published_at": "2026-07-08T00:00:00Z",
      "captured_at": "2026-07-08T13:00:00Z",
      "tags": ["mercado_capitais"],
      "relevance": "media",
      "signals": ["noticia_institucional"],
      "source_hash": "sha256:..."
    }
  ]
}
```

### 4.3 Campos obrigatorios por item

| Campo | Tipo | Regra |
| --- | --- | --- |
| `id` | string | Deterministico, derivado de `channel`, data e URL canonica ou slug. |
| `channel` | enum | `noticias`, `novidades_dados`, `normas`, `atos_declaratorios` quando suportado. |
| `kind` | enum | `noticia`, `novidade_dados`, `norma`, `ato_declaratorio`, `consulta_publica`, `outro`. |
| `title` | string | Titulo publico preservado. |
| `summary` | string ou null | Resumo curto, sem copiar documento integral; limite recomendado de 1.000 caracteres. |
| `url` | string | URL canonica da CVM. |
| `published_at` | datetime ou null | Data publicada pela CVM quando extraivel. |
| `captured_at` | datetime | Momento UTC da coleta. |
| `tags` | array[string] | Tags normalizadas, em snake_case ASCII. |
| `relevance` | enum | `baixa`, `media`, `alta`, `desconhecida`. |
| `signals` | array[string] | Sinais determinísticos que explicam a classificacao. |
| `source_hash` | string | Hash do trecho normalizado usado para detectar mudanca. |

### 4.4 Estados por canal

| `status` | Significado |
| --- | --- |
| `success` | Canal coletado e parseado com sucesso. |
| `not_modified` | Coleta pulada por ETag/Last-Modified quando o servidor suportar. |
| `partial` | Canal respondeu, mas alguns itens foram rejeitados por contrato. |
| `failed` | Canal falhou; o feed deve preservar o ultimo snapshot valido dos demais canais. |
| `disabled` | Canal configurado, mas desligado por feature flag. |

Falha parcial nao deve apagar itens validos publicados anteriormente dentro da janela. O feed deve expor `channels_failed` e `channels[].error` para que o frontend mostre staleness sem depender de logs.

---

## 5. Coleta, normalizacao e classificacao

### 5.1 Coletor assíncrono

Responsabilidades:

1. carregar configuracao `RADAR_CVM_*`;
2. executar requests HTTP com `httpx`, timeout por canal e `User-Agent` identificavel;
3. respeitar `ETag` e `Last-Modified` quando disponiveis;
4. parsear HTML com extratores isolados por canal usando `selectolax` com backend Lexbor como parser primario;
5. validar itens contra schema fechado;
6. mesclar itens novos com o ultimo snapshot valido dentro da janela configurada;
7. publicar snapshot historico e `latest.json`;
8. emitir logs estruturados e metricas quando `ENABLE_PROMETHEUS_METRICS=true`.

Dependencias novas aceitas para o MVP:

- `selectolax`: parser HTML principal, com CSS selectors, performance alta e backend Lexbor preferencial;
- `boto3`: cliente S3-compatible para publicar no Cloudflare R2.

`beautifulsoup4`/`lxml` ficam fora do MVP, a menos que um canal especifico prove, por teste de snapshot, que `selectolax` nao parseia o HTML da CVM com estabilidade suficiente.

### 5.2 Regras de classificacao deterministica

A classificacao inicial deve ser explicavel por `signals`, nao por modelo opaco.

| Tag | Termos/sinais iniciais |
| --- | --- |
| `normativa` | resolucao, instrucao, deliberacao, parecer de orientacao, audiencia publica, consulta publica |
| `dados_abertos` | portal de dados, dados abertos, dataset, arquivo, csv, zip |
| `layout` | layout, leiaute, coluna, campo, schema, estrutura, dicionario |
| `atividade_sancionadora` | termo de compromisso, multa, sancionador, inabilitacao, suspensao |
| `mercado_capitais` | oferta publica, intermediario, companhia aberta, fundo, valores mobiliarios |
| `agenda_evento` | agenda, evento, curso, treinamento, reuniao |

Relevancia sugerida:

- `alta`: mudanca de layout/dataset, norma nova ou alterada, alerta regulatorio, sancao com impacto amplo;
- `media`: consulta publica, noticia institucional com impacto operacional, publicacao de relatorio relevante;
- `baixa`: agenda, eventos, cursos, comunicados sem impacto operacional claro;
- `desconhecida`: item valido sem sinal suficiente.

O criterio "precisao > 80%" so deve virar aceite depois de existir conjunto de avaliacao manual. No MVP, o aceite e classificacao deterministica, testada e auditavel.

---

## 6. Configuracao proposta

Adicionar somente quando o servico for implementado:

```bash
RADAR_CVM_ENABLED=false
RADAR_CVM_QUEUE_NAME=celery
RADAR_CVM_STORAGE_BACKEND=r2  # r2 | local
RADAR_CVM_STORAGE_PREFIX=radar-cvm/
RADAR_CVM_PUBLIC_BASE_URL=
RADAR_CVM_RETENTION_DAYS=90
RADAR_CVM_MAX_ITEMS=500
RADAR_CVM_REQUEST_TIMEOUT_SECONDS=30
RADAR_CVM_USER_AGENT="Radar-Informativo-Tucano-CVM/1.0"
RADAR_CVM_CACHE_CONTROL="public, max-age=3600"

# Cloudflare R2 via API S3-compatible/boto3
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

Schedules devem ser definidos no `beat_schedule` existente somente quando `RADAR_CVM_ENABLED=true`. O schedule nao deve ser ativado por `AUTO_TRIGGER_UPDATES`, pois esse flag pertence ao fluxo de atualizacoes de artefatos de dados.

O R2 deve ser configurado para leitura publica do prefixo publicado e CORS compatível com o frontend `http://cvm.companhias.tucano.beakcloud.com`, no minimo com `GET` e `HEAD`. Credenciais `RADAR_CVM_R2_*` nunca devem ser expostas ao frontend.

---

## 7. Observabilidade e operacao

### 7.1 Logs

Cada execucao deve registrar:

- `run_id`;
- canais planejados, coletados, pulados e com falha;
- contagem de itens novos, itens reaproveitados e itens rejeitados;
- motivo de rejeicao por contrato;
- chave publicada e checksum;
- duracao total e por canal.

### 7.2 Metricas

Se `ENABLE_PROMETHEUS_METRICS=true`, expor metricas no mesmo padrao do projeto:

| Metrica | Tipo | Labels |
| --- | --- | --- |
| `radar_collection_duration_seconds` | histogram | `channel`, `status` |
| `radar_items_total` | counter | `channel`, `result` |
| `radar_publish_total` | counter | `backend`, `status` |
| `radar_last_success_timestamp` | gauge | `channel` |
| `radar_feed_age_seconds` | gauge | `backend` |

### 7.3 Staleness

Dados antigos sao preferiveis a feed indisponivel, mas o artefato deve tornar staleness visivel:

- `generated_at` mostra a idade global do feed;
- `channels[].last_success_at` mostra a idade por canal;
- `channels[].error` descreve falha recente sem quebrar consumidores;
- alerta operacional deve disparar se nenhum canal tiver sucesso em 24h.

O staleness aceitavel para a primeira UI e de atualizacao minima diaria. A frequencia de coleta pode ser maior, mas o contrato operacional deve garantir que uma falta total de sucesso por mais de 24h seja visivel e alertavel.

---

## 8. Seguranca e conformidade

- Coletar apenas conteudo publico da CVM.
- Publicar feed publico; nao usar URL assinada no MVP.
- Usar `User-Agent` identificavel.
- Respeitar limites implicitos com timeout, retries pequenos e frequencia conservadora.
- Nao usar proxy rotativo para contornar bloqueio; se a CVM bloquear, reduzir frequencia e registrar incidente operacional.
- Nao copiar documentos integrais para o feed; publicar resumo curto e link canonico.
- Se o feed for publico, garantir que nao contenha tokens, caminhos internos, stack traces ou dados de configuracao.

---

## 9. Riscos e mitigacoes

| Risco | Impacto | Probabilidade | Mitigacao |
| --- | --- | --- | --- |
| Mudanca estrutural no HTML gov.br | Alto | Medio | Parsers por canal, snapshots HTML em testes, status `failed` por canal e alerta quando item count cair para zero. |
| URL de canal muda | Medio | Medio | Configurar URLs por settings e manter canais candidatos desabilitados ate validacao. |
| Radar Informativo conflita com `updates-service` | Alto | Baixo | Proibir disparo automatico de ingestao; Radar Informativo publica apenas sinais consultivos. |
| Tasks competem com ingestao | Alto | Baixo | Nao rotear para `ingestion`/`ingestion_control`; usar fila dedicada ou `celery` com volume baixo validado. |
| R2/boto3 adiciona nova dependencia operacional | Medio | Medio | Isolar em `R2RadarPublisher`, manter `LocalRadarPublisher` para testes, validar endpoint/bucket/cache/CORS em runbook. |
| Classificacao gera falso positivo | Medio | Medio | Expor `signals`, manter regras deterministicas e permitir `relevance=desconhecida`. |
| Feed fica obsoleto silenciosamente | Alto | Baixo | `generated_at`, `last_success_at` por canal e alerta de staleness. |

---

## 10. Criterios de aceite

### 10.1 MVP

- [ ] Coletar `noticias` e `novidades_dados` via task Celery periodica quando `RADAR_CVM_ENABLED=true`.
- [ ] Coletar `normas` cobrindo resolucoes, deliberacoes, pareceres de orientacao e audiencias/consultas publicas.
- [ ] Nao rotear tasks para `ingestion` ou `ingestion_control`.
- [ ] Publicar `latest.json` fechado e versionado no Cloudflare R2 usando `boto3`.
- [ ] Manter publicador local em `STORAGE_DIR/radar/` para desenvolvimento e testes.
- [ ] Expor leitura publica do feed sem URL assinada.
- [ ] Preservar ultimo snapshot valido quando um canal falhar.
- [ ] Deduplicar itens por ID deterministico e/ou URL canonica.
- [ ] Expor staleness no proprio JSON.
- [ ] Cobrir parsers com testes de snapshot HTML.
- [ ] Cobrir contrato JSON com teste de schema e compatibilidade.
- [ ] Validar CORS/cache para `http://cvm.companhias.tucano.beakcloud.com`.
- [ ] Documentar configuracao e operacao se houver mudanca de worker/schedule.

### 10.2 V1

- [ ] Adicionar historico versionado com retencao configuravel.
- [ ] Emitir metricas Prometheus quando habilitadas.
- [ ] Adicionar canal `atos_declaratorios` apenas com URL e parser estabilizados.

---

## 11. Plano de implementacao sugerido

| Fase | Entrega | Observacoes |
| --- | --- | --- |
| 0. Validacao | Confirmar URLs, snapshots HTML, R2 publico e CORS do frontend | Sem mudanca de contrato publico. |
| MVP | Task Celery, parsers de `noticias`, `novidades_dados` e `normas`, publisher R2/local, JSON fechado | Evitar PostgreSQL e endpoints. |
| V1 | Metricas, historico e runbook completo | Atualizar docs operacionais. |
| V1.1 | Endurecimento de canais e retencao historica | Ajustar com dados reais de producao. |
| V2 | Alertas ou API read-only opcional | So se houver caso de uso que justifique sair do feed estatico. |

Se a implementacao criar tabelas operacionais para execucoes do Radar Informativo, isso passa a ser mudanca persistida estrutural e exige Alembic migration, contexto de persistencia, testes SQLite/PostgreSQL e documentacao de contrato.

---

## 12. Decisoes humanas registradas

1. O feed do Radar Informativo Tucano CVM sera publico; o MVP nao usa URL assinada.
2. O alvo de producao e Cloudflare R2, compativel com API S3 e acessado pelo backend via `boto3`.
3. O parser HTML primario sera `selectolax` com backend Lexbor, acompanhado de testes de snapshot por canal.
4. O canal de normas deve cobrir resolucoes, deliberacoes, pareceres de orientacao e audiencias/consultas publicas.
5. A primeira UI consumidora sera `tucano-cvm-frontend`, em `http://cvm.companhias.tucano.beakcloud.com`.
6. Atualizacao minima diaria e aceitavel; falha total por mais de 24h deve ficar visivel no JSON e em alerta operacional.

---

## 13. Referencias verificadas

- Noticias CVM: `https://www.gov.br/cvm/pt-br/assuntos/noticias`
- Normas CVM: `https://www.gov.br/cvm/pt-br/assuntos/normas`
- Resolucoes CVM: `https://www.gov.br/cvm/pt-br/assuntos/normas/resolucoes`
- Novidades do Portal de Dados CVM: `https://dados.cvm.gov.br/pages/novidades`
- Atos Declaratorios, caminho historico observado: `https://www.gov.br/cvm/pt-br/Treinamento/legislacao/atos-declaratorios/atos-declaratorios`
- Cloudflare R2 S3-compatible API: `https://developers.cloudflare.com/r2/get-started/s3/`
- Cloudflare R2 com boto3: `https://developers.cloudflare.com/r2/examples/aws/boto3/`
- selectolax: `https://selectolax.readthedocs.io/`
