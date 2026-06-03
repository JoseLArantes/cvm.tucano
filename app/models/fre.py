import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FreDocumento(Base):
    __tablename__ = "fre_documentos"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            name="uq_fre_documentos_chave_natural",
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
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    alterado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class FreAuditor(Base):
    __tablename__ = "fre_auditores"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_auditor",
            name="uq_fre_auditores_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(String(255))
    id_auditor: Mapped[int] = mapped_column(Integer, index=True)
    auditor: Mapped[str | None] = mapped_column(String(255))
    cpf_auditor: Mapped[str | None] = mapped_column(String(20))
    cnpj_auditor: Mapped[str | None] = mapped_column(String(14))
    codigo_cvm_auditor: Mapped[int | None] = mapped_column(Integer)
    tipo_origem_auditor: Mapped[str | None] = mapped_column(String(255))
    data_inicio_contratacao: Mapped[date | None] = mapped_column(Date)
    data_fim_contratacao: Mapped[date | None] = mapped_column(Date)
    data_inicio_prestacao_servico: Mapped[date | None] = mapped_column(Date)
    servico_contratado: Mapped[str | None] = mapped_column(Text)
    remuneracao_auditor: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    justificativa_substituicao: Mapped[str | None] = mapped_column(Text)
    razao_apresentada: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreCapitalSocial(Base):
    __tablename__ = "fre_capital_social"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_capital_social",
            name="uq_fre_capital_social_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(String(255))
    id_capital_social: Mapped[int] = mapped_column(Integer, index=True)
    tipo_capital: Mapped[str | None] = mapped_column(String(255))
    data_autorizacao_aprovacao: Mapped[date | None] = mapped_column(Date)
    valor_capital: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    prazo_integralizacao: Mapped[str | None] = mapped_column(String(255))
    quantidade_acoes_ordinarias: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_acoes_preferenciais: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_total_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FrePosicaoAcionaria(Base):
    __tablename__ = "fre_posicoes_acionarias"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_acionista",
            name="uq_fre_posicoes_acionarias_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(String(255))
    id_acionista: Mapped[int] = mapped_column(Integer, index=True)
    acionista: Mapped[str | None] = mapped_column(String(255))
    tipo_pessoa_acionista: Mapped[str | None] = mapped_column(String(100))
    cpf_cnpj_acionista: Mapped[str | None] = mapped_column(String(20))
    id_acionista_relacionado: Mapped[int | None] = mapped_column(Integer)
    acionista_relacionado: Mapped[str | None] = mapped_column(String(255))
    tipo_pessoa_acionista_relacionado: Mapped[str | None] = mapped_column(String(100))
    cpf_cnpj_acionista_relacionado: Mapped[str | None] = mapped_column(String(20))
    quantidade_acao_ordinaria_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_acao_ordinaria_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    quantidade_acao_preferencial_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_acao_preferencial_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    quantidade_total_acoes_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_total_acoes_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    nacionalidade: Mapped[str | None] = mapped_column(String(100))
    sigla_uf: Mapped[str | None] = mapped_column(String(5))
    residente_exterior: Mapped[bool | None] = mapped_column(Boolean)
    representante_legal: Mapped[str | None] = mapped_column(String(255))
    tipo_pessoa_representante_legal: Mapped[str | None] = mapped_column(String(100))
    cpf_cnpj_representante_legal: Mapped[str | None] = mapped_column(String(20))
    data_composicao_capital_social: Mapped[date | None] = mapped_column(Date)
    data_ultima_alteracao: Mapped[date | None] = mapped_column(Date)
    acionista_controlador: Mapped[bool | None] = mapped_column(Boolean)
    participante_acordo_acionistas: Mapped[bool | None] = mapped_column(Boolean)

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreRemuneracaoTotalOrgao(Base):
    __tablename__ = "fre_remuneracoes_totais_orgaos"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "orgao_administracao",
            "data_inicio_exercicio_social",
            "data_fim_exercicio_social",
            name="uq_fre_remuneracoes_totais_orgaos_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(String(255))
    data_inicio_exercicio_social: Mapped[date | None] = mapped_column(Date)
    data_fim_exercicio_social: Mapped[date | None] = mapped_column(Date)
    total_remuneracao: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    orgao_administracao: Mapped[str | None] = mapped_column(String(255))
    numero_membros: Mapped[int | None] = mapped_column(Integer)
    total_remuneracao_orgao: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    numero_membros_remunerados: Mapped[int | None] = mapped_column(Integer)
    salario: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    beneficios_diretos_indiretos: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    participacoes_comites: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    outros_valores_fixos: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    descricao_outros_remuneracoes_fixas: Mapped[str | None] = mapped_column(Text)
    bonus: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    participacao_resultados: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    participacao_reunioes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    outros_valores_variaveis: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    comissoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    descricao_outros_remuneracoes_variaveis: Mapped[str | None] = mapped_column(Text)
    pos_emprego: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    cessacao_cargo: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    baseada_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    observacao: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreEmpregadoPosicaoGenero(Base):
    __tablename__ = "fre_empregados_posicao_genero"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "posicao",
            name="uq_fre_empregados_posicao_genero_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(String(255))
    posicao: Mapped[str] = mapped_column(String(255), index=True)
    quantidade_feminino: Mapped[int | None] = mapped_column(Integer)
    quantidade_masculino: Mapped[int | None] = mapped_column(Integer)
    quantidade_nao_binario: Mapped[int | None] = mapped_column(Integer)
    quantidade_outros: Mapped[int | None] = mapped_column(Integer)
    quantidade_sem_resposta: Mapped[int | None] = mapped_column(Integer)

    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
