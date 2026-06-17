---
title: Schemas de Companhias
sidebar_position: 3
---

# Schemas de Companhias

## `CompanhiaResposta`

Schema principal da entidade raiz do domínio.

### Schema

```python
class CompanhiaResposta(BaseModel):
    id: UUID
    cnpj_companhia: str
    codigo_cvm: Optional[int]
    denominacao_social: Optional[str]
    denominacao_comercial: Optional[str]
    situacao_registro: Optional[str]
    data_registro: Optional[date]
    data_constituicao: Optional[date]
    data_cancelamento: Optional[date]
    motivo_cancelamento: Optional[str]
    data_inicio_situacao: Optional[date]
    setor_atividade: Optional[str]
    tipo_mercado: Optional[str]
    categoria_registro: Optional[str]
    data_inicio_categoria: Optional[date]
    situacao_emissor: Optional[str]
    data_inicio_situacao_emissor: Optional[date]
    controle_acionario: Optional[str]
    endereco: Dict[str, Any]
    responsavel: Dict[str, Any]
    auditor: Optional[str]
    cnpj_auditor: Optional[str]
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime
```

### Exemplo JSON

```json
{
  "id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
  "cnpj_companhia": "08773135000100",
  "codigo_cvm": 25224,
  "denominacao_social": "2W ECOBANK S.A. - EM RECUPERACAO JUDICIAL",
  "denominacao_comercial": "2W ECOBANK S.A.",
  "situacao_registro": "SUSPENSO(A) - DECISAO ADM",
  "data_registro": "2020-10-29",
  "data_constituicao": "2007-03-23",
  "data_cancelamento": null,
  "motivo_cancelamento": null,
  "data_inicio_situacao": "2026-05-19",
  "setor_atividade": "Energia Eletrica",
  "tipo_mercado": "Novo Mercado",
  "categoria_registro": "Categoria A",
  "data_inicio_categoria": "2020-10-29",
  "situacao_emissor": "EM RECUPERACAO JUDICIAL OU EQUIVALENTE",
  "data_inicio_situacao_emissor": "2025-04-23",
  "controle_acionario": "PRIVADO",
  "endereco": {
    "tipo_endereco": "SEDE",
    "logradouro": "Avenida Dr. Chucri Zaidan, 1550",
    "complemento": "8 and-conj 815-sl 1",
    "bairro": "Chacara Santo Antoni",
    "municipio": "SAO PAULO",
    "uf": "SP",
    "cep": "4711130",
    "pais": "BRASIL",
    "telefone": "39579400",
    "ddd_telefone": "11",
    "fax": "39579499",
    "ddd_fax": "11",
    "email": "ri@2wecobank.com.br"
  },
  "responsavel": {
    "nome_responsavel": "FERNANDO GUEDES VIEIRA",
    "tipo_responsavel": "DIRETOR DE RELACOES COM INVESTIDORES",
    "logradouro": "AV DR. CHUCRI ZAIDAN, 1550",
    "complemento": "8 AND-CONJ815-SL1",
    "bairro": "CHACARA STO. ANTONIO",
    "municipio": "SAO PAULO",
    "uf": "SP",
    "cep": "4711130",
    "telefone": "39579400",
    "ddd_telefone": "11",
    "email": "juridico@2wecobank.com.br",
    "data_inicio_responsavel": "2026-04-22"
  },
  "auditor": "GRANT THORNTON AUDITORES INDEPENDENTES LTDA.",
  "cnpj_auditor": "10830108000165",
  "criado_em": "2026-05-30T14:30:00Z",
  "sincronizado_em": "2026-05-30T14:30:00Z",
  "alterado_em": "2026-05-30T14:30:00Z"
}
```

### Campos Principais

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID | Identificador interno estável |
| `cnpj_companhia` | string | CNPJ com 14 dígitos (sem pontuação) |
| `codigo_cvm` | integer \| null | Código CVM da companhia |
| `denominacao_social` | string \| null | Razão social completa |
| `denominacao_comercial` | string \| null | Nome fantasia |
| `situacao_registro` | string \| null | Situação do registro (ATIVO, SUSPENSO, etc.) |
| `data_registro` | date \| null | Data de concessão do registro |
| `data_constituicao` | date \| null | Data de fundação |
| `setor_atividade` | string \| null | Setor econômico |
| `tipo_mercado` | string \| null | Segmento de listagem |
| `controle_acionario` | string \| null | Tipo de controle (PRIVADO, ESTATAL) |
| `endereco` | object | Endereço estruturado |
| `responsavel` | object | Responsável cadastral |
| `auditor` | string \| null | Nome do auditor independente |
| `cnpj_auditor` | string \| null | CNPJ do auditor |

### Campos de Rastreabilidade

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `criado_em` | datetime | Timestamp da primeira inserção |
| `sincronizado_em` | datetime | Última vez que foi reencontrado na fonte |
| `alterado_em` | datetime | Última alteração real de negócio |

---

## `ListaCompanhiasResposta`

Response para `GET /companhias`.

### Schema

```python
class ListaCompanhiasResposta(BaseModel):
    dados: List[CompanhiaResposta]
    paginacao: Paginacao
```

### Exemplo JSON

```json
{
  "dados": [
    {
      "id": "f4f6a9d8-...",
      "cnpj_companhia": "08773135000100",
      "codigo_cvm": 25224,
      "denominacao_social": "2W ECOBANK S.A.",
      "..."
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 100,
    "total": 1
  }
}
```

---

## `ConsultaCompanhiaMestreResposta`

Response para `GET /companhias/mestre`. Agrega todos os endpoints de uma companhia.

### Schema

```python
class ConsultaCompanhiaMestreResposta(BaseModel):
    companhia: CompanhiaResposta
    documentos_dfp: ListaDocumentosFinanceirosResposta
    documentos_itr: ListaDocumentosFinanceirosResposta
    composicao_capital_dfp: ListaComposicoesCapitalResposta
    composicao_capital_itr: ListaComposicoesCapitalResposta
    pareceres_dfp: ListaPareceresFinanceirosResposta
    pareceres_itr: ListaPareceresFinanceirosResposta
    demonstracoes: Dict[str, ListaDemonstracoesFinanceirasResposta]
    fre_documentos: ListaFreDocumentosResposta
    fre_auditores: ListaFreAuditoresResposta
    fre_capital_social: ListaFreCapitalSocialResposta
    fre_posicao_acionaria: ListaFrePosicaoAcionariaResposta
    fre_remuneracao_total_orgao: ListaFreRemuneracaoTotalOrgaoResposta
    fre_empregados_posicao_genero: ListaFreEmpregadoPosicaoGeneroResposta
    ipe_documentos: ListaIpeDocumentosResposta
```

### Chaves do Mapa `demonstracoes`

O campo `demonstracoes` é um dicionário onde as chaves seguem o padrão `{formulario}_{tipo}_{escopo}`:

```json
{
  "demonstracoes": {
    "dfp_balanco_patrimonial_ativo_consolidado": {...},
    "dfp_balanco_patrimonial_ativo_individual": {...},
    "dfp_balanco_patrimonial_passivo_consolidado": {...},
    "dfp_balanco_patrimonial_passivo_individual": {...},
    "dfp_demonstracao_resultado_consolidado": {...},
    "dfp_demonstracao_resultado_individual": {...},
    "dfp_fluxo_caixa_metodo_direto_consolidado": {...},
    "dfp_fluxo_caixa_metodo_indireto_consolidado": {...},
    "dfp_mutacoes_patrimonio_liquido_consolidado": {...},
    "dfp_resultado_abrangente_consolidado": {...},
    "dfp_valor_adicionado_consolidado": {...},
    "itr_balanco_patrimonial_ativo_consolidado": {...},
    "itr_balanco_patrimonial_ativo_individual": {...},
    "itr_demonstracao_resultado_consolidado": {...},
    "itr_demonstracao_resultado_individual": {...}
  }
}
```

### Exemplo de Uso

```bash
GET /companhias/mestre?codigo_cvm=25224&limite_por_endpoint=50
```

Cada endpoint agregado retorna no máximo `limite_por_endpoint` itens (padrão: 100, máx: 500).

---

## Estrutura do Objeto `endereco`

```json
{
  "tipo_endereco": "SEDE",
  "logradouro": "Avenida Dr. Chucri Zaidan, 1550",
  "complemento": "8 and-conj 815-sl 1",
  "bairro": "Chacara Santo Antoni",
  "municipio": "SAO PAULO",
  "uf": "SP",
  "cep": "4711130",
  "pais": "BRASIL",
  "telefone": "39579400",
  "ddd_telefone": "11",
  "fax": "39579499",
  "ddd_fax": "11",
  "email": "ri@2wecobank.com.br"
}
```

## Estrutura do Objeto `responsavel`

```json
{
  "nome_responsavel": "FERNANDO GUEDES VIEIRA",
  "tipo_responsavel": "DIRETOR DE RELACOES COM INVESTIDORES",
  "logradouro": "AV DR. CHUCRI ZAIDAN, 1550",
  "complemento": "8 AND-CONJ815-SL1",
  "bairro": "CHACARA STO. ANTONIO",
  "municipio": "SAO PAULO",
  "uf": "SP",
  "cep": "4711130",
  "telefone": "39579400",
  "ddd_telefone": "11",
  "email": "juridico@2wecobank.com.br",
  "data_inicio_responsavel": "2026-04-22"
}
```

---

## Filtros de Query

### `GET /companhias`

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ com ou sem pontuação |
| `codigo_cvm` | integer | Código CVM |
| `nome` | string | Busca por nome (razão social ou comercial) |
| `situacao_registro` | string | Filtrar por situação |
| `ordenar` | string | `ativa_nome`, `nome`, `codigo_cvm` |
| `pagina` | integer | Número da página (padrão: 1) |
| `tamanho_pagina` | integer | Itens por página (padrão: 100, máx: 500) |

### `GET /companhias/mestre`

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `cnpj_companhia` | string | Um dos dois | CNPJ da companhia |
| `codigo_cvm` | integer | Um dos dois | Código CVM da companhia |
| `limite_por_endpoint` | integer | Não | Máximo de itens por endpoint (padrão: 100, máx: 500) |