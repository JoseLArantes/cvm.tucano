import csv
import hashlib
import io
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo, RegistroQuarentena
from app.services.normalizacao import normalizar_linha_cadastro, normalizar_texto

ARQUIVO_CADASTRO = "cad_cia_aberta.csv"

_CAMPOS_NEGOCIO_COMPANHIA = {
    "cnpj_companhia",
    "codigo_cvm",
    "denominacao_social",
    "denominacao_comercial",
    "situacao_registro",
    "data_registro",
    "data_constituicao",
    "data_cancelamento",
    "motivo_cancelamento",
    "data_inicio_situacao",
    "setor_atividade",
    "tipo_mercado",
    "categoria_registro",
    "data_inicio_categoria",
    "situacao_emissor",
    "data_inicio_situacao_emissor",
    "controle_acionario",
    "endereco",
    "responsavel",
    "auditor",
    "cnpj_auditor",
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
    if isinstance(valor_a, str) or isinstance(valor_b, str):
        return normalizar_texto(valor_a) == normalizar_texto(valor_b)
    return valor_a == valor_b


def _registrar_quarentena(
    db: Session,
    *,
    execucao_id: Any,
    linha_origem: int,
    motivo: str,
    dados_originais: dict[str, Any],
) -> None:
    db.add(
        RegistroQuarentena(
            execucao_sincronizacao_id=execucao_id,
            arquivo_origem=ARQUIVO_CADASTRO,
            ano_origem=None,
            linha_origem=linha_origem,
            motivo=motivo[:255] if motivo else "",
            dados_originais=dados_originais,
        )
    )


def sincronizar_cadastro_companhias(db: Session, task_id: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/{ARQUIVO_CADASTRO}"
    execucao = ExecucaoSincronizacao(
        tipo_fonte="cadastro",
        ano=None,
        id_tarefa=task_id,
        arquivo=ARQUIVO_CADASTRO,
        url=url,
        status="em_execucao",
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    try:
        resposta = httpx.get(url, timeout=120)
        resposta.raise_for_status()
        payload = resposta.content
        hash_arquivo = hashlib.sha256(payload).hexdigest()

        execucao.hash_arquivo = hash_arquivo
        anterior = db.scalar(
            select(ExecucaoSincronizacao).where(
                ExecucaoSincronizacao.tipo_fonte == "cadastro",
                ExecucaoSincronizacao.arquivo == ARQUIVO_CADASTRO,
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

        csv_texto = _decode_csv(payload)
        leitor = csv.DictReader(io.StringIO(csv_texto), delimiter=";")

        vistos: set[str] = set()
        inseridos = 0
        atualizados = 0
        inalterados = 0
        rejeitados = 0
        lidas = 0

        for linha_origem, linha in enumerate(leitor, start=2):
            lidas += 1
            try:
                normalizada = normalizar_linha_cadastro(
                    linha,
                    arquivo_origem=ARQUIVO_CADASTRO,
                    ano_origem=None,
                    linha_origem=linha_origem,
                )
            except Exception as exc:
                _registrar_quarentena(
                    db,
                    execucao_id=execucao.id,
                    linha_origem=linha_origem,
                    motivo=f"normalizacao_invalida: {exc}",
                    dados_originais=linha,
                )
                rejeitados += 1
                continue

            cnpj = normalizada["cnpj_companhia"]
            if cnpj in vistos:
                _registrar_quarentena(
                    db,
                    execucao_id=execucao.id,
                    linha_origem=linha_origem,
                    motivo="chave_natural_duplicada_no_arquivo",
                    dados_originais=linha,
                )
                rejeitados += 1
                continue
            vistos.add(cnpj)

            existente = db.scalar(select(Companhia).where(Companhia.cnpj_companhia == cnpj))
            agora = _agora()
            if existente is None:
                companhia = Companhia(**normalizada, criado_em=agora, sincronizado_em=agora, alterado_em=agora)
                db.add(companhia)
                inseridos += 1
                continue

            alteracoes: dict[str, tuple[Any, Any]] = {}
            for campo in _CAMPOS_NEGOCIO_COMPANHIA:
                valor_antigo = getattr(existente, campo)
                valor_novo = normalizada[campo]
                if not _equivalente(valor_antigo, valor_novo):
                    alteracoes[campo] = (valor_antigo, valor_novo)

            existente.sincronizado_em = agora
            existente.arquivo_origem = ARQUIVO_CADASTRO
            existente.ano_origem = None
            existente.linha_origem = linha_origem
            existente.hash_origem = normalizada["hash_origem"]

            if alteracoes:
                for campo, (_, valor_novo) in alteracoes.items():
                    setattr(existente, campo, valor_novo)
                existente.alterado_em = agora
                atualizados += 1
                for campo, (valor_antigo, valor_novo) in alteracoes.items():
                    db.add(
                        HistoricoAlteracaoCampo(
                            entidade="companhias",
                            entidade_id=existente.id,
                            companhia_id=existente.id,
                            campo=campo,
                            valor_anterior=None if valor_antigo is None else str(valor_antigo),
                            valor_novo=None if valor_novo is None else str(valor_novo),
                            alterado_em=agora,
                            execucao_sincronizacao_id=execucao.id,
                            arquivo_origem=ARQUIVO_CADASTRO,
                            ano_origem=None,
                        )
                    )
            else:
                inalterados += 1

        execucao.total_linhas_lidas = lidas
        execucao.total_inseridos = inseridos
        execucao.total_atualizados = atualizados
        execucao.total_inalterados = inalterados
        execucao.total_rejeitados = rejeitados
        execucao.status = "sucesso"
        execucao.finalizada_em = _agora()
        db.commit()
        return {
            "execucao_id": str(execucao.id),
            "status": "sucesso",
            "total_linhas_lidas": lidas,
            "total_inseridos": inseridos,
            "total_atualizados": atualizados,
            "total_inalterados": inalterados,
            "total_rejeitados": rejeitados,
        }
    except Exception as exc:
        db.rollback()
        execucao_em_erro = db.get(ExecucaoSincronizacao, execucao.id)
        if execucao_em_erro is not None:
            execucao_em_erro.status = "falha"
            execucao_em_erro.mensagem_erro = str(exc)
            execucao_em_erro.finalizada_em = _agora()
            db.commit()
        raise
