# CVM


## 1. O que é a CVM

A Comissão de Valores Mobiliários (CVM) é o regulador do mercado de capitais brasileiro. No contexto de companhias abertas, a CVM exige que emissores divulguem informações cadastrais, financeiras, societárias e de governança de forma padronizada.

Esses dados existem por razões regulatórias e econômicas:

- reduzir assimetria de informação entre companhia, investidor, analista, auditor e mercado;
- permitir supervisão regulatória e enforcement;
- viabilizar comparabilidade entre emissores;
- preservar histórico de versões, reapresentações e mudanças relevantes;
- dar transparência para decisões de investimento, crédito, compliance e governança.

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

## 3. Fontes oficiais da CVM usadas

Quatro grupos principais de dados:

- cadastro de companhias abertas;
- DFP;
- ITR;
- FRE.

## 4. Visão geral das fontes

| Fonte | O que é | Periodicidade oficial | Papel no sistema |
| --- | --- | --- | --- |
| Cadastro | Informação cadastral do emissor | Diária | Entidade raiz do domínio |
| DFP | Demonstrações Financeiras Padronizadas | Semanal | Base anual de demonstrações financeiras |
| ITR | Informações Trimestrais | Semanal | Base trimestral de demonstrações financeiras |
| FRE | Formulário de Referência | Semanal | Base de governança, capital, auditoria, remuneração e RH |

## 5. Cadastro de companhias abertas

### 5.1 O que é

O cadastro de companhias abertas é a base mestra de identificação do emissor. É a fonte que informa quem é a companhia, qual o seu CNPJ, qual o código CVM, qual a situação do registro e diversos atributos cadastrais e administrativos.

Sem essa base, os documentos financeiros e societários ficam soltos. Ela é o ponto de ancoragem do domínio.

### 5.2 Por que existe

Do ponto de vista regulatório, a CVM precisa manter um cadastro atualizado dos emissores regulados. Do ponto de vista de negócio, esse cadastro resolve o problema de identidade: ele permite ligar documentos, eventos e demonstrações à entidade econômica correta.

### 5.3 Fontes oficiais

- Página do conjunto: `https://dados.cvm.gov.br/dataset/cia_aberta-cad`
- Arquivo de dados: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv`
- Metadados/dicionário: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/META/meta_cad_cia_aberta.txt`

### 5.4 Frequência de atualização

- Periodicidade oficial do conjunto: diária.
- O conjunto disponibiliza as informações cadastrais referentes ao último dia útil.

### 5.5 O que normalmente aparece nesse dado

Os campos cadastrais usados por este projeto representam:

- identificação do emissor: CNPJ, código CVM, razão social, nome comercial;
- status regulatório: situação do registro, categoria, situação do emissor;
- datas relevantes: registro, constituição, cancelamento, início de categoria;
- classificação: setor de atividade, tipo de mercado, controle acionário;
- dados de contato e estrutura administrativa;
- auditor cadastral.

### 5.6 Por que ele é a entidade raiz

Todos os documentos financeiros e societários precisam ser ligados a uma companhia. No projeto, isso é feito principalmente por:

- `cnpj_companhia`;
- `codigo_cvm`.

Sem esse vínculo, os dados financeiros perdem valor operacional, porque deixam de ser consultáveis por emissor.

## 6. DFP — Demonstrações Financeiras Padronizadas

### 6.1 O que é

O DFP é o formulário periódico anual de demonstrações financeiras padronizadas. Ele existe para padronizar a prestação anual de informações contábeis pelos emissores.

No portal da CVM, o conjunto informa que o DFP é um documento eletrônico de encaminhamento periódico previsto no art. 22, inciso IV, da Resolução CVM nº 80/22.

### 6.2 Por que existe

O DFP existe para que o mercado compare demonstrações financeiras anuais de empresas diferentes com uma estrutura regulatória comum. Isso é fundamental para:

- análise fundamentalista;
- acompanhamento de resultados anuais;
- comparação setorial;
- reconciliação contábil;
- auditoria e fiscalização.

### 6.3 Fontes oficiais

- Página do conjunto: `https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp`
- Diretório de dados: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/`
- Metadados/dicionário: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/META/meta_dfp_cia_aberta_txt.zip`

### 6.4 Frequência de atualização

- Periodicidade oficial do conjunto: semanal.
- O próprio conjunto informa que os arquivos são atualizados semanalmente com eventuais reapresentações.

### 6.5 O que o conjunto contém

O DFP disponibiliza, entre outros grupos:

- BPA — Balanço Patrimonial Ativo;
- BPP — Balanço Patrimonial Passivo;
- DFC-MD — Demonstração de Fluxo de Caixa, método direto;
- DFC-MI — Demonstração de Fluxo de Caixa, método indireto;
- DMPL — Demonstração das Mutações do Patrimônio Líquido;
- DRA — Demonstração do Resultado Abrangente;
- DRE — Demonstração do Resultado;
- DVA — Demonstração do Valor Adicionado;
- pareceres e declarações;
- dados da empresa e composição do capital;
- links para os formulários entregues.

### 6.6 Valor de negócio

O DFP é a visão anual padronizada da saúde financeira do emissor. Ele suporta:

- comparação entre exercícios;
- cálculo de séries históricas anuais;
- monitoramento de reapresentações;
- construção de indicadores contábeis;
- validações de consistência entre contas e documentos.

## 7. ITR — Informações Trimestrais

### 7.1 O que é

O ITR é o formulário trimestral de informações contábeis. No portal da CVM, ele é descrito como documento eletrônico de encaminhamento periódico previsto no art. 22, inciso V, da Resolução CVM nº 80/22.

### 7.2 Por que existe

Do ponto de vista de mercado, o ITR existe para dar mais frequência informacional. Ele reduz o intervalo entre divulgações anuais e permite acompanhar a evolução da companhia dentro do exercício social.

### 7.3 Fontes oficiais

- Página do conjunto: `https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr`
- Diretório de dados: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/`
- Metadados/dicionário: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/META/meta_itr_cia_aberta_txt.zip`

### 7.4 Frequência de atualização

- Periodicidade oficial do conjunto: semanal.
- A página do conjunto informa atualização semanal com eventuais reapresentações.

### 7.5 O que o conjunto contém

O ITR contém grupos muito parecidos com o DFP, mas voltados ao acompanhamento trimestral:

- BPA;
- BPP;
- DFC-MD;
- DFC-MI;
- DMPL;
- DRA;
- DRE;
- DVA;
- pareceres e declarações;
- dados da empresa e composição do capital;
- links para formulários.

### 7.6 Valor de negócio

O ITR é a base para:

- análise intranual;
- monitoramento de resultados trimestrais;
- detecção mais rápida de deterioração ou melhora operacional;
- comparação entre trimestres e entre companhias;
- apoio a modelos quantitativos e gatilhos operacionais.

## 8. FRE — Formulário de Referência

### 8.1 O que é

O FRE é o formulário que consolida informações amplas sobre o emissor. Segundo a CVM, ele é um documento eletrônico de encaminhamento periódico e eventual previsto no art. 22, inciso II, da Resolução CVM nº 80/22.

### 8.2 Por que existe

O FRE existe porque o mercado não vive só de demonstração financeira. Para entender um emissor, também é necessário conhecer:

- atividades da empresa;
- fatores de risco;
- estrutura de capital;
- administração;
- auditoria;
- remuneração;
- recursos humanos;
- relações com partes relacionadas;
- valores mobiliários emitidos.

Ele é o formulário mais rico em termos de contexto corporativo.

### 8.3 Fontes oficiais

- Página do conjunto: `https://dados.cvm.gov.br/dataset/cia_aberta-doc-fre`
- Diretório de dados: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/`
- Metadados/dicionário: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/META/meta_fre_cia_aberta.zip`

### 8.4 Frequência de atualização

- Periodicidade oficial do conjunto: semanal.
- A página do conjunto informa atualização semanal com eventuais reapresentações.

### 8.5 O que o conjunto contém

O FRE cobre um universo muito mais amplo do que DFP e ITR. O conjunto inclui:

- documento principal;
- auditores;
- capital social;
- posição acionária;
- remuneração;
- recursos humanos;
- vários outros subarquivos temáticos do formulário.

O próprio conjunto destaca arquivos adicionais aplicáveis à versão mais nova do formulário, em especial a partir de 2023, como dados de diversidade de gênero, raça/cor, PCD e partes de remuneração baseada em ações.

### 8.6 Valor de negócio

O FRE é crucial para:

- due diligence de emissores;
- análise de governança;
- análise de concentração acionária;
- acompanhamento de remuneração de administradores;
- monitoramento de mudanças societárias e de auditoria;
- criação de perfis corporativos ricos para plataformas financeiras.

## 9. Caminhos oficiais dos dados

Esta seção resume os caminhos mais úteis para desenvolvimento.

### 9.1 Cadastro

- Página: `https://dados.cvm.gov.br/dataset/cia_aberta-cad`
- Dados: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv`
- Meta: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/META/meta_cad_cia_aberta.txt`

### 9.2 DFP

- Página: `https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp`
- Diretório: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/`
- Meta: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/META/meta_dfp_cia_aberta_txt.zip`

### 9.3 ITR

- Página: `https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr`
- Diretório: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/`
- Meta: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/META/meta_itr_cia_aberta_txt.zip`

### 9.4 FRE

- Página: `https://dados.cvm.gov.br/dataset/cia_aberta-doc-fre`
- Diretório: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/`
- Meta: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/META/meta_fre_cia_aberta.zip`

## 10. Frequência de atualização das bases

| Base | Frequência | Observação prática |
| --- | --- | --- |
| Cadastro | Diária | Base de identidade do emissor |
| DFP | Semanal | Atualiza reapresentações e histórico recente |
| ITR | Semanal | Atualiza reapresentações trimestrais |
| FRE | Semanal | Atualiza reapresentações e versões do formulário |

Do ponto de vista de engenharia, isso significa que o sistema precisa:

- aceitar reprocessamento sem duplicar registros;
- identificar quando o conteúdo mudou de verdade;
- preservar histórico e versões;
- diferenciar “sincronizado novamente” de “alterado de fato”.

## 11. Como os dados da CVM entram no modelo interno

Este projeto não replica a CVM de forma literal. Ele cria um modelo interno orientado a consulta, auditoria e consistência.

A estratégia é:

1. baixar os arquivos oficiais;
2. normalizar nomes, tipos e chaves;
3. relacionar documentos à companhia correta;
4. persistir com rastreabilidade de origem;
5. registrar alterações reais de negócio;
6. expor tudo por API.

## 12. Fontes oficiais consultadas

- Cadastro de companhias abertas: `https://dados.cvm.gov.br/dataset/cia_aberta-cad`
- DFP: `https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp`
- ITR: `https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr`
- FRE: `https://dados.cvm.gov.br/dataset/cia_aberta-doc-fre`
- Repositório de arquivos da CVM: `https://dados.cvm.gov.br/dados/`

## 13. Observação final

Este documento descreve o domínio CVM usado por este projeto e o modelo interno da aplicação no estado atual do repositório. Para detalhes de implementação do produto, complementar com:

- `README.md`

