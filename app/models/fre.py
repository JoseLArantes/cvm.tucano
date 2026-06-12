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
    denominacao_companhia: Mapped[str | None] = mapped_column(Text)
    categoria_documento: Mapped[str | None] = mapped_column(Text)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    data_recebimento: Mapped[date | None] = mapped_column(Date)
    link_documento: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_auditor: Mapped[int] = mapped_column(Integer, index=True)
    auditor: Mapped[str | None] = mapped_column(Text)
    cpf_auditor: Mapped[str | None] = mapped_column(String(20))
    cnpj_auditor: Mapped[str | None] = mapped_column(String(14))
    codigo_cvm_auditor: Mapped[int | None] = mapped_column(Integer)
    tipo_origem_auditor: Mapped[str | None] = mapped_column(Text)
    data_inicio_contratacao: Mapped[date | None] = mapped_column(Date)
    data_fim_contratacao: Mapped[date | None] = mapped_column(Date)
    data_inicio_prestacao_servico: Mapped[date | None] = mapped_column(Date)
    servico_contratado: Mapped[str | None] = mapped_column(Text)
    remuneracao_auditor: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    justificativa_substituicao: Mapped[str | None] = mapped_column(Text)
    razao_apresentada: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_capital_social: Mapped[int] = mapped_column(Integer, index=True)
    tipo_capital: Mapped[str | None] = mapped_column(Text)
    data_autorizacao_aprovacao: Mapped[date | None] = mapped_column(Date)
    valor_capital: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    prazo_integralizacao: Mapped[str | None] = mapped_column(Text)
    quantidade_acoes_ordinarias: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_acoes_preferenciais: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_total_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))

    arquivo_origem: Mapped[str] = mapped_column(Text)
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
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_acionista: Mapped[int] = mapped_column(Integer, index=True)
    acionista: Mapped[str | None] = mapped_column(Text)
    tipo_pessoa_acionista: Mapped[str | None] = mapped_column(Text)
    cpf_cnpj_acionista: Mapped[str | None] = mapped_column(String(20))
    id_acionista_relacionado: Mapped[int | None] = mapped_column(Integer)
    acionista_relacionado: Mapped[str | None] = mapped_column(Text)
    tipo_pessoa_acionista_relacionado: Mapped[str | None] = mapped_column(Text)
    cpf_cnpj_acionista_relacionado: Mapped[str | None] = mapped_column(String(20))
    quantidade_acao_ordinaria_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_acao_ordinaria_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    quantidade_acao_preferencial_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_acao_preferencial_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    quantidade_total_acoes_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_total_acoes_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    nacionalidade: Mapped[str | None] = mapped_column(Text)
    sigla_uf: Mapped[str | None] = mapped_column(String(5))
    residente_exterior: Mapped[bool | None] = mapped_column(Boolean)
    representante_legal: Mapped[str | None] = mapped_column(Text)
    tipo_pessoa_representante_legal: Mapped[str | None] = mapped_column(Text)
    cpf_cnpj_representante_legal: Mapped[str | None] = mapped_column(String(20))
    data_composicao_capital_social: Mapped[date | None] = mapped_column(Date)
    data_ultima_alteracao: Mapped[date | None] = mapped_column(Date)
    acionista_controlador: Mapped[bool | None] = mapped_column(Boolean)
    participante_acordo_acionistas: Mapped[bool | None] = mapped_column(Boolean)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    data_inicio_exercicio_social: Mapped[date | None] = mapped_column(Date)
    data_fim_exercicio_social: Mapped[date | None] = mapped_column(Date)
    total_remuneracao: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    orgao_administracao: Mapped[str | None] = mapped_column(Text)
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

    arquivo_origem: Mapped[str] = mapped_column(Text)
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
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    posicao: Mapped[str] = mapped_column(Text, index=True)
    quantidade_feminino: Mapped[int | None] = mapped_column(Integer)
    quantidade_masculino: Mapped[int | None] = mapped_column(Integer)
    quantidade_nao_binario: Mapped[int | None] = mapped_column(Integer)
    quantidade_outros: Mapped[int | None] = mapped_column(Integer)
    quantidade_sem_resposta: Mapped[int | None] = mapped_column(Integer)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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


class FreParticipacaoSociedade(Base):
    __tablename__ = "fre_participacoes_sociedades"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_sociedade",
            name="uq_fre_participacoes_sociedades_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_sociedade: Mapped[int] = mapped_column(Integer, index=True)
    razao_social: Mapped[str | None] = mapped_column(Text)
    cnpj: Mapped[str | None] = mapped_column(String(14))
    tipo_sociedade: Mapped[str | None] = mapped_column(Text)
    descricao_atividades: Mapped[str | None] = mapped_column(Text)
    pais_sede: Mapped[str | None] = mapped_column(Text)
    uf_sede: Mapped[str | None] = mapped_column(String(5))
    municipio_sede: Mapped[str | None] = mapped_column(Text)
    participacao_emissor: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    possui_registro_cvm: Mapped[bool | None] = mapped_column(Boolean)
    codigo_cvm: Mapped[int | None] = mapped_column(Integer, index=True)
    razao_aquisicao_manutencao: Mapped[str | None] = mapped_column(Text)
    data_valor_mercado: Mapped[date | None] = mapped_column(Date)
    data_valor_contabil: Mapped[date | None] = mapped_column(Date)
    valor_mercado: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    valor_contabil: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
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


class FreEmpregadoPosicaoLocal(Base):
    __tablename__ = "fre_empregados_posicao_local"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "posicao",
            name="uq_fre_empregados_posicao_local_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    posicao: Mapped[str] = mapped_column(Text, index=True)
    quantidade_norte: Mapped[int | None] = mapped_column(Integer)
    quantidade_nordeste: Mapped[int | None] = mapped_column(Integer)
    quantidade_centro_oeste: Mapped[int | None] = mapped_column(Integer)
    quantidade_sudeste: Mapped[int | None] = mapped_column(Integer)
    quantidade_sul: Mapped[int | None] = mapped_column(Integer)
    quantidade_exterior: Mapped[int | None] = mapped_column(Integer)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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


class FreEmpregadoPosicaoFaixaEtaria(Base):
    __tablename__ = "fre_empregados_posicao_faixa_etaria"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "posicao",
            name="uq_fre_empregados_posicao_faixa_etaria_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    posicao: Mapped[str] = mapped_column(Text, index=True)
    quantidade_ate_30_anos: Mapped[int | None] = mapped_column(Integer)
    quantidade_30_a_50_anos: Mapped[int | None] = mapped_column(Integer)
    quantidade_acima_50_anos: Mapped[int | None] = mapped_column(Integer)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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


class FreEmpregadoPosicaoDeclaracaoRaca(Base):
    __tablename__ = "fre_empregados_posicao_declaracao_raca"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "posicao",
            name="uq_fre_empregados_posicao_declaracao_raca_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    posicao: Mapped[str] = mapped_column(Text, index=True)
    quantidade_amarelo: Mapped[int | None] = mapped_column(Integer)
    quantidade_branco: Mapped[int | None] = mapped_column(Integer)
    quantidade_preto: Mapped[int | None] = mapped_column(Integer)
    quantidade_pardo: Mapped[int | None] = mapped_column(Integer)
    quantidade_indigena: Mapped[int | None] = mapped_column(Integer)
    quantidade_outros: Mapped[int | None] = mapped_column(Integer)
    quantidade_sem_resposta: Mapped[int | None] = mapped_column(Integer)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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


class FreEmpregadoPcd(Base):
    __tablename__ = "fre_empregados_pcd"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "codigo_posicao",
            "posicao",
            name="uq_fre_empregados_pcd_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    codigo_posicao: Mapped[int | None] = mapped_column(Integer, index=True)
    posicao: Mapped[str] = mapped_column(Text, index=True)
    quantidade_pcd: Mapped[int | None] = mapped_column(Integer)
    quantidade_nao_pcd: Mapped[int | None] = mapped_column(Integer)
    quantidade_sem_resposta: Mapped[int | None] = mapped_column(Integer)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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


class FreEmpregadoLocalFaixaEtaria(Base):
    __tablename__ = "fre_empregados_local_faixa_etaria"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "local",
            name="uq_fre_empregados_local_faixa_etaria_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    local: Mapped[str] = mapped_column(Text, index=True)
    quantidade_ate_30_anos: Mapped[int | None] = mapped_column(Integer)
    quantidade_30_a_50_anos: Mapped[int | None] = mapped_column(Integer)
    quantidade_acima_50_anos: Mapped[int | None] = mapped_column(Integer)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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


class FreEmpregadoLocalDeclaracaoRaca(Base):
    __tablename__ = "fre_empregados_local_declaracao_raca"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "local",
            name="uq_fre_empregados_local_declaracao_raca_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    local: Mapped[str] = mapped_column(Text, index=True)
    quantidade_amarelo: Mapped[int | None] = mapped_column(Integer)
    quantidade_branco: Mapped[int | None] = mapped_column(Integer)
    quantidade_preto: Mapped[int | None] = mapped_column(Integer)
    quantidade_pardo: Mapped[int | None] = mapped_column(Integer)
    quantidade_indigena: Mapped[int | None] = mapped_column(Integer)
    quantidade_outros: Mapped[int | None] = mapped_column(Integer)
    quantidade_sem_resposta: Mapped[int | None] = mapped_column(Integer)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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


class FreEmpregadoLocalDeclaracaoGenero(Base):
    __tablename__ = "fre_empregados_local_declaracao_genero"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "local",
            name="uq_fre_empregados_local_declaracao_genero_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    local: Mapped[str] = mapped_column(Text, index=True)
    quantidade_feminino: Mapped[int | None] = mapped_column(Integer)
    quantidade_masculino: Mapped[int | None] = mapped_column(Integer)
    quantidade_nao_binario: Mapped[int | None] = mapped_column(Integer)
    quantidade_outros: Mapped[int | None] = mapped_column(Integer)
    quantidade_sem_resposta: Mapped[int | None] = mapped_column(Integer)

    arquivo_origem: Mapped[str] = mapped_column(Text)
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


class FreResponsavel(Base):
    __tablename__ = "fre_responsaveis"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome_responsavel",
            "cargo_responsavel",
            name="uq_fre_responsaveis_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    nome_responsavel: Mapped[str | None] = mapped_column(Text)
    cargo_responsavel: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreCapitalSocialClasseAcao(Base):
    __tablename__ = "fre_capital_social_classes_acoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_capital_social",
            "tipo_classe_acao_preferencial",
            name="uq_fre_cap_social_classes_acoes_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_capital_social: Mapped[int] = mapped_column(Integer, index=True)
    tipo_classe_acao_preferencial: Mapped[str | None] = mapped_column(Text)
    quantidade_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreCapitalSocialTituloConversivel(Base):
    __tablename__ = "fre_capital_social_titulos_conversiveis"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_capital_social",
            "titulo_conversivel_acao",
            name="uq_fre_cap_social_tit_conv_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_capital_social: Mapped[int] = mapped_column(Integer, index=True)
    titulo_conversivel_acao: Mapped[str | None] = mapped_column(Text)
    condicoes_conversao: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreDistribuicaoCapital(Base):
    __tablename__ = "fre_distribuicao_capital"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            name="uq_fre_distribuicao_capital_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    data_ultima_assembleia: Mapped[date | None] = mapped_column(Date)
    quantidade_acoes_ordinarias_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_acoes_ordinarias_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    quantidade_acoes_preferenciais_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_acoes_preferenciais_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    quantidade_total_acoes_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_total_acoes_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    quantidade_acionistas_pf: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_acionistas_pj: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_acionistas_investidores_institucionais: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreDistribuicaoCapitalClasseAcao(Base):
    __tablename__ = "fre_distribuicao_capital_classes_acoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "sigla_classe_acoes_preferenciais",
            name="uq_fre_dist_capital_classes_acoes_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    classe_acoes_preferenciais: Mapped[str | None] = mapped_column(Text)
    sigla_classe_acoes_preferenciais: Mapped[str | None] = mapped_column(String(50))
    quantidade_acoes_preferenciais_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_acoes_preferenciais_circulacao: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FrePosicaoAcionariaClasseAcao(Base):
    __tablename__ = "fre_posicoes_acionarias_classes_acoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_acionista",
            "tipo_classe_acao_preferencial",
            name="uq_fre_posicoes_acionarias_classes_acoes_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_acionista: Mapped[int] = mapped_column(Integer, index=True)
    tipo_classe_acao_preferencial: Mapped[str | None] = mapped_column(Text)
    quantidade_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    percentual_acoes: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreRemuneracaoMaximaMinimaMedia(Base):
    __tablename__ = "fre_remuneracoes_maximas_minimas_medias"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "orgao_administracao",
            "data_inicio_exercicio_social",
            "data_fim_exercicio_social",
            name="uq_fre_remun_max_min_med_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    data_inicio_exercicio_social: Mapped[date | None] = mapped_column(Date)
    data_fim_exercicio_social: Mapped[date | None] = mapped_column(Date)
    orgao_administracao: Mapped[str | None] = mapped_column(Text)
    numero_membros: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    numero_membros_remunerados: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    valor_maior_remuneracao: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    valor_medio_remuneracao: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    valor_menor_remuneracao: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    observacao: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreRemuneracaoVariavel(Base):
    __tablename__ = "fre_remuneracoes_variaveis"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "orgao_administracao",
            "data_inicio_exercicio_social",
            "data_fim_exercicio_social",
            name="uq_fre_remuneracoes_variaveis_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    data_inicio_exercicio_social: Mapped[date | None] = mapped_column(Date)
    data_fim_exercicio_social: Mapped[date | None] = mapped_column(Date)
    orgao_administracao: Mapped[str | None] = mapped_column(Text)
    quantidade_total_membros: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_membros_remunerados: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    bonus_valor_minimo: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    bonus_valor_maximo: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    bonus_valor_metas_atingidas: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    bonus_valor_efetivo: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    participacao_valor_minimo: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    participacao_valor_maximo: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    participacao_valor_metas_atingidas: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    participacao_valor_efetivo: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreRemuneracaoAcao(Base):
    __tablename__ = "fre_remuneracoes_acoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "orgao_administracao",
            "data_inicio_exercicio_social",
            "data_fim_exercicio_social",
            name="uq_fre_remuneracoes_acoes_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    data_inicio_exercicio_social: Mapped[date | None] = mapped_column(Date)
    data_fim_exercicio_social: Mapped[date | None] = mapped_column(Date)
    orgao_administracao: Mapped[str | None] = mapped_column(Text)
    quantidade_total_membros: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_membros_remunerados: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    preco_medio_ponderado_opcoes_em_aberto: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    preco_medio_ponderado_opcoes_exercidas: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    preco_medio_ponderado_opcoes_perdidas: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    diluicao_potencial: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreAcaoEntregue(Base):
    __tablename__ = "fre_acoes_entregues"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "orgao_administracao",
            "data_inicio_exercicio_social",
            "data_fim_exercicio_social",
            name="uq_fre_acoes_entregues_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    data_inicio_exercicio_social: Mapped[date | None] = mapped_column(Date)
    data_fim_exercicio_social: Mapped[date | None] = mapped_column(Date)
    orgao_administracao: Mapped[str | None] = mapped_column(Text)
    quantidade_total_membros: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_membros_remunerados: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    quantidade_acoes: Mapped[int | None] = mapped_column(Integer)
    preco_medio_ponderado_aquisicao: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    preco_medio_ponderado_mercado: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    valor_diferenca_aquisicao_mercado: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreAdministradorMembroConselhoFiscal(Base):
    __tablename__ = "fre_administradores_membros_conselho_fiscal"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome",
            "cpf",
            "orgao_administracao",
            name="uq_fre_admin_memb_cons_fisc_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    orgao_administracao: Mapped[str | None] = mapped_column(Text)
    nome: Mapped[str] = mapped_column(Text, index=True)
    cpf: Mapped[str | None] = mapped_column(String(20))
    profissao: Mapped[str | None] = mapped_column(Text)
    cargo_eletivo_ocupado: Mapped[str | None] = mapped_column(Text)
    complemento_cargo_eletivo_ocupado: Mapped[str | None] = mapped_column(Text)
    data_eleicao: Mapped[date | None] = mapped_column(Date)
    data_posse: Mapped[date | None] = mapped_column(Date)
    data_inicio_primeiro_mandato: Mapped[date | None] = mapped_column(Date)
    prazo_mandato: Mapped[str | None] = mapped_column(Text)
    eleito_controlador: Mapped[str | None] = mapped_column(String(50))
    outro_cargo_funcao: Mapped[str | None] = mapped_column(Text)
    experiencia_profissional: Mapped[str | None] = mapped_column(Text)
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    numero_mandatos_consecutivos: Mapped[int | None] = mapped_column(Integer)
    percentual_participacao_reunioes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreMembroComite(Base):
    __tablename__ = "fre_membros_comites"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome",
            "cpf",
            "tipo_comite",
            name="uq_fre_membros_comites_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    nome: Mapped[str] = mapped_column(Text, index=True)
    cpf: Mapped[str | None] = mapped_column(String(20))
    profissao: Mapped[str | None] = mapped_column(Text)
    tipo_comite: Mapped[str | None] = mapped_column(Text, index=True)
    descricao_outros_comites: Mapped[str | None] = mapped_column(Text)
    cargo_ocupado: Mapped[str | None] = mapped_column(Text)
    descricao_outro_cargo_ocupado: Mapped[str | None] = mapped_column(Text)
    data_eleicao: Mapped[date | None] = mapped_column(Date)
    data_posse: Mapped[date | None] = mapped_column(Date)
    data_inicio_primeiro_mandato: Mapped[date | None] = mapped_column(Date)
    prazo_mandato: Mapped[str | None] = mapped_column(Text)
    outro_cargo_funcao: Mapped[str | None] = mapped_column(Text)
    experiencia_profissional: Mapped[str | None] = mapped_column(Text)
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    numero_mandatos_consecutivos: Mapped[int | None] = mapped_column(Integer)
    percentual_participacao_reunioes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreRelacaoFamiliar(Base):
    __tablename__ = "fre_relacoes_familiares"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome_administrador",
            "nome_pessoa_relacionada",
            "tipo_parentesco",
            name="uq_fre_relacoes_familiares_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    nome_administrador: Mapped[str] = mapped_column(Text, index=True)
    cpf_administrador: Mapped[str | None] = mapped_column(String(20))
    nome_emissor: Mapped[str | None] = mapped_column(Text)
    cnpj_emissor: Mapped[str | None] = mapped_column(String(14))
    cargo_administrador: Mapped[str | None] = mapped_column(Text)
    nome_pessoa_relacionada: Mapped[str] = mapped_column(Text, index=True)
    cpf_pessoa_relacionada: Mapped[str | None] = mapped_column(String(20))
    nome_emissor_pessoa_relacionada: Mapped[str | None] = mapped_column(Text)
    cnpj_emissor_pessoa_relacionada: Mapped[str | None] = mapped_column(String(14))
    cargo_Pessoa_relacionada: Mapped[str | None] = mapped_column(Text)
    tipo_parentesco: Mapped[str | None] = mapped_column(Text, index=True)
    observacao: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreRelacaoSubordinacao(Base):
    __tablename__ = "fre_relacoes_subordinacao"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome_administrador",
            "nome_pessoa_relacionada",
            "tipo_relacao",
            name="uq_fre_relacoes_subordinacao_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    data_inicio_exercicio_social: Mapped[date | None] = mapped_column(Date)
    data_fim_exercicio_social: Mapped[date | None] = mapped_column(Date)
    nome_administrador: Mapped[str] = mapped_column(Text, index=True)
    cpf_administrador: Mapped[str | None] = mapped_column(String(20))
    cargo_administrador: Mapped[str | None] = mapped_column(Text)
    nome_pessoa_relacionada: Mapped[str] = mapped_column(Text, index=True)
    tipo_pessoa_relacionada: Mapped[str | None] = mapped_column(Text)
    documento_pessoa_relacionada: Mapped[str | None] = mapped_column(String(20))
    cargo_pessoa_relacionada: Mapped[str | None] = mapped_column(Text)
    categoria_pessoa_relacionada: Mapped[str | None] = mapped_column(Text)
    tipo_relacao: Mapped[str | None] = mapped_column(Text, index=True)
    observacao: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreTransacaoParteRelacionada(Base):
    __tablename__ = "fre_transacoes_partes_relacionadas"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "parte_relacionada",
            "relacao_emissor",
            "data_transacao",
            name="uq_fre_transacoes_partes_relac_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    parte_relacionada: Mapped[str] = mapped_column(Text, index=True)
    tipo_pessoa: Mapped[str | None] = mapped_column(Text)
    documento_parte_relacionada: Mapped[str | None] = mapped_column(String(20))
    relacao_emissor: Mapped[str | None] = mapped_column(Text, index=True)
    data_transacao: Mapped[date | None] = mapped_column(Date)
    objeto_contrato: Mapped[str | None] = mapped_column(Text)
    montante_envolvido: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    saldo_existente: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    montante_interesse_parte_relacionada: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    garantia_seguro: Mapped[str | None] = mapped_column(Text)
    duracao_transacao: Mapped[str | None] = mapped_column(Text)
    emprestimo_divida: Mapped[str | None] = mapped_column(Text)
    rescisao: Mapped[str | None] = mapped_column(Text)
    natureza_razao_operacao: Mapped[str | None] = mapped_column(Text)
    taxa_juros: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    posicao_contratual_emissor: Mapped[str | None] = mapped_column(Text)
    especificacao_posicao_contratual_emissor: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreCapitalSocialAumento(Base):
    __tablename__ = "fre_capital_social_aumentos"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_capital_social",
            name="uq_fre_capital_social_aumentos_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_capital_social: Mapped[int] = mapped_column(Integer, index=True)
    data_deliberacao: Mapped[date | None] = mapped_column(Date)
    valor_aumento: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    origem_aumento: Mapped[str | None] = mapped_column(Text)
    quantidade_acoes_ordinarias: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    quantidade_acoes_preferenciais: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    quantidade_total_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreCapitalSocialAumentoClasseAcao(Base):
    __tablename__ = "fre_capital_social_aumento_classes_acoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_capital_social",
            "tipo_classe_acao_preferencial",
            name="uq_fre_cap_soc_aumento_classes_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_capital_social: Mapped[int] = mapped_column(Integer, index=True)
    tipo_classe_acao_preferencial: Mapped[str] = mapped_column(Text, index=True)
    quantidade_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreCapitalSocialDesdobramento(Base):
    __tablename__ = "fre_capital_social_desdobramentos"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_capital_social",
            name="uq_fre_capital_social_desdobramentos_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_capital_social: Mapped[int] = mapped_column(Integer, index=True)
    data_deliberacao: Mapped[date | None] = mapped_column(Date)
    tipo_desdobramento: Mapped[str | None] = mapped_column(Text)
    proporcao_acoes_novas: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    proporcao_acoes_antigas: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    quantidade_acoes_ordinarias: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    quantidade_acoes_preferenciais: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    quantidade_total_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreCapitalSocialDesdobramentoClasseAcao(Base):
    __tablename__ = "fre_capital_social_desdobramento_classes_acoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_capital_social",
            "tipo_classe_acao_preferencial",
            name="uq_fre_cap_soc_desdob_classes_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_capital_social: Mapped[int] = mapped_column(Integer, index=True)
    tipo_classe_acao_preferencial: Mapped[str] = mapped_column(Text, index=True)
    quantidade_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreCapitalSocialReducao(Base):
    __tablename__ = "fre_capital_social_reducoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_capital_social",
            name="uq_fre_capital_social_reducoes_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_capital_social: Mapped[int] = mapped_column(Integer, index=True)
    data_deliberacao: Mapped[date | None] = mapped_column(Date)
    valor_reducao: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    motivo_reducao: Mapped[str | None] = mapped_column(Text)
    quantidade_acoes_ordinarias: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    quantidade_acoes_preferenciais: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    quantidade_total_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreCapitalSocialReducaoClasseAcao(Base):
    __tablename__ = "fre_capital_social_reducao_classes_acoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_capital_social",
            "tipo_classe_acao_preferencial",
            name="uq_fre_cap_soc_reducao_classes_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_capital_social: Mapped[int] = mapped_column(Integer, index=True)
    tipo_classe_acao_preferencial: Mapped[str] = mapped_column(Text, index=True)
    quantidade_acoes: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreDireitoAcao(Base):
    __tablename__ = "fre_direitos_acoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "tipo_classe_acao",
            "direito_voto",
            name="uq_fre_direitos_acoes_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    tipo_classe_acao: Mapped[str] = mapped_column(Text, index=True)
    direito_voto: Mapped[str] = mapped_column(Text, index=True)
    outros_direitos: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreVolumeValorMobiliario(Base):
    __tablename__ = "fre_volumes_valores_mobiliarios"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "classe_valor_mobiliario",
            name="uq_fre_vol_val_mob_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    classe_valor_mobiliario: Mapped[str] = mapped_column(Text, index=True)
    sigla_classe_acoes_preferenciais: Mapped[str | None] = mapped_column(Text)
    volume_negociacao: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreOutroValorMobiliario(Base):
    __tablename__ = "fre_outros_valores_mobiliarios"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome_valor_mobiliario",
            name="uq_fre_outros_val_mob_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    nome_valor_mobiliario: Mapped[str] = mapped_column(Text, index=True)
    caracteristicas_valor_mobiliario: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreTitularValorMobiliario(Base):
    __tablename__ = "fre_titulares_valores_mobiliarios"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome_titular",
            "classe_valor_mobiliario",
            name="uq_fre_titulares_val_mob_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    nome_titular: Mapped[str] = mapped_column(Text, index=True)
    cpf_cnpj_titular: Mapped[str | None] = mapped_column(String(20))
    classe_valor_mobiliario: Mapped[str] = mapped_column(Text, index=True)
    quantidade_valores_mobiliarios: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    percentual_classe: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreMercadoEstrangeiro(Base):
    __tablename__ = "fre_mercados_estrangeiros"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome_mercado",
            name="uq_fre_mercados_estrangeiros_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    nome_mercado: Mapped[str] = mapped_column(Text, index=True)
    orgao_regulador: Mapped[str | None] = mapped_column(Text)
    data_admissao: Mapped[date | None] = mapped_column(Date)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreTituloExterior(Base):
    __tablename__ = "fre_titulos_exterior"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "nome_titulo",
            name="uq_fre_titulos_exterior_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    nome_titulo: Mapped[str] = mapped_column(Text, index=True)
    pais_emissao: Mapped[str | None] = mapped_column(Text)
    caracteristicas: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FrePlanoRecompra(Base):
    __tablename__ = "fre_planos_recompra"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_plano_recompra",
            name="uq_fre_planos_recompra_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_plano_recompra: Mapped[int] = mapped_column(Integer, index=True)
    data_deliberacao: Mapped[date | None] = mapped_column(Date)
    objetivo_plano: Mapped[str | None] = mapped_column(Text)
    limite_prazo_aquisicao: Mapped[str | None] = mapped_column(Text)
    quantidade_total_ordinarias_adquiridas: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    quantidade_total_preferenciais_adquiridas: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FrePlanoRecompraClasseAcao(Base):
    __tablename__ = "fre_plano_recompra_classes_acoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "id_plano_recompra",
            "tipo_classe_acao_preferencial",
            name="uq_fre_plano_recompra_classes_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    id_plano_recompra: Mapped[int] = mapped_column(Integer, index=True)
    tipo_classe_acao_preferencial: Mapped[str] = mapped_column(Text, index=True)
    quantidade_acoes_adquiridas: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreValorMobiliarioTesourariaMovimentacao(Base):
    __tablename__ = "fre_valores_mobiliarios_tesouraria_movimentacoes"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "classe_valor_mobiliario",
            "data_movimentacao",
            name="uq_fre_val_mob_tes_mov_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    classe_valor_mobiliario: Mapped[str] = mapped_column(Text, index=True)
    data_movimentacao: Mapped[date] = mapped_column(Date, index=True)
    quantidade_movimentada: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    natureza_movimentacao: Mapped[str | None] = mapped_column(Text)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreValorMobiliarioTesourariaUltimoExercicio(Base):
    __tablename__ = "fre_valores_mobiliarios_tesouraria_ultimos_exercicios"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "classe_valor_mobiliario",
            "historico_exercicio",
            name="uq_fre_val_mob_tes_ult_ex_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    classe_valor_mobiliario: Mapped[str] = mapped_column(Text, index=True)
    historico_exercicio: Mapped[str] = mapped_column(Text, index=True)
    quantidade_acoes_tesouraria: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreAdministradorDeclaracaoGenero(Base):
    __tablename__ = "fre_administradores_declaracao_genero"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "orgao_administracao",
            name="uq_fre_adm_dec_gen_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    orgao_administracao: Mapped[str] = mapped_column(Text, index=True)
    quantidade_feminino: Mapped[int | None] = mapped_column(Integer)
    quantidade_masculino: Mapped[int | None] = mapped_column(Integer)
    quantidade_nao_binario: Mapped[int | None] = mapped_column(Integer)
    quantidade_outros: Mapped[int | None] = mapped_column(Integer)
    quantidade_sem_resposta: Mapped[int | None] = mapped_column(Integer)
    nao_aplicavel: Mapped[bool | None] = mapped_column(Boolean)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreAdministradorDeclaracaoRaca(Base):
    __tablename__ = "fre_administradores_declaracao_raca"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "orgao_administracao",
            name="uq_fre_adm_dec_raca_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    orgao_administracao: Mapped[str] = mapped_column(Text, index=True)
    quantidade_amarelo: Mapped[int | None] = mapped_column(Integer)
    quantidade_branco: Mapped[int | None] = mapped_column(Integer)
    quantidade_preto: Mapped[int | None] = mapped_column(Integer)
    quantidade_pardo: Mapped[int | None] = mapped_column(Integer)
    quantidade_indigena: Mapped[int | None] = mapped_column(Integer)
    quantidade_outros: Mapped[int | None] = mapped_column(Integer)
    quantidade_sem_resposta: Mapped[int | None] = mapped_column(Integer)
    nao_aplicavel: Mapped[bool | None] = mapped_column(Boolean)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FreAdministradorPcd(Base):
    __tablename__ = "fre_administradores_pcd"
    __table_args__ = (
        UniqueConstraint(
            "id_documento",
            "versao",
            "data_referencia",
            "cnpj_companhia",
            "orgao_administracao",
            name="uq_fre_adm_pcd_chave_natural",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    cnpj_companhia: Mapped[str] = mapped_column(String(14), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    versao: Mapped[int] = mapped_column(Integer, index=True)
    id_documento: Mapped[int] = mapped_column(Integer, index=True)
    nome_companhia: Mapped[str | None] = mapped_column(Text)
    orgao_administracao: Mapped[str] = mapped_column(Text, index=True)
    quantidade_pcd: Mapped[int | None] = mapped_column(Integer)
    quantidade_nao_pcd: Mapped[int | None] = mapped_column(Integer)
    quantidade_sem_resposta: Mapped[int | None] = mapped_column(Integer)
    nao_aplicavel: Mapped[bool | None] = mapped_column(Boolean)

    arquivo_origem: Mapped[str] = mapped_column(Text)
    ano_origem: Mapped[int | None] = mapped_column(Integer, index=True)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sincronizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alterado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
