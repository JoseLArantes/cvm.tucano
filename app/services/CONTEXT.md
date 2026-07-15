# Analysis and Service Context

This context covers domain services outside the ingestion subpackage, especially the analysis layer and canonical materialization.

## Scope

- `app/services/analise.py`
- `app/api/routers/analise.py`
- `app/schemas/analise.py`
- `app/models/analise.py`
- Materialization orchestration and Celery tasks in `app/worker/tasks.py`
- Financial helper services such as `app/services/financeiro_mapas.py` and `app/services/financeiro_valores.py`
- Tests for analysis, materialization campaigns, monitoring, and worker edge cases

For ingestion internals, also read `app/services/ingestion/CONTEXT.md`.

## Domain vocabulary

- **Analysis layer** means derived financial analysis exposed under `/analise/companhias/...`.
- **Canonical analysis** means persisted, normalized analysis rows that should be reused instead of recomputed per request.
- **Runtime fallback** means a request-time computation used only when canonical data is unavailable. Responses must expose this through `resolution.mode`.
- **Annual analysis** means historical annual analysis as a first-class behavior, not a one-off latest-year shortcut.
- **Materialization** means computing and persisting the canonical analysis layer.
- **Fundamentalist Read Model** means the persisted projection of a complete Fundamental Analysis response for one exact analysis context. It is built by the same analysis service rules used by the REST API and points to the canonical materialization execution that produced it.
- **Delivery Cache** means a disposable Redis copy of a serialized Fundamentalist Read Model or short-lived runtime fallback. It is never canonical state and may be rebuilt without data loss.
- **Campaign** means a grouped materialization workload by company and scope.
- **Item** means a unit of campaign work for one company/scope target.
- **Chunk** means the executable slice leased to a worker.
- **Admission gate** means the control that prevents new materialization chunks from starting during active ingestion or manual pause.
- **Scope** means analysis scope such as `consolidated` or `individual`.
- **Radar Informativo Tucano CVM** means the consultative feed of public institutional or regulatory CVM updates, separate from canonical ingestion and analysis.
- **Monitored channel** means a public CVM page watched by Radar Informativo Tucano CVM, such as news or data-portal updates. Avoid using **Source** for this concept because ingestion uses Source for structured CVM datasets.
- **Radar item** means one normalized public update emitted by Radar Informativo Tucano CVM with a canonical URL, classification signals, and publication/capture timestamps.
- **Análise Fundamentalista** (Fundamental Analysis) means a multi-stage, explainable analysis layer compiled into a single, authenticated response covering four stages (pilares).
- **Pilar** (Stage) means one of the four mandatory stages composing the Fundamental Analysis report: ponto_partida, resultado_eficiencia, caixa_solidez, governanca_conclusao.
- **Evidência** (Evidence) means a deterministic, traceable factual element (e.g., metric observation, signal, event, or document) with a stable, deterministic `evidence_id`.
- **Lacuna Analítica** (Analytical Gap) means an explicit unavailability of financial or institutional data, represented as unavailable rather than estimated or zeroed.
- **Conclusão Neutra** (Neutral Conclusion) means delivering only factual, objective information and data provenance without generating investment scores, recommendations, or qualitative advice.


## Operational rules

- Materialization exists to avoid expensive per-request recomputation.
- The default Fundamentalist Read Model is prewarmed after successful canonical materialization. Other exact canonical contexts may be persisted on first read.
- Version delivery caches by the complete analysis context, calculation version, and canonical materialization generation.
- Redis failure must degrade to the persisted read model or service compilation without changing the public response payload.
- Use the dedicated `analise_materializacao` queue for materialization work.
- Keep ingestion operational priority above materialization.
- The admission gate must block new chunks during active ingestion or manual pause.
- Do not reintroduce massive post-ingestion per-company fan-out.
- Preserve observability by campaign, item, chunk, and execution under `/analise/materializacoes/...`.
- Campaign recovery must distinguish stale chunks, pending undispatched campaigns, waiting-for-gate states, waiting-for-slot states, and active chunks.

## Rules for analysis changes

- Keep analysis contracts closed and typed.
- Keep units explicit for all values.
- Preserve `resolution.mode` semantics.
- Test both canonical and runtime fallback paths when behavior changes.
- Test monitoring and status edge cases when materialization behavior changes.
- If persisted analysis state changes, add an Alembic migration and update `app/models/CONTEXT.md` assumptions as needed.
