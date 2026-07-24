# ADR 0006: Read model persistido para Análise Fundamentalista

## Status

Aceito.

## Contexto

`GET /analise/companhias/{codigo_cvm}/fundamentalista` agrega séries, comparações, qualidade, sinais, eventos e evidências. Mesmo quando os fatos canônicos já estão materializados, recompilar o relatório completo a cada request repete consultas e transformação em Python. Esse custo não é compatível com instâncias pequenas de PostgreSQL nem com múltiplas réplicas da API.

O contrato público deve continuar com as mesmas URLs, parâmetros, schemas e semântica de `resolution.mode`. O cache não pode esconder a geração canônica usada, tornar uma resposta histórica inconsistente nem criar uma segunda implementação das regras analíticas.

## Decisão

O relatório agregado usa um **Fundamentalist Read Model** persistido em PostgreSQL por contexto exato:

- companhia e escopo;
- periodicidade, base e horizonte;
- corte `as_of`;
- blocos opcionais incluídos;
- versão de cálculo e versão do relatório.

O read model é produzido pelas mesmas funções de `app/services/analise.py` usadas pela API. O recorte padrão `annual/fy/5/latest`, sem grafo, é pré-compilado após cada materialização canônica bem-sucedida. Outros recortes canônicos são compilados e persistidos na primeira leitura. Uma nova execução canônica substitui a geração anterior do mesmo contexto.

Redis funciona somente como **Delivery Cache**. Sua chave inclui o contexto completo, a versão de cálculo e o UUID da geração canônica. Concorrência em cache miss é coordenada por lock temporário. Indisponibilidade do Redis degrada para leitura do read model ou compilação pelo service, sem alterar o payload.

O endpoint entrega `ETag`, aceita `If-None-Match` e pode responder `304 Not Modified`. Os headers `X-Analise-Source` e `X-Analise-Generation` tornam observável a origem e a geração da resposta.

O pool SQLAlchemy é limitado explicitamente por processo. O orçamento total de conexões deve considerar API, workers e réplicas, pois cada processo possui seu próprio pool.

## Consequências

Positivas:

- o caminho canônico comum deixa de recompor dezenas de consultas por request;
- o payload e as regras de negócio permanecem centralizados no service de análise;
- cache Redis pode ser purgado sem perda de estado canônico;
- `as_of` e os filtros continuam fazendo parte da identidade do resultado;
- a geração da materialização invalida naturalmente as chaves de entrega antigas.

Negativas:

- materializações passam a executar o prewarm de um relatório adicional;
- snapshots ocupam espaço no PostgreSQL e precisam acompanhar versões de cálculo e contrato;
- recortes não pré-aquecidos ainda pagam uma compilação inicial;
- `runtime_fallback` continua mais caro e recebe apenas cache curto, pois não representa estado canônico.

## Substitui

Esta decisão substitui apenas o item 4 do ADR 0005, que proibia materialização física do relatório no primeiro corte. Os demais limites daquele ADR continuam válidos.
