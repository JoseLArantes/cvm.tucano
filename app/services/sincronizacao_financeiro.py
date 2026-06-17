import csv
import hashlib
import io
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.financeiro import ComposicaoCapital, DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo, RegistroQuarentena
from app.services.financeiro_mapas import arquivos_demonstracao
from app.services.financeiro_valores import normalizar_decimal_financeiro
from app.services.normalizacao import (
    gerar_hash_canonico,
    normalizar_cnpj,
    normalizar_conta_fixa,
    normalizar_data,
    normalizar_inteiro,
    normalizar_texto,
)

_BATCH_COMMIT_LINHAS = 5000

_CAMPOS_NEGOCIO_DOCUMENTOS = {
    "companhia_id",
    "tipo_formulario",
    "cnpj_companhia",
    "codigo_cvm",
    "data_referencia",
    "versao",
    "denominacao_companhia",
    "categoria_documento",
    "id_documento",
    "data_recebimento",
    "link_documento",
}
_CAMPOS_NEGOCIO_DEMONSTRACOES = {
    "companhia_id",
    "tipo_formulario",
    "tipo_demonstracao",
    "escopo_demonstracao",
    "cnpj_companhia",
    "codigo_cvm",
    "data_referencia",
    "versao",
    "denominacao_companhia",
    "grupo_demonstracao",
    "moeda",
    "escala_moeda",
    "ordem_exercicio",
    "data_inicio_exercicio",
    "data_fim_exercicio",
    "codigo_conta",
    "coluna_df",
    "descricao_conta",
    "valor_conta",
    "conta_fixa",
}
_CAMPOS_NEGOCIO_COMPOSICAO = {
    "companhia_id",
    "tipo_formulario",
    "cnpj_companhia",
    "codigo_cvm",
    "data_referencia",
    "versao",
    "denominacao_companhia",
    "quantidade_acoes_ordinarias_capital_integralizado",
    "quantidade_acoes_preferenciais_capital_integralizado",
    "quantidade_total_acoes_capital_integralizado",
    "quantidade_acoes_ordinarias_tesouraria",
    "quantidade_acoes_preferenciais_tesouraria",
    "quantidade_total_acoes_tesouraria",
}
_CAMPOS_NEGOCIO_PARECERES = {
    "companhia_id",
    "tipo_formulario",
    "cnpj_companhia",
    "codigo_cvm",
    "data_referencia",
    "versao",
    "denominacao_companhia",
    "tipo_relatorio_auditor",
    "tipo_parecer_declaracao",
    "numero_item_parecer_declaracao",
    "texto_parecer_declaracao",
}


def _agora() -> datetime:
    return datetime.now(UTC)


def _decode_csv(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "latin1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", payload, 0, 1, "Falha ao decodificar CSV")


def _equivalente(valor_a: Any, valor_b: Any) -> bool:
    if isinstance(valor_a, dict) and isinstance(valor_b, dict):
        chaves = set(valor_a.keys()) | set(valor_b.keys())
        return all(_equivalente(valor_a.get(chave), valor_b.get(chave)) for chave in chaves)
    if isinstance(valor_a, Decimal) or isinstance(valor_b, Decimal):
        if valor_a is None or valor_b is None:
            return valor_a is valor_b
        return Decimal(str(valor_a)) == Decimal(str(valor_b))
    if isinstance(valor_a, str) or isinstance(valor_b, str):
        return normalizar_texto(valor_a) == normalizar_texto(valor_b)
    return valor_a == valor_b


def _valor_historico(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, dict):
        return str({k: valor[k] for k in sorted(valor)})
    return str(valor)


def _registrar_quarentena(
    db: Session,
    *,
    execucao_id: Any,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
    motivo: str,
    dados_originais: dict[str, Any],
) -> None:
    db.add(
        RegistroQuarentena(
            execucao_sincronizacao_id=execucao_id,
            arquivo_origem=arquivo_origem,
            ano_origem=ano_origem,
            linha_origem=linha_origem,
            motivo=motivo[:255] if motivo else "",
            dados_originais=dados_originais,
        )
    )


def _normalizar_documento(
    linha: dict[str, Any],
    *,
    tipo_formulario: str,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
) -> dict[str, Any]:
    dados = {
        "tipo_formulario": tipo_formulario,
        "cnpj_companhia": normalizar_cnpj(str(linha.get("CNPJ_CIA", ""))),
        "codigo_cvm": normalizar_inteiro(linha.get("CD_CVM")),
        "data_referencia": normalizar_data(linha.get("DT_REFER")),
        "versao": normalizar_inteiro(linha.get("VERSAO")),
        "denominacao_companhia": normalizar_texto(linha.get("DENOM_CIA")),
        "categoria_documento": normalizar_texto(linha.get("CATEG_DOC")),
        "id_documento": normalizar_inteiro(linha.get("ID_DOC")),
        "data_recebimento": normalizar_data(linha.get("DT_RECEB")),
        "link_documento": normalizar_texto(linha.get("LINK_DOC")),
        "arquivo_origem": arquivo_origem,
        "ano_origem": ano_origem,
        "linha_origem": linha_origem,
    }
    if dados["data_referencia"] is None or dados["versao"] is None or dados["id_documento"] is None:
        raise ValueError("campo_obrigatorio_ausente")
    return dados


def _normalizar_demonstracao(
    linha: dict[str, Any],
    *,
    tipo_formulario: str,
    tipo_demonstracao: str,
    escopo_demonstracao: str,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
) -> dict[str, Any]:
    dados = {
        "tipo_formulario": tipo_formulario,
        "tipo_demonstracao": tipo_demonstracao,
        "escopo_demonstracao": escopo_demonstracao,
        "cnpj_companhia": normalizar_cnpj(str(linha.get("CNPJ_CIA", ""))),
        "codigo_cvm": normalizar_inteiro(linha.get("CD_CVM")),
        "data_referencia": normalizar_data(linha.get("DT_REFER")),
        "versao": normalizar_inteiro(linha.get("VERSAO")),
        "denominacao_companhia": normalizar_texto(linha.get("DENOM_CIA")),
        "grupo_demonstracao": normalizar_texto(linha.get("GRUPO_DFP")),
        "moeda": normalizar_texto(linha.get("MOEDA")),
        "escala_moeda": normalizar_texto(linha.get("ESCALA_MOEDA")),
        "ordem_exercicio": normalizar_texto(linha.get("ORDEM_EXERC")),
        "data_inicio_exercicio": normalizar_data(linha.get("DT_INI_EXERC")),
        "data_fim_exercicio": normalizar_data(linha.get("DT_FIM_EXERC")),
        "codigo_conta": normalizar_texto(linha.get("CD_CONTA")),
        "coluna_df": normalizar_texto(linha.get("COLUNA_DF")) or "",
        "descricao_conta": normalizar_texto(linha.get("DS_CONTA")),
        "valor_conta": normalizar_decimal_financeiro(linha.get("VL_CONTA")),
        "conta_fixa": normalizar_conta_fixa(linha.get("ST_CONTA_FIXA")),
        "arquivo_origem": arquivo_origem,
        "ano_origem": ano_origem,
        "linha_origem": linha_origem,
    }
    if dados["data_referencia"] is None or dados["versao"] is None:
        raise ValueError("campo_obrigatorio_ausente")
    return dados


def _normalizar_composicao_capital(
    linha: dict[str, Any],
    *,
    tipo_formulario: str,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
) -> dict[str, Any]:
    dados = {
        "tipo_formulario": tipo_formulario,
        "cnpj_companhia": normalizar_cnpj(str(linha.get("CNPJ_CIA", ""))),
        "codigo_cvm": None,
        "data_referencia": normalizar_data(linha.get("DT_REFER")),
        "versao": normalizar_inteiro(linha.get("VERSAO")),
        "denominacao_companhia": normalizar_texto(linha.get("DENOM_CIA")),
        "quantidade_acoes_ordinarias_capital_integralizado": normalizar_decimal_financeiro(
            linha.get("QT_ACAO_ORDIN_CAP_INTEGR")
        ),
        "quantidade_acoes_preferenciais_capital_integralizado": normalizar_decimal_financeiro(
            linha.get("QT_ACAO_PREF_CAP_INTEGR")
        ),
        "quantidade_total_acoes_capital_integralizado": normalizar_decimal_financeiro(
            linha.get("QT_ACAO_TOTAL_CAP_INTEGR")
        ),
        "quantidade_acoes_ordinarias_tesouraria": normalizar_decimal_financeiro(linha.get("QT_ACAO_ORDIN_TESOURO")),
        "quantidade_acoes_preferenciais_tesouraria": normalizar_decimal_financeiro(
            linha.get("QT_ACAO_PREF_TESOURO")
        ),
        "quantidade_total_acoes_tesouraria": normalizar_decimal_financeiro(linha.get("QT_ACAO_TOTAL_TESOURO")),
        "arquivo_origem": arquivo_origem,
        "ano_origem": ano_origem,
        "linha_origem": linha_origem,
    }
    if dados["data_referencia"] is None or dados["versao"] is None:
        raise ValueError("campo_obrigatorio_ausente")
    return dados


def _normalizar_parecer(
    linha: dict[str, Any],
    *,
    tipo_formulario: str,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
) -> dict[str, Any]:
    tipo_relatorio = normalizar_texto(linha.get("TP_RELAT_AUD"))
    if tipo_relatorio is None:
        tipo_relatorio = normalizar_texto(linha.get("TP_RELAT_ESP"))

    dados = {
        "tipo_formulario": tipo_formulario,
        "cnpj_companhia": normalizar_cnpj(str(linha.get("CNPJ_CIA", ""))),
        "codigo_cvm": None,
        "data_referencia": normalizar_data(linha.get("DT_REFER")),
        "versao": normalizar_inteiro(linha.get("VERSAO")),
        "denominacao_companhia": normalizar_texto(linha.get("DENOM_CIA")),
        "tipo_relatorio_auditor": tipo_relatorio,
        "tipo_parecer_declaracao": normalizar_texto(linha.get("TP_PARECER_DECL")),
        "numero_item_parecer_declaracao": normalizar_texto(linha.get("NUM_ITEM_PARECER_DECL")),
        "texto_parecer_declaracao": normalizar_texto(linha.get("TXT_PARECER_DECL")),
        "arquivo_origem": arquivo_origem,
        "ano_origem": ano_origem,
        "linha_origem": linha_origem,
    }
    if dados["data_referencia"] is None or dados["versao"] is None:
        raise ValueError("campo_obrigatorio_ausente")
    return dados


def _resolver_companhia(db: Session, cnpj_companhia: str, codigo_cvm: int | None) -> Companhia | None:
    if normalizar_texto(cnpj_companhia):
        return db.scalar(select(Companhia).where(Companhia.cnpj_companhia == cnpj_companhia))
    if codigo_cvm is None:
        return None
    return db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))


def _indexar_companhias(db: Session) -> tuple[dict[str, Companhia], dict[int, Companhia]]:
    companhias = db.execute(select(Companhia)).scalars().all()
    por_cnpj = {companhia.cnpj_companhia: companhia for companhia in companhias if companhia.cnpj_companhia}
    por_codigo = {companhia.codigo_cvm: companhia for companhia in companhias if companhia.codigo_cvm is not None}
    return por_cnpj, por_codigo


def _resolver_companhia_indexada(
    cnpj_companhia: str, codigo_cvm: int | None, *, por_cnpj: dict[str, Companhia], por_codigo: dict[int, Companhia]
) -> Companhia | None:
    if normalizar_texto(cnpj_companhia):
        return por_cnpj.get(cnpj_companhia)
    if codigo_cvm is None:
        return None
    return por_codigo.get(codigo_cvm)


def _atualizar_execucao(
    execucao: ExecucaoSincronizacao, contadores: dict[str, int], *, status: str | None = None
) -> None:
    execucao.total_linhas_lidas = contadores["lidas"]
    execucao.total_inseridos = contadores["inseridos"]
    execucao.total_atualizados = contadores["atualizados"]
    execucao.total_inalterados = contadores["inalterados"]
    execucao.total_rejeitados = contadores["rejeitados"]
    if status is not None:
        execucao.status = status


def _upsert_registro(
    db: Session,
    *,
    model: type[Any],
    entidade: str,
    campos_chave: tuple[str, ...],
    campos_negocio: set[str],
    dados: dict[str, Any],
    execucao_id: Any,
    contadores: dict[str, int],
) -> Any:
    filtro = [getattr(model, campo) == dados[campo] for campo in campos_chave]
    query: Select[tuple[Any]] = select(model).where(*filtro)
    existente = db.scalar(query)
    agora = _agora()

    dados_para_hash = {k: v for k, v in dados.items() if k not in {"linha_origem"}}
    dados["hash_origem"] = gerar_hash_canonico(dados_para_hash, campos_ignorados={"hash_origem"})

    if existente is None:
        novo_obj = model(**dados, criado_em=agora, sincronizado_em=agora, alterado_em=agora)
        db.add(novo_obj)
        contadores["inseridos"] += 1
        return novo_obj

    alteracoes: dict[str, tuple[Any, Any]] = {}
    for campo in campos_negocio:
        valor_antigo = getattr(existente, campo)
        valor_novo = dados[campo]
        if not _equivalente(valor_antigo, valor_novo):
            alteracoes[campo] = (valor_antigo, valor_novo)

    existente.sincronizado_em = agora
    existente.arquivo_origem = dados["arquivo_origem"]
    existente.ano_origem = dados["ano_origem"]
    existente.linha_origem = dados["linha_origem"]
    existente.hash_origem = dados["hash_origem"]

    if not alteracoes:
        contadores["inalterados"] += 1
        return existente

    for campo, (_, valor_novo) in alteracoes.items():
        setattr(existente, campo, valor_novo)
    existente.alterado_em = agora
    contadores["atualizados"] += 1
    for campo, (valor_antigo, valor_novo) in alteracoes.items():
        db.add(
            HistoricoAlteracaoCampo(
                entidade=entidade,
                entidade_id=existente.id,
                companhia_id=dados.get("companhia_id"),
                campo=campo,
                valor_anterior=_valor_historico(valor_antigo),
                valor_novo=_valor_historico(valor_novo),
                alterado_em=agora,
                execucao_sincronizacao_id=execucao_id,
                arquivo_origem=dados["arquivo_origem"],
                ano_origem=dados["ano_origem"],
            )
        )
    return existente


def _arquivos_esperados(prefixo: str, ano: int) -> set[str]:
    esperados = {
        f"{prefixo}_cia_aberta_{ano}.csv",
        f"{prefixo}_cia_aberta_composicao_capital_{ano}.csv",
        f"{prefixo}_cia_aberta_parecer_{ano}.csv",
    }
    for nome_arquivo, _, _ in arquivos_demonstracao(prefixo, ano):
        esperados.add(nome_arquivo)
    return esperados


def _sincronizar_formulario(
    db: Session, *, prefixo: str, tipo_formulario: str, ano: int, task_id: str | None = None
) -> dict[str, Any]:
    total_companhias = db.query(Companhia).count()
    if total_companhias == 0:
        raise ValueError("cadastro_companhias_nao_ingestado")

    settings = get_settings()
    arquivo_zip = f"{prefixo}_cia_aberta_{ano}.zip"
    url = f"{settings.cvm_base_url}/CIA_ABERTA/DOC/{tipo_formulario}/DADOS/{arquivo_zip}"
    execucao = ExecucaoSincronizacao(
        tipo_fonte=prefixo,
        ano=ano,
        id_tarefa=task_id,
        arquivo=arquivo_zip,
        url=url,
        status="em_execucao",
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    try:
        resposta = httpx.get(url, timeout=300)
        resposta.raise_for_status()
        payload = resposta.content
        hash_arquivo = hashlib.sha256(payload).hexdigest()
        execucao.hash_arquivo = hash_arquivo

        anterior = db.scalar(
            select(ExecucaoSincronizacao).where(
                ExecucaoSincronizacao.tipo_fonte == prefixo,
                ExecucaoSincronizacao.ano == ano,
                ExecucaoSincronizacao.hash_arquivo == hash_arquivo,
                ExecucaoSincronizacao.status == "sucesso",
                ExecucaoSincronizacao.id != execucao.id,
            )
        )
        if anterior is not None:
            execucao.status = "skipped"
            execucao.finalizada_em = _agora()
            db.commit()
            return {"execucao_id": str(execucao.id), "status": "skipped"}

        zip_buffer = io.BytesIO(payload)
        with zipfile.ZipFile(zip_buffer) as zip_ref:
            arquivos_zip = set(zip_ref.namelist())
            esperados = _arquivos_esperados(prefixo, ano)
            faltando = sorted(esperados - arquivos_zip)
            if faltando:
                raise ValueError(f"arquivo_nao_esperado_ausente: {','.join(faltando)}")

            mapa_demonstracoes = {
                nome_arquivo: (tipo_demonstracao, escopo)
                for nome_arquivo, tipo_demonstracao, escopo in arquivos_demonstracao(prefixo, ano)
            }

            contadores = {
                "lidas": 0,
                "inseridos": 0,
                "atualizados": 0,
                "inalterados": 0,
                "rejeitados": 0,
            }
            companhias_por_cnpj, companhias_por_codigo = _indexar_companhias(db)

            arquivos_processar = sorted(esperados)
            for arquivo_csv in arquivos_processar:
                with zip_ref.open(arquivo_csv) as arquivo_handle:
                    texto = _decode_csv(arquivo_handle.read())
                leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
                chaves_vistas: set[tuple[Any, ...]] = set()

                for linha_origem, linha in enumerate(leitor, start=2):
                    contadores["lidas"] += 1
                    try:
                        if arquivo_csv == f"{prefixo}_cia_aberta_{ano}.csv":
                            dados = _normalizar_documento(
                                linha,
                                tipo_formulario=tipo_formulario,
                                arquivo_origem=arquivo_csv,
                                ano_origem=ano,
                                linha_origem=linha_origem,
                            )
                            chave_natural = (
                                dados["tipo_formulario"],
                                dados["id_documento"],
                                dados["versao"],
                                dados["data_referencia"],
                            )
                            tipo_modelo = "documentos"
                        elif arquivo_csv == f"{prefixo}_cia_aberta_composicao_capital_{ano}.csv":
                            dados = _normalizar_composicao_capital(
                                linha,
                                tipo_formulario=tipo_formulario,
                                arquivo_origem=arquivo_csv,
                                ano_origem=ano,
                                linha_origem=linha_origem,
                            )
                            chave_natural = (
                                dados["tipo_formulario"],
                                dados["cnpj_companhia"],
                                dados["data_referencia"],
                                dados["versao"],
                            )
                            tipo_modelo = "composicao"
                        elif arquivo_csv == f"{prefixo}_cia_aberta_parecer_{ano}.csv":
                            dados = _normalizar_parecer(
                                linha,
                                tipo_formulario=tipo_formulario,
                                arquivo_origem=arquivo_csv,
                                ano_origem=ano,
                                linha_origem=linha_origem,
                            )
                            chave_natural = (
                                dados["tipo_formulario"],
                                dados["cnpj_companhia"],
                                dados["data_referencia"],
                                dados["versao"],
                                dados["tipo_relatorio_auditor"],
                                dados["tipo_parecer_declaracao"],
                                dados["numero_item_parecer_declaracao"],
                            )
                            tipo_modelo = "parecer"
                        else:
                            tipo_demonstracao, escopo_demonstracao = mapa_demonstracoes[arquivo_csv]
                            dados = _normalizar_demonstracao(
                                linha,
                                tipo_formulario=tipo_formulario,
                                tipo_demonstracao=tipo_demonstracao,
                                escopo_demonstracao=escopo_demonstracao,
                                arquivo_origem=arquivo_csv,
                                ano_origem=ano,
                                linha_origem=linha_origem,
                            )
                            chave_natural = (
                                dados["tipo_formulario"],
                                dados["tipo_demonstracao"],
                                dados["escopo_demonstracao"],
                                dados["cnpj_companhia"],
                                dados["data_referencia"],
                                dados["versao"],
                                dados["grupo_demonstracao"],
                                dados["ordem_exercicio"],
                                dados["data_fim_exercicio"],
                                dados["codigo_conta"],
                                dados["coluna_df"],
                            )
                            tipo_modelo = "demonstracao"
                    except Exception as exc:
                        _registrar_quarentena(
                            db,
                            execucao_id=execucao.id,
                            arquivo_origem=arquivo_csv,
                            ano_origem=ano,
                            linha_origem=linha_origem,
                            motivo=f"normalizacao_invalida: {exc}",
                            dados_originais=linha,
                        )
                        contadores["rejeitados"] += 1
                        continue

                    if chave_natural in chaves_vistas:
                        _registrar_quarentena(
                            db,
                            execucao_id=execucao.id,
                            arquivo_origem=arquivo_csv,
                            ano_origem=ano,
                            linha_origem=linha_origem,
                            motivo="chave_natural_duplicada_no_arquivo",
                            dados_originais=linha,
                        )
                        contadores["rejeitados"] += 1
                        continue
                    chaves_vistas.add(chave_natural)

                    companhia = _resolver_companhia_indexada(
                        cnpj_companhia=dados["cnpj_companhia"],
                        codigo_cvm=dados.get("codigo_cvm"),
                        por_cnpj=companhias_por_cnpj,
                        por_codigo=companhias_por_codigo,
                    )
                    if companhia is None:
                        _registrar_quarentena(
                            db,
                            execucao_id=execucao.id,
                            arquivo_origem=arquivo_csv,
                            ano_origem=ano,
                            linha_origem=linha_origem,
                            motivo="companhia_nao_encontrada",
                            dados_originais=linha,
                        )
                        contadores["rejeitados"] += 1
                        continue

                    dados["companhia_id"] = companhia.id
                    if dados.get("codigo_cvm") is None:
                        dados["codigo_cvm"] = companhia.codigo_cvm

                    if tipo_modelo == "documentos":
                        _upsert_registro(
                            db,
                            model=DocumentoFinanceiro,
                            entidade="documentos_financeiros",
                            campos_chave=("tipo_formulario", "id_documento", "versao", "data_referencia"),
                            campos_negocio=_CAMPOS_NEGOCIO_DOCUMENTOS,
                            dados=dados,
                            execucao_id=execucao.id,
                            contadores=contadores,
                        )
                    elif tipo_modelo == "demonstracao":
                        _upsert_registro(
                            db,
                            model=DemonstracaoFinanceira,
                            entidade="demonstracoes_financeiras",
                            campos_chave=(
                                "tipo_formulario",
                                "tipo_demonstracao",
                                "escopo_demonstracao",
                                "cnpj_companhia",
                                "data_referencia",
                                "versao",
                                "grupo_demonstracao",
                                "ordem_exercicio",
                                "data_fim_exercicio",
                                "codigo_conta",
                                "coluna_df",
                            ),
                            campos_negocio=_CAMPOS_NEGOCIO_DEMONSTRACOES,
                            dados=dados,
                            execucao_id=execucao.id,
                            contadores=contadores,
                        )
                    elif tipo_modelo == "composicao":
                        _upsert_registro(
                            db,
                            model=ComposicaoCapital,
                            entidade="composicoes_capital",
                            campos_chave=("tipo_formulario", "cnpj_companhia", "data_referencia", "versao"),
                            campos_negocio=_CAMPOS_NEGOCIO_COMPOSICAO,
                            dados=dados,
                            execucao_id=execucao.id,
                            contadores=contadores,
                        )
                    else:
                        _upsert_registro(
                            db,
                            model=ParecerFinanceiro,
                            entidade="pareceres_financeiros",
                            campos_chave=(
                                "tipo_formulario",
                                "cnpj_companhia",
                                "data_referencia",
                                "versao",
                                "tipo_relatorio_auditor",
                                "tipo_parecer_declaracao",
                                "numero_item_parecer_declaracao",
                            ),
                            campos_negocio=_CAMPOS_NEGOCIO_PARECERES,
                            dados=dados,
                            execucao_id=execucao.id,
                            contadores=contadores,
                        )

                    if contadores["lidas"] % _BATCH_COMMIT_LINHAS == 0:
                        _atualizar_execucao(execucao, contadores)
                        db.commit()
                        if execucao.status == "cancelada":
                            return {
                                "execucao_id": str(execucao.id),
                                "status": "cancelada",
                                "total_linhas_lidas": contadores["lidas"],
                                "total_inseridos": contadores["inseridos"],
                                "total_atualizados": contadores["atualizados"],
                                "total_inalterados": contadores["inalterados"],
                                "total_rejeitados": contadores["rejeitados"],
                            }

        if execucao.status == "cancelada":
            db.commit()
            return {
                "execucao_id": str(execucao.id),
                "status": "cancelada",
                "total_linhas_lidas": contadores["lidas"],
                "total_inseridos": contadores["inseridos"],
                "total_atualizados": contadores["atualizados"],
                "total_inalterados": contadores["inalterados"],
                "total_rejeitados": contadores["rejeitados"],
            }
        _atualizar_execucao(execucao, contadores, status="sucesso")
        execucao.finalizada_em = _agora()
        db.commit()
        return {
            "execucao_id": str(execucao.id),
            "status": "sucesso",
            "total_linhas_lidas": contadores["lidas"],
            "total_inseridos": contadores["inseridos"],
            "total_atualizados": contadores["atualizados"],
            "total_inalterados": contadores["inalterados"],
            "total_rejeitados": contadores["rejeitados"],
        }
    except Exception as exc:
        db.rollback()
        execucao_erro = db.get(ExecucaoSincronizacao, execucao.id)
        if execucao_erro is not None:
            execucao_erro.status = "falha"
            execucao_erro.mensagem_erro = str(exc)
            execucao_erro.finalizada_em = _agora()
            db.commit()
        raise


def sincronizar_dfp(db: Session, ano: int, task_id: str | None = None) -> dict[str, Any]:
    return _sincronizar_formulario(db, prefixo="dfp", tipo_formulario="DFP", ano=ano, task_id=task_id)


def sincronizar_itr(db: Session, ano: int, task_id: str | None = None) -> dict[str, Any]:
    return _sincronizar_formulario(db, prefixo="itr", tipo_formulario="ITR", ano=ano, task_id=task_id)
