---
title: Setores e Análise de Grupos
sidebar_position: 6
---

# Setores e análise de grupos

Todas as rotas desta página exigem o bearer token da API. Os endpoints do dicionário usam a taxonomia publicada e retornam sua versão para que o cliente saiba qual classificação compôs a resposta.

## Taxonomias publicadas

### `GET /setores/taxonomias`

Lista os dicionários conhecidos, sua fonte, estado e publicação atual.

- `cvm_cadastro`: rótulo de setor informado no cadastro de companhias da CVM.
- `b3`: reservada para classificação oficial da B3. Permanece sem publicação até que haja uma fonte autorizada disponível para ingestão.

### `GET /setores/taxonomias/{taxonomia}/versoes`

Lista publicações em ordem decrescente. Cada item informa o checksum semântico, a referência da fonte, os instantes observados/publicados e o resumo da publicação. Reingestões sem mudança semântica não criam uma nova versão.

## Catálogo e vínculos

### `GET /setores`

Parâmetros:

| Campo | Padrão | Descrição |
| --- | --- | --- |
| `taxonomia` | `cvm_cadastro` | Taxonomia publicada a consultar. |
| `nome` | — | Busca por trecho no nome ou na chave normalizada. |
| `incluir_inativos` | `false` | Inclui setores que já não têm atribuições vigentes. |
| `pagina` | `1` | Página iniciada em 1. |
| `tamanho_pagina` | `100` | Entre 1 e 500. |

A resposta contém `dados`, paginação, `taxonomia` e `versao_taxonomia`. Cada setor tem UUID opaco, nome, chave normalizada, nível, pai, estado e total de companhias com atribuição vigente.

A chave CVM normaliza Unicode para NFC, espaços consecutivos e caixa baixa Unicode (`lower`) com resultado em NFC. A regra conserva acentos e pontuação e não aplica expansões de equivalência como `ß` para `ss`. Uma diferença semântica de grafia não é fundida automaticamente. O valor de origem permanece na classificação para auditoria; a resposta de companhia também preserva `setor_atividade`.

### `GET /setores/{setor_id}`

Retorna o setor, versão, contagem vigente, aliases explícitos e correspondências auditadas. `incluir_correspondencias=false` omite somente as relações cruzadas.

### `GET /setores/{setor_id}/companhias`

Lista companhias com atribuição vigente ao setor, com paginação e o filtro `taxonomia` (padrão `cvm_cadastro`). Um setor conhecido pode retornar uma lista vazia.

### Filtro em `GET /companhias`

`setor_id={uuid}` restringe a lista a companhias ligadas ao setor vigente. `taxonomia` seleciona a classificação e também preenche `setor_id` e `taxonomia_setorial` nas respostas de companhia. O texto legado `setor_atividade` continua disponível com o cadastro CVM.

## Curadoria do dicionário

As operações abaixo exigem permissão administrativa além do bearer token geral.

### `POST /setores/aliases`

Cria um alias explícito na mesma taxonomia. O corpo recebe `taxonomia`, `setor_id`, `rotulo_origem`, `evidencias`, `justificativa` e `revisado_por`. O alias aponta para um conceito existente e não modifica seu UUID. Rótulos já presentes como conceito ou alias retornam `409 ROTULO_SETOR_JA_CADASTRADO`.

### `POST /setores/correspondencias`

Cria uma relação direcional entre conceitos publicados. `tipo` aceita `equivalente`, `mais_amplo`, `mais_estreito` e `relacionado`. O registro inclui evidência, justificativa, revisão e versão do mapeamento; relações muitos-para-muitos são permitidas.

Até a publicação de uma fonte B3 autorizada, consultas e curadoria envolvendo `b3` retornam `409 TAXONOMIA_SEM_PUBLICACAO`.

## Agregar margens

### `POST /analise/companhias/agregacoes`

Calcula margens anuais de um conjunto de emissores a partir dos fatos canônicos de análise, com uma leitura em lote dos componentes financeiros.

```json
{
  "taxonomia": "cvm_cadastro",
  "companhia_ids": [],
  "codigos_cvm": [906],
  "setores": [],
  "categorias_registro": ["Categoria A"],
  "tipos_emissor": [],
  "situacoes_registro": ["ATIVO"],
  "anos": [2023, 2024],
  "escopo": "consolidated",
  "metricas": ["margem_liquida"],
  "estatisticas": ["media_simples", "mediana", "razao_das_somas"],
  "agrupar_por": ["setor"],
  "as_of": null,
  "incluir_detalhamento": false
}
```

Filtros diferentes são intersectados; valores dentro da mesma lista formam uma união. `companhia_ids` (UUIDs internos) e `codigos_cvm` formam uma única seleção por união, limitada a 500 identidades combinadas; `setores` aceita até 100 UUIDs. A seleção resultante é limitada a 5.000 companhias. São aceitos de 1 a 10 exercícios e as métricas `margem_bruta`, `margem_ebit` e `margem_liquida`. `agrupar_por` aceita até duas dimensões distintas dentre `setor`, `categoria_registro`, `tipo_emissor` e `situacao_registro`, e a resposta tem limite de 5.000 células. O resultado utiliza a classificação vigente da taxonomia solicitada em todos os exercícios. Informe algum seletor de universo ou `todas=true` isoladamente; a seleção ampla nunca é implícita.

`estatisticas` aceita `media_simples`, `mediana` e `razao_das_somas`; se omitida, retorna as três. Os fatos necessários são `lucro_bruto` ou `ebit` ou `lucro_liquido`, mais `receita_liquida`, para `annual/fy`, no escopo solicitado e na versão de cálculo vigente. A margem é calculada apenas com numerador e denominador canônicos em BRL e receita positiva. Lacunas, emissor sem código CVM e incompatibilidade de unidade reduzem a cobertura; prejuízo é mantido como margem negativa.

Cada célula informa `unit=ratio`, estado (`disponivel`, `parcial` ou `indisponivel`), seleção, elegibilidade e motivos de exclusão. As estatísticas são:

- `media_simples`: média das margens individuais, com o mesmo peso por emissor;
- `mediana`: centro da distribuição das margens individuais;
- `razao_das_somas`: soma dos numeradores dividida pela soma das receitas elegíveis.

`as_of` seleciona a revisão financeira cujo intervalo de conhecimento contém a data. Sem esse campo, são usadas revisões vigentes. A resposta informa `calculation_version`, `resolution_mode=canonical`, a versão da taxonomia, a geração financeira e uma impressão digital do recorte. `atualidade` permanece `indeterminada` com o motivo `LINHAGEM_DE_ENTRADA_NAO_COMPROVADA` enquanto a execução canônica não registrar a assinatura das entradas DFP/ITR cobertas por companhia e escopo; a geração identificada não é apresentada como prova de atualidade.

`incluir_detalhamento=true` retorna os componentes e a proveniência documental do numerador e da receita de cada emissor elegível; é limitado a 500 companhias selecionadas. O resumo projeta apenas valor/unidade do JSON canônico, sem transferir proveniência completa. Resumos e detalhamento usam a mesma consulta em lote; o cache Redis de entrega tem namespace, TTL e chave separados, incluindo o corpo normalizado, a versão da taxonomia e a geração financeira. Se o Redis estiver indisponível, a consulta continua pelo banco.

Uma taxonomia conhecida mas ainda sem publicação retorna `409`; IDs de setor desconhecidos no detalhe retornam `404`; corpos inválidos ou detalhamento acima do limite retornam `422`.
