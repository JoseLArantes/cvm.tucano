import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Paginacao


class DocumentoFinanceiroResposta(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "bbf228f5-5627-4fc5-a490-318b8ba31e43",
                "companhia_id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
                "tipo_formulario": "DFP",
                "cnpj_companhia": "08773135000100",
                "codigo_cvm": 25224,
                "data_referencia": "2025-12-31",
                "versao": 1,
                "denominacao_companhia": "EMPRESA A",
                "categoria_documento": "DFP",
                "id_documento": 123,
                "data_recebimento": "2026-01-01",
                "link_documento": "http://exemplo",
                "arquivo_origem": "dfp_cia_aberta_2025.csv",
                "ano_origem": 2025,
                "linha_origem": 2,
                "criado_em": "2026-05-30T14:30:00Z",
                "sincronizado_em": "2026-05-30T14:30:00Z",
                "alterado_em": "2026-05-30T14:30:00Z",
            }
        },
    )

    id: uuid.UUID = Field(description="Identificador interno do documento normalizado.")
    companhia_id: uuid.UUID | None = Field(description="FK para a companhia relacionada, quando resolvida.")
    tipo_formulario: str = Field(description="Tipo de formulario de origem: DFP ou ITR.")
    cnpj_companhia: str = Field(description="CNPJ da companhia com 14 digitos.")
    codigo_cvm: int | None = Field(description="Codigo CVM da companhia, quando presente.")
    data_referencia: date = Field(description="Data de referencia do documento.")
    versao: int = Field(description="Versao do formulario publicada pela CVM.")
    denominacao_companhia: str | None = Field(description="Denominacao da companhia no arquivo de origem.")
    categoria_documento: str | None = Field(description="Categoria documental reportada pela CVM.")
    id_documento: int = Field(description="Identificador do documento na CVM.")
    data_recebimento: date | None = Field(description="Data de recebimento do documento pela CVM.")
    link_documento: str | None = Field(description="URL de acesso ao documento, quando fornecida.")
    arquivo_origem: str = Field(description="Arquivo CSV de origem no ZIP anual.")
    ano_origem: int | None = Field(description="Ano do ZIP de origem processado.")
    linha_origem: int | None = Field(description="Linha do CSV de origem.")
    criado_em: datetime = Field(description="Timestamp de insercao do registro.")
    sincronizado_em: datetime = Field(description="Timestamp da ultima sincronizacao em que o registro foi visto.")
    alterado_em: datetime = Field(description="Timestamp da ultima alteracao real de dados de negocio.")


class DemonstracaoFinanceiraResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Identificador interno da linha de demonstracao.")
    companhia_id: uuid.UUID | None = Field(description="FK para a companhia relacionada, quando resolvida.")
    tipo_formulario: str = Field(description="Tipo de formulario de origem: DFP ou ITR.")
    tipo_demonstracao: str = Field(description="Tipo normalizado da demonstracao (DRE, DVA, BPA, etc.).")
    escopo_demonstracao: str = Field(description="Escopo contabil da demonstracao: consolidado ou individual.")
    cnpj_companhia: str = Field(description="CNPJ da companhia com 14 digitos.")
    codigo_cvm: int | None = Field(description="Codigo CVM da companhia, quando presente.")
    data_referencia: date = Field(description="Data de referencia contabil.")
    versao: int = Field(description="Versao do formulario.")
    denominacao_companhia: str | None = Field(description="Denominacao da companhia na origem.")
    grupo_demonstracao: str | None = Field(description="Grupo do formulario reportado pela CVM (GRUPO_DFP).")
    moeda: str | None = Field(description="Moeda do valor contabil.")
    escala_moeda: str | None = Field(description="Escala aplicada aos valores monetarios.")
    ordem_exercicio: str | None = Field(description="Ordem do exercicio (ultimo, penultimo, etc.).")
    data_inicio_exercicio: date | None = Field(description="Data de inicio do exercicio.")
    data_fim_exercicio: date | None = Field(description="Data de fim do exercicio.")
    codigo_conta: str | None = Field(description="Codigo da conta contabil.")
    descricao_conta: str | None = Field(description="Descricao textual da conta contabil.")
    valor_conta: Decimal | None = Field(description="Valor contabil da conta.")
    conta_fixa: bool | None = Field(description="Indica se a conta e fixa na taxonomia CVM.")
    arquivo_origem: str = Field(description="Arquivo CSV de origem no ZIP anual.")
    ano_origem: int | None = Field(description="Ano do ZIP de origem processado.")
    linha_origem: int | None = Field(description="Linha do CSV de origem.")
    criado_em: datetime = Field(description="Timestamp de insercao do registro.")
    sincronizado_em: datetime = Field(description="Timestamp da ultima sincronizacao em que o registro foi visto.")
    alterado_em: datetime = Field(description="Timestamp da ultima alteracao real de dados de negocio.")


class ComposicaoCapitalResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Identificador interno da linha de composicao de capital.")
    companhia_id: uuid.UUID | None = Field(description="FK para a companhia relacionada, quando resolvida.")
    tipo_formulario: str = Field(description="Tipo de formulario de origem: DFP ou ITR.")
    cnpj_companhia: str = Field(description="CNPJ da companhia com 14 digitos.")
    codigo_cvm: int | None = Field(description="Codigo CVM da companhia, quando presente.")
    data_referencia: date = Field(description="Data de referencia da composicao de capital.")
    versao: int = Field(description="Versao do formulario.")
    denominacao_companhia: str | None = Field(description="Denominacao da companhia na origem.")
    quantidade_acoes_ordinarias_capital_integralizado: Decimal | None = Field(
        description="Quantidade de acoes ordinarias no capital integralizado."
    )
    quantidade_acoes_preferenciais_capital_integralizado: Decimal | None = Field(
        description="Quantidade de acoes preferenciais no capital integralizado."
    )
    quantidade_total_acoes_capital_integralizado: Decimal | None = Field(
        description="Quantidade total de acoes no capital integralizado."
    )
    quantidade_acoes_ordinarias_tesouraria: Decimal | None = Field(
        description="Quantidade de acoes ordinarias em tesouraria."
    )
    quantidade_acoes_preferenciais_tesouraria: Decimal | None = Field(
        description="Quantidade de acoes preferenciais em tesouraria."
    )
    quantidade_total_acoes_tesouraria: Decimal | None = Field(
        description="Quantidade total de acoes em tesouraria."
    )
    arquivo_origem: str = Field(description="Arquivo CSV de origem no ZIP anual.")
    ano_origem: int | None = Field(description="Ano do ZIP de origem processado.")
    linha_origem: int | None = Field(description="Linha do CSV de origem.")
    criado_em: datetime = Field(description="Timestamp de insercao do registro.")
    sincronizado_em: datetime = Field(description="Timestamp da ultima sincronizacao em que o registro foi visto.")
    alterado_em: datetime = Field(description="Timestamp da ultima alteracao real de dados de negocio.")


class ParecerFinanceiroResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Identificador interno da linha de parecer.")
    companhia_id: uuid.UUID | None = Field(description="FK para a companhia relacionada, quando resolvida.")
    tipo_formulario: str = Field(description="Tipo de formulario de origem: DFP ou ITR.")
    cnpj_companhia: str = Field(description="CNPJ da companhia com 14 digitos.")
    codigo_cvm: int | None = Field(description="Codigo CVM da companhia, quando presente.")
    data_referencia: date = Field(description="Data de referencia do parecer.")
    versao: int = Field(description="Versao do formulario.")
    denominacao_companhia: str | None = Field(description="Denominacao da companhia na origem.")
    tipo_relatorio_auditor: str | None = Field(description="Tipo de relatorio do auditor independente.")
    tipo_parecer_declaracao: str | None = Field(description="Tipo de parecer/declaracao informado pela CVM.")
    numero_item_parecer_declaracao: str | None = Field(description="Numero do item textual do parecer/declaracao.")
    texto_parecer_declaracao: str | None = Field(description="Conteudo textual do parecer/declaracao.")
    arquivo_origem: str = Field(description="Arquivo CSV de origem no ZIP anual.")
    ano_origem: int | None = Field(description="Ano do ZIP de origem processado.")
    linha_origem: int | None = Field(description="Linha do CSV de origem.")
    criado_em: datetime = Field(description="Timestamp de insercao do registro.")
    sincronizado_em: datetime = Field(description="Timestamp da ultima sincronizacao em que o registro foi visto.")
    alterado_em: datetime = Field(description="Timestamp da ultima alteracao real de dados de negocio.")


class ListaDocumentosFinanceirosResposta(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"dados": [], "paginacao": {"pagina": 1, "tamanho_pagina": 100, "total": 0}}}
    )
    dados: list[DocumentoFinanceiroResposta] = Field(description="Lista paginada de documentos financeiros.")
    paginacao: Paginacao = Field(description="Metadados de paginacao da consulta.")


class ListaDemonstracoesFinanceirasResposta(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"dados": [], "paginacao": {"pagina": 1, "tamanho_pagina": 100, "total": 0}}}
    )
    dados: list[DemonstracaoFinanceiraResposta] = Field(
        description="Lista paginada de linhas de demonstracoes financeiras."
    )
    paginacao: Paginacao = Field(description="Metadados de paginacao da consulta.")


class ListaComposicoesCapitalResposta(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"dados": [], "paginacao": {"pagina": 1, "tamanho_pagina": 100, "total": 0}}}
    )
    dados: list[ComposicaoCapitalResposta] = Field(description="Lista paginada de composicoes de capital.")
    paginacao: Paginacao = Field(description="Metadados de paginacao da consulta.")


class ListaPareceresFinanceirosResposta(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"dados": [], "paginacao": {"pagina": 1, "tamanho_pagina": 100, "total": 0}}}
    )
    dados: list[ParecerFinanceiroResposta] = Field(description="Lista paginada de pareceres e declaracoes.")
    paginacao: Paginacao = Field(description="Metadados de paginacao da consulta.")
