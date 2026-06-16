import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FcaDocumento(Base):
    __tablename__ = "fca_documentos"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            name="uq_fca_documentos_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    denominacao_companhia: Mapped[str | None] = mapped_column(String(255))
    categoria_documento: Mapped[str | None] = mapped_column(String(255))
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    data_recebimento: Mapped[date | None] = mapped_column(Date)
    link_documento: Mapped[str | None] = mapped_column(String(1000))
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FcaGeral(Base):
    __tablename__ = "fca_geral"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            name="uq_fca_geral_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_empresarial: Mapped[str | None] = mapped_column(String(255))
    data_nome_empresarial: Mapped[date | None] = mapped_column(Date)
    nome_empresarial_anterior: Mapped[str | None] = mapped_column(String(255))
    data_constituicao: Mapped[date | None] = mapped_column(Date)
    data_registro_cvm: Mapped[date | None] = mapped_column(Date)
    categoria_registro_cvm: Mapped[str | None] = mapped_column(String(100))
    data_categoria_registro_cvm: Mapped[date | None] = mapped_column(Date)
    situacao_registro_cvm: Mapped[str | None] = mapped_column(String(100))
    data_situacao_registro_cvm: Mapped[date | None] = mapped_column(Date)
    pais_origem: Mapped[str | None] = mapped_column(String(100))
    pais_custodia_valores_mobiliarios: Mapped[str | None] = mapped_column(String(100))
    setor_atividade: Mapped[str | None] = mapped_column(String(255))
    descricao_atividade: Mapped[str | None] = mapped_column(Text)
    situacao_emissor: Mapped[str | None] = mapped_column(String(100))
    data_situacao_emissor: Mapped[date | None] = mapped_column(Date)
    especie_controle_acionario: Mapped[str | None] = mapped_column(String(100))
    data_especie_controle_acionario: Mapped[date | None] = mapped_column(Date)
    dia_encerramento_exercicio_social: Mapped[int | None] = mapped_column(Integer)
    mes_encerramento_exercicio_social: Mapped[int | None] = mapped_column(Integer)
    data_alteracao_exercicio_social: Mapped[date | None] = mapped_column(Date)
    pagina_web: Mapped[str | None] = mapped_column(String(1000))
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FcaEndereco(Base):
    __tablename__ = "fca_enderecos"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "tipo_endereco",
            "logradouro",
            "cep",
            name="uq_fca_enderecos_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_empresarial: Mapped[str | None] = mapped_column(String(255))
    tipo_endereco: Mapped[str | None] = mapped_column(String(100), index=True)
    logradouro: Mapped[str | None] = mapped_column(String(255))
    complemento: Mapped[str | None] = mapped_column(String(255))
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(100))
    sigla_uf: Mapped[str | None] = mapped_column(String(5))
    pais: Mapped[str | None] = mapped_column(String(100), index=True)
    cep: Mapped[str | None] = mapped_column(String(20))
    caixa_postal: Mapped[str | None] = mapped_column(String(50))
    ddi_telefone: Mapped[str | None] = mapped_column(String(10))
    ddd_telefone: Mapped[str | None] = mapped_column(String(10))
    telefone: Mapped[str | None] = mapped_column(String(50))
    ddi_fax: Mapped[str | None] = mapped_column(String(10))
    ddd_fax: Mapped[str | None] = mapped_column(String(10))
    fax: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FcaDri(Base):
    __tablename__ = "fca_dri"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "cpf_responsavel",
            "tipo_responsavel",
            "data_inicio_atuacao",
            "tipo_endereco",
            "logradouro",
            "cep",
            "telefone",
            "email_dri",
            name="uq_fca_dri_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_empresarial: Mapped[str | None] = mapped_column(String(255))
    tipo_responsavel: Mapped[str | None] = mapped_column(String(100))
    nome_dri: Mapped[str | None] = mapped_column(String(255), index=True)
    cpf_responsavel: Mapped[str | None] = mapped_column(String(20))
    tipo_endereco: Mapped[str | None] = mapped_column(String(100))
    logradouro: Mapped[str | None] = mapped_column(String(255))
    complemento: Mapped[str | None] = mapped_column(String(255))
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(100))
    sigla_uf: Mapped[str | None] = mapped_column(String(5))
    uf: Mapped[str | None] = mapped_column(String(100))
    pais: Mapped[str | None] = mapped_column(String(100))
    cep: Mapped[str | None] = mapped_column(String(20))
    ddi_telefone: Mapped[str | None] = mapped_column(String(10))
    ddd_telefone: Mapped[str | None] = mapped_column(String(10))
    telefone: Mapped[str | None] = mapped_column(String(50))
    ddi_fax: Mapped[str | None] = mapped_column(String(10))
    ddd_fax: Mapped[str | None] = mapped_column(String(10))
    fax: Mapped[str | None] = mapped_column(String(50))
    email_dri: Mapped[str | None] = mapped_column(String(255), index=True)
    data_inicio_atuacao: Mapped[date | None] = mapped_column(Date)
    data_fim_atuacao: Mapped[date | None] = mapped_column(Date)
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FcaAuditor(Base):
    __tablename__ = "fca_auditores"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "cpf_cnpj_auditor",
            "codigo_cvm_auditor",
            "data_inicio_atuacao_auditor",
            "data_fim_atuacao_auditor",
            "responsavel_tecnico",
            "cpf_responsavel_tecnico",
            "data_inicio_atuacao_responsavel_tecnico",
            name="uq_fca_auditores_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_empresarial: Mapped[str | None] = mapped_column(String(255))
    nome_auditor: Mapped[str | None] = mapped_column(String(255), index=True)
    cpf_cnpj_auditor: Mapped[str | None] = mapped_column(String(20))
    codigo_cvm_auditor: Mapped[str | None] = mapped_column(String(20), index=True)
    origem_auditor: Mapped[str | None] = mapped_column(String(100))
    data_inicio_atuacao_auditor: Mapped[date | None] = mapped_column(Date)
    data_fim_atuacao_auditor: Mapped[date | None] = mapped_column(Date)
    responsavel_tecnico: Mapped[str | None] = mapped_column(String(255))
    cpf_responsavel_tecnico: Mapped[str | None] = mapped_column(String(20))
    data_inicio_atuacao_responsavel_tecnico: Mapped[date | None] = mapped_column(Date)
    data_fim_atuacao_responsavel_tecnico: Mapped[date | None] = mapped_column(Date)
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FcaValorMobiliario(Base):
    __tablename__ = "fca_valores_mobiliarios"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "tipo_valor_mobiliario",
            "codigo_negociacao",
            "mercado",
            "sigla_classe_acao_preferencial",
            "classe_acao_preferencial",
            "composicao_bdr_unit",
            "data_inicio_negociacao",
            "data_fim_negociacao",
            "data_inicio_listagem",
            "data_fim_listagem",
            name="uq_fca_valores_mobiliarios_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_empresarial: Mapped[str | None] = mapped_column(String(255))
    tipo_valor_mobiliario: Mapped[str | None] = mapped_column(String(255), index=True)
    sigla_classe_acao_preferencial: Mapped[str | None] = mapped_column(String(20))
    classe_acao_preferencial: Mapped[str | None] = mapped_column(String(100))
    codigo_negociacao: Mapped[str | None] = mapped_column(String(100))
    composicao_bdr_unit: Mapped[str | None] = mapped_column(String(255))
    mercado: Mapped[str | None] = mapped_column(String(100))
    sigla_entidade_administradora: Mapped[str | None] = mapped_column(String(50))
    entidade_administradora: Mapped[str | None] = mapped_column(String(255))
    data_inicio_negociacao: Mapped[date | None] = mapped_column(Date)
    data_fim_negociacao: Mapped[date | None] = mapped_column(Date)
    segmento: Mapped[str | None] = mapped_column(String(100))
    data_inicio_listagem: Mapped[date | None] = mapped_column(Date)
    data_fim_listagem: Mapped[date | None] = mapped_column(Date)
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FcaDepartamentoAcionistas(Base):
    __tablename__ = "fca_departamentos_acionistas"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "contato",
            "email",
            "tipo_endereco",
            name="uq_fca_departamentos_acionistas_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_empresarial: Mapped[str | None] = mapped_column(String(255))
    contato: Mapped[str | None] = mapped_column(String(255), index=True)
    data_inicio_contato: Mapped[date | None] = mapped_column(Date)
    data_fim_contato: Mapped[date | None] = mapped_column(Date)
    tipo_endereco: Mapped[str | None] = mapped_column(String(100), index=True)
    logradouro: Mapped[str | None] = mapped_column(String(255))
    complemento: Mapped[str | None] = mapped_column(String(255))
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(100))
    sigla_uf: Mapped[str | None] = mapped_column(String(5), index=True)
    pais: Mapped[str | None] = mapped_column(String(100), index=True)
    cep: Mapped[str | None] = mapped_column(String(20))
    ddi_telefone: Mapped[str | None] = mapped_column(String(10))
    ddd_telefone: Mapped[str | None] = mapped_column(String(10))
    telefone: Mapped[str | None] = mapped_column(String(50))
    ddi_fax: Mapped[str | None] = mapped_column(String(10))
    ddd_fax: Mapped[str | None] = mapped_column(String(10))
    fax: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
