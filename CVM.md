# CVM - Comissão de Valores Mobiliários

A **Comissão de Valores Mobiliários (CVM)** é a autarquia federal, vinculada ao Ministério da Fazenda, encarregada de disciplinar, fiscalizar e desenvolver o mercado de capitais no Brasil. A instituição foi fundada em 7 de dezembro de 1976 pela [Lei nº 6.385](http://www.planalto.gov.br/ccivil_03/leis/l6385.htm) (lançada simultaneamente à histórica Lei das S.A. - [Lei nº 6.404](http://www.planalto.gov.br/ccivil_03/leis/l6404compilada.htm)).

A instituição nasceu no contexto de expansão e modernização da economia brasileira, com a missão de trazer segurança jurídica, integridade e transparência a um ambiente de investimentos em ações que, até então, carecia de regulação centralizada. Como órgão regulador, sua existência baseia-se em pilares fundamentais: a proteção ao investidor (assegurando tratamento equitativo e coibindo fraudes ou uso de informação privilegiada), a disseminação pública de informações periódicas e eventuais pelas companhias listadas, e o fomento à atração de poupança privada para o financiamento empresarial por meio de ações, debêntures e fundos de investimento.

A CVM disponibiliza dados de acesso público que existem por razões regulatórias e econômicas, como:

- reduzir assimetria de informação entre companhia, investidor, analista, auditor e mercado;
- permitir supervisão regulatória e enforcement;
- viabilizar comparabilidade entre emissores;
- preservar histórico de versões, reapresentações e mudanças relevantes;
- dar transparência para decisões de investimento, crédito, compliance e governança.

### Links Úteis
*   [Site Oficial da CVM](https://www.gov.br/cvm/pt-br) - Canal institucional, notícias e consultas interativas.
*   [Portal de Dados Abertos da CVM](https://dados.cvm.gov.br/) - Fonte oficial dos dados estruturados brutos utilizados neste projeto.
*   [Consulta Cadastral de Companhias](https://www.gov.br/cvm/pt-br/assuntos/regulados/consultas/companhias) - Sistema para pesquisa direta e visualização de documentos de empresas específicas.

# Arquivos Públicos da CVM - Companhias

Os dados da CVM são públicos, mas o consumo direto deles costuma ser operacionalmente caro. Os principais problemas são:

- arquivos distribuídos em múltiplos conjuntos e múltiplos anos;
- formatos ZIP/CSV com muitos layouts;
- necessidade de entender chaves naturais e relacionamentos entre documentos;
- reapresentações e versões de documentos;
- nomes de colunas técnicos e inconsistências de preenchimento;
- ausência de uma API pronta para consulta orientada a produto.

Na prática, isso afeta:

- produtos financeiros que precisam consultar dados consolidados de emissores;
- times quantitativos que precisam comparar companhias ao longo do tempo;
- times de compliance e auditoria que precisam rastrear origem e alteração de cada linha;
- operações internas que precisam automatizar sincronizações sem “blind import”.

Este projeto faz a ponte entre o dado regulatório bruto e o dado de aplicação.

---

## 1. CGVN - Informe sobre Código Brasileiro de Governança Corporativa

### Visão Geral
O **Informe do Código de Governança (ICBGC)** é um documento eletrônico de encaminhamento periódico previsto no artigo 32 da Resolução CVM nº 80/22 [[10]]. Seu objetivo é que as companhias abertas informem, por meio de abordagem "pratique ou explique", se seguem determinadas práticas de governança corporativa recomendadas pelo Código Brasileiro de Governança Corporativa [[9]].

### Base Legal
- Resolução CVM nº 80/22, artigo 32
- Código Brasileiro de Governança Corporativa - Companhias Abertas

### Finalidade
Permitir que investidores e mercado avaliem o nível de aderência das companhias às melhores práticas de governança corporativa, promovendo transparência e comparabilidade entre as empresas [[7]].

### Frequência de Atualização
- **Periodicidade**: Semanal (com eventuais reapresentações) [[10]]
- **Histórico**: Dados disponíveis desde 2018 [[10]]

### Arquivos Disponíveis (2026)

#### `cgvn_cia_aberta_2026.csv`
- **Descrição**: Arquivo principal contendo os informes de governança corporativa das companhias abertas
- **Dados Contidos**:
  - Código CVM da companhia
  - CNPJ da companhia
  - Nome da companhia
  - Data de referência do informe
  - Data de entrega do documento
  - Versão do documento
  - Protocolo de entrega
  - Link para download do documento original
  
- **Importância**: Permite analisar o nível de conformidade das companhias com as práticas recomendadas de governança corporativa
- **Uso Principal**: Análise de governança corporativa, rankings de governança, estudos acadêmicos sobre qualidade da gestão

#### `cgvn_cia_aberta_praticas_2026.csv`
- **Descrição**: Arquivo detalhado contendo as práticas de governança declaradas por cada companhia
- **Dados Contidos**:
  - Código CVM
  - CNPJ
  - Identificação da prática de governança
  - Descrição da prática
  - Indicação se a companhia adota a prática ("pratique") ou justifica a não adoção ("explique")
  - Detalhes da implementação
  
- **Importância**: Fornece granularidade sobre quais práticas específicas cada companhia adota
- **Uso Principal**: Análise detalhada de políticas de governança, comparação entre setores, due diligence

---

## 2. VLMO - Valores Mobiliários Negociados e Detidos

### Visão Geral
**Valores Mobiliários Negociados e Detidos** são informações de encaminhamento periódico à CVM, conforme previsto no artigo 11 da Resolução CVM nº 44 [[11]]. Este conjunto de dados fornece informações sobre a negociação e detenção de valores mobiliários pelas companhias.

### Base Legal
- Resolução CVM nº 44, artigo 11
- Resolução CVM nº 80/22

### Finalidade
Monitorar e divulgar informações sobre a movimentação de valores mobiliários, permitindo análise de liquidez, concentração de capital e padrões de negociação [[15]].

### Frequência de Atualização
- **Periodicidade**: Semanal (com eventuais reapresentações) [[11]]
- **Histórico**: Dados disponíveis nos últimos cinco anos [[11]]

### Arquivos Disponíveis (2026)

#### `vlmo_cia_aberta_2026.csv`
- **Descrição**: Arquivo principal com informações sobre valores mobiliários negociados e detidos
- **Dados Contidos**:
  - Código CVM da companhia
  - CNPJ da companhia
  - Nome da companhia
  - Tipo de valor mobiliário
  - Espécie do valor mobiliário
  - Quantidade negociada
  - Quantidade detida
  - Período de referência
  - Data de entrega
  - Valor de negociação
  
- **Importância**: Essencial para análise de mercado, liquidez e concentração acionária
- **Uso Principal**: Análise de mercado de capitais, estudos de liquidez, monitoramento de concentração de capital

#### `vlmo_cia_aberta_con_2026.csv`
- **Descrição**: Arquivo consolidado com informações consolidadas sobre valores mobiliários
- **Dados Contidos**:
  - Dados consolidados de valores mobiliários
  - Informações agregadas por tipo de valor mobiliário
  - Totais consolidados por companhia
  - Informações de controle acionário
  
- **Importância**: Fornece visão consolidada da estrutura de capital e movimentação
- **Uso Principal**: Análise de estrutura de capital, estudos de controle acionário, relatórios para investidores

---

## 3. IPE - Informações Periódicas e Eventuais

### Visão Geral
O conjunto de dados **IPE** disponibiliza os documentos não estruturados de companhias, incluindo documentos periódicos e eventuais entregues nos últimos cinco anos [[22]]. É um repositório abrangente de comunicações ao mercado.

### Base Legal
- Resolução CVM nº 80/22
- Diversas resoluções específicas sobre tipos de documentos

### Finalidade
Centralizar todas as comunicações obrigatórias das companhias abertas ao mercado, incluindo fatos relevantes, avisos aos acionistas, estatutos sociais, políticas corporativas e outros documentos regulatórios [[21]].

### Frequência de Atualização
- **Periodicidade**: Semanal (com eventuais reapresentações) [[22]]
- **Histórico**: Dados disponíveis desde 2003 [[22]]

### Arquivo Disponível (2026)

#### `ipe_cia_aberta_2026.csv`
- **Descrição**: Arquivo índice contendo metadados de todos os documentos periódicos e eventuais entregues pelas companhias
- **Dados Contidos** [[20]]:
  - **Assunto**: Descrição do assunto do documento
  - **Categoria**: Categoria do documento (ex: Fato Relevante, Aviso aos Acionistas, Estatuto Social, etc.)
  - **CNPJ_Companhia**: CNPJ da companhia emissora
  - **Codigo_CVM**: Código CVM da companhia
  - **Data_Entrega**: Data de entrega/recebimento do documento (AAAA-MM-DD)
  - **Data_Referencia**: Data de referência do documento (AAAA-MM-DD)
  - **Especie**: Espécie do documento
  - **Link_Download**: Endereço URL para download do documento original
  - **Nome_Companhia**: Nome da companhia emissora
  - **Protocolo_Entrega**: Número do protocolo de entrega
  - **Tipo**: Tipo específico do documento
  - **Tipo_Apresentacao**: Tipo de apresentação (consolidado, individual, etc.)
  - **Versao**: Versão do documento
  
- **Categorias de Documentos Incluídos** [[22]]:
  - Acordo de Acionistas
  - Assembleia
  - Aviso aos Acionistas
  - Aviso aos Debenturistas
  - Calendário de Eventos Corporativos
  - Carta Anual de Governança Corporativa
  - Código de Conduta
  - Comunicado ao Mercado
  - Estatuto Social
  - **Fato Relevante**
  - OPA - Edital de Oferta Pública de Ações
  - Plano de Remuneração Baseado em Ações
  - Política de Dividendos
  - Política de Negociação
  - Política de Sustentabilidade
  - Regimento Interno (Conselho de Administração, Diretoria, Comitês)
  - Relatório de Sustentabilidade
  - E muitos outros (mais de 40 categorias)
  
- **Importância**: Fonte primária para monitoramento de eventos corporativos, fatos relevantes e mudanças regulatórias
- **Uso Principal**: Monitoramento de mercado em tempo real, análise de eventos corporativos, compliance, jornalismo financeiro, sistemas de alerta

---

## 4. FCA - Formulário Cadastral Anual de Companhias

### Visão Geral
O **Formulário Cadastral (FCA)** é um documento eletrônico de encaminhamento periódico e eventual, previsto no artigo 22, inciso I, da Resolução CVM nº 80/22 [[30]]. Contém informações cadastrais completas das companhias abertas.

### Base Legal
- Resolução CVM nº 80/22, artigo 22, inciso I
- Anexo B da Resolução CVM 80

### Finalidade
Reunir informações sobre os dados e características principais da companhia e dos valores mobiliários emitidos, servindo como base cadastral para todas as demais obrigações regulatórias [[36]].

### Frequência de Atualização
- **Periodicidade**: Semanal (com eventuais reapresentações) [[30]]
- **Histórico**: Dados disponíveis desde 2010 [[30]]

### Arquivos Disponíveis (2026)

#### `fca_cia_aberta_2026.csv`
- **Descrição**: Arquivo índice com informações gerais do Formulário Cadastral
- **Dados Contidos**:
  - Código CVM
  - CNPJ
  - Nome da companhia
  - Data de referência
  - Data de entrega
  - Versão do formulário
  - Link para download do documento original
  
- **Importância**: Ponto de entrada para acessar todos os dados cadastrais da companhia
- **Uso Principal**: Identificação de companhias, validação de dados cadastrais

#### `fca_cia_aberta_geral_2026.csv`
- **Descrição**: Dados gerais da companhia (Seção 1 do Anexo 22 da ICVM 480) [[30]]
- **Dados Contidos**:
  - Denominação social
  - Denominação comercial
  - Data de constituição
  - Objeto social
  - Atividades principais
  - Controle acionário
  - Exercício social
  
- **Importância**: Informações básicas essenciais sobre a companhia
- **Uso Principal**: Cadastro de empresas, análise setorial, estudos de mercado

#### `fca_cia_aberta_endereco_2026.csv`
- **Descrição**: Endereços da companhia (Itens 1.25 a 1.30 do Anexo 22 da ICVM 480) [[30]]
- **Dados Contidos**:
  - Endereço da sede
  - Endereço de correspondência
  - Logradouro, número, complemento
  - Bairro, município, UF, CEP
  - Telefone, fax, e-mail
  - Tipo de endereço
  
- **Importância**: Informações de contato e localização
- **Uso Principal**: Contato com companhias, análise geográfica de empresas

#### `fca_cia_aberta_canal_divulgacao_2026.csv`
- **Descrição**: Canais de divulgação da companhia (Item 1.24 do Anexo 22 da ICVM 480) [[30]]
- **Dados Contidos**:
  - Site de relações com investidores
  - Endereços eletrônicos de divulgação
  - Jornais de publicação
  - Mídias utilizadas para comunicação
  
- **Importância**: Identifica onde a companhia divulga informações ao mercado
- **Uso Principal**: Monitoramento de canais de RI, análise de transparência

#### `fca_cia_aberta_valor_mobiliario_2026.csv`
- **Descrição**: Informações sobre valores mobiliários emitidos (Seção 2 do Anexo 22 da ICVM 480) [[30]]
- **Dados Contidos**:
  - Tipo de valor mobiliário (ações, debêntures, etc.)
  - Espécie (ordinárias, preferenciais)
  - Classe
  - Quantidade emitida
  - Características especiais
  - Direitos e vantagens
  
- **Importância**: Estrutura completa de capital da companhia
- **Uso Principal**: Análise de estrutura de capital, valuation, estudos de governança

#### `fca_cia_aberta_auditor_2026.csv`
- **Descrição**: Informações sobre auditores independentes (Seção 3 do Anexo 22 da ICVM 480) [[30]]
- **Dados Contidos**:
  - Nome do auditor independente
  - CNPJ do auditor
  - Data de início da contratação
  - Tempo de atuação
  
- **Importância**: Transparência sobre auditoria e independência
- **Uso Principal**: Análise de qualidade da auditoria, monitoramento de rotatividade

#### `fca_cia_aberta_escriturador_2026.csv`
- **Descrição**: Informações sobre escriturador de valores mobiliários (Seção 4 do Anexo 22 da ICVM 480) [[30]]
- **Dados Contidos**:
  - Nome do escriturador
  - CNPJ do escriturador
  - Dados de contato
  
- **Importância**: Identificação do agente responsável pela escrituração
- **Uso Principal**: Contato para assuntos acionários, transferência de ações

#### `fca_cia_aberta_dri_2026.csv`
- **Descrição**: Informações sobre o Diretor de Relações com Investidores (Seção 5 do Anexo 22 da ICVM 480) [[30]]
- **Dados Contidos**:
  - Nome do DRI
  - Dados de contato (telefone, e-mail)
  - Data de início da atuação
  - Formação profissional
  
- **Importância**: Ponto de contato oficial para investidores
- **Uso Principal**: Contato com RI, análise de qualidade da área de RI

#### `fca_cia_aberta_pais_estrangeiro_negociacao_2026.csv`
- **Descrição**: Países onde há negociação de valores mobiliários (Itens 1.14 e 1.15 do Anexo 22 da ICVM 480) [[30]]
- **Dados Contidos**:
  - País estrangeiro
  - Bolsa ou mercado onde há negociação
  - Tipo de valor mobiliário negociado
  - Data de início da negociação
  
- **Importância**: Identifica internacionalização do capital da companhia
- **Uso Principal**: Análise de ADRs, estudos de internacionalização, arbitragem

---

## 5. FRE - Formulário de Referência

### Visão Geral
O **Formulário de Referência (FRE)** é um documento eletrônico de encaminhamento periódico e eventual, previsto no artigo 22, inciso II, da Resolução CVM nº 80/22 [[39]]. Reúne todas as informações referentes ao emissor, incluindo atividades, fatores de risco, administração, estrutura de capital, dados financeiros e operações com partes relacionadas [[39]].

### Base Legal
- Resolução CVM nº 80/22, artigo 22, inciso II
- Anexo C da Resolução CVM 80/22
- Resolução CVM nº 198 (alterações recentes)

### Finalidade
Servir como instrumento abrangente de divulgação de informações sobre a companhia, substituindo antigos formulários e centralizando informações essenciais para decisão de investimento [[44]].

### Frequência de Atualização
- **Periodicidade**: Semanal (com eventuais reapresentações) [[39]]
- **Histórico**: Dados disponíveis desde 2010 [[39]]

### Arquivos Disponíveis (2026)

#### `fre_cia_aberta_2026.csv`
- **Descrição**: Arquivo índice com metadados dos Formulários de Referência
- **Dados Contidos**:
  - Código CVM, CNPJ, nome da companhia
  - Data de referência e data de entrega
  - Versão do formulário
  - Link para download do documento original
  
- **Importância**: Ponto de entrada para acessar o FRE completo
- **Uso Principal**: Identificação de FREs disponíveis, monitoramento de atualizações

#### `fre_cia_aberta_responsavel_2026.csv`
- **Descrição**: Identificação dos responsáveis pelo FRE (Item 1.1 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Nome do responsável
  - Cargo/função
  - Declaração de responsabilidade sobre as informações
  
- **Importância**: Accountability e responsabilidade pelas informações divulgadas
- **Uso Principal**: Identificação de responsáveis, compliance

#### `fre_cia_aberta_auditor_2026.csv`
- **Descrição**: Auditores independentes - identificação e remuneração (Itens 2.1/2 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Nome do auditor
  - CNPJ
  - Valor da remuneração por serviços de auditoria
  - Valor da remuneração por outros serviços
  - Tempo de atuação
  
- **Importância**: Transparência sobre relação com auditores
- **Uso Principal**: Análise de independência de auditores, estudos de qualidade de auditoria

#### `fre_cia_aberta_capital_social_2026.csv`
- **Descrição**: Informações sobre capital social (Item 17.1 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Capital social autorizado
  - Capital social subscrito
  - Capital social realizado
  - Data de referência
  
- **Importância**: Base para análise de estrutura de capital
- **Uso Principal**: Valuation, análise financeira, estudos de alavancagem

#### `fre_cia_aberta_capital_social_classe_acao_2026.csv`
- **Descrição**: Capital social detalhado por classe de ação (Item 17.1 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Classe de ação (ON, PN, etc.)
  - Quantidade de ações por classe
  - Valor nominal
  - Direitos específicos
  
- **Importância**: Detalhamento da estrutura acionária
- **Uso Principal**: Análise de governança, cálculo de indicadores

#### `fre_cia_aberta_capital_social_titulo_conversivel_2026.csv`
- **Descrição**: Títulos conversíveis em ações (Item 17.1 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Tipo de título conversível
  - Quantidade emitida
  - Condições de conversão
  - Prazo de conversão
  
- **Importância**: Identifica potencial de diluição
- **Uso Principal**: Análise de diluição, valuation, estudos de estrutura de capital

#### `fre_cia_aberta_distribuicao_capital_2026.csv`
- **Descrição**: Distribuição de capital (Item 15.3 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Faixas de participação acionária
  - Quantidade de acionistas por faixa
  - Percentual do capital por faixa
  
- **Importância**: Análise de dispersão ou concentração acionária
- **Uso Principal**: Estudos de governança, análise de liquidez, monitoramento de controle

#### `fre_cia_aberta_distribuicao_capital_classe_acao_2026.csv`
- **Descrição**: Distribuição de capital por classe de ação (Item 15.3.d do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Distribuição detalhada por classe
  - Acionistas controladores
  - Acionistas minoritários
  
- **Importância**: Detalhamento da distribuição por tipo de ação
- **Uso Principal**: Análise de controle, estudos de tag along

#### `fre_cia_aberta_posicao_acionaria_2026.csv`
- **Descrição**: Posição acionária (Item 15.1/2 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Principais acionistas
  - Quantidade de ações
  - Percentual de participação
  - Tipo de controle
  
- **Importância**: Identificação dos controladores e grandes acionistas
- **Uso Principal**: Análise de controle, monitoramento de mudanças acionárias, due diligence

#### `fre_cia_aberta_posicao_acionaria_classe_acao_2026.csv`
- **Descrição**: Posição acionária detalhada por classe de ação (Item 15.1/2 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Posição acionária segregada por classe
  - Direitos de voto por classe
  
- **Importância**: Análise detalhada do poder de voto
- **Uso Principal**: Estudos de governança, análise de controle

#### `fre_cia_aberta_administrador_membro_conselho_fiscal_2026.csv`
- **Descrição**: Composição e experiência dos administradores e membros do conselho fiscal (Itens 12.5/6 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Nome do administrador/conselheiro
  - Cargo
  - Data de nascimento
  - Formação acadêmica
  - Experiência profissional
  - Outras participações em conselhos
  
- **Importância**: Avaliação da qualidade e experiência da gestão
- **Uso Principal**: Análise de governança, due diligence, estudos de qualidade da gestão

#### `fre_cia_aberta_membro_comite_2026.csv`
- **Descrição**: Composição dos comitês (Itens 12.7/8 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Nome do comitê (Auditoria, RH, etc.)
  - Membros do comitê
  - Frequência de reuniões
  - Atribuições
  
- **Importância**: Estrutura de governança e controles internos
- **Uso Principal**: Análise de governança, estudos de melhores práticas

#### `fre_cia_aberta_relacao_familiar_2026.csv`
- **Descrição**: Relações familiares entre administradores (Item 12.9 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Identificação dos administradores com relações familiares
  - Tipo de relação familiar
  - Cargos ocupados
  
- **Importância**: Identificação de potenciais conflitos de interesse
- **Uso Principal**: Análise de governança, estudos de nepotismo

#### `fre_cia_aberta_relacao_subordinacao_2026.csv`
- **Descrição**: Relações de subordinação, prestação de serviço ou controle (Item 12.10 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Relações hierárquicas
  - Prestação de serviços entre partes relacionadas
  - Acordos de controle
  
- **Importância**: Transparência sobre estrutura de controle
- **Uso Principal**: Análise de governança, estudos de controle

#### `fre_cia_aberta_remuneracao_total_orgao_2026.csv`
- **Descrição**: Remuneração total do conselho de administração, diretoria estatutária e conselho fiscal (Item 13.2 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Valor total da remuneração por órgão
  - Remuneração fixa
  - Remuneração variável
  - Benefícios
  
- **Importância**: Transparência sobre custos de administração
- **Uso Principal**: Análise de remuneração executiva, benchmarks, governança

#### `fre_cia_aberta_remuneracao_maxima_minima_media_2026.csv`
- **Descrição**: Remuneração máxima, mínima e média dos órgãos de administração (Item 13.11 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Remuneração máxima
  - Remuneração mínima
  - Remuneração média
  - Por órgão (Conselho, Diretoria, Conselho Fiscal)
  
- **Importância**: Análise de equidade e dispersão salarial
- **Uso Principal**: Estudos de remuneração, análise de desigualdade, governança

#### `fre_cia_aberta_remuneracao_acao_2026.csv`
- **Descrição**: Remuneração baseada em ações (item 8.5 do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Planos de remuneração em ações
  - Quantidade de ações destinadas
  - Condições de vesting
  - Valor dos planos
  
- **Importância**: Alinhamento de interesses entre gestão e acionistas
- **Uso Principal**: Análise de incentivos, governança, estudos de alinhamento

#### `fre_cia_aberta_remuneracao_variavel_2026.csv`
- **Descrição**: Remuneração variável (item 8.3 do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Bônus
  - PLR (Participação nos Lucros e Resultados)
  - Metas e critérios
  - Valores pagos
  
- **Importância**: Estrutura de incentivos da gestão
- **Uso Principal**: Análise de remuneração, governança, estudos de performance

#### `fre_cia_aberta_aao_entregue_2026.csv`
- **Descrição**: Ações entregues como remuneração (item 8.11 do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Quantidade de ações entregues
  - Beneficiários
  - Data de entrega
  - Valor
  
- **Importância**: Detalhamento da remuneração em ações
- **Uso Principal**: Análise de diluição, governança

#### `fre_cia_aberta_participacao_sociedade_2026.csv`
- **Descrição**: Participação em outras sociedades (Item 9.1.c do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Nome da sociedade participada
  - CNPJ
  - Percentual de participação
  - Tipo de controle
  - Atividade principal
  
- **Importância**: Estrutura do grupo econômico
- **Uso Principal**: Análise de estrutura societária, estudos de consolidação

#### `fre_cia_aberta_transacao_parte_relacionada_2026.csv`
- **Descrição**: Transações com partes relacionadas (Item 16.2 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Tipo de transação
  - Parte relacionada
  - Valor da transação
  - Condições
  - Prazo
  
- **Importância**: Transparência sobre conflitos de interesse
- **Uso Principal**: Análise de governança, due diligence, auditoria

#### `fre_cia_aberta_outro_valor_mobiliario_2026.csv`
- **Descrição**: Outros valores mobiliários emitidos (Item 18.5 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Tipo de valor mobiliário (debêntures, notas comerciais, etc.)
  - Características
  - Quantidade emitida
  - Direitos
  
- **Importância**: Estrutura completa de capital
- **Uso Principal**: Análise de estrutura de capital, valuation

#### `fre_cia_aberta_titulo_exterior_2026.csv`
- **Descrição**: Títulos emitidos no exterior (Item 18.8 do Anexo 24 da ICVM 480) [[39]]
- **Dados Contidos**:
  - Tipo de título (ADR, GDR, bonds)
  - País de emissão
  - Quantidade
  - Características
  
- **Importância**: Internacionalização do capital
- **Uso Principal**: Análise de ADRs, estudos de internacionalização

#### Arquivos de Diversidade e Inclusão (Novos desde 2023)

#### `fre_cia_aberta_administrador_declaracao_genero_2026.csv`
- **Descrição**: Quantidade de membros dos órgãos de administração por declaração de gênero (item 7.1D do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Quantidade de homens
  - Quantidade de mulheres
  - Quantidade de outros gêneros
  - Percentuais
  
- **Importância**: Diversidade de gênero na gestão
- **Uso Principal**: Estudos de diversidade, ESG, governança

#### `fre_cia_aberta_administrador_declaracao_raca_2026.csv`
- **Descrição**: Quantidade de membros por declaração de cor e raça (item 7.1D do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Distribuição por cor/raça
  - Percentuais
  
- **Importância**: Diversidade racial na gestão
- **Uso Principal**: Estudos de diversidade, ESG, responsabilidade social

#### `fre_cia_aberta_administrador_PCD_2026.csv`
- **Descrição**: Quantidade de membros - Pessoas com Deficiência (item 7.1D do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Quantidade de PCDs
  - Tipo de deficiência
  
- **Importância**: Inclusão de PCDs na gestão
- **Uso Principal**: Estudos de inclusão, ESG

#### Arquivos de Recursos Humanos

#### `fre_cia_aberta_empregado_posicao_declaracao_genero_2026.csv`
- **Descrição**: Quantidade de empregados por declaração de gênero e posição (item 10.1A do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Gênero por nível hierárquico
  - Quantidade e percentuais
  
- **Importância**: Diversidade de gênero em toda a organização
- **Uso Principal**: Estudos de diversidade, ESG

#### `fre_cia_aberta_empregado_posicao_declaracao_raca_2026.csv`
- **Descrição**: Quantidade de empregados por cor/raça e posição (item 10.1A do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Cor/raça por nível hierárquico
  - Quantidade e percentuais
  
- **Importância**: Diversidade racial em toda a organização
- **Uso Principal**: Estudos de diversidade, ESG

#### `fre_cia_aberta_empregado_posicao_faixa_etaria_2026.csv`
- **Descrição**: Quantidade de empregados por posição e faixa etária (item 10.1A do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Faixas etárias por nível hierárquico
  - Quantidade e percentuais
  
- **Importância**: Diversidade etária e pirâmide organizacional
- **Uso Principal**: Estudos de diversidade, planejamento de sucessão

#### `fre_cia_aberta_empregado_posicao_local_2026.csv`
- **Descrição**: Quantidade de empregados por posição e localização geográfica (item 10.1A do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Localização geográfica por nível
  - Quantidade de empregados
  
- **Importância**: Distribuição geográfica da força de trabalho
- **Uso Principal**: Análise operacional, estudos de expansão

#### `fre_cia_aberta_empregado_local_declaracao_genero_2026.csv`
- **Descrição**: Quantidade de empregados por localização geográfica e gênero (item 10.1A do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Gênero por localização
  - Quantidade e percentuais
  
- **Importância**: Diversidade regional
- **Uso Principal**: Estudos de diversidade, análise regional

#### `fre_cia_aberta_empregado_local_declaracao_raca_2026.csv`
- **Descrição**: Quantidade de empregados por localização geográfica e cor/raça (item 10.1A do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Cor/raça por localização
  - Quantidade e percentuais
  
- **Importância**: Diversidade racial regional
- **Uso Principal**: Estudos de diversidade, análise regional

#### `fre_cia_aberta_empregado_local_faixa_etaria_2026.csv`
- **Descrição**: Quantidade de empregados por localização geográfica e faixa etária (item 10.1A do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Faixa etária por localização
  - Quantidade e percentuais
  
- **Importância**: Perfil etário regional
- **Uso Principal**: Análise demográfica, planejamento

#### `fre_cia_aberta_empregado_PCD_2026.csv`
- **Descrição**: Quantidade de empregados - Pessoas com Deficiência (item 10.1A do Anexo C da Resolução CVM 80/22) [[39]]
- **Dados Contidos**:
  - Quantidade de PCDs
  - Tipo de deficiência
  - Nível hierárquico
  
- **Importância**: Inclusão de PCDs
- **Uso Principal**: Estudos de inclusão, compliance com Lei de Cotas

#### `fre_cia_aberta_informacao_financeira_2026.csv`
- **Descrição**: Resumo das informações financeiras históricas selecionadas
- **Dados Contidos**:
  - Dados de ativo total, patrimônio líquido, receita líquida e resultado líquido históricos apresentados no FRE
  - Indicadores financeiros selecionados
  
- **Importância**: Visão histórica compacta dentro do Formulário de Referência
- **Uso Principal**: Análise de tendências financeiras multianuais

#### `fre_cia_aberta_endividamento_2026.csv`
- **Descrição**: Detalhamento do endividamento e fontes de financiamento
- **Dados Contidos**:
  - Divisão de dívidas por vencimento (curto e longo prazo)
  - Segregação por indexador (juros fixos, flutuantes, câmbio, etc.)
  - Garantias prestadas
  
- **Importância**: Diagnóstico de risco de crédito e estrutura de capital
- **Uso Principal**: Análise de liquidez e solvência

#### `fre_cia_aberta_fatores_risco_2026.csv`
- **Descrição**: Fatores de risco reportados pela companhia
- **Dados Contidos**:
  - Fatores de risco classificados por categoria (mercado, operacional, regulatório, financeiro, etc.)
  - Grau de relevância atribuído pela companhia
  
- **Importância**: Análise qualitativa de riscos operacionais e corporativos
- **Uso Principal**: Avaliação de risco, due diligence

---

## 6. ITR - Informações Trimestrais

### Visão Geral
O **Formulário de Informações Trimestrais (ITR)** é um documento eletrônico de encaminhamento periódico previsto no artigo 22, inciso V, da Resolução CVM nº 80/22 [[49]]. Contém as informações contábeis trimestrais das companhias abertas.

### Base Legal
- Resolução CVM nº 80/22, artigo 22, inciso V
- Artigos 27 a 29 da Resolução CVM 80/22

### Finalidade
Divulgar informações contábeis trimestrais, permitindo acompanhamento da performance financeira das companhias ao longo do ano [[51]].

### Frequência de Atualização
- **Periodicidade**: Semanal (com eventuais reapresentações) [[49]]
- **Histórico**: Dados disponíveis desde 2011 [[49]]

### Arquivos Disponíveis (2026)

#### `itr_cia_aberta_2026.csv`
- **Descrição**: Arquivo índice com metadados dos ITRs
- **Dados Contidos**:
  - Código CVM, CNPJ, nome da companhia
  - Data de referência (trimestre)
  - Data de entrega
  - Versão
  - Link para download
  
- **Importância**: Ponto de entrada para acessar ITRs
- **Uso Principal**: Identificação de ITRs disponíveis

#### Arquivos de Demonstrações Financeiras

**Nota**: As demonstrações financeiras estão disponíveis em duas versões:
- **con**: Consolidadas (grupo econômico)
- **ind**: Individuais (companhia individual)

#### `itr_cia_aberta_BPA_con_2026.csv` e `itr_cia_aberta_BPA_ind_2026.csv`
- **Descrição**: Balanço Patrimonial do Ativo (Consolidado e Individual)
- **Dados Contidos**:
  - Código da conta
  - Descrição da conta
  - Valor no período atual
  - Valor no período anterior
  - Contas fixas e não fixas
  
- **Importância**: Posição patrimonial da companhia
- **Uso Principal**: Análise financeira, valuation, estudos de solvência

#### `itr_cia_aberta_BPP_con_2026.csv` e `itr_cia_aberta_BPP_ind_2026.csv`
- **Descrição**: Balanço Patrimonial do Passivo (Consolidado e Individual)
- **Dados Contidos**:
  - Passivo circulante e não circulante
  - Patrimônio líquido
  - Contas detalhadas
  
- **Importância**: Estrutura de passivos e capital próprio
- **Uso Principal**: Análise de endividamento, estrutura de capital

#### `itr_cia_aberta_DRE_con_2026.csv` e `itr_cia_aberta_DRE_ind_2026.csv`
- **Descrição**: Demonstração do Resultado do Exercício (Consolidada e Individual)
- **Dados Contidos**:
  - Receita operacional
  - Custos e despesas
  - Lucro bruto, operacional e líquido
  - Linhas detalhadas de resultado
  
- **Importância**: Performance operacional e rentabilidade
- **Uso Principal**: Análise de rentabilidade, projeções, valuation

#### `itr_cia_aberta_DFC_MD_con_2026.csv` e `itr_cia_aberta_DFC_MD_ind_2026.csv`
- **Descrição**: Demonstração de Fluxos de Caixa - Método Direto (Consolidada e Individual)
- **Dados Contidos**:
  - Fluxos de caixa operacionais
  - Fluxos de investimento
  - Fluxos de financiamento
  - Entradas e saídas detalhadas
  
- **Importância**: Geração e uso de caixa
- **Uso Principal**: Análise de liquidez, geração de caixa

#### `itr_cia_aberta_DFC_MI_con_2026.csv` e `itr_cia_aberta_DFC_MI_ind_2026.csv`
- **Descrição**: Demonstração de Fluxos de Caixa - Método Indireto (Consolidada e Individual)
- **Dados Contidos**:
  - Lucro líquido como ponto de partida
  - Ajustes
  - Variação de ativos e passivos
  
- **Importância**: Reconciliação do lucro com geração de caixa
- **Uso Principal**: Análise de qualidade do lucro

#### `itr_cia_aberta_DMPL_con_2026.csv` e `itr_cia_aberta_DMPL_ind_2026.csv`
- **Descrição**: Demonstração das Mutações do Patrimônio Líquido (Consolidada e Individual)
- **Dados Contidos**:
  - Saldo inicial
  - Aumentos e reduções
  - Lucro do período
  - Dividendos
  - Saldo final
  
- **Importância**: Evolução do patrimônio líquido
- **Uso Principal**: Análise de criação de valor, distribuição de dividendos

#### `itr_cia_aberta_DRA_con_2026.csv` e `itr_cia_aberta_DRA_ind_2026.csv`
- **Descrição**: Demonstração de Resultado Abrangente (Consolidada e Individual)
- **Dados Contidos**:
  - Resultado do exercício
  - Outros resultados abrangentes
  - Resultado abrangente total
  
- **Importância**: Visão completa de resultados
- **Uso Principal**: Análise completa de performance

#### `itr_cia_aberta_DVA_con_2026.csv` e `itr_cia_aberta_DVA_ind_2026.csv`
- **Descrição**: Demonstração de Valor Adicionado (Consolidada e Individual)
- **Dados Contidos**:
  - Receita
  - Insumos
  - Valor adicionado
  - Distribuição (empregados, governo, acionistas)
  
- **Importância**: Contribuição da empresa para a sociedade
- **Uso Principal**: Análise de responsabilidade social, estudos econômicos

#### `itr_cia_aberta_composicao_capital_2026.csv`
- **Descrição**: Composição do capital social
- **Dados Contidos**:
  - Capital subscrito e realizado
  - Quantidade de ações por tipo
  - Alterações no período
  
- **Importância**: Estrutura de capital
- **Uso Principal**: Análise de capital, diluição

#### `itr_cia_aberta_parecer_2026.csv`
- **Descrição**: Pareceres e declarações dos auditores
- **Dados Contidos**:
  - Texto do parecer do auditor
  - Opinião (sem ressalvas, com ressalvas, etc.)
  - Data do parecer
  - Nome do auditor
  
- **Importância**: Qualidade e confiabilidade das informações
- **Uso Principal**: Análise de qualidade contábil, auditoria

### Regras de Negócio e Ingestão de Dados (ITR)

> [!IMPORTANT]
> **Deduplicação de Versões (Max Version):**
> A CVM permite o reenvio de demonstrações financeiras (ITR) corrigidas pelas companhias. O arquivo de dados conterá múltiplas versões para o mesmo período. Para evitar duplicidades e contabilidade incorreta, o pipeline de dados deve agrupar os registros por `CD_CVM` (ou `CNPJ_CIA`) e `DT_REFER`, mantendo apenas a linha com o maior valor na coluna `VERSAO`.

> [!NOTE]
> **Hierarquia das Contas Contábeis (`CD_CONTA`):**
> A estrutura de contas segue uma árvore de plano de contas rígida e padronizada pela CVM:
> *   `1` - Ativo Total
>     *   `1.01` - Ativo Circulante
>         *   `1.01.01` - Caixa e Equivalentes de Caixa
> *   `2` - Passivo Total (Passivo + PL)
>     *   `2.01` - Passivo Circulante
>     *   `2.03` - Patrimônio Líquido
> *   `3` - Demonstração do Resultado (DRE)
>     *   `3.01` - Receita de Venda de Bens e/ou Serviços
>     *   `3.11` - Lucro/Prejuízo Líquido do Período

> [!TIP]
> **Consolidado vs. Individual:**
> Priorizar sempre a base consolidada (`con`) para a análise fundamentalista ou de valuation de holdings, pois reflete a soma total das operações do grupo. A base individual (`ind`) exibe somente os números contábeis da holding-mãe.

---

## 7. DFP - Demonstrações Financeiras Padronizadas (Anuais)

### Visão Geral
O **Formulário de Demonstrações Financeiras Padronizadas (DFP)** é um documento eletrônico de encaminhamento periódico previsto no artigo 22, inciso IV, da Resolução CVM nº 80/22 [[61]]. Contém as demonstrações financeiras anuais completas das companhias.

### Base Legal
- Resolução CVM nº 80/22, artigo 22, inciso IV
- Artigos 27 a 29 da Resolução CVM 80/22

### Finalidade
Divulgar as demonstrações financeiras anuais auditadas, fornecendo a visão completa e auditada da situação financeira e performance das companhias [[62]].

### Frequência de Atualização
- **Periodicidade**: Semanal (com eventuais reapresentações) [[61]]
- **Histórico**: Dados disponíveis desde 2010 [[61]]

### Arquivos Disponíveis (2026)

#### `dfp_cia_aberta_2026.csv`
- **Descrição**: Arquivo índice com metadados dos DFPs
- **Dados Contidos**:
  - Código CVM, CNPJ, nome da companhia
  - Data de referência (exercício social)
  - Data de entrega
  - Versão
  - Link para download
  
- **Importância**: Ponto de entrada para acessar DFPs
- **Uso Principal**: Identificação de DFPs disponíveis

#### Arquivos de Demonstrações Financeiras Anuais

**Nota**: Assim como no ITR, as demonstrações estão disponíveis em versões consolidadas (con) e individuais (ind).

#### `dfp_cia_aberta_BPA_con_2026.csv` e `dfp_cia_aberta_BPA_ind_2026.csv`
- **Descrição**: Balanço Patrimonial do Ativo Anual (Consolidado e Individual)
- **Dados Contidos**:
  - Ativo circulante e não circulante
  - Contas detalhadas de ativos
  - Valores auditados
  
- **Importância**: Posição patrimonial anual auditada
- **Uso Principal**: Análise financeira anual, valuation

#### `dfp_cia_aberta_BPP_con_2026.csv` e `dfp_cia_aberta_BPP_ind_2026.csv`
- **Descrição**: Balanço Patrimonial do Passivo Anual (Consolidado e Individual)
- **Dados Contidos**:
  - Passivo circulante e não circulante
  - Patrimônio líquido
  - Contas detalhadas
  
- **Importância**: Estrutura de passivos anual auditada
- **Uso Principal**: Análise de solvência, estrutura de capital

#### `dfp_cia_aberta_DRE_con_2026.csv` e `dfp_cia_aberta_DRE_ind_2026.csv`
- **Descrição**: Demonstração do Resultado do Exercício Anual (Consolidada e Individual)
- **Dados Contidos**:
  - Resultado anual completo
  - Todas as linhas de resultado
  - Valores auditados
  
- **Importância**: Performance anual auditada
- **Uso Principal**: Análise de rentabilidade anual, projeções

#### `dfp_cia_aberta_DFC_MI_con_2026.csv` e `dfp_cia_aberta_DFC_MI_ind_2026.csv`
- **Descrição**: Demonstração de Fluxos de Caixa - Método Indireto Anual (Consolidada e Individual)
- **Dados Contidos**:
  - Fluxos de caixa anuais
  - Reconciliação completa
  
- **Importância**: Geração de caixa anual
- **Uso Principal**: Análise de geração de caixa, valuation

#### `dfp_cia_aberta_DMPL_con_2026.csv` e `dfp_cia_aberta_DMPL_ind_2026.csv`
- **Descrição**: Demonstração das Mutações do Patrimônio Líquido Anual (Consolidada e Individual)
- **Dados Contidos**:
  - Evolução anual do PL
  - Todos os movimentos
  
- **Importância**: Criação de valor anual
- **Uso Principal**: Análise de criação de valor

#### `dfp_cia_aberta_DRA_con_2026.csv` e `dfp_cia_aberta_DRA_ind_2026.csv`
- **Descrição**: Demonstração de Resultado Abrangente Anual (Consolidada e Individual)
- **Dados Contidos**:
  - Resultado abrangente anual
  
- **Importância**: Visão completa de resultados anuais
- **Uso Principal**: Análise completa de performance anual

#### `dfp_cia_aberta_DVA_con_2026.csv` e `dfp_cia_aberta_DVA_ind_2026.csv`
- **Descrição**: Demonstração de Valor Adicionado Anual (Consolidada e Individual)
- **Dados Contidos**:
  - Valor adicionado anual
  - Distribuição completa
  
- **Importância**: Contribuição econômica anual
- **Uso Principal**: Análise econômica, ESG

#### `dfp_cia_aberta_composicao_capital_2026.csv`
- **Descrição**: Composição do capital social anual
- **Dados Contidos**:
  - Capital social no encerramento do exercício
  - Alterações durante o ano
  
- **Importância**: Estrutura de capital anual
- **Uso Principal**: Análise de capital

#### `dfp_cia_aberta_parecer_2026.csv`
- **Descrição**: Pareceres dos auditores independentes anuais
- **Dados Contidos**:
  - Opinião do auditor sobre as demonstrações anuais
  - Texto completo do parecer
  - Ressalvas, ênfases
  
- **Importância**: Confiabilidade das informações anuais
- **Uso Principal**: Análise de qualidade contábil, auditoria

### Regras de Negócio e Ingestão de Dados (DFP)

> [!IMPORTANT]
> **Deduplicação de Versões (Max Version):**
> Assim como no ITR, no DFP anual deve ser aplicada a regra de seleção da versão mais recente (maior valor na coluna `VERSAO`) agrupado por `CD_CVM` e `DT_REFER` para garantir que demonstrações auditadas reapresentadas sobrescrevam os envios originais incorretos.

> [!NOTE]
> **Escala da Moeda:**
> Valores nos arquivos contábeis anuais do DFP estão sujeitos à escala informada na coluna `ESCALA_MOEDA`. Na maioria das companhias abertas brasileiras, a escala é "MIL", significando que os valores contábeis expressos nas tabelas devem ser multiplicados por 1.000 para refletirem o valor monetário real.

> [!NOTE]
> **Semântica de API e correção operacional:**
> Nos endpoints financeiros do projeto, `valor_conta` deve representar o montante monetário absoluto após aplicação da `ESCALA_MOEDA`, enquanto o valor bruto reportado pela CVM permanece disponível separadamente como referência de auditoria. Registros DFP/ITR ingeridos antes da correção do parser de decimais precisam ser reparados por replay/ressincronização a partir dos payloads brutos retidos.

---

## 8. Cadastro - Cadastro Geral de Companhias

### Visão Geral
O conjunto de dados de **Cadastro** contém informações cadastrais básicas das companhias abertas registradas na CVM, incluindo dados de identificação, situação do registro e informações de contato [[67]].

### Base Legal
- Resolução CVM nº 80/22
- Normas de registro de companhias abertas

### Finalidade
Fornecer o cadastro oficial de todas as companhias abertas registradas na CVM, servindo como base para todos os demais conjuntos de dados [[67]].

### Frequência de Atualização
- **Periodicidade**: Diária [[67]]
- **Referência**: Dados referentes ao último dia útil [[67]]

### Arquivos Disponíveis

#### `cad_cia_aberta.csv`

- **Dados Contidos** [[88]]:
  - **CNPJ_CIA**: CNPJ da companhia (chave universal)
  - **CD_CVM**: Código identificador mestre da CVM
  - **DENOM_SOCIAL**: Razão social completa da companhia
  - **DENOM_COMERC**: Nome fantasia/comercial
  - **DT_REG**: Data de concessão do registro na CVM
  - **DT_CONST**: Data de constituição (fundação) da companhia
  - **SIT**: Situação cadastral atual (ex: ATIVO, CANCELADO, SUSPENSO)
  - **DT_CANCEL** e **MOTIVO_CANCEL**: Data e motivo de cancelamento do registro (se houver)
  - **CATEG_REG**: Categoria de registro corporativo (Categoria A ou B)
  - **CONTROLE_ACI**: Controle acionário (Nacional, Estrangeiro, etc.)
  - **CNAE_FISCAL**: Código CNAE fiscal principal
  - **CNAE_SUBCLASS**: Subclasse CNAE
  - **TIPO_MERCADO**: Mercado de listagem (Novo Mercado, Nível 1, Nível 2, Tradicional, Bovespa Mais, etc.)
  - **DT_INI_MERCADO**: Data de início no mercado
  - **CNPJ_AUDITOR** e **NOME_AUDITOR**: Dados do auditor independente ativo
  - **CNAE_PRINCIPAL**: Descrição do CNAE principal
  - **PAIS_CUSTODIA**: País de custódia dos valores mobiliários
  - **PAIS_NEGOCIACAO**: País onde há negociação
  - **BOLSA_NEGOCIACAO**: Bolsa onde há negociação
  
- **Importância**: Base de referência para todos os demais conjuntos de dados da CVM; essencial para qualquer análise que envolva identificação de companhias abertas

### Regras de Negócio e Ingestão de Dados (Cadastro)

> [!IMPORTANT]
> **Categoria A vs. Categoria B (`CATEG_REG`):**
> *   **Categoria A:** Autoriza a emissão de qualquer valor mobiliário, incluindo **ações** ordinárias e preferenciais negociadas em bolsa.
> *   **Categoria B:** Autoriza a emissão de valores mobiliários de renda fixa (como debêntures, notas comerciais ou notas promissórias), mas **não autoriza a emissão de ações**.
> *   *Regra de Ingestão:* Se o objetivo do pipeline for construir painéis de ações negociadas na bolsa de valores (B3), deve-se filtrar apenas os registros onde `CATEG_REG == 'A'`.

> [!NOTE]
> **Situação do Registro (`SIT`):**
> *   `ATIVO`: Companhia operacional obrigada a enviar informações periódicas.
> *   `CANCELADO`: Registro baixado devido a fechamento de capital, fusão, cisão ou falência.
> *   `SUSPENSO`: Registro inativo temporariamente devido ao atraso no cumprimento de obrigações regulatórias por mais de 12 meses.
- **Uso Principal**: 
  - Mapeamento completo do universo de companhias abertas no Brasil
  - Cruzamento de dados com outros conjuntos (FRE, DFP, ITR, etc.)
  - Análise setorial por CNAE
  - Monitoramento de status de registro (novas aberturas de capital, cancelamentos, mudanças de categoria)
  - Estudos de mercado de capitais brasileiro
  - Identificação de companhias por mercado de listagem (governança corporativa)

---

#### `cad_cia_estrang.csv`
- **Descrição**: Cadastro completo de companhias estrangeiras com valores mobiliários negociados no Brasil (ADR Level 2, Level 3, BDRs, etc.)
- **Dados Contidos** [[88]]:
  - **CD_CVM**: Código CVM da companhia estrangeira
  - **CNPJ_CIA**: CNPJ da filial ou representante no Brasil (se aplicável)
  - **DENOM_SOCIAL**: Denominação social original
  - **DENOM_COMERC**: Denominação comercial
  - **PAIS_ORIGEM**: País de origem da companhia
  - **DT_REG**: Data de registro na CVM
  - **SIT**: Situação do registro (ATIVO, CANCELADO, SUSPENSO)
  - **DT_CANCEL**: Data de cancelamento do registro
  - **MOTIVO_CANCEL**: Motivo do cancelamento
  - **CATEG_REG**: Categoria de registro (A, B, etc.)
  - **TIPO_MERCADO**: Mercado de listagem no Brasil
  - **DT_INI_MERCADO**: Data de início de negociação no Brasil
  - **CNAE_FISCAL**: Código CNAE (se aplicável)
  - **BOLSA_ORIGEM**: Bolsa de origem (NYSE, NASDAQ, LSE, etc.)
  - **BOLSA_NEGOCIACAO**: Bolsa onde há negociação no Brasil
  - **PAIS_NEGOCIACAO**: Países onde há negociação
  - **INSTRUMENTO**: Tipo de instrumento (ADR, BDR, etc.)
  - **PROGRAMA**: Tipo de programa (Patrocinado, Não Patrocinado)
  - **NOME_AUDITOR**: Nome do auditor independente
  - **CNPJ_AUDITOR**: CNPJ do auditor
  
- **Importância**: Permite analisar o universo de empresas estrangeiras com presença no mercado brasileiro de capitais; essencial para estudos de internacionalização e investimentos cross-border
- **Uso Principal**: 
  - Análise de ADRs e BDRs negociados no Brasil
  - Estudos de internacionalização de mercados
  - Monitoramento de companhias estrangeiras ativas no Brasil
  - Cruzamento com dados de negociação e preços
  - Due diligence de empresas estrangeiras com listagem brasileira
  - Análise de fluxos de capital internacional

---

## Resumo Comparativo dos Conjuntos de Dados

| Conjunto | Sigla | Periodicidade | Conteúdo Principal | Desde |
|----------|-------|---------------|-------------------|-------|
| Governança Corporativa | CGVN | Semanal | Práticas de governança ("pratique ou explique") | 2018 |
| Valores Mobiliários | VLMO | Semanal | Negociação e detenção de valores mobiliários | Últimos 5 anos |
| Informações Periódicas e Eventuais | IPE | Semanal | Documentos não estruturados (Fatos Relevantes, etc.) | 2003 |
| Formulário Cadastral | FCA | Semanal | Dados cadastrais completos da companhia | 2010 |
| Formulário de Referência | FRE | Semanal | Informações detalhadas (estrutura, governança, remuneração, etc.) | 2010 |
| Informações Trimestrais | ITR | Semanal | Demonstrações financeiras trimestrais | 2011 |
| Demonstrações Financeiras Padronizadas | DFP | Semanal | Demonstrações financeiras anuais | 2010 |
| Cadastro | CAD | Diária | Cadastro básico de companhias abertas | Contínuo |

---

## Considerações Gerais sobre Uso dos Dados

### Formatos e Estrutura
- Todos os arquivos são disponibilizados em formato **CSV** (Comma-Separated Values)
- Os arquivos ZIP contêm múltiplos CSV relacionados ao mesmo conjunto de dados
- A codificação padrão é **UTF-8**
- O separador de campo é geralmente o **ponto-e-vírgula (;)**

### Chaves de Ligação entre Arquivos
Os principais campos para cruzamento entre diferentes conjuntos de dados são:
- **CD_CVM**: Código CVM da companhia (chave primária)
- **CNPJ_CIA**: CNPJ da companhia
- **DT_REFER**: Data de referência do documento
- **VERSAO**: Versão do documento (para identificar reapresentações)

### Boas Práticas de Uso
1. **Sempre utilizar a última versão** dos documentos (filtrar pela maior `VERSAO` para cada `CD_CVM` e `DT_REFER`)
2. **Cruzar com o cadastro** (`cad_cia_aberta.csv`) para obter informações atualizadas sobre situação e denominação
3. **Considerar o exercício social** ao analisar DFPs (geralmente encerram em 31/12, mas algumas companhias têm exercícios atípicos)
4. **Atenção aos valores monetários**: verificar a escala (milhares, milhões) indicada nos arquivos
5. **Consolidado vs. Individual**: escolher a versão adequada conforme o objetivo da análise

### Aplicações Comuns
- **Análise Fundamentalista**: Uso combinado de DFP, ITR, FRE e FCA
- **Estudos de Governança Corporativa**: Uso de FRE, CGVN e FCA
- **Análise ESG**: Uso de FRE (dados de diversidade), IPE (relatórios de sustentabilidade)
- **Monitoramento de Mercado**: Uso de IPE (fatos relevantes), VLMO (negociação)
- **Pesquisa Acadêmica**: Uso de todos os conjuntos para estudos empíricos
- **Jornalismo Financeiro**: Uso de IPE, DFP, ITR para reportagens
- **Compliance e Due Diligence**: Uso de FCA, FRE, CAD

---
## Como funciona a atualização dos arquivos CVM

### 1. O mecanismo de reapresentação

Quando uma companhia detecta um erro ou precisa corrigir um formulário já entregue, ela envia uma **reapresentação** via Sistema Empresas.NET. Cada envio recebe um número de versão sequencial: a entrega original é a versão `1`, a primeira correção é `2`, a segunda é `3`, e assim por diante.

O campo **`VERSAO`** presente em todos os CSVs de companhias (DFP, ITR, FRE, FCA, CGVN etc.) é exatamente esse número. Ele é a chave para identificar reapresentações. A chave primária lógica de qualquer registro nesses arquivos é sempre a combinação:

```
CNPJ_CIA + DT_REFER + VERSAO
```

---

### 2. Como a CVM atualiza os arquivos CSV

Este é o ponto mais importante: **a CVM não usa append nem atualização parcial — ela regera o arquivo CSV inteiro do ano e o substitui completamente.** Quando qualquer empresa envia uma reapresentação, o ZIP/CSV do ano correspondente é reprocessado e sobrescrito no servidor.

O comportamento concreto é:

- **O arquivo anual (ex: `dfp_cia_aberta_2025.zip`) é substituído por completo** toda semana.
- O novo arquivo contém **todas as versões de todos os formulários** entregues até aquele momento — incluindo tanto a versão original quanto as reapresentações de cada empresa. Não há remoção das versões antigas: o CSV acumula **todas as versões**, e cabe ao consumidor filtrar pela mais recente.
- Por isso, para obter os dados mais atuais de uma empresa, você deve **filtrar pelo maior valor de `VERSAO`** para cada combinação `CNPJ_CIA + DT_REFER`.

**Exemplo prático:** Se a Petrobras enviou o DFP 2024 três vezes (original + 2 correções), o arquivo `dfp_cia_aberta_2024.zip` terá três blocos de linhas para a Petrobras, com `VERSAO = 1`, `2` e `3`. A versão correta a usar é a `3`.

---

### 3. Cadência de atualização por conjunto

A atualização dos arquivos mais recentes ocorre de terça a sábado, às 08h, com os dados recebidos até as 23h59 do dia anterior. Arquivos de períodos mais antigos são atualizados semanalmente, toda segunda-feira às 08h.

Para os conjuntos de companhias abertas especificamente:

| Conjunto | Cadência |
|---|---|
| CAD (Cadastro) | Diária |
| DFP, ITR, FRE, FCA, CGVN, VLMO | Semanal (ano corrente e A-1) |
| IPE | Semanal (ano corrente e A-1) |
| Anos mais antigos (A-2 em diante) | Semanal, mas menos prioritário |

---

### 4. Como saber quando houve alterações

Há três formas, do mais simples ao mais robusto:

**a) Página de Novidades do portal**

Todas as mudanças estruturais no Portal de Dados Abertos — novos campos, novos arquivos, descontinuações — são sempre comunicadas por meio da página Novidades do Portal.

URL: `https://dados.cvm.gov.br/pages/novidades`

Útil para mudanças de esquema (colunas novas, arquivos renomeados etc.), mas não notifica reapresentações individuais de empresas.

**b) Comparar o `Last-Modified` ou tamanho do arquivo via HTTP**

O servidor da CVM retorna o header `Last-Modified` em requisições HTTP. Você pode fazer um `HEAD` request no arquivo ZIP antes de baixá-lo e comparar com o valor anterior. Se mudou, há dados novos.

```python
import requests

url = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip"
r = requests.head(url)
print(r.headers.get("Last-Modified"))
# Ex: Mon, 09 Jun 2026 08:03:41 GMT
```

**c) Comparar o campo `DT_ENTREGA` dentro do CSV**

Dentro de qualquer arquivo de índice (ex: `dfp_cia_aberta_2026.csv`), o campo **`DT_ENTREGA`** registra a data e hora exata em que cada formulário foi entregue à CVM. Ao baixar o arquivo semanalmente e comparar com a versão anterior, qualquer linha com `DT_ENTREGA` nova indica uma entrega ou reapresentação ocorrida naquela semana.

---

### 5. Estratégia recomendada para manter uma base atualizada

```
1. Toda segunda-feira, faça HEAD no ZIP de interesse
2. Se Last-Modified mudou → baixe o arquivo
3. Carregue o CSV e filtre: para cada (CNPJ_CIA, DT_REFER), 
   mantenha somente o registro com MAX(VERSAO)
4. Faça um UPSERT na sua base local usando 
   (CNPJ_CIA, DT_REFER) como chave de negócio
```

Assim você sempre tem a versão mais recente de cada empresa sem duplicar dados nem reprocessar o histórico inteiro.

---

## Fontes e Referências

Os dados são disponibilizados oficialmente pelo Portal de Dados Abertos da CVM em:
- **URL principal**: https://dados.cvm.gov.br/
- **Documentação técnica**: Cada conjunto possui um arquivo de dicionário de dados (geralmente em formato TXT ou PDF) dentro do próprio pacote ZIP
- **Layouts e dicionários**: Disponíveis em https://www.gov.br/cvm/pt-br/assuntos/intermediarios/leiaute-dos-arquivos-xml-e-csv

Para dúvidas específicas sobre os dados, a CVM disponibiliza canais de atendimento através do portal Gov.br.

---



*Documento elaborado com base nas informações públicas disponíveis no Portal de Dados Abertos da CVM, atualizado para o ano de 2026.*
