import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Paginacao


class FcaDocumentoResposta(BaseModel):
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


class FcaGeralResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    codigo_cvm: int | None
    data_referencia: date
    versao: int
    id_documento: int
    nome_empresarial: str | None
    data_nome_empresarial: date | None
    nome_empresarial_anterior: str | None
    data_constituicao: date | None
    data_registro_cvm: date | None
    categoria_registro_cvm: str | None
    data_categoria_registro_cvm: date | None
    situacao_registro_cvm: str | None
    data_situacao_registro_cvm: date | None
    pais_origem: str | None
    pais_custodia_valores_mobiliarios: str | None
    setor_atividade: str | None
    descricao_atividade: str | None
    situacao_emissor: str | None
    data_situacao_emissor: date | None
    especie_controle_acionario: str | None
    data_especie_controle_acionario: date | None
    dia_encerramento_exercicio_social: int | None
    mes_encerramento_exercicio_social: int | None
    data_alteracao_exercicio_social: date | None
    pagina_web: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class FcaEnderecoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: date
    versao: int
    id_documento: int
    nome_empresarial: str | None
    tipo_endereco: str | None
    logradouro: str | None
    complemento: str | None
    bairro: str | None
    cidade: str | None
    sigla_uf: str | None
    pais: str | None
    cep: str | None
    caixa_postal: str | None
    ddi_telefone: str | None
    ddd_telefone: str | None
    telefone: str | None
    ddi_fax: str | None
    ddd_fax: str | None
    fax: str | None
    email: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class FcaDriResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: date
    versao: int
    id_documento: int
    nome_empresarial: str | None
    tipo_responsavel: str | None
    nome_dri: str | None
    cpf_responsavel: str | None
    tipo_endereco: str | None
    logradouro: str | None
    complemento: str | None
    bairro: str | None
    cidade: str | None
    sigla_uf: str | None
    uf: str | None
    pais: str | None
    cep: str | None
    ddi_telefone: str | None
    ddd_telefone: str | None
    telefone: str | None
    ddi_fax: str | None
    ddd_fax: str | None
    fax: str | None
    email_dri: str | None
    data_inicio_atuacao: date | None
    data_fim_atuacao: date | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class FcaAuditorResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: date
    versao: int
    id_documento: int
    nome_empresarial: str | None
    nome_auditor: str | None
    cpf_cnpj_auditor: str | None
    codigo_cvm_auditor: int | None
    origem_auditor: str | None
    data_inicio_atuacao_auditor: date | None
    data_fim_atuacao_auditor: date | None
    responsavel_tecnico: str | None
    cpf_responsavel_tecnico: str | None
    data_inicio_atuacao_responsavel_tecnico: date | None
    data_fim_atuacao_responsavel_tecnico: date | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class FcaValorMobiliarioResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: date
    versao: int
    id_documento: int
    nome_empresarial: str | None
    tipo_valor_mobiliario: str | None
    sigla_classe_acao_preferencial: str | None
    classe_acao_preferencial: str | None
    codigo_negociacao: str | None
    composicao_bdr_unit: str | None
    mercado: str | None
    sigla_entidade_administradora: str | None
    entidade_administradora: str | None
    data_inicio_negociacao: date | None
    data_fim_negociacao: date | None
    segmento: str | None
    data_inicio_listagem: date | None
    data_fim_listagem: date | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class FcaDepartamentoAcionistasResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    companhia_id: uuid.UUID | None
    cnpj_companhia: str
    data_referencia: date
    versao: int
    id_documento: int
    nome_empresarial: str | None
    contato: str | None
    data_inicio_contato: date | None
    data_fim_contato: date | None
    tipo_endereco: str | None
    logradouro: str | None
    complemento: str | None
    bairro: str | None
    cidade: str | None
    sigla_uf: str | None
    pais: str | None
    cep: str | None
    ddi_telefone: str | None
    ddd_telefone: str | None
    telefone: str | None
    ddi_fax: str | None
    ddd_fax: str | None
    fax: str | None
    email: str | None
    arquivo_origem: str
    ano_origem: int | None
    linha_origem: int | None
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime


class ListaFcaDocumentosResposta(BaseModel):
    dados: list[FcaDocumentoResposta] = Field(description="Lista paginada de documentos FCA.")
    paginacao: Paginacao


class ListaFcaGeralResposta(BaseModel):
    dados: list[FcaGeralResposta] = Field(description="Lista paginada de dados gerais FCA.")
    paginacao: Paginacao


class ListaFcaEnderecosResposta(BaseModel):
    dados: list[FcaEnderecoResposta] = Field(description="Lista paginada de enderecos FCA.")
    paginacao: Paginacao


class ListaFcaDriResposta(BaseModel):
    dados: list[FcaDriResposta] = Field(description="Lista paginada de registros DRI FCA.")
    paginacao: Paginacao


class ListaFcaAuditoresResposta(BaseModel):
    dados: list[FcaAuditorResposta] = Field(description="Lista paginada de auditores FCA.")
    paginacao: Paginacao


class ListaFcaValoresMobiliariosResposta(BaseModel):
    dados: list[FcaValorMobiliarioResposta] = Field(description="Lista paginada de valores mobiliarios FCA.")
    paginacao: Paginacao


class ListaFcaDepartamentoAcionistasResposta(BaseModel):
    dados: list[FcaDepartamentoAcionistasResposta] = Field(
        description="Lista paginada de departamentos de atendimento a acionistas FCA."
    )
    paginacao: Paginacao
