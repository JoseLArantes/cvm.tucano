---
title: Setores e Análise de Grupos
sidebar_position: 6
---

# Setores e análise de grupos

Todas as rotas desta página exigem `Authorization: Bearer <token>`. As operações de curadoria e o upload manual B3 exigem, além do token, uma credencial administrativa: usuário com permissão `is_admin` ou token de sistema. As consultas do dicionário usam uma publicação específica e retornam sua versão quando a resposta representa um catálogo ou conjunto de companhias.

## Taxonomias publicadas

### `GET /setores/taxonomias`

Lista os dicionários conhecidos, sua fonte, estado e publicação atual. Use `codigo` como valor de `taxonomia` nas demais rotas. `versao_atual` identifica a última publicação semântica, não a data em que o arquivo foi baixado.

- `cvm_cadastro`: rótulo cadastral informado pela CVM. A ingestão do cadastro publica os conceitos e atribui as companhias com base em `setor_atividade`.
- `b3`: hierarquia de setor, subsetor e segmento publicada pelo upload manual de uma planilha. A importação não associa emissores B3 às companhias CVM. Antes da primeira publicação, consultas que dependam dessa taxonomia respondem `409 TAXONOMIA_SEM_PUBLICACAO`.

### `GET /setores/taxonomias/{taxonomia}/versoes`

Lista publicações em ordem decrescente de `versao`. Cada item inclui `checksum_fonte` (SHA-256 dos bytes da fonte, quando disponível), `checksum_semantico` (conteúdo dos conceitos e relações), `referencia_fonte`, `observada_em`, `publicada_em` e um resumo. Reenvios podem ter checksum de arquivo diferente sem gerar outra versão se a hierarquia semântica não mudou. Taxonomia inexistente retorna `404`; uma taxonomia cadastrada ainda sem versão pode retornar uma lista vazia.

## Importação manual da hierarquia B3

O fluxo publica exclusivamente o vocabulário setorial B3. A CVM continua sendo a fonte de verdade para a identidade e os dados cadastrais das companhias. Não use as colunas de emissores do arquivo para resolver companhias: uma futura atribuição B3 precisa de regra explícita, correspondência curada e trilha de proveniência.

### Planilha aceita

O arquivo precisa ser um `.xlsx` de até 10 MiB. O parser procura exatamente uma aba com a hierarquia e cabeçalho nas colunas B-D:

| Coluna | Cabeçalho reconhecido | Conteúdo importado |
| --- | --- | --- |
| B | `SETOR` ou `SETOR ECONÔMICO` | Nome do setor. |
| C | `SUBSETOR` | Nome do subsetor do setor corrente. |
| D | `SEGMENTO` | Nome do segmento do subsetor corrente. |

O cabeçalho é comparado sem diferenciar caixa e após compactar espaços. Linhas sem nome de setor ou subsetor reutilizam o último valor não vazio daquele nível, conforme o formato tabular hierárquico. Toda linha que contém segmento precisa resultar em setor e subsetor. Cabeçalhos repetidos reiniciam o preenchimento hierárquico. Caminhos duplicados são publicados uma vez. O parser limita cada aba a 10.000 linhas.

As colunas E em diante não são lidas. Isso inclui razão social/nome de pregão do emissor, código de negociação/ticker e segmento de listagem. Planilhas com mais de uma aba que contenha o cabeçalho esperado, sem nenhuma aba válida, sem segmentos ou com caminho incompleto são rejeitadas.

### `POST /setores/taxonomias/b3/importacoes`

Recebe `multipart/form-data`. O campo `arquivo` é obrigatório; os demais são opcionais:

| Campo | Tipo | Limite | Descrição |
| --- | --- | --- | --- |
| `arquivo` | arquivo `.xlsx` | 10 MiB | Arquivo original recebido. A extensão e o conteúdo XLSX são validados. |
| `data_atualizacao_fonte` | data `AAAA-MM-DD` | — | Data de atualização indicada pela B3/operador. Não é inferida dos metadados do XLSX. |
| `referencia_fonte` | texto | 255 caracteres | URL ou referência do download; padrão é a [página de classificação setorial B3](https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/acoes/consultas/classificacao-setorial/). |
| `observacao` | texto | 1.000 caracteres | Nota operacional opcional, por exemplo, quem conferiu o arquivo ou de onde foi baixado. |

Exemplo enviando o arquivo local:

```bash
curl --fail-with-body -X POST http://localhost:8007/setores/taxonomias/b3/importacoes \
  -H "Authorization: Bearer $TUCANO_CVM_TOKEN" \
  -F "arquivo=@data/ClassifSetorial.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
  -F "data_atualizacao_fonte=2026-11-10" \
  -F "referencia_fonte=https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/acoes/consultas/classificacao-setorial/" \
  -F "observacao=Arquivo baixado e conferido manualmente"
```

O serviço lê somente B-D, preserva o original em `STORAGE_DIR/setores/b3/<sha256>.xlsx` e registra uma tentativa com o hash, o tamanho, o nome original, o responsável autenticado e as datas. O valor `importado_por` é o nome do usuário administrador ou `token_sistema` quando se usa a credencial de sistema. `importada_em` e `concluida_em` são instantes do servidor em UTC; `data_atualizacao_fonte` é a data informada pelo operador. Se o dado for enviado, a versão também preenche `observada_em` à meia-noite UTC dessa data.

Cada nó recebe identidade dentro da taxonomia B3 baseada no nível e no caminho hierárquico normalizado. O mesmo caminho conserva o UUID em reimportações. O checksum semântico considera nomes, níveis e pais; sua mudança cria a próxima versão e registra nós novos, renomeados, rehierarquizados e desativados. Um caminho diferente não é unido automaticamente a um ID existente, ainda que a grafia pareça semelhante. Use a curadoria de alias/correspondência com evidência para registrar equivalências explicitamente.

| `status` | Significado | Publicação |
| --- | --- | --- |
| `sucesso` | Planilha válida com mudança semântica. | Cria uma versão e informa `versao_taxonomia`. |
| `sem_alteracao` | Planilha válida equivalente à versão vigente, mesmo que os bytes do XLSX mudem. | Registra a tentativa e aponta para a versão atual; não cria versão. |
| `rejeitada` | Arquivo XLSX inválido ou layout/hierarquia incompatível. | Registra o motivo e a tentativa no histórico, sem publicar conceitos. Retorna HTTP `422`. |
| `processando` | Estado reservado para futura execução assíncrona. | Não é retornado pelo processamento síncrono atual. |

Exemplo de resposta em uma primeira publicação (UUID e contagens variam conforme a planilha):

```json
{
  "id": "0c8df70a-33c6-4c1a-b690-8dd2a49c615b",
  "taxonomia": "b3",
  "nome_arquivo": "ClassifSetorial.xlsx",
  "checksum_sha256": "342a9966b1cafe0ee226de66b398a9288c5ad9ba93c40cbc2d2bc3354ba454aa",
  "tamanho_bytes": 16149,
  "data_atualizacao_fonte": "2026-11-10",
  "importado_por": "token_sistema",
  "status": "sucesso",
  "versao_taxonomia": 1,
  "resumo": {
    "referencia_fonte": "https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/acoes/consultas/classificacao-setorial/",
    "observacao": "Arquivo baixado e conferido manualmente",
    "setores": 11,
    "subsetores": 45,
    "segmentos": 86,
    "classificacoes_de_emissores_importadas": 0,
    "nos_publicados": 142,
    "mudancas": 142
  },
  "erro": null,
  "importada_em": "2026-11-10T12:00:00Z",
  "concluida_em": "2026-11-10T12:00:01Z"
}
```

O campo `classificacoes_de_emissores_importadas` é sempre `0`: não são criadas linhas em `companhia_classificacoes_setoriais` para a taxonomia B3. A importação também não altera os vínculos `cvm_cadastro` existentes. Uma resposta `422` por conteúdo inclui `detail.codigo=ARQUIVO_CLASSIFICACAO_B3_REJEITADO`, `detail.importacao_id` e `detail.mensagem`; use o ID para consultar o histórico. Erros de extensão, excesso de tamanho ou validação do formulário são detectados antes do parser e não geram registro de importação.

### `GET /setores/taxonomias/b3/importacoes`

Lista as importações da mais recente para a mais antiga. `limite` aceita 1 a 500 e tem padrão 100. A resposta usa o mesmo formato do POST e omite o caminho absoluto no armazenamento e os bytes do arquivo.

```bash
curl -H "Authorization: Bearer $TUCANO_CVM_TOKEN" \
  "http://localhost:8007/setores/taxonomias/b3/importacoes?limite=50"
```

Use `GET /setores/taxonomias/b3/versoes` para verificar versões publicadas e `GET /setores/taxonomias` para obter o estado atual da taxonomia. O histórico de uploads é operacional; o histórico de versões é semântico. Uma importação rejeitada aparece no primeiro, mas não cria item no segundo.

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

Até uma importação válida da hierarquia B3, consultas e curadoria envolvendo `b3` retornam `409 TAXONOMIA_SEM_PUBLICACAO`. A importação da hierarquia, sozinha, não cria vínculos de companhias com a B3; filtros e agregações por esse catálogo dependem de classificações ou correspondências curadas separadamente.

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
