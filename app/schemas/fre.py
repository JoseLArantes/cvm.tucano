import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import BrazilianDate, BrazilianDateTime, CanonicalDecimal, Paginacao, PeriodicModel


class FreDocumentoResposta(PeriodicModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    codigo_cvm: int | None
    data_referencia: BrazilianDate
    versao: int
    denominacao_companhia: str | None
    categoria_documento: str | None
    id_documento: int
    data_recebimento: BrazilianDate | None
    link_documento: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreAuditorResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_auditor: int
    auditor: str | None
    cpf_auditor: str | None
    cnpj_auditor: str | None
    codigo_cvm_auditor: str | None
    tipo_origem_auditor: str | None
    data_inicio_contratacao: BrazilianDate | None
    data_fim_contratacao: BrazilianDate | None
    data_inicio_prestacao_servico: BrazilianDate | None
    servico_contratado: str | None
    remuneracao_auditor: str | None
    justificativa_substituicao: str | None
    razao_apresentada: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreCapitalSocialResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_capital_social: int
    tipo_capital: str | None
    data_autorizacao_aprovacao: BrazilianDate | None
    valor_capital: CanonicalDecimal | None
    prazo_integralizacao: str | None
    quantidade_acoes_ordinarias: CanonicalDecimal | None
    quantidade_acoes_preferenciais: CanonicalDecimal | None
    quantidade_total_acoes: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FrePosicaoAcionariaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_acionista: int
    acionista: str | None
    tipo_pessoa_acionista: str | None
    cpf_cnpj_acionista: str | None
    id_acionista_relacionado: int | None
    acionista_relacionado: str | None
    tipo_pessoa_acionista_relacionado: str | None
    cpf_cnpj_acionista_relacionado: str | None
    quantidade_acao_ordinaria_circulacao: CanonicalDecimal | None
    percentual_acao_ordinaria_circulacao: CanonicalDecimal | None
    quantidade_acao_preferencial_circulacao: CanonicalDecimal | None
    percentual_acao_preferencial_circulacao: CanonicalDecimal | None
    quantidade_total_acoes_circulacao: CanonicalDecimal | None
    percentual_total_acoes_circulacao: CanonicalDecimal | None
    nacionalidade: str | None
    sigla_uf: str | None
    residente_exterior: bool | None
    representante_legal: str | None
    tipo_pessoa_representante_legal: str | None
    cpf_cnpj_representante_legal: str | None
    data_composicao_capital_social: BrazilianDate | None
    data_ultima_alteracao: BrazilianDate | None
    acionista_controlador: bool | None
    participante_acordo_acionistas: bool | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreRemuneracaoTotalOrgaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    data_inicio_exercicio_social: BrazilianDate | None
    data_fim_exercicio_social: BrazilianDate | None
    total_remuneracao: CanonicalDecimal | None
    orgao_administracao: str | None
    numero_membros: int | None
    total_remuneracao_orgao: CanonicalDecimal | None
    numero_membros_remunerados: int | None
    salario: CanonicalDecimal | None
    beneficios_diretos_indiretos: CanonicalDecimal | None
    participacoes_comites: CanonicalDecimal | None
    outros_valores_fixos: CanonicalDecimal | None
    descricao_outros_remuneracoes_fixas: str | None
    bonus: CanonicalDecimal | None
    participacao_resultados: CanonicalDecimal | None
    participacao_reunioes: CanonicalDecimal | None
    outros_valores_variaveis: CanonicalDecimal | None
    comissoes: CanonicalDecimal | None
    descricao_outros_remuneracoes_variaveis: str | None
    pos_emprego: CanonicalDecimal | None
    cessacao_cargo: CanonicalDecimal | None
    baseada_acoes: CanonicalDecimal | None
    observacao: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreEmpregadoPosicaoGeneroResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    posicao: str
    quantidade_feminino: int | None
    quantidade_masculino: int | None
    quantidade_nao_binario: int | None
    quantidade_outros: int | None
    quantidade_sem_resposta: int | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreParticipacaoSociedadeResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_sociedade: int
    razao_social: str | None
    cnpj: str | None
    tipo_sociedade: str | None
    descricao_atividades: str | None
    pais_sede: str | None
    uf_sede: str | None
    municipio_sede: str | None
    participacao_emissor: CanonicalDecimal | None
    possui_registro_cvm: bool | None
    codigo_cvm: int | None
    razao_aquisicao_manutencao: str | None
    data_valor_mercado: BrazilianDate | None
    data_valor_contabil: BrazilianDate | None
    valor_mercado: CanonicalDecimal | None
    valor_contabil: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreEmpregadoPosicaoLocalResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    posicao: str
    quantidade_norte: int | None
    quantidade_nordeste: int | None
    quantidade_centro_oeste: int | None
    quantidade_sudeste: int | None
    quantidade_sul: int | None
    quantidade_exterior: int | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreEmpregadoPosicaoFaixaEtariaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    posicao: str
    quantidade_ate_30_anos: int | None
    quantidade_30_a_50_anos: int | None
    quantidade_acima_50_anos: int | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreEmpregadoPosicaoDeclaracaoRacaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    posicao: str
    quantidade_amarelo: int | None
    quantidade_branco: int | None
    quantidade_preto: int | None
    quantidade_pardo: int | None
    quantidade_indigena: int | None
    quantidade_outros: int | None
    quantidade_sem_resposta: int | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreEmpregadoPcdResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    codigo_posicao: int | None
    posicao: str
    quantidade_pcd: int | None
    quantidade_nao_pcd: int | None
    quantidade_sem_resposta: int | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreEmpregadoLocalFaixaEtariaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    local: str
    quantidade_ate_30_anos: int | None
    quantidade_30_a_50_anos: int | None
    quantidade_acima_50_anos: int | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreEmpregadoLocalDeclaracaoRacaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    local: str
    quantidade_amarelo: int | None
    quantidade_branco: int | None
    quantidade_preto: int | None
    quantidade_pardo: int | None
    quantidade_indigena: int | None
    quantidade_outros: int | None
    quantidade_sem_resposta: int | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreEmpregadoLocalDeclaracaoGeneroResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    local: str
    quantidade_feminino: int | None
    quantidade_masculino: int | None
    quantidade_nao_binario: int | None
    quantidade_outros: int | None
    quantidade_sem_resposta: int | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreRelacaoFamiliarResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    nome_administrador: str | None
    cpf_administrador: str | None
    nome_emissor: str | None
    cnpj_emissor: str | None
    cargo_administrador: str | None
    nome_pessoa_relacionada: str
    cpf_pessoa_relacionada: str | None
    nome_emissor_pessoa_relacionada: str | None
    cnpj_emissor_pessoa_relacionada: str | None
    cargo_Pessoa_relacionada: str | None
    tipo_parentesco: str | None
    observacao: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreResponsavelResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    nome_responsavel: str | None
    cargo_responsavel: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreCapitalSocialClasseAcaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_capital_social: int
    tipo_classe_acao_preferencial: str | None
    quantidade_acoes: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreCapitalSocialTituloConversivelResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_capital_social: int
    titulo_conversivel_acao: str | None
    condicoes_conversao: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreDistribuicaoCapitalResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    data_ultima_assembleia: BrazilianDate | None
    quantidade_acoes_ordinarias_circulacao: CanonicalDecimal | None
    percentual_acoes_ordinarias_circulacao: CanonicalDecimal | None
    quantidade_acoes_preferenciais_circulacao: CanonicalDecimal | None
    percentual_acoes_preferenciais_circulacao: CanonicalDecimal | None
    quantidade_total_acoes_circulacao: CanonicalDecimal | None
    percentual_total_acoes_circulacao: CanonicalDecimal | None
    quantidade_acionistas_pf: CanonicalDecimal | None
    quantidade_acionistas_pj: CanonicalDecimal | None
    quantidade_acionistas_investidores_institucionais: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreDistribuicaoCapitalClasseAcaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    classe_acoes_preferenciais: str | None
    sigla_classe_acoes_preferenciais: str | None
    quantidade_acoes_preferenciais_circulacao: CanonicalDecimal | None
    percentual_acoes_preferenciais_circulacao: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FrePosicaoAcionariaClasseAcaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_acionista: int
    tipo_classe_acao_preferencial: str | None
    quantidade_acoes: CanonicalDecimal | None
    percentual_acoes: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreRemuneracaoMaximaMinimaMediaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    data_inicio_exercicio_social: BrazilianDate | None
    data_fim_exercicio_social: BrazilianDate | None
    orgao_administracao: str | None
    numero_membros: CanonicalDecimal | None
    numero_membros_remunerados: CanonicalDecimal | None
    valor_maior_remuneracao: CanonicalDecimal | None
    valor_medio_remuneracao: CanonicalDecimal | None
    valor_menor_remuneracao: CanonicalDecimal | None
    observacao: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreRemuneracaoVariavelResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    data_inicio_exercicio_social: BrazilianDate | None
    data_fim_exercicio_social: BrazilianDate | None
    orgao_administracao: str | None
    quantidade_total_membros: CanonicalDecimal | None
    quantidade_membros_remunerados: CanonicalDecimal | None
    bonus_valor_minimo: CanonicalDecimal | None
    bonus_valor_maximo: CanonicalDecimal | None
    bonus_valor_metas_atingidas: CanonicalDecimal | None
    bonus_valor_efetivo: CanonicalDecimal | None
    participacao_valor_minimo: CanonicalDecimal | None
    participacao_valor_maximo: CanonicalDecimal | None
    participacao_valor_metas_atingidas: CanonicalDecimal | None
    participacao_valor_efetivo: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreRemuneracaoAcaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    data_inicio_exercicio_social: BrazilianDate | None
    data_fim_exercicio_social: BrazilianDate | None
    orgao_administracao: str | None
    quantidade_total_membros: CanonicalDecimal | None
    quantidade_membros_remunerados: CanonicalDecimal | None
    preco_medio_ponderado_opcoes_em_aberto: CanonicalDecimal | None
    preco_medio_ponderado_opcoes_exercidas: CanonicalDecimal | None
    preco_medio_ponderado_opcoes_perdidas: CanonicalDecimal | None
    diluicao_potencial: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreAcaoEntregueResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    data_inicio_exercicio_social: BrazilianDate | None
    data_fim_exercicio_social: BrazilianDate | None
    orgao_administracao: str | None
    quantidade_total_membros: CanonicalDecimal | None
    quantidade_membros_remunerados: CanonicalDecimal | None
    quantidade_acoes: int | None
    preco_medio_ponderado_aquisicao: CanonicalDecimal | None
    preco_medio_ponderado_mercado: CanonicalDecimal | None
    valor_diferenca_aquisicao_mercado: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFreDocumentosResposta(BaseModel):
    dados: list[FreDocumentoResposta] = Field(description="Lista paginada de documentos FRE.")
    paginacao: Paginacao


class ListaFreAuditoresResposta(BaseModel):
    dados: list[FreAuditorResposta] = Field(description="Lista paginada de auditores FRE.")
    paginacao: Paginacao


class ListaFreCapitalSocialResposta(BaseModel):
    dados: list[FreCapitalSocialResposta] = Field(description="Lista paginada de capital social FRE.")
    paginacao: Paginacao


class ListaFrePosicaoAcionariaResposta(BaseModel):
    dados: list[FrePosicaoAcionariaResposta] = Field(description="Lista paginada de posição acionária FRE.")
    paginacao: Paginacao


class ListaFreRemuneracaoTotalOrgaoResposta(BaseModel):
    dados: list[FreRemuneracaoTotalOrgaoResposta] = Field(
        description="Lista paginada de remuneração total por órgão FRE."
    )
    paginacao: Paginacao


class ListaFreEmpregadoPosicaoGeneroResposta(BaseModel):
    dados: list[FreEmpregadoPosicaoGeneroResposta] = Field(
        description="Lista paginada de empregados por posição e gênero FRE."
    )
    paginacao: Paginacao


class ListaFreParticipacoesSociedadesResposta(BaseModel):
    dados: list[FreParticipacaoSociedadeResposta] = Field(description="Lista paginada de participacoes em sociedades FRE.")
    paginacao: Paginacao


class ListaFreEmpregadoPosicaoLocalResposta(BaseModel):
    dados: list[FreEmpregadoPosicaoLocalResposta] = Field(description="Lista paginada de empregados por posicao e local FRE.")
    paginacao: Paginacao


class ListaFreEmpregadoPosicaoFaixaEtariaResposta(BaseModel):
    dados: list[FreEmpregadoPosicaoFaixaEtariaResposta] = Field(description="Lista paginada de empregados por posicao e faixa etaria FRE.")
    paginacao: Paginacao


class ListaFreEmpregadoPosicaoDeclaracaoRacaResposta(BaseModel):
    dados: list[FreEmpregadoPosicaoDeclaracaoRacaResposta] = Field(description="Lista paginada de empregados por posicao e declaracao de raca FRE.")
    paginacao: Paginacao


class ListaFreEmpregadoPcdResposta(BaseModel):
    dados: list[FreEmpregadoPcdResposta] = Field(description="Lista paginada de empregados PCD FRE.")
    paginacao: Paginacao


class ListaFreEmpregadoLocalFaixaEtariaResposta(BaseModel):
    dados: list[FreEmpregadoLocalFaixaEtariaResposta] = Field(description="Lista paginada de empregados por local e faixa etaria FRE.")
    paginacao: Paginacao


class ListaFreEmpregadoLocalDeclaracaoRacaResposta(BaseModel):
    dados: list[FreEmpregadoLocalDeclaracaoRacaResposta] = Field(description="Lista paginada de empregados por local e declaracao de raca FRE.")
    paginacao: Paginacao


class ListaFreEmpregadoLocalDeclaracaoGeneroResposta(BaseModel):
    dados: list[FreEmpregadoLocalDeclaracaoGeneroResposta] = Field(description="Lista paginada de empregados por local e declaracao de genero FRE.")
    paginacao: Paginacao


class ListaFreRelacoesFamiliaresResposta(BaseModel):
    dados: list[FreRelacaoFamiliarResposta] = Field(description="Lista paginada de relacoes familiares declaradas no FRE.")
    paginacao: Paginacao


class ListaFreResponsaveisResposta(BaseModel):
    dados: list[FreResponsavelResposta] = Field(description="Lista paginada de pessoas responsaveis pelo FRE.")
    paginacao: Paginacao


class ListaFreCapitalSocialClassesAcoesResposta(BaseModel):
    dados: list[FreCapitalSocialClasseAcaoResposta] = Field(
        description="Lista paginada de classes de acoes do capital social FRE."
    )
    paginacao: Paginacao


class ListaFreCapitalSocialTitulosConversiveisResposta(BaseModel):
    dados: list[FreCapitalSocialTituloConversivelResposta] = Field(
        description="Lista paginada de titulos conversiveis do capital social FRE."
    )
    paginacao: Paginacao


class ListaFreDistribuicaoCapitalResposta(BaseModel):
    dados: list[FreDistribuicaoCapitalResposta] = Field(description="Lista paginada de distribuicao de capital FRE.")
    paginacao: Paginacao


class ListaFreDistribuicaoCapitalClassesAcoesResposta(BaseModel):
    dados: list[FreDistribuicaoCapitalClasseAcaoResposta] = Field(
        description="Lista paginada de classes de acoes da distribuicao de capital FRE."
    )
    paginacao: Paginacao


class ListaFrePosicoesAcionariasClassesAcoesResposta(BaseModel):
    dados: list[FrePosicaoAcionariaClasseAcaoResposta] = Field(
        description="Lista paginada de classes de acoes da posicao acionaria FRE."
    )
    paginacao: Paginacao


class ListaFreRemuneracoesMaximasMinimasMediasResposta(BaseModel):
    dados: list[FreRemuneracaoMaximaMinimaMediaResposta] = Field(
        description="Lista paginada de remuneracoes maximas, minimas e medias FRE."
    )
    paginacao: Paginacao


class ListaFreRemuneracoesVariaveisResposta(BaseModel):
    dados: list[FreRemuneracaoVariavelResposta] = Field(description="Lista paginada de remuneracoes variaveis FRE.")
    paginacao: Paginacao


class ListaFreRemuneracoesAcoesResposta(BaseModel):
    dados: list[FreRemuneracaoAcaoResposta] = Field(description="Lista paginada de remuneracoes baseadas em acoes FRE.")
    paginacao: Paginacao


class ListaFreAcoesEntreguesResposta(BaseModel):
    dados: list[FreAcaoEntregueResposta] = Field(description="Lista paginada de acoes entregues FRE.")
    paginacao: Paginacao


class FreVolumeValorMobiliarioResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    classe_valor_mobiliario: str
    sigla_classe_acoes_preferenciais: str | None
    volume_negociacao: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFreVolumeValoresMobiliariosResposta(BaseModel):
    dados: list[FreVolumeValorMobiliarioResposta] = Field(description="Lista paginada de volumes de valores mobiliarios FRE.")
    paginacao: Paginacao


class FreOutroValorMobiliarioResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    nome_valor_mobiliario: str
    caracteristicas_valor_mobiliario: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFreOutrosValoresMobiliariosResposta(BaseModel):
    dados: list[FreOutroValorMobiliarioResposta] = Field(description="Lista paginada de outros valores mobiliarios FRE.")
    paginacao: Paginacao


class FreTitularValorMobiliarioResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    nome_titular: str
    cpf_cnpj_titular: str | None
    classe_valor_mobiliario: str
    quantidade_valores_mobiliarios: CanonicalDecimal | None
    percentual_classe: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFreTitularesValoresMobiliariosResposta(BaseModel):
    dados: list[FreTitularValorMobiliarioResposta] = Field(description="Lista paginada de titulares de valores mobiliarios FRE.")
    paginacao: Paginacao


class FreMercadoEstrangeiroResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    nome_mercado: str
    orgao_regulador: str | None
    data_admissao: BrazilianDate | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFreMercadosEstrangeirosResposta(BaseModel):
    dados: list[FreMercadoEstrangeiroResposta] = Field(description="Lista paginada de mercados estrangeiros FRE.")
    paginacao: Paginacao


class FreTituloExteriorResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    nome_titulo: str
    pais_emissao: str | None
    caracteristicas: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFreTitulosExteriorResposta(BaseModel):
    dados: list[FreTituloExteriorResposta] = Field(description="Lista paginada de titulos emitidos no exterior FRE.")
    paginacao: Paginacao


class FrePlanoRecompraResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_plano_recompra: int
    data_deliberacao: BrazilianDate | None
    objetivo_plano: str | None
    limite_prazo_aquisicao: str | None
    quantidade_total_ordinarias_adquiridas: CanonicalDecimal | None
    quantidade_total_preferenciais_adquiridas: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFrePlanosRecompraResposta(BaseModel):
    dados: list[FrePlanoRecompraResposta] = Field(description="Lista paginada de planos de recompra de acoes FRE.")
    paginacao: Paginacao


class FrePlanoRecompraClasseAcaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_plano_recompra: int
    especie_acao: str | None
    tipo_classe_acao_preferencial: str | None
    quantidade_acoes_adquiridas: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFrePlanoRecompraClassesAcoesResposta(BaseModel):
    dados: list[FrePlanoRecompraClasseAcaoResposta] = Field(description="Lista paginada de classes de acoes nos planos de recompra FRE.")
    paginacao: Paginacao


class FreValorMobiliarioTesourariaMovimentacaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    classe_valor_mobiliario: str
    data_movimentacao: BrazilianDate
    quantidade_movimentada: CanonicalDecimal | None
    natureza_movimentacao: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFreValoresMobiliariosTesourariaMovimentacoesResposta(BaseModel):
    dados: list[FreValorMobiliarioTesourariaMovimentacaoResposta] = Field(description="Lista paginada de movimentacoes de valores mobiliarios em tesouraria FRE.")
    paginacao: Paginacao


class FreValorMobiliarioTesourariaUltimoExercicioResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    classe_valor_mobiliario: str
    historico_exercicio: str
    quantidade_acoes_tesouraria: CanonicalDecimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFreValoresMobiliariosTesourariaUltimosExerciciosResposta(BaseModel):
    dados: list[FreValorMobiliarioTesourariaUltimoExercicioResposta] = Field(description="Lista paginada de saldos do ultimo exercicio de valores mobiliarios em tesouraria FRE.")
    paginacao: Paginacao


class FreAdministradorDeclaracaoGeneroResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    orgao_administracao: str
    quantidade_feminino: int | None
    quantidade_masculino: int | None
    quantidade_nao_binario: int | None
    quantidade_outros: int | None
    quantidade_sem_resposta: int | None
    nao_aplicavel: bool | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreAdministradorDeclaracaoRacaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    orgao_administracao: str
    quantidade_amarelo: int | None
    quantidade_branco: int | None
    quantidade_preto: int | None
    quantidade_pardo: int | None
    quantidade_indigena: int | None
    quantidade_outros: int | None
    quantidade_sem_resposta: int | None
    nao_aplicavel: bool | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class FreAdministradorPcdResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: BrazilianDate
    versao: int
    id_documento: int
    nome_companhia: str | None
    orgao_administracao: str
    quantidade_pcd: int | None
    quantidade_nao_pcd: int | None
    quantidade_sem_resposta: int | None
    nao_aplicavel: bool | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: BrazilianDateTime
    sincronizado_em: BrazilianDateTime
    alterado_em: BrazilianDateTime


class ListaFreAdministradoresDeclaracaoGeneroResposta(BaseModel):
    dados: list[FreAdministradorDeclaracaoGeneroResposta] = Field(description="Lista paginada de declarações de gênero de administradores FRE.")
    paginacao: Paginacao


class ListaFreAdministradoresDeclaracaoRacaResposta(BaseModel):
    dados: list[FreAdministradorDeclaracaoRacaResposta] = Field(description="Lista paginada de declarações de raça de administradores FRE.")
    paginacao: Paginacao


class ListaFreAdministradoresPcdResposta(BaseModel):
    dados: list[FreAdministradorPcdResposta] = Field(description="Lista paginada de declarações PCD de administradores FRE.")
    paginacao: Paginacao
