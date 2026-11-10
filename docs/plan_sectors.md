# Plano de setores e análise de grupos de companhias

Proposta de implementação · 9 de novembro de 2026

## Objetivo e decisão

Transformar o setor de atividade informado pela CVM em um recurso consultável, com identificador estável e vínculo com a companhia. A API deve responder quais companhias pertencem a um setor, quais margens elas apresentaram em cada exercício e qual é a margem de um grupo escolhido pelo consumidor. O mesmo grupo pode ser repartido por setor, categoria de registro ou outros atributos cadastrais tipados.

O dicionário setorial publica taxonomias independentes. O catálogo e o vínculo CVM entram na promoção do cadastro. A classificação B3 pode ser publicada separadamente, assim que houver uma fonte autorizada para a API. A análise de grupos lê os fatos canônicos por companhia e exercício e agrega conforme a taxonomia escolhida. A entrega inicial usa a materialização de análise existente, com cache de entrega para recortes repetidos. Cada lista enviada à API é uma consulta de leitura síncrona.

## O que o Tucano já tem

| Área | Comportamento atual | Consequência para o plano |
| --- | --- | --- |
| Cadastro CVM | A ingestão normaliza `SETOR_ATIV` e `CATEG_REG` nos arquivos de companhias abertas e estrangeiras. A seleção canônica preenche `Companhia` e os registros de origem ficam em `CompanhiaRegistroCvm`. | Reutilizar a seleção canônica para obter um único vínculo atual por companhia. [Promoção do cadastro](../app/services/ingestion/cadastro.py) |
| API de companhias | `GET /companhias` aceita CNPJ, código CVM, nome e situação. `CompanhiaResposta` já expõe `setor_atividade` como texto e `categoria_registro`. | Manter esses campos e acrescentar o identificador setorial ao contrato. [Router de companhias](../app/api/routers/companhias.py), [schema](../app/schemas/companhia.py) |
| FCA | `FcaGeral` guarda setor, categoria, situação e data de referência por documento e versão. `FcaDocumento` guarda a data de recebimento e o link. | O FCA oferece evidência documental para uma futura classificação histórica com cobertura própria. [Modelos do FCA](../app/models/fca.py) |
| Análise | `AnaliseFatoRevision` guarda observações e indisponibilidades por companhia, escopo, base, período e métrica, com intervalos de conhecimento e proveniência. Receita líquida, lucro bruto, EBIT, lucro líquido e EBITDA já têm fatos no catálogo. A margem líquida é uma métrica derivada e o relatório fundamentalista monta outras margens a partir dos componentes. | Consultar os componentes em lote e compartilhar as definições financeiras do serviço existente. [Modelo de fatos](../app/models/analise.py), [serviço de análise](../app/services/analise.py) |
| Entrega fundamentalista | O relatório usa um read model persistido por contexto, com pré-aquecimento do recorte padrão. O router tem cache Redis opcional por contexto e geração, lock temporário, fallback para o serviço e revalidação HTTP no GET. O Redis é desabilitado por padrão para esse cache na configuração. | Reaproveitar o cliente e o padrão de cache por geração. O recorte setorial tem dependências adicionais e cardinalidade maior. [ADR 0006](adr/0006-read-model-fundamentalista-persistido.md), [cache Redis](../app/core/cache.py), [configuração](../app/core/config.py) |
| Operação | A finalização bem-sucedida de DFP/ITR cria uma campanha de análise, com itens por companhia/escopo e processamento em chunks. O resolvedor canônico procura uma execução bem-sucedida com cobertura completa na versão de cálculo vigente. Por padrão, a criação de campanhas exclui companhias com registro cancelado. | Reutilizar a orquestração e distinguir a última execução válida da atualidade dos insumos que ela cobriu. Planejar o backfill de canceladas quando necessário para a cobertura histórica. [Worker](../app/worker/tasks.py), [serviço de análise](../app/services/analise.py), [contexto de análise](../app/services/CONTEXT.md) |

### Inspeção dos arquivos da CVM

Amostra coletada em 09/11/2026. As contagens se referem a linhas dos arquivos e os rótulos distintos foram contados após remover espaços externos.

| Arquivo | Linhas | Rótulos distintos preenchidos | Linhas sem setor | Linhas sem categoria |
| --- | ---: | ---: | ---: | ---: |
| `cad_cia_aberta.csv` | 2.679 | 70 | 6 | 1.239 |
| `cad_cia_estrang.csv` | 27 | 9 | 13 | 1 |
| `fca_cia_aberta_geral_2025.csv` | 715 | 54 | 0 | 0 |

Os arquivos trazem rótulos como “Energia Elétrica”, “Emp. Adm. Part. - Energia Elétrica” e “Emp. Adm. Part. - Sem Setor Principal”. A distinção é relevante para o catálogo. Campos vazios são lacunas, inclusive quando a companhia tem demonstrações financeiras. [Cadastro de abertas](https://dados.cvm.gov.br/dataset/cia_aberta-cad), [cadastro de estrangeiras](https://dados.cvm.gov.br/dados/CIA_ESTRANG/CAD/DADOS/), [arquivos FCA](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/)

Na DRE consolidada do DFP de 2025, as linhas do exercício corrente usam o código `3.01` para receitas de vendas, intermediação financeira ou atividades seguradoras, conforme a estrutura. A conta `3.05` pode representar resultado antes do resultado financeiro e dos tributos, resultado antes dos tributos ou outras receitas e despesas operacionais. A elegibilidade da margem deve verificar a semântica da conta de origem, além do código. [DFP 2025 da CVM](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip)

## Pesquisa e implicações para o desenho

| Referência | Prática observada | Aplicação proposta |
| --- | --- | --- |
| B3 | Classifica companhias negociadas por setor, subsetor e segmento. Considera a contribuição das atividades à receita e tem regra específica para holdings. | Oferecer a visão B3 como taxonomia própria, com cobertura e linhagem independentes da CVM. [Critério da B3](https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/acoes/consultas/criterio-de-classificacao/), [níveis da classificação](https://www.b3.com.br/data/files/0F/35/F5/02/3C0FF91094DCD8F9AC094EA8/Diretrizes%20Novo%20ISEB3_2026.pdf) |
| W3C SKOS | Distingue relações hierárquicas internas de correspondências entre taxonomias. Define relações de equivalência, aproximação e granularidade. | Tipar o cruzamento CVM ↔ B3 e manter a evidência de cada relação. Usar essa semântica em tabelas relacionais. [SKOS, propriedades de mapeamento](https://www.w3.org/TR/skos-reference/#mapping) |
| MSCI/S&P GICS e FTSE Russell ICB | Usam hierarquias explícitas e classificam a atividade principal com critérios de negócio e receita. GICS atribui uma classificação por nível. | Dar identidade estável ao rótulo e garantir um vínculo principal por companhia em cada taxonomia. Hierarquias futuras precisam de uma fonte ou regra documentada. [GICS](https://www.msci.com/indexes/index-resources/gics), [ICB](https://www.lseg.com/en/ftse-russell/industry-classification-benchmark-icb) |
| TradingView | Combina filtros de setor, dados financeiros, margens e listas de ativos. | Usar o setor como filtro de descoberta e permitir consulta por lista explícita. O universo do Tucano usa o emissor CVM como unidade, evitando repetir uma companhia com várias ações. [Stock Screener](https://www.tradingview.com/support/solutions/43000718866-tradingview-stock-screener-trade-smarter-not-harder/) |
| Koyfin | O screener combina universo e filtros. As watchlists oferecem resumo com média, mediana e métodos ponderados distintos. | Expor estatísticas com nomes diferentes e permitir inspecionar as companhias que contribuíram para cada resultado. [My Screens](https://www.koyfin.com/help/my-screens/), [Summary Rows](https://www.koyfin.com/help/mastering-portfolio-tracking-with-koyfin/) |
| FactSet | A Formula API aceita uma lista de identificadores ou um universo definido. A documentação de snapshots distingue o período financeiro do corte para análise retrospectiva. | Separar seleção de companhias, períodos, corte informacional e métricas no contrato. Limitar a consulta a dimensões e fórmulas conhecidas. [SDK oficial](https://github.com/factset/enterprise-sdk/blob/main/code/python/Formula/v1/README.md), [ExtractDataSnapshot](https://go.factset.com/hubfs/Website_Downloads/Statistical%20Package%20Integration/Docs%203.0/ExtractDataSnapshot.pdf) |
| Aswath Damodaran, NYU Stern | Publica margens por indústria, informa quantidade de empresas e documenta a margem líquida setorial como a razão entre lucro e receita acumulados no grupo. | Oferecer `razao_das_somas` separadamente da média simples e retornar cobertura por métrica e período. [Tabela de margens](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/margin.html), [definições das variáveis](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/variable.htm) |
| Kimball Group | Recomenda declarar o grão dos fatos e guardar os componentes aditivos de razões. O histórico de atributos pode ser registrado com intervalos. | Reutilizar fatos por companhia e exercício, calcular razões depois de selecionar os contribuintes e tratar a classificação histórica como dimensão própria. [Grão](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/grain/), [fatos não aditivos](https://www.kimballgroup.com/wp-content/uploads/2013/08/2013.09-Kimball-Dimensional-Modeling-Techniques11.pdf), [dimensão tipo 2](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/) |
| CPC 22 / IFRS 8 | Segmentos operacionais refletem como a administração acompanha o negócio. Podem ter bases próprias de mensuração e exigem conciliação com o consolidado. | Modelar receitas e resultados divulgados por segmento operacional em um grão separado, com mensuração, eliminações e evidência próprias. [CPC 22, itens 5 e 20–30](https://conteudo.cvm.gov.br/export/sites/cvm/menu/regulados/normascontabeis/cpc/CPC_22_rev_08.pdf), [IFRS 8](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-8-operating-segments/) |

## Modelo proposto

- **Setor de atividade CVM** é o rótulo cadastral usado para classificar o emissor. O dicionário guarda cada conceito em `setores`, com UUID opaco, taxonomia e identidade única nessa taxonomia. Para a CVM, a identidade inicial é a chave obtida com NFC, normalização de espaços e caixa. Para a B3, usar um código oficial estável quando fornecido ou a chave do caminho hierárquico normalizado. Preservar nome de exibição, texto de origem, acentos e pontuação. Tratar grafias equivalentes por alias explícito dentro da mesma taxonomia, mantendo a referência aos IDs já emitidos.
- **Classificação setorial atual** é o vínculo publicado entre companhia e taxonomia. Persistir em `companhia_classificacoes_setoriais` com uma atribuição principal vigente por `companhia_id` e taxonomia. Na B3, vincular ao nível mais específico comprovado e obter os níveis acima pela hierarquia. `Companhia.id` é a identidade interna e `codigo_cvm` é o seletor da consulta financeira. Uma companhia sem código CVM continua visível no catálogo e aparece como lacuna se entrar no universo por filtros.
- **Categoria de registro CVM** é o atributo cadastral `CATEG_REG`. Ela compõe filtros e agrupamentos junto com `tipo_emissor` e `situacao_registro`. Campos ausentes podem formar um grupo com chave nula e rótulo de apresentação “Não informado”. Um valor nulo de setor fica fora do catálogo de setores.
- **Fato financeiro canônico** é a observação de uma métrica de uma companhia em um escopo, base e período, com versão de cálculo e intervalo de conhecimento. Os fatos de receita e de resultado são independentes do setor e podem ser reutilizados depois de uma reclassificação.
- **Grupo de companhias** é o conjunto de identidades que satisfaz a seleção da consulta. A lista explícita e os filtros setoriais ou cadastrais podem ser combinados. Cada companhia conta uma vez em cada célula de período, métrica e agrupamento.
- **Segmento operacional** é a unidade de negócio divulgada pelo emissor. Uma companhia pode ter vários segmentos operacionais e uma classificação principal por taxonomia. A margem consolidada integra o grupo setorial como margem da companhia inteira.

### Dicionário setorial, correspondências e auditoria

| Registro | O que guarda |
| --- | --- |
| Versão publicada de uma taxonomia | Fonte, referência do arquivo ou entrega, checksum, data da fonte quando fornecida, instante da observação, versão das regras e identificação da publicação. |
| Conceito setorial | Identidade estável e revisões de nome, nível, pai, aliases e situação. A CVM começa com um nível. A B3 pode ter setor, subsetor e segmento setorial. |
| Classificação da companhia | Companhia, conceito, rótulo original, referência à evidência na fonte e intervalo de versões da atribuição. Resolver a identidade por identificador inequívoco do emissor, como CNPJ ou código CVM, reutilizando o cadastro canônico. Vários tickers podem apontar para a mesma companhia. Casos sem resolução ou com conflito ficam registrados como lacunas. |
| Correspondência entre conceitos | Setor de origem, setor de destino, direção, tipo (`equivalente`, `mais_amplo`, `mais_estreito`, `relacionado`), evidência, justificativa, autoria da revisão e versão de publicação. Relações muitos-para-muitos podem documentar diferenças de granularidade. |

- `cvm_cadastro` usa os rótulos oficiais da CVM. `b3` usa atribuições por companhia comprovadas em uma fonte oficial ou em uma entrega que documente a proveniência oficial. As correspondências explicam a relação entre conceitos e permitem navegação. Somente a atribuição verificada entra na visão oficial B3. Se houver demanda para aplicar uma regra de correspondência a companhias sem vínculo oficial, publicar a inferência sob uma taxonomia curada distinta e indicar a regra usada.
- Um rótulo da CVM pode corresponder a um subsetor B3 mais amplo ou a vários segmentos. Por exemplo, o Bradesco (código CVM 906) consta como “Bancos” no cadastro CVM e como “Financeiro / Intermediários Financeiros / Bancos” na B3. O vínculo da companhia sustenta essa comparação. A semelhança dos nomes pode sugerir uma correspondência de dicionário para revisão. Um emissor ausente da entrega B3 continua consultável na CVM e aparece como `sem_classificacao` se entrar no universo B3 por lista ou outro filtro sem setor. [Cadastro CVM](https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv), [Bradesco na B3](https://sistemaswebb3-listados.b3.com.br/listedCompaniesPage/main/906/BBDC/overview?language=pt-br)
- Comparar cada lote validado com a última publicação da sua taxonomia. Registrar rótulos novos, aliases, renomes, troca de pai, reclassificação de companhia, retirada e mudanças nas correspondências. Rótulos válidos novos da CVM entram com ID próprio e evento para revisão do dicionário. Uma ausência só encerra vínculo quando uma entrega completa e validada comprovar a retirada. Entrega parcial ou falha mantém a publicação anterior e deixa diagnóstico.
- Publicar o diff e a versão em uma transação, preservando o histórico das mudanças. Armazenar apenas revisões alteradas e garantir no máximo uma atribuição vigente por companhia e taxonomia. Registrar cada entrega na linhagem mesmo quando o conteúdo semântico permanece igual e a versão publicada é mantida. Vincular a entrega CVM à execução de ingestão existente. Revisar correspondências em lotes versionados, com validação de referências e de ciclos na hierarquia. A revisão é independente da ingestão prioritária da CVM.
- A página pública de classificação da B3 restringe coleta automatizada. A disponibilização de `b3` depende de um canal que autorize a obtenção e o uso dos dados na API. Avaliar uma entrega de referência autorizada, com versão, cobertura e identificadores de emissor. O UP2DATA é um canal de dados de referência a investigar. A disponibilidade desse conjunto e as condições de distribuição precisam ser confirmadas antes de habilitar a taxonomia. [Página de classificação da B3](https://b3.com.br/main.jsp?doui_processActionId=setLocaleProcessAction&locale=pt_BR&lumA=1&lumII=8A80CB81633FBF0B016340BEB8A2534D&lumPageId=8A6883565186B02601518BBB7DAC76B5), [UP2DATA](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/up2data/)

### Tempo e comparabilidade

- Na entrega inicial, filtros e agrupamentos usam a classificação **atual** da taxonomia selecionada. A resposta informa `classificacao=atual`, a versão da publicação e a data de referência quando comprovada. Uma série histórica aplica esse mesmo grupo a todos os anos. Isso pode mudar a composição de consultas repetidas após uma reclassificação ou cancelamento. A situação do registro só restringe o grupo quando solicitada.
- `as_of` é o corte informacional dos fatos financeiros. Aplicar a mesma regra de revisões da análise (`known_from <= as_of < known_to`, com limite final aberto). Sem corte, usar as revisões abertas da versão canônica vigente. A análise atual usa a data de referência quando falta data de recebimento. Para agregações com corte explícito, exigir evidência de que os documentos que sustentam ambos os componentes já estavam disponíveis e marcar `data_conhecimento_indeterminada` quando essa prova faltar. Manter os dois relógios explícitos na resposta.
- Na evolução histórica, modelar observações de classificação com `companhia_id`, `setor_id`, categoria e demais atributos que tenham evidência histórica, data de referência, data de conhecimento, fonte e documento/versão. Usar FCA elegível com referência até a data-alvo e recebimento até o corte de conhecimento, com seleção determinística da referência e versão. Separar “classificação observada no fechamento de cada exercício” de “grupo cadastral atual aplicado à série”. Mostrar ausência de evidência histórica e limitar a cobertura declarada. A captura de um snapshot do cadastro comprova apenas a classificação observada a partir daquela captura.

### Métricas e cobertura

Começar com `margem_bruta` (`lucro_bruto / receita_liquida`), `margem_ebit` (`ebit / receita_liquida`) e `margem_liquida` (`lucro_liquido / receita_liquida`). Centralizar o mapa de fórmulas e reutilizar o seletor canônico de contas, versões e escalas. Incluir `margem_ebitda` após medir cobertura e explicitar a definição do EBITDA derivado pela análise atual.

Para a mesma métrica, período e grupo, usar o mesmo conjunto de observações elegíveis nas três estatísticas.

| Estatística | Fórmula | Interpretação |
| --- | --- | --- |
| `media_simples` | `sum(resultado_i / receita_i) / n` | Cada companhia pesa igualmente. |
| `mediana` | Mediana das margens individuais | Representa o centro da distribuição. Para amostra par, usar a média dos dois valores centrais. |
| `razao_das_somas` | `sum(resultado_i) / sum(receita_i)` | Cada companhia tem peso proporcional à receita positiva. |

Exemplo com dois emissores. A tem receita 100 e lucro 20. B tem receita 900 e lucro 90. A média simples e a mediana são `0.15` e a razão das somas é `0.11`. Se uma terceira companhia do grupo tem receita zero, a cobertura é 2 de 3 e nenhuma das estatísticas incorpora a terceira companhia. Serializar com `CanonicalDecimal`, `unit=ratio` para margens e `unit=BRL` para valores monetários comprovadamente nessa unidade. A interface pode apresentar `0.15` como 15%.

- A primeira versão trabalha com `annual/fy`, períodos `FYyyyy` e um escopo por requisição. O padrão é `consolidated`, com `individual` explícito. Selecionar o mesmo ano fiscal para todos e conferir datas de início e fim de ambos os componentes em cada companhia. Excluir exercícios de transição com duração irregular. Para fechamentos em meses distintos, retornar alerta de comparabilidade com as datas no detalhamento.
- Exigir receita estritamente positiva e numerador disponível na mesma unidade e escopo. Preservar lucro zero e prejuízo como observações válidas. Na primeira versão, limitar a amostra a valores em reais, verificando em lote a moeda de origem pelas referências dos fatos quando o payload canônico não a comprovar. Sinalizar `receita_nao_positiva`, `componente_ausente`, `periodo_incompativel` e `unidade_incompativel` separadamente. A restrição de receita positiva é uma política do benchmark, explícita no contrato.
- Antes de liberar cada métrica, verificar a semântica das contas de origem em amostras de bancos, seguradoras, securitizadoras e companhias não financeiras. Marcar `metrica_nao_aplicavel` quando o componente contábil tiver outro significado. Usar regra verificável por estrutura/conta ou mapeamento explícito e versionado. Enquanto a aplicabilidade de um layout estiver indeterminada, reportar a lacuna em vez de inferir pelo nome do setor.
- Contar selecionadas, elegíveis, excluídas e motivos por célula, com motivo primário por exclusão e ordem de precedência documentada. Retornar `null` e status de indisponibilidade para amostra sem observações válidas. Uma observação válida pode gerar estatística com `n=1`. Séries com composição diferente entre anos mostram suas coberturas por ano.
- O detalhamento apresenta companhia, período real, versão de cálculo, margem e componentes com evidência documental, ou motivo da exclusão. Os dados seguem o limite de neutralidade e rastreabilidade da análise fundamentalista. [ADR 0005](adr/0005-fronteira-analise-explicavel.md)
- A razão das somas é uma estatística dos emissores selecionados. Um conjunto com controladora e controlada pode ter sobreposição econômica entre demonstrações consolidadas. A API deve explicar essa limitação, pois a seleção do usuário define os emissores incluídos.

## Endpoints propostos

Usar o roteador protegido e a autenticação bearer atual. Usar paginação e envelopes do projeto nas listas e schemas fechados para os novos contratos. As rotas de análise permanecem sob `/analise/companhias/...`.

| Endpoint | Contrato inicial |
| --- | --- |
| `GET /setores/taxonomias` | Informa as taxonomias disponíveis, a versão publicada, os níveis e a referência da fonte. |
| `GET /setores/taxonomias/{taxonomia}/versoes` | Lista publicações com data, referência da fonte e contagens de inclusões, reclassificações e retiradas. Os registros de revisão guardam os detalhes de antes e depois para auditoria. |
| `GET /setores?taxonomia=cvm_cadastro` | Lista paginada com `id`, `nome`, `nivel`, `setor_pai_id` e `total_companhias` na versão publicada. Aceita busca por nome e filtro por nível. Contagens por ancestral deduplicam companhias. |
| `GET /setores/{setor_id}` | Detalhe, taxonomia, versão e contagem de vínculos. `incluir_correspondencias=true` inclui relações publicadas com outras taxonomias e respectivas referências. Um setor conhecido sem vínculos continua consultável. |
| `GET /setores/{setor_id}/companhias` | Lista companhias vinculadas ao setor ou a seus descendentes, com os filtros e a paginação de `GET /companhias`. A taxonomia vem do setor indicado no path. |
| `GET /companhias?setor_id={id}&taxonomia=b3` | Filtra pelo vínculo vigente da taxonomia selecionada. Aceita `categoria_registro` e `tipo_emissor` com os filtros existentes. Expõe a classificação escolhida no resumo e no detalhe e preserva `setor_atividade` com o valor cadastral CVM. |
| `POST /analise/companhias/agregacoes` | Consulta estatísticas e composição por lista, filtros ou grupos. `taxonomia` seleciona a classificação do resultado. Para agrupar pela B3, `nivel_setorial` permite escolher setor, subsetor ou segmento. |

Usar `404` para setor desconhecido no path ou no filtro por ID, `422` para identificador malformado e `200` com lista vazia quando um setor conhecido não tiver companhias que correspondam aos filtros.

`cvm_cadastro` é o padrão. IDs de outra taxonomia e níveis incompatíveis com a selecionada retornam `422`. A seleção explícita de uma taxonomia reconhecida sem publicação retorna `409` com `TAXONOMIA_SEM_PUBLICACAO`. Dentro de um recorte, filtrar e agrupar com a mesma versão. Um grupo no nível B3 solicitado inclui o ancestral correspondente. Quando faltar classificação nesse nível, a chave fica nula e a cobertura setorial fica separada da disponibilidade financeira.

Corpo ilustrativo para comparar a margem líquida de um grupo escolhido pelo consumidor em dois exercícios e abrir a composição da primeira página.

```json
{
  "taxonomia": "cvm_cadastro",
  "universo": { "codigos_cvm": [9512, 4170] },
  "periodos": ["FY2023", "FY2024"],
  "escopo": "consolidated",
  "metricas": ["margem_liquida"],
  "estatisticas": ["media_simples", "mediana", "razao_das_somas"],
  "agrupar_por": [],
  "detalhamento": { "pagina": 1, "tamanho_pagina": 50 }
}
```

- `universo` aceita `codigos_cvm`, `setor_ids`, `categorias_registro`, `tipos_emissor` e `situacoes_registro`. Valores dentro de cada filtro formam uma união e filtros distintos se intersectam. Exigir pelo menos um seletor preenchido ou `todas=true` sozinho. Deduplicar listas. Identificadores sintaticamente válidos e desconhecidos retornam `404` com os IDs desconhecidos. Interseção válida vazia retorna `200` com universo vazio.
- `agrupar_por` aceita até duas dimensões distintas da lista `setor`, `categoria_registro`, `tipo_emissor` e `situacao_registro`. Vazio gera o total do universo. Para um benchmark por setor, enviar `universo.setor_ids` e `agrupar_por=["setor"]`. Limites iniciais propostos de 500 códigos explícitos, 100 IDs de setor e 10 exercícios. Validar o orçamento da combinação em teste de carga. Enums, campos extras, listas explicitamente vazias nos filtros e combinações inválidas retornam `422`.
- A resposta ecoa o recorte efetivo, `taxonomia`, `versao_taxonomia`, `nivel_setorial`, o modo de classificação, `as_of`, a versão das fórmulas e `resolution.mode`. Cada célula tem chaves de grupo, período, métrica, unidade, estatísticas, contagens, cobertura e alertas. O status da célula é `disponivel` quando todas as selecionadas são elegíveis, `parcial` quando apenas parte é elegível e `indisponivel` quando nenhuma é elegível. `detalhamento` é opcional e pagina apenas os itens de composição, ordenados por grupo, período, métrica e identidade da companhia. Estatísticas e contagens sempre cobrem o recorte completo. Retornar uma impressão digital do recorte e das gerações efetivamente lidas para o consumidor detectar mudança entre páginas.
- Um grupo com fatos canônicos parciais retorna `200` com as lacunas e a cobertura. A primeira entrega lê somente fatos canônicos e usa `resolution.mode=canonical` para resultados produzidos por esse caminho, inclusive quando a amostra tem lacunas. Um futuro fallback deve ser explícito e limitado. Falha de leitura do banco segue o tratamento de erro da API.
- Testar exemplos no OpenAPI com filtros válidos, nulos, universo vazio, amostra parcial, versões reapresentadas e falhas de autenticação. Documentar os limites, a política de composição e as unidades nos schemas e nas descrições.

Exemplo de uma célula sem agrupamento com a terceira companhia excluída por receita não positiva.

```json
{
  "grupo": [],
  "period_id": "FY2024",
  "metric_id": "margem_liquida",
  "unit": "ratio",
  "status": "parcial",
  "estatisticas": {
    "media_simples": "0.15",
    "mediana": "0.15",
    "razao_das_somas": "0.11"
  },
  "cobertura": {
    "selecionadas": 3,
    "elegiveis": 2,
    "excluidas": 1,
    "motivos": [{ "codigo": "receita_nao_positiva", "total": 1 }]
  },
  "alertas": []
}
```

## Promoção, materialização e atualidade

1. **Cadastro.** Resolver setor em lote para as chaves distintas e gravar o vínculo CVM junto com a promoção da companhia, na mesma transação que publica a ingestão. Um rótulo vazio em registro válido encerra o vínculo. A unicidade da chave e o upsert garantem estabilidade em reexecução e concorrência. O backfill parte dos campos canônicos já promovidos, é retomável e valida correspondência entre rótulo e classificação antes da abertura das rotas. Cobrir caminhos que escrevem no cadastro, inclusive sincronização direta, worker e backfill. Uma futura importação B3 publica uma versão independente pelo mesmo modelo de classificação e dispensa recálculo financeiro.
2. **Leitura financeira.** Buscar companhias, contexto e revisões necessárias em lote. Aplicar os filtros de canonicidade e de tempo já usados pela análise. Ler numeradores e denominadores das mesmas revisões com uma visão consistente do banco durante a requisição. Resolver duplicidade como inconsistência observável. Validar o payload JSON existente nos schemas tipados e usar decimais até a serialização. Medir latência, volume e consultas SQL em grupos pequenos e amplos, com várias métricas e dez exercícios. Registrar o plano de execução no PostgreSQL e validar a lógica também no SQLite. Evitar uma chamada ao resolvedor ou relatório fundamentalista por companhia.
3. **Extensão condicionada à medição.** Se o custo da leitura dos fatos JSON for alto, projetar somente os componentes financeiros necessários como colunas numéricas, por companhia, escopo, base, período, versão de cálculo e intervalo de conhecimento. Associar a projeção às revisões e à execução que a publicou. Preencher pelo mesmo serviço de materialização, com publicação atômica, reconstrução pelos fatos e teste de equivalência com a leitura direta. Usar o dispatcher, os chunks e a fila `analise_materializacao` existentes. Respeitar o gate de admissão e a prioridade da ingestão. Mudanças cadastrais entram no próximo join e dispensam recálculo dos fatos financeiros.
4. **Cobertura operacional.** Expor separadamente disponibilidade do valor, última geração canônica usada e atualidade perante os insumos. Um sucesso antigo pode sustentar uma observação com atualização pendente. Comparar a geração com as revisões ou assinaturas de entrada requeridas por companhia, escopo e janela, usando o histórico de ingestão e as execuções existentes. Registrar a assinatura coberta na execução de análise se a linhagem atual não permitir reconstruí-la. Retornar atualidade `atual`, `pendente`, `falha` ou `indeterminada`, com contagens por célula e evidência no detalhamento. Um sucesso sem cobertura completa, inclusive o caso de cancelada ignorada, não prova atualidade.
5. **Reprocessamento.** A falha posterior para uma entrada ainda requerida mantém a cobertura pendente ou falha. Uma execução posterior que cobre a mesma entrada, ou uma substituição comprovada para o mesmo escopo, restabelece a cobertura e conserva as tentativas no histórico. Em publicação parcial ou falha de materialização, preservar a última geração válida e indicar o estado efetivo. Considerar membros reaproveitados e reapresentações na prova de cobertura. Uma republicação com equivalência comprovada de todos os membros pode manter a cobertura existente. Registrar pendências recuperáveis e diagnósticos por campanha, item e execução em `/analise/materializacoes/...`. As fontes operacionais primárias continuam sendo `ExecucaoSincronizacao` e `IngestionRun`. [ADR 0007](adr/0007-referencia-remota-reconhecida-sem-reingestao.md)

## Eficiência da consulta e cache

### Caminho de leitura

- Resolver a versão setorial e o universo no PostgreSQL em lote. Indexar vínculos vigentes por taxonomia/setor/companhia e por companhia/taxonomia. Resolver ancestrais da B3 em lote no catálogo publicado, mantendo uma linha por companhia no nível solicitado. Usar a mesma entrada de cache para o resumo em todas as páginas de um recorte.
- Buscar apenas fatos dos anos, escopo e componentes necessários. Começar pelos índices existentes de `AnaliseFatoRevision` e medir com `EXPLAIN (ANALYZE, BUFFERS)` em ambiente de teste. Se a consulta ampla exigir outro índice, escolher a ordem das colunas a partir dos planos para consultas por lista e por setor. Evitar ler versões encerradas no caso corrente e carregar proveniência completa de todas as companhias só para montar o resumo. [Índices atuais](../app/models/analise.py)
- Se a leitura sem cache continuar cara, aplicar a projeção tipada descrita acima. Agregar média, mediana e razão das somas a partir dos mesmos contribuintes no PostgreSQL e validar a equivalência com o caminho portátil dos testes. Guardar componentes e períodos, permitindo recompor grupos mesmo após mudanças de taxonomia. Medianas de subgrupos não permitem obter a mediana do conjunto.

### Cache de entrega e invalidação

- Reusar `RedisCache` para leitura, gravação com TTL e lock com token. Manter namespace e configurações setoriais próprios. Usar hash do corpo normalizado, com padrões explícitos, listas que funcionam como conjuntos deduplicadas e ordenação preservada quando fizer parte do contrato. A chave inclui taxonomia, nível, filtros, agrupamentos, métricas, estatísticas, períodos, escopo, `as_of`, versão de fórmulas e contrato. [Cache Redis](../app/core/cache.py), [ADR 0006](adr/0006-read-model-fundamentalista-persistido.md)
- Ler as gerações publicadas do PostgreSQL com uma consulta pequena, antes de acessar o cache. A chave inclui a geração cadastral dos campos usados na resposta, a versão publicada da taxonomia que inclui os vínculos, e a geração financeira do escopo. O detalhe com correspondências também depende da versão do mapeamento. Inicialmente, uma geração financeira por escopo invalida de forma conservadora, inclusive para consultas históricas. Medir a taxa de invalidação e a contenção antes de considerar gerações mais finas por período. Evitar reconstruir a lista de contribuintes ou fazer hash de todos os fatos para encontrar a chave.
- Atualizar as gerações na transação que publica os dados correspondentes. Mudança apenas setorial ou cadastral invalida a composição sem rematerializar as margens. Reapresentação publicada, remoção de fato ou reconciliação que altere a elegibilidade canônica invalida os resultados financeiros do escopo. Em miss, ler gerações e insumos no mesmo snapshot de banco para impedir que um cálculo novo seja salvo sob uma chave antiga. O TTL libera memória de chaves que saíram de uso.
- Cachear o resumo e a composição agregada sem o detalhamento integral. Se houver demanda por páginas repetidas, cachear só as páginas acessadas, com os parâmetros de paginação e as mesmas gerações. Calcular ou consultar a atualidade operacional em lote fora do payload cacheado, pois uma falha ou pendência muda a atualidade mesmo com valores canônicos idênticos. Montar o mesmo contrato em hit, miss ou indisponibilidade do Redis.
- Priorizar recortes comuns de setor e exercício. Para listas ad hoc, admitir somente entradas dentro do limite de tamanho e usar TTL curto ou cache após repetição. Limitar bytes, cardinalidade e concorrência de consultas caras. Como o Redis configurado também é usado pelo Celery, dimensionar o cache para não pressionar a fila e isolar o armazenamento de cache se a capacidade exigir. [Configuração do Celery](../app/worker/celery_app.py)
- Em miss concorrente, uma requisição calcula por chave e as demais aguardam por tempo limitado. Liberar a conexão do banco durante a espera no Redis. Limitar consultas em voo e o tempo de leitura também sem Redis, aplicando a resposta de sobrecarga quando o limite for atingido. Para as rotas GET do catálogo, considerar `ETag` privado e `If-None-Match`. No POST de agregações, usar o cache interno e retornar a identificação das gerações no payload.
- Começar com cache sob demanda. Só se a medição justificar, pré-aquecer um conjunto fixo de recortes populares após publicações, com trabalho coalescido e limitado pelo gate de materialização. Para listas arbitrárias, o caminho de referência continua sendo a leitura em lote dos fatos. Persistir um read model de resumo apenas se houver poucos recortes estáveis com ganho comprovado.

### Critérios de desempenho e consistência

Medir p50 e p95, tempo e linhas lidas no banco, volume transferido, CPU, pressão no pool, taxa de hit, descartes por tamanho e tempo de espera pelo lock. Repetir com cache quente, frio, desabilitado e com Redis indisponível, incluindo concorrência e ingestão ativa. Usar grupos pequenos, um setor amplo, uma lista de 500 companhias e o universo de dez exercícios com três métricas. Metas iniciais para calibrar no ambiente de referência, com dez consultas concorrentes, são p95 de até 250 ms em hit e até 1 s em miss para recortes comuns. Medir o teto do universo completo separadamente antes de publicar os limites.

Verificar que o número de consultas SQL por requisição se mantém limitado conforme aumenta o número de companhias. Testar que uma reclassificação muda o grupo com os mesmos fatos financeiros, que uma reapresentação muda as margens, que uma mudança em correspondência invalida o detalhe correspondente e que uma falha de ingestão continua visível em hit. Cobrir também publicação concorrente com preenchimento de cache, páginas de gerações distintas, repetição de lote sem alterações e isolamento de chaves CVM/B3.

## Entregas e critérios de aceite

1. **Dicionário e classificação CVM.** Criar modelos, migração Alembic, backfill e rotas cadastrais. Verificar cadastro aberto e estrangeiro, vazio, variação de grafia, holding, duplicatas, reingestão, rollback, troca de setor, contagens, paginação, canceladas, ausência de código CVM e compatibilidade dos campos legados.
2. **Benchmark anual e detalhamento.** Implementar leitura em lote e schemas. Verificar fórmulas com pesos diferentes, reapresentação antes e depois do corte, filtros em interseção, agrupamento por categoria e setor, universo vazio, amostra parcial, anos sem observações, receitas inválidas, prejuízo, moeda/escala, datas, escopos e estruturas contábeis especiais. Confirmar a paridade da margem individual com a análise existente para componentes elegíveis.
3. **Operação, cache e desempenho.** Implementar a geração dos dados e o cache de entrega. Validar última tentativa, última geração válida e estado da entrada requerida. Testar falha seguida de replay equivalente, atualização pendente e invalidação. Medir a consulta e decidir sobre projeção tipada, com teste de gate e recuperação de chunks se houver extensão da materialização. Qualquer mudança persistida exige migração.
4. **B3 e correspondências.** Habilitar a taxonomia após confirmar a fonte. Testar publicação de uma hierarquia com cobertura parcial, ausência de vínculo, ambiguidade de emissor, deduplicação por ancestral, mudança de rótulo ou pai, reclassificação, correspondência um-para-muitos e troca explícita entre CVM e B3 no mesmo recorte financeiro.
5. **Evoluções separadas.** Depois da entrega anual, avaliar ITR trimestral isolado, YTD e TTM como bases explícitas e mutuamente distintas. Para classificação histórica, validar disponibilidade, versões e data de recebimento dos FCA antes de publicar o modo histórico. Para segmentos operacionais, inventariar os membros estruturados do FRE e as notas explicativas DFP/ITR. Só publicar fatos quando houver origem reproduzível por companhia, segmento, período, versão, medida, unidade e base de mensuração. Separar receita externa, intersegmentos e eliminações. O campo `segmentos` hoje sai vazio no bloco de margens da análise fundamentalista. A ingestão de uma nova fonte ou de novos membros só se justifica quando a investigação confirmar a disponibilidade desses dados. [FRE da CVM](https://dados.cvm.gov.br/dataset/cia_aberta-doc-fre), [DFP da CVM](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp), [implementação do bloco de margens](../app/services/analise.py)

Ao implementar, documentar o comportamento publicado no OpenAPI e no Docusaurus e registrar endpoints, filtros, campos e semântica no changelog do frontend com a data da sessão de implementação. Executar as validações do repositório.

```bash
docker compose run --rm cvm_api mypy .
docker compose run --rm cvm_api ruff check . --ignore E501
docker compose run --rm cvm_api python -m pytest -q
npm --prefix docusaurus run build
```
