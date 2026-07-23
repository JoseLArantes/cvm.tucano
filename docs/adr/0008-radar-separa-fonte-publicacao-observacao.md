# ADR 0008: Radar separa fonte, publicação e observação

## Status

Aceito.

## Contexto

Páginas índice e novas coletas eram tratadas como itens equivalentes a publicações. Isso fazia páginas fixas aparecerem na linha do tempo e permitia que `captured_at` promovesse conteúdo antigo para o dia da execução.

## Decisão

O Radar mantém fontes monitoradas em `sources[]`, publicações individuais em `items[]` e observações apenas no estado operacional. Identidade e ordenação das publicações são estáveis e independentes da execução; `published_at` vem de evidência editorial oficial e `last_seen_at` nunca participa da posição na linha do tempo. O feed v2 é canônico, enquanto `radar-cvm/latest.json` é uma projeção v1 temporária.

## Consequências

- sitemaps, RSS, índices e arquivos anuais não são notícias ou normas;
- uma coleta sem mudança atualiza apenas a observação;
- correções de data não alteram o ID;
- mudanças de conteúdo não promovem publicações antigas para o dia atual;
- consumidores novos devem usar `radar-cvm/v2/latest.json`.
