# Fundos de Investimento Imobiliário

Os endpoints `/fiis` retornam os dados declarados pela CVM no Informe Mensal Estruturado. Todas as rotas exigem o token da API. Os caminhos usam o CNPJ canônico de 14 caracteres, sem pontuação, e o tipo `fundo` ou `classe`. O tipo descreve o informe publicado; o cadastro formal e o vínculo regulatório entre fundo e classe não são carregados por esta fonte.

O catálogo seleciona o informe mais recente que consta no snapshot anual publicado para cada identidade. `competencia` é a data de referência formatada como `AAAA-MM`. Decimais são serializados como strings para preservar a precisão da CVM. Cada seção inclui `unidades`, um mapa dos campos em `dados` para `BRL`, `BRL/cota`, `cotas`, `contagens`, `percentual CVM` ou unidade descritiva. Valores monetários são expressos em reais, quantidades de cotas podem ser fracionárias e contagens de cotistas são inteiros. Os campos cujo nome começa com `Percentual_` preservam a escala decimal reportada pela CVM.

## `GET /fiis`

Lista fundos e classes com os fundamentos do informe vigente.

| Parâmetro | Tipo | Descrição |
| --- | --- | --- |
| `pagina` | inteiro, padrão `1` | Página da resposta. |
| `tamanho_pagina` | inteiro, padrão `100`, máximo `500` | Número máximo de registros. |
| `cnpj` | texto | CNPJ de 14 caracteres, numérico ou alfanumérico, com ou sem pontuação. |
| `tipo` | `fundo` ou `classe` | Tipo do registro publicado no informe. |
| `nome` | texto | Busca parcial sem diferenciar maiúsculas e minúsculas. |
| `codigo_isin` | texto | Código ISIN do informe. |
| `segmento_atuacao` | texto | Segmento informado no perfil. |
| `negociado_em_bolsa` | booleano | Indicador de negociação em bolsa informado no perfil. |

Os filtros de perfil são aplicados depois de selecionar o informe vigente. A resposta usa `dados` e `paginacao`, com patrimônio líquido, ativo, valor patrimonial por cota, total de cotistas, dividend yield e disponibilidade das três seções. `disponibilidade_secoes` informa `disponivel`, `ambiguo` ou `ausente`.

## `GET /fiis/{cnpj}/{tipo}`

Retorna `identidade` e `informe_atual`, com o perfil e as seções disponíveis da referência mais recente. Retorna `404` quando não existe informe vigente para a identidade.

## `GET /fiis/{cnpj}/{tipo}/informes`

Lista as competências em ordem decrescente. `competencia_inicio` e `competencia_fim` aceitam `AAAA-MM` e são inclusivos. `todas_versoes=false` seleciona a maior versão presente no snapshot atual para cada competência. Com `todas_versoes=true`, a resposta inclui todas as versões já observadas, inclusive as que saíram do snapshot atual; `consta_no_snapshot_atual` identifica cada versão. Uma identidade inexistente retorna `404`; filtros que não selecionem competências retornam uma lista vazia. A paginação e os campos-resumo são iguais aos de `GET /fiis`.

## `GET /fiis/{cnpj}/{tipo}/informes/{competencia}`

Retorna o informe completo para uma competência `AAAA-MM`, incluindo perfil, `geral`, `complemento`, `ativo_passivo` e `proveniencia`. Sem `versao`, seleciona a maior versão presente no snapshot atual. O parâmetro opcional `versao` consulta uma versão já observada, incluindo uma versão que deixou de constar no snapshot atual. `consta_no_snapshot_atual` indica essa condição.

Cada seção financeira retorna `status`, `dados`, `unidades`, `proveniencia`, `consta_no_snapshot_atual` e `variantes`. Se o CNPJ, a competência e a versão identificam uma única seção, `status` é `disponivel`. Se fundo e classe compartilham a chave e há mais de uma composição financeira sem forma segura de atribuição, `status` é `ambiguo`, `dados` é `null` e `variantes` apresenta cada composição distinta com unidades e proveniência individual. Duplicatas idênticas em quantidade compatível com as linhas do informe geral podem ser atribuídas a cada tipo. Uma seção sem linha correspondente retorna `status=ausente`.

Parâmetros inválidos retornam `422`. Informes ou identidades inexistentes retornam `404`. Os leiautes verificados de 2016 a 2026 usam os mesmos nomes canônicos. Campos incorporados depois, como `CRI_CRA` e `LCI_LCA`, aparecem como `null` nos anos anteriores. Valores decimais permanecem strings na escala exata do arquivo. A proveniência de cada seção e de cada variante identifica CSV, ZIP, linha, hash, execução e presença no snapshot atual.
