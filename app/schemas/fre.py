import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Paginacao


class FreDocumentoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    codigo_cvm: int | None
    data_referencia: date
    versao: int
    denominacao_companhia: str | None
    categoria_documento: str | None
    id_documento: int
    data_recebimento: date | None
    link_documento: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class FreAuditorResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: date
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_auditor: int
    auditor: str | None
    cpf_auditor: str | None
    cnpj_auditor: str | None
    codigo_cvm_auditor: int | None
    tipo_origem_auditor: str | None
    data_inicio_contratacao: date | None
    data_fim_contratacao: date | None
    data_inicio_prestacao_servico: date | None
    servico_contratado: str | None
    remuneracao_auditor: Decimal | None
    justificativa_substituicao: str | None
    razao_apresentada: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class FreCapitalSocialResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: date
    versao: int
    id_documento: int
    nome_companhia: str | None
    id_capital_social: int
    tipo_capital: str | None
    data_autorizacao_aprovacao: date | None
    valor_capital: Decimal | None
    prazo_integralizacao: str | None
    quantidade_acoes_ordinarias: Decimal | None
    quantidade_acoes_preferenciais: Decimal | None
    quantidade_total_acoes: Decimal | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class FrePosicaoAcionariaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: date
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
    quantidade_acao_ordinaria_circulacao: Decimal | None
    percentual_acao_ordinaria_circulacao: Decimal | None
    quantidade_acao_preferencial_circulacao: Decimal | None
    percentual_acao_preferencial_circulacao: Decimal | None
    quantidade_total_acoes_circulacao: Decimal | None
    percentual_total_acoes_circulacao: Decimal | None
    nacionalidade: str | None
    sigla_uf: str | None
    residente_exterior: bool | None
    representante_legal: str | None
    tipo_pessoa_representante_legal: str | None
    cpf_cnpj_representante_legal: str | None
    data_composicao_capital_social: date | None
    data_ultima_alteracao: date | None
    acionista_controlador: bool | None
    participante_acordo_acionistas: bool | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class FreRemuneracaoTotalOrgaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: date
    versao: int
    id_documento: int
    nome_companhia: str | None
    data_inicio_exercicio_social: date | None
    data_fim_exercicio_social: date | None
    total_remuneracao: Decimal | None
    orgao_administracao: str | None
    numero_membros: int | None
    total_remuneracao_orgao: Decimal | None
    numero_membros_remunerados: int | None
    salario: Decimal | None
    beneficios_diretos_indiretos: Decimal | None
    participacoes_comites: Decimal | None
    outros_valores_fixos: Decimal | None
    descricao_outros_remuneracoes_fixas: str | None
    bonus: Decimal | None
    participacao_resultados: Decimal | None
    participacao_reunioes: Decimal | None
    outros_valores_variaveis: Decimal | None
    comissoes: Decimal | None
    descricao_outros_remuneracoes_variaveis: str | None
    pos_emprego: Decimal | None
    cessacao_cargo: Decimal | None
    baseada_acoes: Decimal | None
    observacao: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class FreEmpregadoPosicaoGeneroResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: date
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
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


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
