import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import BrazilianDate, BrazilianDateTime, CanonicalDecimal, Paginacao, PeriodicModel


class DocumentoFinanceiroResposta(PeriodicModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "bbf228f5-5627-4fc5-a490-318b8ba31e43",
                "companhia_id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
                "tipo_formulario": "DFP",
                "cnpj_companhia": "08773135000100",
                "codigo_cvm": 25224,
                "data_referencia": "31/12/2025",
                "versao": 1,
                "denominacao_companhia": "EMPRESA A",
                "categoria_documento": "DFP",
                "id_documento": 123,
                "data_recebimento": "01/01/2026",
                "link_documento": "http://exemplo",
                "arquivo_origem": "dfp_cia_aberta_2025.csv",
                "ano_origem": 2025,
                "linha_origem": 2,
                "criado_em": "30/05/2026 14:30:00",
                "sincronizado_em": "30/05/2026 14:30:00",
                "alterado_em": "30/05/2026 14:30:00",
            }
        },
    )

    id: uuid.UUID = Field(description="Identificador interno do documento normalizado.")
    companhia_id: uuid.UUID | None = Field(description="FK para a companhia relacionada, quando resolvida.")
    tipo_formulario: str = Field(description="Tipo de formulario de origem: DFP ou ITR.")
    cnpj_companhia: str = Field(description="CNPJ da companhia com 14 digitos.")
    codigo_cvm: int | None = Field(description="Codigo CVM da companhia, quando presente.")
    data_referencia: BrazilianDate = Field(description="Data de referencia do documento.")
    versao: int = Field(description="Versao do formulario publicada pela CVM.")
    denominacao_companhia: str | None = Field(description="Denominacao da companhia no arquivo de origem.")
    categoria_documento: str | None = Field(description="Categoria documental reportada pela CVM.")
    id_documento: int = Field(description="Identificador do documento na CVM.")
    data_recebimento: BrazilianDate | None = Field(description="Data de recebimento do documento pela CVM.")
    link_documento: str | None = Field(description="URL de acesso ao documento, quando fornecida.")
    arquivo_origem: str = Field(description="Arquivo CSV de origem no ZIP anual.")
    ano_origem: int | None = Field(description="Ano do ZIP de origem processado.")
    linha_origem: int | None = Field(description="Linha do CSV de origem.")
    criado_em: BrazilianDateTime = Field(description="Data e hora de insercao do registro, em `DD/MM/AAAA HH:MM:SS`.")
    sincronizado_em: BrazilianDateTime = Field(
        description="Data e hora da ultima sincronizacao em que o registro foi visto, em `DD/MM/AAAA HH:MM:SS`."
    )
    alterado_em: BrazilianDateTime = Field(
        description="Data e hora da ultima alteracao real de dados de negocio, em `DD/MM/AAAA HH:MM:SS`."
    )


class DemonstracaoFinanceiraResposta(PeriodicModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "bbf228f5-5627-4fc5-a490-318b8ba31e43",
                "companhia_id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
                "tipo_formulario": "DFP",
                "tipo_demonstracao": "demonstracao_resultado",
                "escopo_demonstracao": "individual",
                "cnpj_companhia": "00000000000191",
                "codigo_cvm": 1023,
                "data_referencia": "31/12/2025",
                "versao": 1,
                "denominacao_companhia": "BCO BRASIL S.A.",
                "grupo_demonstracao": "DF Individual - Demonstração do Resultado",
                "moeda": "REAL",
                "escala_moeda": "MIL",
                "fator_escala_moeda": 1000,
                "ordem_exercicio": "ÚLTIMO",
                "data_inicio_exercicio": "01/01/2025",
                "data_fim_exercicio": "31/12/2025",
                "codigo_conta": "3.03",
                "coluna_df": "",
                "descricao_conta": "Receita Líquida",
                "valor_conta": "740500000",
                "valor_conta_reportado": "740500",
                "conta_fixa": True,
                "arquivo_origem": "dfp_cia_aberta_DRE_ind_2025.csv",
                "ano_origem": 2025,
                "linha_origem": 2960,
                "criado_em": "30/05/2026 14:30:00",
                "sincronizado_em": "30/05/2026 14:30:00",
                "alterado_em": "30/05/2026 14:30:00",
            }
        },
    )

    id: uuid.UUID = Field(description="Identificador interno da linha de demonstracao.")
    companhia_id: uuid.UUID | None = Field(description="FK para a companhia relacionada, quando resolvida.")
    tipo_formulario: str = Field(description="Tipo de formulario de origem: DFP ou ITR.")
    tipo_demonstracao: str = Field(description="Tipo normalizado da demonstracao (DRE, DVA, BPA, etc.).")
    escopo_demonstracao: str = Field(description="Escopo contabil da demonstracao: consolidado ou individual.")
    cnpj_companhia: str = Field(description="CNPJ da companhia com 14 digitos.")
    codigo_cvm: int | None = Field(description="Codigo CVM da companhia, quando presente.")
    data_referencia: BrazilianDate = Field(description="Data de referencia contabil.")
    versao: int = Field(description="Versao do formulario.")
    denominacao_companhia: str | None = Field(description="Denominacao da companhia na origem.")
    grupo_demonstracao: str | None = Field(description="Grupo do formulario reportado pela CVM (GRUPO_DFP).")
    moeda: str | None = Field(description="Moeda do valor contabil.")
    escala_moeda: str | None = Field(
        description=(
            "Escala monetaria informada pela CVM no arquivo de origem, como `UNIDADE`, `MIL` ou `MILHAO`. "
            "A API preserva este valor para auditoria, mas `valor_conta` ja retorna o montante ajustado por essa escala."
        )
    )
    fator_escala_moeda: int = Field(
        description=(
            "Multiplicador numerico derivado de `escala_moeda` e aplicado ao valor reportado. "
            "Exemplos: `UNIDADE` => 1, `MIL` => 1000, `MILHAO` => 1000000."
        )
    )
    ordem_exercicio: str | None = Field(description="Ordem do exercicio (ultimo, penultimo, etc.).")
    data_inicio_exercicio: BrazilianDate | None = Field(description="Data de inicio do exercicio.")
    data_fim_exercicio: BrazilianDate | None = Field(description="Data de fim do exercicio.")
    codigo_conta: str | None = Field(description="Codigo da conta contabil.")
    coluna_df: str = Field(
        description="Eixo COLUNA_DF reportado pela CVM em demonstracoes matriciais, como DMPL. Vazio quando o arquivo nao usa esse eixo."
    )
    descricao_conta: str | None = Field(description="Descricao textual da conta contabil.")
    valor_conta: CanonicalDecimal | None = Field(
        description=(
            "Valor contabil ajustado para o montante monetario absoluto em reais, serializado como string decimal canônica. "
            "Este campo e calculado a partir do valor reportado pela CVM multiplicado por `fator_escala_moeda`. "
            "A resposta nunca usa separadores de milhares nem localizacao pt-BR."
        )
    )
    valor_conta_reportado: CanonicalDecimal | None = Field(
        description=(
            "Valor bruto reportado pela CVM apos parsing do CSV estruturado, antes da aplicacao de `escala_moeda`, "
            "serializado como string decimal canônica."
        )
    )
    conta_fixa: bool | None = Field(description="Indica se a conta e fixa na taxonomia CVM.")
    arquivo_origem: str = Field(description="Arquivo CSV de origem no ZIP anual.")
    ano_origem: int | None = Field(description="Ano do ZIP de origem processado.")
    linha_origem: int | None = Field(description="Linha do CSV de origem.")
    criado_em: BrazilianDateTime = Field(description="Data e hora de insercao do registro, em `DD/MM/AAAA HH:MM:SS`.")
    sincronizado_em: BrazilianDateTime = Field(
        description="Data e hora da ultima sincronizacao em que o registro foi visto, em `DD/MM/AAAA HH:MM:SS`."
    )
    alterado_em: BrazilianDateTime = Field(
        description="Data e hora da ultima alteracao real de dados de negocio, em `DD/MM/AAAA HH:MM:SS`."
    )


class ComposicaoCapitalResposta(PeriodicModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Identificador interno da linha de composicao de capital.")
    companhia_id: uuid.UUID | None = Field(description="FK para a companhia relacionada, quando resolvida.")
    tipo_formulario: str = Field(description="Tipo de formulario de origem: DFP ou ITR.")
    cnpj_companhia: str = Field(description="CNPJ da companhia com 14 digitos.")
    codigo_cvm: int | None = Field(description="Codigo CVM da companhia, quando presente.")
    data_referencia: BrazilianDate = Field(description="Data de referencia da composicao de capital.")
    versao: int = Field(description="Versao do formulario.")
    denominacao_companhia: str | None = Field(description="Denominacao da companhia na origem.")
    quantidade_acoes_ordinarias_capital_integralizado: CanonicalDecimal | None = Field(
        description="Quantidade de acoes ordinarias no capital integralizado."
    )
    quantidade_acoes_preferenciais_capital_integralizado: CanonicalDecimal | None = Field(
        description="Quantidade de acoes preferenciais no capital integralizado."
    )
    quantidade_total_acoes_capital_integralizado: CanonicalDecimal | None = Field(
        description="Quantidade total de acoes no capital integralizado."
    )
    quantidade_acoes_ordinarias_tesouraria: CanonicalDecimal | None = Field(
        description="Quantidade de acoes ordinarias em tesouraria."
    )
    quantidade_acoes_preferenciais_tesouraria: CanonicalDecimal | None = Field(
        description="Quantidade de acoes preferenciais em tesouraria."
    )
    quantidade_total_acoes_tesouraria: CanonicalDecimal | None = Field(
        description="Quantidade total de acoes em tesouraria."
    )
    arquivo_origem: str = Field(description="Arquivo CSV de origem no ZIP anual.")
    ano_origem: int | None = Field(description="Ano do ZIP de origem processado.")
    linha_origem: int | None = Field(description="Linha do CSV de origem.")
    criado_em: BrazilianDateTime = Field(description="Data e hora de insercao do registro, em `DD/MM/AAAA HH:MM:SS`.")
    sincronizado_em: BrazilianDateTime = Field(
        description="Data e hora da ultima sincronizacao em que o registro foi visto, em `DD/MM/AAAA HH:MM:SS`."
    )
    alterado_em: BrazilianDateTime = Field(
        description="Data e hora da ultima alteracao real de dados de negocio, em `DD/MM/AAAA HH:MM:SS`."
    )


class ParecerFinanceiroResposta(PeriodicModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Identificador interno da linha de parecer.")
    companhia_id: uuid.UUID | None = Field(description="FK para a companhia relacionada, quando resolvida.")
    tipo_formulario: str = Field(description="Tipo de formulario de origem: DFP ou ITR.")
    cnpj_companhia: str = Field(description="CNPJ da companhia com 14 digitos.")
    codigo_cvm: int | None = Field(description="Codigo CVM da companhia, quando presente.")
    data_referencia: BrazilianDate = Field(description="Data de referencia do parecer.")
    versao: int = Field(description="Versao do formulario.")
    denominacao_companhia: str | None = Field(description="Denominacao da companhia na origem.")
    tipo_relatorio_auditor: str | None = Field(description="Tipo de relatorio do auditor independente.")
    tipo_parecer_declaracao: str | None = Field(description="Tipo de parecer/declaracao informado pela CVM.")
    numero_item_parecer_declaracao: str | None = Field(description="Numero do item textual do parecer/declaracao.")
    texto_parecer_declaracao: str | None = Field(description="Conteudo textual do parecer/declaracao.")
    arquivo_origem: str = Field(description="Arquivo CSV de origem no ZIP anual.")
    ano_origem: int | None = Field(description="Ano do ZIP de origem processado.")
    linha_origem: int | None = Field(description="Linha do CSV de origem.")
    criado_em: BrazilianDateTime = Field(description="Data e hora de insercao do registro, em `DD/MM/AAAA HH:MM:SS`.")
    sincronizado_em: BrazilianDateTime = Field(
        description="Data e hora da ultima sincronizacao em que o registro foi visto, em `DD/MM/AAAA HH:MM:SS`."
    )
    alterado_em: BrazilianDateTime = Field(
        description="Data e hora da ultima alteracao real de dados de negocio, em `DD/MM/AAAA HH:MM:SS`."
    )


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
