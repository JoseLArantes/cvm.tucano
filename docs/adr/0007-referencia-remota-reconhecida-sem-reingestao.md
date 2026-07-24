# ADR 0007: Referência remota reconhecida sem reingestão

## Status

Aceito.

## Contexto

A CVM pode republicar um ZIP com novos headers HTTP, compressão ou metadados internos sem alterar o SHA-256 dos CSVs contidos nele. Tratar esse caso como `ready_for_ingestion` comunica uma mudança de dados inexistente e executa trabalho desnecessário. Descartar a pendência também não resolve o problema, pois a comparação seguinte continua usando o artefato realmente ingerido e detecta novamente os mesmos metadados remotos.

Sobrescrever `IngestionFile` ou `SourceArtifactSnapshot` foi rejeitado porque essas entidades registram a proveniência do artefato efetivamente ingerido. Alterá-las para descrever um ZIP que não passou pela ingestão tornaria a linhagem imprecisa.

## Decisão

Uma análise com equivalência SHA-256 de todos os members resulta em `content_unchanged`, não em `ready_for_ingestion`.

O operador pode reconhecer os metadados remotos por uma ação específica que não dispara ingestão. A referência reconhecida registra o fingerprint dos members, os headers remotos, o operador, o instante da confirmação e a ingestão canônica usada como baseline.

O scanner pode usar essa referência somente enquanto a mesma ingestão canônica continuar vigente. Uma nova ingestão bem-sucedida substitui implicitamente sua aplicabilidade.

## Consequências

- mudança de distribuição e mudança de dados passam a ter ciclos operacionais distintos;
- referências de proveniência permanecem imutáveis;
- o mesmo ZIP republicado não reaparece indefinidamente após reconhecimento;
- reconhecer referência exige evidência de equivalência por member e nunca executa Celery;
- descartar continua sendo uma decisão de ignorar, sem atualizar baseline.
