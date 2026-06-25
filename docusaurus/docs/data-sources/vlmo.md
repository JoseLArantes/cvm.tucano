---
title: Valores Mobiliários Negociados e Detidos (VLMO)
sidebar_position: 8
---

# Valores Mobiliários Negociados e Detidos (VLMO)

## O que é VLMO

**VLMO** significa **Valores Mobiliários Negociados e Detidos**.

Na prática, é o conjunto de informações que mostra:

- as **posições detidas** por administradores, conselheiros, controladores e pessoas vinculadas; e
- as **movimentações** feitas com valores mobiliários emitidos pela própria companhia, por sua controladora ou por suas controladas abertas.

No Portal de Dados Abertos da CVM, esse conjunto é descrito como informação de encaminhamento periódico prevista no **artigo 11 da Resolução CVM nº 44** e enviada por meio do **Sistema Empresas.NET**.

## Por que esse conjunto existe

O objetivo regulatório do VLMO é dar transparência para negociações e posições de pessoas com potencial acesso privilegiado a informação relevante.

Em termos operacionais, ele ajuda a CVM e o mercado a acompanhar:

- exposição patrimonial de insiders e vinculados;
- compras, vendas e outras mutações de posição;
- reapresentações do formulário;
- cumprimento de prazos de comunicação;
- possíveis padrões de negociação sensíveis para supervisão.

Pela própria Resolução CVM 44, os diretores, membros do conselho de administração, conselho fiscal e órgãos técnicos ou consultivos estatutários devem informar à companhia a titularidade e as negociações realizadas com esses valores mobiliários. O mesmo artigo prevê, entre outros casos, comunicação em até **5 dias** após cada negócio.

## Por que VLMO é útil

Para análise de mercado e governança, VLMO é útil para:

- monitorar **comportamento de insiders**;
- observar mudanças de posição de **controladores e vinculados**;
- detectar períodos com aumento de vendas, compras ou ajustes patrimoniais;
- cruzar negociações com **fatos relevantes**, resultados e eventos societários;
- entender se uma movimentação representa negociação de mercado, plano de remuneração, subscrição, empréstimo de ações, bonificação, grupamento, posse ou simples saldo inicial.

É um conjunto especialmente útil em:

- compliance;
- supervisão de insider trading;
- due diligence de governança;
- análise de incentivos da administração;
- pesquisa acadêmica sobre comportamento de insiders.

## Metadados técnicos

| Campo | Valor |
|-------|-------|
| **Fonte CVM** | `vlmo` |
| **Dataset oficial CVM** | `cia_aberta-doc-vlmo` |
| **Arquivo ZIP anual** | `vlmo_cia_aberta_{ano}.zip` |
| **Periodicidade no Empresas.NET** | Mensal para posição consolidada e posição individual; eventual para posse de administrador |
| **Periodicidade do portal de dados abertos** | Atualização semanal com reapresentações |
| **Cobertura no portal** | Últimos 5 anos |
| **Arquivos no ZIP aberto** | `vlmo_cia_aberta_{ano}.csv` e `vlmo_cia_aberta_con_{ano}.csv` |
| **Tabelas alvo no Tucano CVM** | `vlmo_documentos`, `vlmo_consolidado` |

### Observação importante sobre o escopo do open data

O manual do Empresas.NET lista três modalidades:

- **Posição Consolidada**
- **Posição Individual**
- **Posse de Administrador**

Mas, no conjunto aberto atualmente disponibilizado pela CVM e ingerido pelo Tucano CVM, o ZIP anual contém:

- um arquivo de cabeçalho documental (`vlmo_cia_aberta_{ano}.csv`); e
- um arquivo consolidado (`vlmo_cia_aberta_con_{ano}.csv`).

Além disso, o manual informa que, ao enviar o formulário individual, o sistema também gera automaticamente o **formulário consolidado**. Isso ajuda a explicar por que o open data é centrado na visão consolidada.

## O que exatamente entra no VLMO

O VLMO não se limita a “compra” e “venda”.

Pelos dados oficiais observados no arquivo consolidado, o conjunto inclui também eventos como:

- saldo inicial;
- posse;
- subscrição;
- homologação de subscrição;
- doação;
- herança;
- plano de remuneração;
- exercício de opção;
- bonificação/desdobramento;
- grupamento;
- empréstimo de ações;
- conversão de debêntures;
- units, bônus de subscrição, recibos e derivativos.

Ou seja: VLMO é um conjunto de **posição + movimentação**, e não apenas um log de trades de bolsa.

## Estrutura no Tucano CVM

O Tucano CVM expõe VLMO em duas tabelas principais:

- `vlmo_documentos`: cabeçalho documental do envio;
- `vlmo_consolidado`: linhas consolidadas de posição e movimentação.

## Endpoints principais

```bash
GET /vlmo/documentos?codigo_cvm=25224
GET /vlmo/consolidado?codigo_cvm=25224&tipo_cargo=Diretor%20ou%20Vinculado
GET /vlmo/consolidado?tipo_movimentacao=Compra%20%C3%A0%20vista&ano_inicio=2026
```

## Arquivo documental: `vlmo_cia_aberta_{ano}.csv`

Esse arquivo funciona como o **índice dos envios**.

Cada linha representa um documento entregue à CVM, com metadados como companhia, data de referência, data de entrega, versão e link de download.

### Campos principais do cabeçalho

| Campo oficial CVM | Campo no Tucano | O que significa |
|---|---|---|
| `CNPJ_Companhia` | `cnpj_companhia` | CNPJ da companhia emissora do formulário |
| `Codigo_CVM` | `codigo_cvm` | Código CVM da companhia |
| `Nome_Companhia` | `nome_companhia` | Nome da companhia |
| `Data_Referencia` | `data_referencia` | Data-base do informe |
| `Categoria` | `categoria` | Categoria do documento no Empresas.NET |
| `Tipo` | `tipo` | Tipo do documento; no open data observado, tipicamente `Posição Consolidada` |
| `Data_Entrega` | `data_entrega` | Data em que o documento foi entregue/recebido |
| `Tipo_Apresentacao` | `tipo_apresentacao` | Tipo de envio, como apresentação inicial ou reapresentação |
| `Motivo_Reapresentacao` | `motivo_reapresentacao` | Justificativa textual da reapresentação, quando houver |
| `Protocolo_Entrega` | `protocolo_entrega` | Protocolo do envio no sistema |
| `Versao` | `versao` | Número da versão do documento |
| `Link_Download` | `link_download` | URL de download do documento oficial |

### Como interpretar `tipo_apresentacao`

Valores observados no arquivo oficial:

- `AP - Apresentação`: envio inicial;
- `RE - Reapresentação Espontânea`: substituição espontânea do documento anterior.

Em termos práticos:

- use `data_referencia` para agrupar o mês/período reportado;
- use `versao` para identificar substituições;
- use `data_entrega` para medir o momento em que o mercado passou a ter acesso àquela versão.

## Arquivo consolidado: `vlmo_cia_aberta_con_{ano}.csv`

Esse é o arquivo mais importante para análise.

Cada linha representa uma **posição consolidada** ou uma **movimentação consolidada** em um determinado contexto de:

- companhia;
- data de referência;
- tipo de empresa relacionada;
- empresa relacionada;
- tipo de cargo;
- tipo de movimentação;
- tipo de ativo.

## Visão geral dos campos de `vlmo_consolidado`

| Campo no Tucano | O que representa |
|---|---|
| `cnpj_companhia` | Companhia que está reportando |
| `nome_companhia` | Nome da companhia reportante |
| `data_referencia` | Data-base do informe |
| `versao` | Versão do envio |
| `tipo_empresa` | Relação da empresa do ativo com a companhia reportante |
| `empresa` | Nome da empresa à qual o valor mobiliário se refere |
| `tipo_cargo` | Grupo de pessoas reportadas |
| `tipo_movimentacao` | Natureza econômica da posição ou mutação |
| `descricao_movimentacao` | Complemento textual da movimentação |
| `tipo_operacao` | Sinal da movimentação: entrada ou saída |
| `tipo_ativo` | Família do valor mobiliário ou instrumento |
| `caracteristica_valor_mobiliario` | Série, classe ou característica específica do instrumento |
| `intermediario` | Intermediário informado, quando aplicável |
| `data_movimentacao` | Data do negócio ou evento, quando aplicável |
| `quantidade` | Quantidade de títulos/unidades |
| `preco_unitario` | Preço unitário informado |
| `volume` | Valor financeiro total da movimentação |

## Campo a campo: explicação detalhada

### `tipo_empresa`

Valores observados:

- `Companhia`
- `Controladora`
- `Controlada`

Significado:

- `Companhia`: o ativo negociado/detido é da própria companhia que reporta;
- `Controladora`: o ativo se refere à controladora da companhia;
- `Controlada`: o ativo se refere a controlada aberta da companhia.

Por que isso existe:

O art. 11 da RCVM 44 não se limita apenas a valores mobiliários emitidos pela própria companhia. Também alcança valores emitidos por controladoras e controladas abertas.

### `empresa`

É o nome da empresa à qual o valor mobiliário se refere.

Exemplo prático:

- a companhia reportante pode ser Banco do Brasil;
- a linha pode estar marcada como `Controlada`;
- `empresa` pode aparecer como `BB SEGURIDADE PARTICIPAÇÕES S.A.`.

Ou seja, `empresa` não é redundante: ela mostra **sobre qual emissor específico** aquela posição ou movimentação incide.

### `tipo_cargo`

Valores observados:

- `Controlador ou Vinculado`
- `Conselho de Administração ou Vinculado`
- `Diretor ou Vinculado`
- `Conselho Fiscal ou Vinculado`
- `Órgão Estatutário ou Vinculado`

Significado:

Esse campo agrupa a posição/movimentação por **categoria regulatória de pessoa obrigada**.

Interpretação prática:

- `Diretor ou Vinculado`: diretores e pessoas ligadas a eles;
- `Conselho de Administração ou Vinculado`: conselheiros de administração e vinculados;
- `Conselho Fiscal ou Vinculado`: membros do conselho fiscal e vinculados;
- `Órgão Estatutário ou Vinculado`: membros de órgãos técnicos/consultivos previstos no estatuto e vinculados;
- `Controlador ou Vinculado`: acionista controlador e pessoas a ele vinculadas.

Observação importante:

No arquivo consolidado aberto, a granularidade é **por grupo**, não por pessoa física nominal. Se a análise exigir o nome individual, essa informação não está nesta tabela consolidada do open data.

### `tipo_movimentacao`

Esse é um dos campos mais importantes.

Ele responde à pergunta: **que tipo de evento patrimonial ocorreu?**

Valores observados com frequência:

- `Saldo Inicial`
- `Compra à vista`
- `Venda à vista`
- `Outras Entradas`
- `Outras Saídas`
- `Posse`
- `Subscrição`
- `Homologação de subscrição`
- `Ações de plano de remuneração`
- `Units de plano de remuneração`
- `Desdobramento/bonificação`
- `Grupamento`
- `Contratação de empréstimo (locador)`
- `Devolução de empréstimo (locador)`
- `Contratação de empréstimo (tomador)`
- `Devolução de empréstimo (tomador)`
- `Doação (doador)`
- `Doação (donatário)`
- `Exercício opção de compra`
- `Exercício opção de venda`
- `Ações decorrentes de exercício de opção de compra`
- `Ações resultantes de conversão de debêntures`

Como usar esse campo:

- para separar posição inicial de negociação efetiva;
- para distinguir transação de mercado de evento societário ou remuneração;
- para detectar mutações sem preço de tela, como posse, bonificação ou grupamento.

### `descricao_movimentacao`

É um campo textual complementar.

Na prática, ele costuma:

- detalhar o contexto da movimentação;
- explicar ajustes;
- identificar plano de remuneração;
- registrar evento societário específico;
- justificar reapresentações ou reclassificações econômicas.

Exemplos observados:

- `AJUSTE DE METODOLOGIA DE APRESENTAÇÃO DE FORMULÁRIO`
- `Plano para Outorga de Ações e/ou Plano para Outorga de Opções de Ações`
- `Conversão da totalidade das ações preferenciais em ações ordinárias`
- `Ajuste de posição inicial (operações reportadas em meses anteriores)`

Leitura correta:

- `tipo_movimentacao` dá a classe principal do evento;
- `descricao_movimentacao` dá o contexto específico.

### `tipo_operacao`

Valores observados:

- `Crédito`
- `Débito`

Significado:

- `Crédito`: entrada/aumento de posição;
- `Débito`: saída/redução de posição.

Diferença para `tipo_movimentacao`:

- `tipo_movimentacao` explica **o que aconteceu**;
- `tipo_operacao` explica **o sinal patrimonial** da linha.

Exemplos:

- `Compra à vista` tende a aparecer como `Crédito`;
- `Venda à vista` tende a aparecer como `Débito`;
- `Saldo Inicial` aparece como a posição de abertura do período.

### `tipo_ativo`

Valores observados:

- `Ações`
- `Debêntures`
- `Opção de Compra`
- `Opção de Venda`
- `Units`
- `Outros`
- `Recibo de Subscrição`
- `Bônus de Subscrição`
- `Derivativos`
- `Opções de Plano de Remuneração`
- `BDR Patrocinados`

Esse campo identifica a **família do instrumento financeiro**.

Ele é útil para separar:

- instrumentos patrimoniais clássicos;
- dívida;
- derivativos;
- instrumentos híbridos;
- instrumentos ligados a planos de incentivo.

### `caracteristica_valor_mobiliario`

Esse campo guarda a característica específica do instrumento.

Exemplos observados:

- `ON`
- `PN`
- `PNA`
- `PNB`
- `PNC`
- `ADR`
- `ADS`
- `KLBN11`
- `IGTI11`
- `EQTL1`
- `PGMN9`
- descrições de emissão, direitos ou estruturas específicas

Como interpretar:

- em ações, costuma indicar a **classe/série** (`ON`, `PN`, etc.);
- em units, pode trazer o **ticker/estrutura** da unit;
- em debêntures, pode trazer a emissão;
- em direitos/opções/derivativos, pode trazer o identificador econômico relevante.

Esse campo não tem domínio fechado robustamente documentado pela CVM no dicionário; ele funciona, na prática, como um campo de caracterização de série/classe/estrutura.

### `intermediario`

É o intermediário informado para a movimentação, quando aplicável.

Valores observados:

- `Itaú Corretora de Valores S.A.`
- `XP`
- `BTG Pactual`
- `ÁGORA CTVM SA`
- `Banco Inter`
- `Particular`
- `Negociação Privada`
- vazio

Leitura correta:

- quando preenchido, indica a corretora/banco/intermediário ou o canal econômico da operação;
- quando vazio, pode significar posição sem operação no período, evento sem intermediário típico, ou ausência de preenchimento relevante naquele contexto.

### `data_movimentacao`

É a data da movimentação.

Mas nem toda linha terá valor nesse campo.

Exemplo:

- `Saldo Inicial` normalmente não representa um negócio do dia, então pode aparecer sem `data_movimentacao`;
- compras, vendas, subscrições, exercícios e outras operações normalmente trazem a data do evento.

### `quantidade`

Quantidade de títulos, ações, units, contratos ou instrumentos reportados na linha.

Uso prático:

- medir a variação de posição;
- reconstruir exposição por tipo de cargo;
- comparar saldo inicial com eventos posteriores.

### `preco_unitario`

Preço unitário informado para a movimentação.

Nem toda linha terá preço:

- posições de abertura (`Saldo Inicial`) normalmente não trazem preço;
- eventos societários ou ajustes podem não ter preço econômico de negociação;
- negociações de mercado tendem a preencher.

### `volume`

Valor financeiro total da movimentação.

Na leitura usual, ele representa o montante financeiro total do evento quando aplicável.

Na prática:

- tende a fazer sentido em compras e vendas;
- pode ficar vazio em linhas puramente posicionais ou em certos eventos patrimoniais sem preço de negociação.

## Diferença entre posição e movimentação

Essa é a distinção mais importante para não interpretar o dataset errado.

### Linha de posição

Exemplo típico:

- `tipo_movimentacao = Saldo Inicial`
- `tipo_operacao = Crédito`
- `data_movimentacao` vazia
- `quantidade` preenchida
- `preco_unitario` e `volume` vazios

Leitura:

- representa estoque/posição de abertura do período, não necessariamente uma transação.

### Linha de movimentação

Exemplo típico:

- `tipo_movimentacao = Compra à vista`
- `tipo_operacao = Crédito`
- `data_movimentacao` preenchida
- `quantidade`, `preco_unitario` e `volume` preenchidos

Leitura:

- representa evento econômico com mudança de posição.

## Como interpretar `data_referencia`

`data_referencia` é a **data-base do informe**, não necessariamente a data de cada negócio.

Por exemplo:

- um documento com `data_referencia = 2026-05-01` representa a posição/movimentação referente àquele período-base;
- as operações individuais, quando existentes na linha, aparecem em `data_movimentacao`;
- o envio à CVM aparece em `data_entrega`, no arquivo documental.

## Como interpretar `versao`

`versao` é crítica em VLMO.

Como os documentos podem ser reapresentados:

- a versão 1 pode ser o envio inicial;
- versões seguintes substituem/retificam o conteúdo;
- o cabeçalho documental traz também `tipo_apresentacao` e `motivo_reapresentacao`.

Em produção, a regra segura é:

- sempre considerar a versão mais recente para a mesma chave documental, salvo necessidade de auditoria histórica.

## O que o VLMO não é

VLMO não deve ser lido como:

- log completo da bolsa;
- tape de negociações intraday;
- posição acionária total de todos os investidores;
- identificação nominativa completa de cada insider na tabela consolidada aberta.

Ele é um **informe regulatório consolidado** sobre pessoas obrigadas e vinculadas.

## Boas práticas de uso analítico

### 1. Não confundir `Saldo Inicial` com negociação

`Saldo Inicial` é posição, não trade.

### 2. Cruzar `data_movimentacao` com `data_entrega`

Isso ajuda a avaliar tempestividade do reporte e janelas regulatórias.

### 3. Separar evento patrimonial de operação de mercado

`Compra à vista` e `Venda à vista` não têm o mesmo significado analítico de:

- `Posse`
- `Grupamento`
- `Bonificação`
- `Plano de remuneração`
- `Conversão de debêntures`

### 4. Tratar `caracteristica_valor_mobiliario` como campo semântico livre

Ele não é apenas “classe da ação”. Em muitos casos contém ticker, emissão, direito, estrutura da unit ou detalhe específico do instrumento.

### 5. Usar `tipo_empresa` para evitar leitura errada do emissor

Uma linha pode estar reportando ativo da própria companhia, da controladora ou de controlada aberta.

## Relação com a API do Tucano CVM

No Tucano CVM:

- `vlmo_documentos` espelha o cabeçalho documental;
- `vlmo_consolidado` expõe as linhas consolidadas já normalizadas;
- datas de resposta usam `DD/MM/AAAA`;
- decimais monetários saem como string decimal canônica.

## Referências oficiais

- [Portal Dados Abertos CVM – dataset `cia_aberta-doc-vlmo`](https://dados.cvm.gov.br/dataset/cia_aberta-doc-vlmo)
- [Notícia da CVM sobre a abertura do conjunto VLMO](https://www.gov.br/cvm/pt-br/assuntos/noticias/2023/portal-dados-abertos-cvm-disponibiliza-informacoes-sobre-valores-mobiliarios-negociados-e-detidos-das-companhias-abertas)
- [Dicionário oficial do conjunto (`meta_vlmo_cia_aberta.zip`)](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/VLMO/META/meta_vlmo_cia_aberta.zip)
- [Manual de Envio de Informações Periódicas e Eventuais (Empresas.NET)](https://www.gov.br/cvm/pt-br/assuntos/regulados/consultas-por-participante/companhias/envio-de-informacoes-enet/manual-de-envio-de-informacoes-periodicas-e-eventuais)

## Nota metodológica

Parte da semântica acima vem diretamente da documentação oficial da CVM.

Outra parte, especialmente para campos como `tipo_movimentacao`, `tipo_cargo`, `tipo_empresa`, `caracteristica_valor_mobiliario` e `intermediario`, foi inferida a partir de:

- nomes oficiais dos campos;
- base legal do formulário;
- comportamento observado no ZIP oficial `vlmo_cia_aberta_2026.zip`;
- domínios reais encontrados no arquivo consolidado publicado pela CVM.

Essa distinção é importante porque o dicionário oficial do arquivo consolidado deixa vários campos sem descrição textual, embora o conteúdo publicado permita interpretação segura do uso prático.
