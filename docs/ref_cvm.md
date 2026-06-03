**Aqui está a lista dos principais campos das bases da CVM para Companhias Abertas (empresas relacionadas à B3).**

A CVM possui dezenas de arquivos e centenas de campos no total (especialmente em FRE, DFP, ITR e demonstrações contábeis). É impossível listar **todos** em uma resposta, mas organizei os mais importantes e utilizados por categoria.

### 1. Base Cadastral (cad_cia_aberta.csv) – Informações Gerais da Empresa

| Nome do Campo (técnico)       | Nome Real / Descrição da Informação |
|-------------------------------|-------------------------------------|
| CD_CVM                        | Código CVM da companhia |
| CNPJ_CIA                      | CNPJ da companhia |
| DENOM_SOCIAL                  | Denominação Social (razão social) |
| DENOM_COMERC                  | Denominação Comercial |
| SIT                           | Situação do registro na CVM |
| DT_REG                        | Data de registro na CVM |
| DT_CANCEL                     | Data de cancelamento do registro |
| MOTIVO_CANCEL                 | Motivo do cancelamento |
| DT_INI_SIT                    | Data de início da situação atual |
| SETOR_ATIV                    | Setor de Atividade |
| CONTROLE_ACIONARIO            | Tipo de controle acionário |
| TP_MERC                       | Tipo de mercado (Novo Mercado, Nível 2, etc.) |
| CATEG_REG                     | Categoria do registro |
| DT_INI_CATEG                  | Data de início da categoria |
| AUDITOR                       | Nome da empresa auditora |
| CNPJ_AUDITOR                  | CNPJ da auditora |
| LOGRADOURO                    | Logradouro (endereço) |
| COMPL                         | Complemento do endereço |
| BAIRRO                        | Bairro |
| MUN                           | Município |
| UF                            | Unidade da Federação (Estado) |
| CEP                           | CEP |
| TEL / FAX / EMAIL             | Telefone, Fax e E-mail da companhia |
| RESP / TP_RESP                | Nome e Tipo do responsável cadastral |

### 2. Campos Comuns em DFP e ITR (Demonstrações Financeiras)

Esses são os campos mais usados nas tabelas de demonstrações (dfp_cia_aberta_*.csv e itr_cia_aberta_*.csv):

| Nome do Campo              | Nome Real / Descrição |
|---------------------------|-----------------------|
| CNPJ_CIA                  | CNPJ da companhia |
| CD_CVM                    | Código CVM |
| DENOM_CIA                 | Denominação da companhia |
| DT_REFER                  | Data de referência da informação (fim do período) |
| VERSAO                    | Versão do formulário |
| GRUPO_DFP                 | Grupo do formulário (DFP ou ITR) |
| ORDEM_EXERC               | Ordem do exercício (ÚLTIMO ou PENÚLTIMO) |
| DT_INI_EXERC              | Data de início do exercício social |
| DT_FIM_EXERC              | Data de fim do exercício social |
| CD_CONTA                  | Código da conta contábil |
| DS_CONTA                  | Descrição da conta contábil |
| VL_CONTA                  | Valor da conta (em reais) |
| ST_CONTA_FIXA             | Indica se a conta é fixa (padrão) |
| COLUNA_DF                 | Coluna da demonstração (por exemplo, “Consolidado” ou “Individual”) |

### 3. Campos Principais do Formulário de Referência (FRE)

O FRE é dividido em vários arquivos CSV (fre_cia_aberta_*.csv). Principais campos comuns:

- **Nome_Companhia** (adicionado recentemente)
- **CNPJ_CIA**, **CD_CVM**, **DT_REFER**
- Campos de administração: cargos, nomes de diretores, conselheiros, remuneração, etc.
- Campos de capital social: quantidade de ações, tipo (ordinárias/preferenciais), etc.
- Campos de riscos, atividades, auditor, controladores, etc.

### 4. Outros Conjuntos Importantes para Empresas Listadas na B3

- **FCA (Formulário Cadastral)**: Similar ao cadastral, mas mais detalhado (inclui **Nome_Empresarial**).
- **Valores Mobiliários Negociados e Detidos (VLMO)**: Quantidade de ações detidas por administradores, controladores, etc.
- **Eventos Societários**: Recompra de ações, aumento de capital, etc.
- **Pareceres do Auditor**: Texto do relatório do auditor independente.

### Observações Importantes

- **DFP/ITR** são os mais ricos em dados financeiros. O coração deles são os campos **CD_CONTA + DS_CONTA + VL_CONTA**.
- Muitos campos repetem em quase todos os arquivos (`CNPJ_CIA`, `CD_CVM`, `DT_REFER`).
- A CVM atualiza os dicionários regularmente. Os metadados oficiais estão em:  
  → [Portal Dados Abertos CVM](https://dados.cvm.gov.br)

** Dicionário de Contas Contábeis (Plano de Contas) usado pela CVM para Companhias Abertas (DFP e ITR).**

A CVM **não** impõe um Plano de Contas rígido e único como o COFI (usado em fundos). As empresas seguem o **CPC/IFRS** (normas internacionais), e a CVM padroniza os códigos de contas (**CD_CONTA**) nas demonstrações enviadas via DFP/ITR.

Existem dois tipos principais:
- **Contas Fixas** (obrigatórias e padronizadas)
- **Contas Não Fixas** (criadas pela própria empresa, geralmente com códigos maiores)

### Estrutura Geral dos Códigos (CD_CONTA)

| Grupo | Significado |
|-------|-------------|
| 1     | **Ativo** |
| 2     | **Passivo** |
| 3     | **Patrimônio Líquido** (ou contas de resultado em alguns casos) |
| 4     | **Receitas** |
| 5     | **Despesas** / Custos |
| 6/7/8/9 | Contas de Resultado, Compensatórias, etc. |

---

### Dicionário das Principais Contas (Mais Usadas)

#### **1. Ativo (BPA - Balanço Patrimonial Ativo)**

| CD_CONTA     | DS_CONTA (Descrição) |
|--------------|----------------------|
| 1            | ATIVO |
| 1.01         | ATIVO CIRCULANTE |
| 1.01.01      | Caixa e Equivalentes de Caixa |
| 1.01.02      | Aplicações Financeiras |
| 1.01.03      | Contas a Receber |
| 1.01.04      | Estoques |
| 1.01.05      | Ativos Biológicos |
| 1.01.06      | Tributos a Recuperar |
| 1.01.07      | Despesas do Exercício Seguinte |
| 1.02         | ATIVO NÃO CIRCULANTE |
| 1.02.01      | Ativo Realizável a Longo Prazo |
| 1.02.02      | Investimentos |
| 1.02.03      | Imobilizado |
| 1.02.04      | Intangível |
| 1.02.05      | Goodwill |

#### **2. Passivo (BPP - Balanço Patrimonial Passivo)**

| CD_CONTA     | DS_CONTA |
|--------------|----------|
| 2            | PASSIVO |
| 2.01         | PASSIVO CIRCULANTE |
| 2.01.01      | Obrigações Trabalhistas e Sociais |
| 2.01.02      | Fornecedores |
| 2.01.03      | Empréstimos e Financiamentos |
| 2.01.04      | Tributos a Pagar |
| 2.01.05      | Dividendos a Pagar |
| 2.02         | PASSIVO NÃO CIRCULANTE |
| 2.02.01      | Empréstimos e Financiamentos |
| 2.02.02      | Tributos Diferidos |
| 2.02.03      | Provisões |
| 2.03         | PASSIVO TOTAL |

#### **3. Patrimônio Líquido**

| CD_CONTA     | DS_CONTA |
|--------------|----------|
| 3.01         | PATRIMÔNIO LÍQUIDO |
| 3.01.01      | Capital Social |
| 3.01.02      | Reservas de Capital |
| 3.01.03      | Reservas de Lucros |
| 3.01.04      | Ajustes de Avaliação Patrimonial |
| 3.01.05      | Lucros/Prejuízos Acumulados |
| 3.01.06      | Ações em Tesouro (negativo) |
| 3.02         | PARTICIPAÇÃO DOS ACIONISTAS NÃO CONTROLADORES |

#### **4. Demonstração do Resultado (DRE)**

| CD_CONTA     | DS_CONTA |
|--------------|----------|
| 4.01         | RECEITA BRUTA |
| 4.02         | DEDUÇÕES DA RECEITA BRUTA |
| 4.03         | RECEITA LÍQUIDA |
| 4.04         | CUSTO DOS PRODUTOS/SERVIÇOS VENDIDOS (CPV/CSV) |
| 4.05         | LUCRO BRUTO |
| 4.06         | DESPESAS OPERACIONAIS |
| 4.07         | Resultado Financeiro |
| 4.08         | Resultado Antes dos Tributos |
| 4.09         | Imposto de Renda e Contribuição Social |
| 4.10         | Lucro/Prejuízo do Período |

#### **Outras Demonstrações Importantes**

- **DRA** (Resultado Abrangente): Inclui outros resultados abrangentes (ex: variação cambial, hedge, etc.).
- **DMPL**: Mutações no Patrimônio Líquido.
- **DFC**: Fluxo de Caixa (Método Direto e Indireto).
- **DVA**: Demonstração do Valor Adicionado.

---

**Observações Importantes:**

- O código completo costuma ter 8–12 dígitos (ex: `1.01.01.01.01`).
- Muitas empresas usam contas **não fixas** (ex: 1.01.09.999 para alguma rubrica específica).
- O campo `ST_CONTA_FIXA` no CSV da CVM indica se a conta é padrão (`S`) ou não (`N`).
- Para ver a lista **exata** e atualizada de todas as contas usadas por uma empresa, baixe os arquivos em:  
  → [https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp](https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp)
