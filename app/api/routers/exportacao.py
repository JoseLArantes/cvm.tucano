import csv
import io
import json
import uuid
from collections.abc import Generator
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Select, select

from app.api.deps import DbSession
from app.models.cgvn import CgvnDocumento, CgvnPratica
from app.models.companhia import Companhia
from app.models.fca import (
    FcaAuditor,
    FcaDocumento,
    FcaDri,
    FcaEndereco,
    FcaGeral,
    FcaValorMobiliario,
)
from app.models.financeiro import (
    ComposicaoCapital,
    DemonstracaoFinanceira,
    DocumentoFinanceiro,
    ParecerFinanceiro,
)
from app.models.fre import (
    FreAcaoEntregue,
    FreAuditor,
    FreCapitalSocial,
    FreCapitalSocialClasseAcao,
    FreCapitalSocialTituloConversivel,
    FreDistribuicaoCapital,
    FreDistribuicaoCapitalClasseAcao,
    FreDocumento,
    FreEmpregadoPosicaoGenero,
    FrePosicaoAcionaria,
    FrePosicaoAcionariaClasseAcao,
    FreRemuneracaoAcao,
    FreRemuneracaoMaximaMinimaMedia,
    FreRemuneracaoTotalOrgao,
    FreRemuneracaoVariavel,
    FreResponsavel,
)
from app.models.ipe import IpeDocumento
from app.models.vlmo import VlmoConsolidado, VlmoDocumento
from app.schemas.exportacao import DatasetResposta, FonteResposta
from app.services.financeiro_valores import colunas_exportacao, serializar_exportacao_linha
from app.services.ingestion.source_registry import (
    listar_datasets,
    listar_fontes,
    obter_fonte,
)
from app.services.normalizacao import (
    data_para_string_br,
    datetime_para_string_br,
    decimal_para_canonical_string,
    normalizar_cnpj,
)

router = APIRouter()

_FRE_DATASETS_PUBLICAMENTE_DESCONTINUADOS = {
    "capital_social_aumento",
    "capital_social_aumento_classe_acao",
    "capital_social_desdobramento",
    "capital_social_desdobramento_classe_acao",
    "capital_social_reducao",
    "capital_social_reducao_classe_acao",
    "direito_acao",
}

# Define the static model mapping for supported datasets
MAP_MODELOS: dict[tuple[str, str], tuple[type[Any], dict[str, Any]]] = {
    ("cadastro", "cadastro_aberta"): (Companhia, {}),
    ("cadastro", "cadastro_estrangeira"): (Companhia, {}),
    ("dfp", "documento_principal"): (DocumentoFinanceiro, {"tipo_formulario": "DFP"}),
    ("dfp", "composicao_capital"): (ComposicaoCapital, {"tipo_formulario": "DFP"}),
    ("dfp", "parecer"): (ParecerFinanceiro, {"tipo_formulario": "DFP"}),
    ("itr", "documento_principal"): (DocumentoFinanceiro, {"tipo_formulario": "ITR"}),
    ("itr", "composicao_capital"): (ComposicaoCapital, {"tipo_formulario": "ITR"}),
    ("itr", "parecer"): (ParecerFinanceiro, {"tipo_formulario": "ITR"}),
    ("ipe", "original"): (IpeDocumento, {}),
    ("vlmo", "original"): (VlmoDocumento, {}),
    ("vlmo", "consolidado"): (VlmoConsolidado, {}),
    ("cgvn", "original"): (CgvnDocumento, {}),
    ("cgvn", "praticas"): (CgvnPratica, {}),
    ("fca", "original"): (FcaDocumento, {}),
    ("fca", "geral"): (FcaGeral, {}),
    ("fca", "endereco"): (FcaEndereco, {}),
    ("fca", "dri"): (FcaDri, {}),
    ("fca", "auditor"): (FcaAuditor, {}),
    ("fca", "valor_mobiliario"): (FcaValorMobiliario, {}),
    ("fre", "documentos"): (FreDocumento, {}),
    ("fre", "auditores"): (FreAuditor, {}),
    ("fre", "capital_social"): (FreCapitalSocial, {}),
    ("fre", "posicao_acionaria"): (FrePosicaoAcionaria, {}),
    ("fre", "remuneracao_total_orgao"): (FreRemuneracaoTotalOrgao, {}),
    ("fre", "empregado_posicao_genero"): (FreEmpregadoPosicaoGenero, {}),
    ("fre", "responsavel"): (FreResponsavel, {}),
    ("fre", "capital_social_classe_acao"): (FreCapitalSocialClasseAcao, {}),
    ("fre", "capital_social_titulo_conversivel"): (FreCapitalSocialTituloConversivel, {}),
    ("fre", "distribuicao_capital"): (FreDistribuicaoCapital, {}),
    ("fre", "distribuicao_capital_classe_acao"): (FreDistribuicaoCapitalClasseAcao, {}),
    ("fre", "posicao_acionaria_classe_acao"): (FrePosicaoAcionariaClasseAcao, {}),
    ("fre", "remuneracao_maxima_minima_media"): (FreRemuneracaoMaximaMinimaMedia, {}),
    ("fre", "remuneracao_variavel"): (FreRemuneracaoVariavel, {}),
    ("fre", "remuneracao_acao"): (FreRemuneracaoAcao, {}),
    ("fre", "acao_entregue"): (FreAcaoEntregue, {}),
}

# Resolve getDataCVM-like aliases to the actual registry dataset keys
ALIASES = {
    "bpa_ind": "demonstracao_balanco_patrimonial_ativo_individual",
    "bpa_con": "demonstracao_balanco_patrimonial_ativo_consolidado",
    "bpp_ind": "demonstracao_balanco_patrimonial_passivo_individual",
    "bpp_con": "demonstracao_balanco_patrimonial_passivo_consolidado",
    "dfc_md_ind": "demonstracao_fluxo_caixa_metodo_direto_individual",
    "dfc_md_con": "demonstracao_fluxo_caixa_metodo_direto_consolidado",
    "dfc_mi_ind": "demonstracao_fluxo_caixa_metodo_indireto_individual",
    "dfc_mi_con": "demonstracao_fluxo_caixa_metodo_indireto_consolidado",
    "dmpl_ind": "demonstracao_mutacoes_patrimonio_liquido_individual",
    "dmpl_con": "demonstracao_mutacoes_patrimonio_liquido_consolidado",
    "dra_ind": "demonstracao_resultado_abrangente_individual",
    "dra_con": "demonstracao_resultado_abrangente_consolidado",
    "dre_ind": "demonstracao_demonstracao_resultado_individual",
    "dre_con": "demonstracao_demonstracao_resultado_consolidado",
    "dva_ind": "demonstracao_valor_adicionado_individual",
    "dva_con": "demonstracao_valor_adicionado_consolidado",
}

for k, v in list(ALIASES.items()):
    ALIASES[f"demonstracao_{k}"] = v


def obter_modelo_e_filtros(fonte: str, dataset: str) -> tuple[type[Any], dict[str, Any]]:
    # Resolve aliases
    dataset_resolvido = ALIASES.get(dataset.lower(), dataset.lower())

    if fonte == "fre" and dataset_resolvido in _FRE_DATASETS_PUBLICAMENTE_DESCONTINUADOS:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Dataset '{dataset}' da fonte 'fre' foi descontinuado publicamente pela CVM a partir de 2024 "
                "e nao e mais exportado por esta API. Consulte os datasets ativos `capital_social`, "
                "`capital_social_classe_acao` e `distribuicao_capital`."
            ),
        )

    if (fonte, dataset_resolvido) in MAP_MODELOS:
        return MAP_MODELOS[(fonte, dataset_resolvido)]

    # Dynamic parsing for DFP/ITR demonstracoes
    if (fonte in ("dfp", "itr")) and dataset_resolvido.startswith("demonstracao_"):
        partes = dataset_resolvido[len("demonstracao_") :].split("_")
        if len(partes) >= 2:
            escopo = partes[-1]
            tipo = "_".join(partes[:-1])
            if escopo in ("individual", "consolidado"):
                tipo_formulario = "DFP" if fonte == "dfp" else "ITR"
                return DemonstracaoFinanceira, {
                    "tipo_formulario": tipo_formulario,
                    "tipo_demonstracao": tipo,
                    "escopo_demonstracao": escopo,
                }

    raise HTTPException(status_code=404, detail=f"Dataset '{dataset}' nao encontrado para a fonte '{fonte}'.")


def _resolver_cnpj_por_codigo_cvm(db: DbSession, codigo_cvm: int) -> str | None:
    return db.scalar(select(Companhia.cnpj_companhia).where(Companhia.codigo_cvm == codigo_cvm))


class CustomEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return datetime_para_string_br(obj)
        if isinstance(obj, date):
            return data_para_string_br(obj)
        if isinstance(obj, Decimal):
            return decimal_para_canonical_string(obj)
        return super().default(obj)


def generate_json(
    db: DbSession, query: Select[Any], Model: type[Any], columns: list[str]
) -> Generator[str, None, None]:
    result = db.execute(query.execution_options(yield_per=1000)).scalars()
    export_columns = colunas_exportacao(Model, columns)
    yield "[\n"
    first = True
    for row in result:
        row_dict = serializar_exportacao_linha(row, export_columns)
        serializable: dict[str, Any] = {}
        for c in export_columns:
            val = row_dict.get(c)
            if isinstance(val, uuid.UUID):
                serializable[c] = str(val)
            elif isinstance(val, datetime):
                serializable[c] = datetime_para_string_br(val)
            elif isinstance(val, date):
                serializable[c] = data_para_string_br(val)
            elif isinstance(val, Decimal):
                serializable[c] = decimal_para_canonical_string(val)
            else:
                serializable[c] = val

        line = json.dumps(serializable, cls=CustomEncoder)
        if not first:
            yield ",\n" + line
        else:
            yield line
            first = False
    yield "\n]"


def generate_csv(db: DbSession, query: Select[Any], Model: type[Any], columns: list[str]) -> Generator[str, None, None]:
    result = db.execute(query.execution_options(yield_per=1000)).scalars()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=",", lineterminator="\n")
    export_columns = colunas_exportacao(Model, columns)
    # Yield header
    writer.writerow(export_columns)
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    for row in result:
        row_dict = serializar_exportacao_linha(row, export_columns)
        vals = []
        for col in export_columns:
            val = row_dict.get(col)
            if val is None:
                vals.append("")
            elif isinstance(val, uuid.UUID):
                vals.append(str(val))
            elif isinstance(val, datetime):
                vals.append(datetime_para_string_br(val) or "")
            elif isinstance(val, date):
                vals.append(data_para_string_br(val) or "")
            elif isinstance(val, Decimal):
                vals.append(decimal_para_canonical_string(val) or "")
            elif isinstance(val, (dict, list)):
                vals.append(json.dumps(val, cls=CustomEncoder))
            else:
                vals.append(str(val))
        writer.writerow(vals)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)


@router.get(
    "/fontes",
    response_model=list[FonteResposta],
    tags=["fontes"],
    summary="Listar fontes CVM disponíveis",
    description=(
        "Retorna uma lista contendo todas as fontes de dados da CVM registradas e catalogadas "
        "no sistema (como cadastro, dfp, itr, fre, fca, ipe, vlmo, cgvn), junto com seus metadados "
        "relevantes tais como descrição, tipo de distribuição (anual compactada ou arquivo único) e "
        "abrangência temporal."
    ),
)
def listar_fontes_api() -> list[FonteResposta]:
    """Retorna a lista de todas as fontes disponíveis no registro."""
    return [
        FonteResposta(
            fonte=f.fonte,
            descricao=f.descricao,
            tipo_distribuicao=f.tipo_distribuicao,
            primeiro_ano=f.primeiro_ano,
            ultimo_ano=f.ultimo_ano,
            status_suporte=f.status_suporte,
        )
        for f in listar_fontes()
    ]


@router.get(
    "/fontes/{fonte}/datasets",
    response_model=list[DatasetResposta],
    tags=["fontes"],
    summary="Listar datasets cadastrados de uma fonte",
    description=(
        "Retorna todos os datasets/tabelas mapeados no catálogo para a fonte fornecida. "
        "Indica a descrição de cada tabela, se é de entrega obrigatória pelas companhias e seu "
        "status atual de suporte para promoção."
    ),
)
def listar_datasets_api(
    fonte: Annotated[
        str,
        Path(
            description=(
                "Chave canônica da fonte de dados (ex: 'cadastro', 'dfp', 'itr', 'fca', 'fre', 'ipe', 'vlmo', 'cgvn')."
            ),
            examples=["fre"],
        ),
    ],
) -> list[DatasetResposta]:
    """Retorna os datasets cadastrados no registro para uma determinada fonte."""
    fonte_item = obter_fonte(fonte.lower())
    if not fonte_item:
        raise HTTPException(status_code=404, detail=f"Fonte '{fonte}' nao encontrada.")
    datasets_publicos = [
        d
        for d in listar_datasets(fonte.lower())
        if not (fonte.lower() == "fre" and d.dataset in _FRE_DATASETS_PUBLICAMENTE_DESCONTINUADOS)
    ]
    return [
        DatasetResposta(
            dataset=d.dataset,
            descricao=d.descricao,
            obrigatorio=d.obrigatorio,
            status_suporte=d.status_suporte,
            exportavel=(fonte.lower(), d.dataset.lower()) in MAP_MODELOS or (
                fonte.lower() in ("dfp", "itr") and d.dataset.lower().startswith("demonstracao_")
            ),
        )
        for d in datasets_publicos
    ]


@router.get(
    "/exportacoes/{fonte}/{dataset}",
    tags=["exportacao"],
    summary="Exportação em lote de dados CVM por streaming",
    description=(
        "Executa uma consulta dinâmica e transmite por streaming o dataset bruto em formato estruturado (JSON ou CSV). "
        "Suporta resolução automática de aliases curtos de demonstrações financeiras (ex: 'bpa_ind' -> "
        "'demonstracao_balanco_patrimonial_ativo_individual'). "
        "Permite aplicar filtros flexíveis de período (ano_inicio/ano_fim) e companhia (cnpj_companhia/codigo_cvm). "
        "Todos os campos decimais são exportados como strings decimais canônicas, sem separadores de milhares e sem localização. "
        "Nos datasets de demonstrações DFP/ITR, `valor_conta` é exportado já ajustado por `ESCALA_MOEDA`, "
        "enquanto `valor_conta_reportado` preserva o número bruto informado pela CVM e `fator_escala_moeda` "
        "explica a multiplicação aplicada. "
        "Datas são serializadas em `DD/MM/AAAA` e datetimes em `DD/MM/AAAA HH:MM:SS`. "
        "Datasets FRE explicitamente descontinuados pela CVM deixam de ser exportáveis publicamente e retornam 404 "
        "com orientação para os quadros ativos de substituição. "
        "Para proteção do serviço, a consulta é limitada a um teto máximo de 100.000 registros por chamada."
    ),
    responses={
        HTTPStatus.OK: {
            "description": (
                "Exportação gerada com sucesso. O conteúdo retornado depende de `formato`: "
                "`application/json` para array de objetos ou `text/csv` para planilha delimitada por vírgula."
            ),
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {"type": "object", "additionalProperties": True},
                    },
                    "examples": {
                        "documento_principal": {
                            "summary": "Exportação JSON de documento financeiro",
                            "value": [
                                {
                                    "id_documento": 111,
                                    "cnpj_companhia": "00000000000191",
                                    "data_referencia": "31/12/2025",
                                    "criado_em": "30/05/2026 14:30:00",
                                }
                            ],
                        }
                    },
                },
                "text/csv": {
                    "schema": {
                        "type": "string",
                        "description": "Conteúdo CSV completo retornado por streaming.",
                    },
                    "examples": {
                        "documento_principal": {
                            "summary": "Exportação CSV de documento financeiro",
                            "value": (
                                "id_documento,cnpj_companhia,data_referencia,criado_em\n"
                                "111,00000000000191,31/12/2025,30/05/2026 14:30:00\n"
                            ),
                        }
                    },
                },
            },
        },
        HTTPStatus.NOT_FOUND: {
            "description": (
                "Fonte ou dataset não encontrado no catálogo suportado, incluindo datasets FRE "
                "publicamente descontinuados pela CVM."
            ),
        },
        HTTPStatus.UNPROCESSABLE_ENTITY: {
            "description": "Parâmetros inválidos, como formato não suportado ou intervalo de anos inconsistente.",
        },
    },
)
def exportar_dataset(
    fonte: Annotated[
        str,
        Path(
            description=(
                "Chave canônica da fonte de dados (ex: 'cadastro', 'dfp', 'itr', 'fca', 'fre', 'ipe', 'vlmo', 'cgvn')."
            ),
            examples=["fre"],
        ),
    ],
    dataset: Annotated[
        str,
        Path(
            description=(
                "Nome do dataset de interesse ou seu alias curto correspondente (ex: 'responsavel', 'bpa_ind')."
            ),
            examples=["responsavel"],
        ),
    ],
    db: DbSession,
    cnpj_companhia: Annotated[
        str | None,
        Query(
            description="CNPJ da companhia emissora de interesse (aceita formatos com ou sem pontuação).",
            examples=["00.000.000/0001-91"],
        ),
    ] = None,
    codigo_cvm: Annotated[
        int | None,
        Query(description="Código regulatório CVM da companhia aberta.", examples=[1023]),
    ] = None,
    ano_inicio: Annotated[
        int | None,
        Query(description="Ano inicial do ZIP/dados de origem para filtragem temporal (inclusive).", examples=[2020]),
    ] = None,
    ano_fim: Annotated[
        int | None,
        Query(description="Ano final do ZIP/dados de origem para filtragem temporal (inclusive).", examples=[2025]),
    ] = None,
    formato: Annotated[
        str,
        Query(
            description=(
                "Formato do arquivo de saída gerado por streaming: 'json' (array de objetos) ou 'csv' "
                "(valores separados por vírgula com linha de cabeçalho)."
            ),
            examples=["json", "csv"],
        ),
    ] = "json",
) -> StreamingResponse:
    """Exporta o dataset solicitado aplicando filtros de ano e companhia, limitado a 100.000 registros."""
    if ano_inicio is not None and ano_fim is not None and ano_inicio > ano_fim:
        raise HTTPException(status_code=422, detail="Intervalo de anos invalido: ano_inicio nao pode ser maior que ano_fim.")

    fonte_item = obter_fonte(fonte.lower())
    if not fonte_item:
        raise HTTPException(status_code=404, detail=f"Fonte '{fonte}' nao encontrada.")

    # Resolve dataset to Model and get static filters
    Model, filtros_estaticos = obter_modelo_e_filtros(fonte.lower(), dataset)

    # Validate that we actually have a DB table mapped to this model
    if not hasattr(Model, "__table__"):
        raise HTTPException(status_code=400, detail="Este dataset nao possui tabela de banco correspondente.")

    # Build base query
    stmt = select(Model)

    # Apply static filters (e.g. tipo_formulario for dfp/itr)
    for col_name, value in filtros_estaticos.items():
        if hasattr(Model, col_name):
            stmt = stmt.where(getattr(Model, col_name) == value)

    # Apply company filters
    cnpj_filtrado = cnpj_companhia
    if codigo_cvm is not None and cnpj_filtrado is None:
        cnpj_filtrado = _resolver_cnpj_por_codigo_cvm(db, codigo_cvm)
        if cnpj_filtrado is None:
            if hasattr(Model, "codigo_cvm"):
                stmt = stmt.where(Model.codigo_cvm == codigo_cvm)
            elif hasattr(Model, "cnpj_companhia"):
                stmt = stmt.where(Model.cnpj_companhia == "__codigo_cvm_nao_encontrado__")

    if cnpj_filtrado is not None and hasattr(Model, "cnpj_companhia"):
        cnpj_limpo = normalizar_cnpj(cnpj_filtrado)
        stmt = stmt.where(Model.cnpj_companhia == cnpj_limpo)

    if codigo_cvm is not None and hasattr(Model, "codigo_cvm"):
        stmt = stmt.where(Model.codigo_cvm == codigo_cvm)

    # Apply year range filters
    if ano_inicio is not None and hasattr(Model, "ano_origem"):
        stmt = stmt.where(Model.ano_origem >= ano_inicio)

    if ano_fim is not None and hasattr(Model, "ano_origem"):
        stmt = stmt.where(Model.ano_origem <= ano_fim)

    # Cap at 100,000 rows
    stmt = stmt.limit(100000)

    # Extract column names in order
    columns = [col.key for col in Model.__mapper__.columns]

    formato_limpo = formato.lower().strip()
    if formato_limpo == "csv":
        return StreamingResponse(
            generate_csv(db, stmt, Model, columns),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={dataset}_export.csv"},
        )
    elif formato_limpo == "json":
        return StreamingResponse(
            generate_json(db, stmt, Model, columns),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={dataset}_export.json"},
        )
    else:
        raise HTTPException(status_code=422, detail="Formato invalido. Escolha 'json' ou 'csv'.")
