---
title: Formulário Cadastral (FCA)
sidebar_position: 6
---

# Formulário Cadastral (FCA)

## O que é FCA

FCA é o Formulário Cadastral das companhias abertas. Ele detalha informações institucionais que complementam o cadastro base, como dados gerais do formulário, endereços, Diretor de Relações com Investidores, auditores, valores mobiliários e canais operacionais ligados à companhia.

No Tucano CVM, o FCA é tratado como uma fonte anual de documentos cadastrais. Alguns membros do pacote são promovidos para tabelas consultáveis pela API; outros são processados na camada de staging conforme o suporte atual da ingestão.

## Por que esse conjunto existe

O cadastro base informa a identidade corrente da companhia. O FCA amplia esse contexto com dados declarados em formulários, preservando versão, data de referência e vínculo documental.

Essa separação é importante porque uma companhia pode ter registros cadastrais correntes e, ao mesmo tempo, histórico de formulários com versões e datas próprias.

## Metadados técnicos

| Campo | Valor |
|-------|-------|
| Fonte no sistema | `fca` |
| Distribuição CVM | ZIP anual |
| Arquivo principal | `fca_cia_aberta_{ano}.zip` |
| Primeiro ano no registro da fonte | 2010 |
| Dependência | `cadastro` |
| Tabelas promovidas | `fca_documentos`, `fca_geral`, `fca_enderecos`, `fca_dri`, `fca_auditores`, `fca_valores_mobiliarios`, `fca_departamentos_acionistas` |
| Chaves de referência | `cnpj_companhia`, `codigo_cvm`, `id_documento` |

## Arquivos do pacote anual

O pacote anual contém um cabeçalho documental e membros especializados por assunto. O suporte atual promove os principais conjuntos cadastrais e mantém outros membros na etapa de staging.

```text
fca_cia_aberta_{ano}.csv
fca_cia_aberta_geral_{ano}.csv
fca_cia_aberta_endereco_{ano}.csv
fca_cia_aberta_dri_{ano}.csv
fca_cia_aberta_auditor_{ano}.csv
fca_cia_aberta_valor_mobiliario_{ano}.csv
fca_cia_aberta_departamento_acionistas_{ano}.csv
fca_cia_aberta_escriturador_{ano}.csv
fca_cia_aberta_canal_divulgacao_{ano}.csv
fca_cia_aberta_pais_estrangeiro_negociacao_{ano}.csv
```

## Estrutura no Tucano CVM

| Dataset | Tabela ou camada | Conteúdo |
|---------|------------------|----------|
| Documento | `fca_documentos` | Cabeçalho do formulário, companhia, versão e data de referência. |
| Geral | `fca_geral` | Dados institucionais gerais declarados no formulário. |
| Endereços | `fca_enderecos` | Endereços e contatos informados pela companhia. |
| DRI | `fca_dri` | Diretor de Relações com Investidores e dados de contato. |
| Auditores | `fca_auditores` | Auditoria independente vinculada ao formulário cadastral. |
| Valores mobiliários | `fca_valores_mobiliarios` | Instrumentos declarados no formulário. |
| Departamento de acionistas | `fca_departamentos_acionistas` | Canais de atendimento a acionistas quando promovidos. |
| Escriturador, canal de divulgação e países de negociação | staging | Membros processados na ingestão, sem endpoint público dedicado nesta versão. |

## Endpoints principais

```bash
GET /fca/documentos?codigo_cvm=25224
GET /fca/geral?codigo_cvm=25224
GET /fca/enderecos?codigo_cvm=25224
GET /fca/dri?codigo_cvm=25224
GET /fca/auditores?codigo_cvm=25224
GET /fca/valores-mobiliarios?codigo_cvm=25224
GET /fca/departamento-acionistas?codigo_cvm=25224
```

## Relação com o cadastro e com o FRE

O cadastro base responde pela identidade corrente da companhia. O FCA descreve informações cadastrais dentro de documentos formais, com data, versão e vínculo ao formulário. Já o FRE cobre um conjunto mais amplo de informações societárias, administração, remuneração, capital, valores mobiliários e governança.

| Aspecto | Cadastro | FCA | FRE |
|---------|----------|-----|-----|
| Papel | Identidade corrente | Formulário cadastral | Formulário de referência |
| Temporalidade | Retrato corrente | Documento anual ou eventual | Documento anual ou eventual |
| Ênfase | Código CVM, CNPJ e situação | Dados institucionais e contatos | Estrutura societária, administração, capital e temas relacionados |
| Chave prática | Companhia | Documento cadastral | Documento de referência |

## Como a ingestão trata a fonte

O arquivo principal do FCA é processado primeiro para ancorar o documento. Os membros filhos são vinculados por companhia e documento, preservando arquivo, linha, ano e hash de origem.

Como nem todos os membros do pacote possuem endpoint público nesta versão, a documentação separa os conjuntos promovidos dos conjuntos tratados em staging. Isso evita sugerir consultas que a API não expõe diretamente.

## Como ler os dados

Use `fca_documentos` para localizar o formulário e sua versão antes de interpretar os quadros filhos. Para dados de contato, endereços e DRI, observe a data de referência do documento, pois ela pode não coincidir com a situação cadastral corrente da tabela `companhias`.
