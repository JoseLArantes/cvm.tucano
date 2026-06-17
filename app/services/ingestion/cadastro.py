from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.identidade import CompanhiaIdentificador, CompanhiaMercado, CompanhiaRegistroCvm
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.dedup import buscar_execucao_hash_existente
from app.services.ingestion.normalizers import (
    gerar_hash_canonico,
    normalizar_cnpj_opcional,
    normalizar_codigo_cvm,
    normalizar_data,
    normalizar_nome_emissor_chave,
    normalizar_texto,
    normalizar_tipo_mercado,
)
from app.services.ingestion.resolver import limpar_caches_resolver

ARQUIVO_CADASTRO_ABERTA = "cad_cia_aberta.csv"
ARQUIVO_CADASTRO_ESTRANGEIRA = "cad_cia_estrang.csv"
FONTE_CADASTRO_ABERTA = "cad_cia_aberta"
FONTE_CADASTRO_ESTRANGEIRA = "cad_cia_estrang"


@dataclass(frozen=True)
class CadastroNormalizationResult:
    status: str
    data: dict[str, Any] | None
    reason_code: str | None = None
    details: dict[str, Any] | None = None


def _agora() -> datetime:
    return datetime.now(UTC)


def _decode_csv(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "latin1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", payload, 0, 1, "Falha ao decodificar CSV")


def _normalizar_endereco(row: dict[str, Any], *, prefixo: str = "") -> dict[str, Any]:
    suffix = prefixo
    return {
        "tipo_endereco": normalizar_texto(row.get(f"TP_ENDER{suffix}")),
        "logradouro": normalizar_texto(row.get(f"LOGRADOURO{suffix}")),
        "complemento": normalizar_texto(row.get(f"COMPL{suffix}")),
        "bairro": normalizar_texto(row.get(f"BAIRRO{suffix}")),
        "municipio": normalizar_texto(row.get(f"MUN{suffix}")),
        "uf": normalizar_texto(row.get(f"UF{suffix}")),
        "pais": normalizar_texto(row.get(f"PAIS{suffix}")),
        "cep": normalizar_texto(row.get(f"CEP{suffix}")),
        "ddd_telefone": normalizar_texto(row.get(f"DDD_TEL{suffix}")),
        "telefone": normalizar_texto(row.get(f"TEL{suffix}")),
        "ddd_fax": normalizar_texto(row.get(f"DDD_FAX{suffix}")),
        "fax": normalizar_texto(row.get(f"FAX{suffix}")),
        "email": normalizar_texto(row.get(f"EMAIL{suffix}")),
    }


def _normalizar_responsavel(row: dict[str, Any]) -> dict[str, Any]:
    data_inicio = normalizar_data(row.get("DT_INI_RESP"))
    return {
        "tipo_responsavel": normalizar_texto(row.get("TP_RESP")),
        "nome_responsavel": normalizar_texto(row.get("RESP")),
        "data_inicio_responsavel": data_inicio.isoformat() if data_inicio is not None else None,
        "logradouro": normalizar_texto(row.get("LOGRADOURO_RESP")),
        "complemento": normalizar_texto(row.get("COMPL_RESP")),
        "bairro": normalizar_texto(row.get("BAIRRO_RESP")),
        "municipio": normalizar_texto(row.get("MUN_RESP")),
        "uf": normalizar_texto(row.get("UF_RESP")),
        "pais": normalizar_texto(row.get("PAIS_RESP")),
        "cep": normalizar_texto(row.get("CEP_RESP")),
        "ddd_telefone": normalizar_texto(row.get("DDD_TEL_RESP")),
        "telefone": normalizar_texto(row.get("TEL_RESP")),
        "ddd_fax": normalizar_texto(row.get("DDD_FAX_RESP")),
        "fax": normalizar_texto(row.get("FAX_RESP")),
        "email": normalizar_texto(row.get("EMAIL_RESP")),
    }


def normalizar_linha_cadastro_aberta(
    row: dict[str, Any],
    *,
    linha_origem: int,
    arquivo_origem: str = ARQUIVO_CADASTRO_ABERTA,
) -> CadastroNormalizationResult:
    cnpj_companhia = normalizar_cnpj_opcional(row.get("CNPJ_CIA"))
    codigo_cvm = normalizar_codigo_cvm(row.get("CD_CVM"))
    denominacao_social = normalizar_texto(row.get("DENOM_SOCIAL"))
    if cnpj_companhia is None and codigo_cvm is None:
        return CadastroNormalizationResult(
            status="invalid",
            data=None,
            reason_code="identidade_ausente",
            details={"linha_origem": linha_origem},
        )
    if denominacao_social is None:
        return CadastroNormalizationResult(
            status="invalid",
            data=None,
            reason_code="denominacao_social_ausente",
            details={"linha_origem": linha_origem},
        )

    endereco = _normalizar_endereco(row)
    responsavel = _normalizar_responsavel(row)
    data = {
        "fonte_cadastro": FONTE_CADASTRO_ABERTA,
        "arquivo_origem": arquivo_origem,
        "linha_origem": linha_origem,
        "ano_origem": None,
        "cnpj_companhia": cnpj_companhia,
        "codigo_cvm": codigo_cvm,
        "denominacao_social": denominacao_social,
        "denominacao_comercial": normalizar_texto(row.get("DENOM_COMERC")),
        "nome_emissor_chave": normalizar_nome_emissor_chave(denominacao_social),
        "pais_origem": normalizar_texto(row.get("PAIS")),
        "situacao_registro": normalizar_texto(row.get("SIT")),
        "data_registro": normalizar_data(row.get("DT_REG")),
        "data_constituicao": normalizar_data(row.get("DT_CONST")),
        "data_cancelamento": normalizar_data(row.get("DT_CANCEL")),
        "motivo_cancelamento": normalizar_texto(row.get("MOTIVO_CANCEL")),
        "data_inicio_situacao": normalizar_data(row.get("DT_INI_SIT")),
        "setor_atividade": normalizar_texto(row.get("SETOR_ATIV")),
        "tipo_mercado": normalizar_tipo_mercado(row.get("TP_MERC")),
        "categoria_registro": normalizar_texto(row.get("CATEG_REG")),
        "data_inicio_categoria": normalizar_data(row.get("DT_INI_CATEG")),
        "situacao_emissor": normalizar_texto(row.get("SIT_EMISSOR")),
        "data_inicio_situacao_emissor": normalizar_data(row.get("DT_INI_SIT_EMISSOR")),
        "controle_acionario": normalizar_texto(row.get("CONTROLE_ACIONARIO")),
        "endereco": endereco,
        "responsavel": responsavel,
        "auditor": normalizar_texto(row.get("AUDITOR")),
        "cnpj_auditor": normalizar_cnpj_opcional(row.get("CNPJ_AUDITOR")),
    }
    data["hash_sem_mercado"] = gerar_hash_canonico(
        {k: v for k, v in data.items() if k not in {"tipo_mercado", "hash_origem", "hash_sem_mercado"}}
    )
    data["hash_origem"] = gerar_hash_canonico({k: v for k, v in data.items() if k != "hash_origem"})
    return CadastroNormalizationResult(status="valid", data=data)


def normalizar_linha_cadastro_estrangeira(
    row: dict[str, Any],
    *,
    linha_origem: int,
    arquivo_origem: str = ARQUIVO_CADASTRO_ESTRANGEIRA,
) -> CadastroNormalizationResult:
    cnpj_companhia = normalizar_cnpj_opcional(row.get("CNPJ"))
    codigo_cvm = normalizar_codigo_cvm(row.get("CD_CVM"))
    denominacao_social = normalizar_texto(row.get("DENOM_SOCIAL"))
    if cnpj_companhia is None and codigo_cvm is None:
        return CadastroNormalizationResult(
            status="invalid",
            data=None,
            reason_code="identidade_ausente",
            details={"linha_origem": linha_origem},
        )
    if denominacao_social is None:
        return CadastroNormalizationResult(
            status="invalid",
            data=None,
            reason_code="denominacao_social_ausente",
            details={"linha_origem": linha_origem},
        )

    data = {
        "fonte_cadastro": FONTE_CADASTRO_ESTRANGEIRA,
        "arquivo_origem": arquivo_origem,
        "linha_origem": linha_origem,
        "ano_origem": None,
        "cnpj_companhia": cnpj_companhia,
        "codigo_cvm": codigo_cvm,
        "denominacao_social": denominacao_social,
        "denominacao_comercial": normalizar_texto(row.get("DENOM_COMERC")),
        "nome_emissor_chave": normalizar_nome_emissor_chave(denominacao_social),
        "pais_origem": normalizar_texto(row.get("PAIS_ORIGEM")),
        "situacao_registro": normalizar_texto(row.get("SIT")),
        "data_registro": normalizar_data(row.get("DT_REG")),
        "data_constituicao": normalizar_data(row.get("DT_CONST")),
        "data_cancelamento": normalizar_data(row.get("DT_CANCEL")),
        "motivo_cancelamento": normalizar_texto(row.get("MOTIVO_CANCEL")),
        "data_inicio_situacao": normalizar_data(row.get("DT_INI_SIT")),
        "setor_atividade": normalizar_texto(row.get("SETOR_ATIV")),
        "tipo_mercado": None,
        "categoria_registro": normalizar_texto(row.get("CATEG_REG")),
        "data_inicio_categoria": normalizar_data(row.get("DT_INI_CATEG")),
        "situacao_emissor": normalizar_texto(row.get("SIT_EMISSOR")),
        "data_inicio_situacao_emissor": normalizar_data(row.get("DT_INI_SIT_EMISSOR")),
        "controle_acionario": normalizar_texto(row.get("CONTROLE_ACIONARIO")),
        "endereco": {},
        "responsavel": {},
        "auditor": normalizar_texto(row.get("AUDITOR")),
        "cnpj_auditor": normalizar_cnpj_opcional(row.get("CNPJ_AUDITOR")),
    }
    data["hash_sem_mercado"] = gerar_hash_canonico(
        {k: v for k, v in data.items() if k not in {"tipo_mercado", "hash_origem", "hash_sem_mercado"}}
    )
    data["hash_origem"] = gerar_hash_canonico({k: v for k, v in data.items() if k != "hash_origem"})
    return CadastroNormalizationResult(status="valid", data=data)


def selecionar_registro_canonico(registros: Iterable[dict[str, Any]]) -> dict[str, Any]:
    registros_lista = list(registros)
    return sorted(registros_lista, key=_chave_ordenacao_registro)[0]


def _chave_ordenacao_registro(registro: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
    situacao = (registro.get("situacao_registro") or "").upper()
    fonte = registro.get("fonte_cadastro")
    return (
        0 if situacao == "ATIVO" else 1,
        0 if registro.get("data_cancelamento") is None else 1,
        -_ordinal(registro.get("data_inicio_situacao")),
        -_ordinal(registro.get("data_registro")),
        0 if fonte == FONTE_CADASTRO_ABERTA else 1,
        registro.get("linha_origem") or 0,
    )


def _ordinal(valor: Any) -> int:
    return 0 if valor is None else valor.toordinal()


def _chave_grupo_companhia(registro: dict[str, Any]) -> tuple[str, str]:
    if registro.get("cnpj_companhia"):
        return ("cnpj", registro["cnpj_companhia"])
    return ("codigo_cvm", str(registro["codigo_cvm"]))


def _buscar_companhia_existente(db: Session, registro: dict[str, Any]) -> Companhia | None:
    cnpj = registro.get("cnpj_companhia")
    codigo_cvm = registro.get("codigo_cvm")
    filtros = []
    if cnpj is not None:
        filtros.append(Companhia.cnpj_companhia == cnpj)
    if codigo_cvm is not None:
        filtros.append(Companhia.codigo_cvm == codigo_cvm)
    if not filtros:
        return None
    return db.scalar(select(Companhia).where(or_(*filtros)))


def _upsert_companhia(db: Session, registro_canonico: dict[str, Any]) -> Companhia:
    companhia = _buscar_companhia_existente(db, registro_canonico)
    agora = _agora()
    if companhia is None:
        companhia = Companhia(
            cnpj_companhia=registro_canonico.get("cnpj_companhia") or f"sem-cnpj-{registro_canonico['codigo_cvm']}",
            codigo_cvm=registro_canonico.get("codigo_cvm"),
            denominacao_social=registro_canonico.get("denominacao_social"),
            denominacao_comercial=registro_canonico.get("denominacao_comercial"),
            situacao_registro=registro_canonico.get("situacao_registro"),
            data_registro=registro_canonico.get("data_registro"),
            data_constituicao=registro_canonico.get("data_constituicao"),
            data_cancelamento=registro_canonico.get("data_cancelamento"),
            motivo_cancelamento=registro_canonico.get("motivo_cancelamento"),
            data_inicio_situacao=registro_canonico.get("data_inicio_situacao"),
            setor_atividade=registro_canonico.get("setor_atividade"),
            tipo_mercado=registro_canonico.get("tipo_mercado"),
            categoria_registro=registro_canonico.get("categoria_registro"),
            data_inicio_categoria=registro_canonico.get("data_inicio_categoria"),
            situacao_emissor=registro_canonico.get("situacao_emissor"),
            data_inicio_situacao_emissor=registro_canonico.get("data_inicio_situacao_emissor"),
            controle_acionario=registro_canonico.get("controle_acionario"),
            endereco=registro_canonico.get("endereco") or {},
            responsavel=registro_canonico.get("responsavel") or {},
            auditor=registro_canonico.get("auditor"),
            cnpj_auditor=registro_canonico.get("cnpj_auditor"),
            tipo_emissor="estrangeira"
            if registro_canonico["fonte_cadastro"] == FONTE_CADASTRO_ESTRANGEIRA
            else "aberta",
            fonte_identidade_principal=registro_canonico["fonte_cadastro"],
            qualidade_identidade="alta",
            arquivo_origem=registro_canonico["arquivo_origem"],
            ano_origem=registro_canonico.get("ano_origem"),
            linha_origem=registro_canonico.get("linha_origem"),
            hash_origem=registro_canonico["hash_origem"],
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
        db.add(companhia)
        db.flush()
        return companhia

    companhia.codigo_cvm = companhia.codigo_cvm or registro_canonico.get("codigo_cvm")
    companhia.denominacao_social = registro_canonico.get("denominacao_social")
    companhia.denominacao_comercial = registro_canonico.get("denominacao_comercial")
    companhia.situacao_registro = registro_canonico.get("situacao_registro")
    companhia.data_registro = registro_canonico.get("data_registro")
    companhia.data_constituicao = registro_canonico.get("data_constituicao")
    companhia.data_cancelamento = registro_canonico.get("data_cancelamento")
    companhia.motivo_cancelamento = registro_canonico.get("motivo_cancelamento")
    companhia.data_inicio_situacao = registro_canonico.get("data_inicio_situacao")
    companhia.setor_atividade = registro_canonico.get("setor_atividade")
    companhia.tipo_mercado = registro_canonico.get("tipo_mercado")
    companhia.categoria_registro = registro_canonico.get("categoria_registro")
    companhia.data_inicio_categoria = registro_canonico.get("data_inicio_categoria")
    companhia.situacao_emissor = registro_canonico.get("situacao_emissor")
    companhia.data_inicio_situacao_emissor = registro_canonico.get("data_inicio_situacao_emissor")
    companhia.controle_acionario = registro_canonico.get("controle_acionario")
    companhia.endereco = registro_canonico.get("endereco") or {}
    companhia.responsavel = registro_canonico.get("responsavel") or {}
    companhia.auditor = registro_canonico.get("auditor")
    companhia.cnpj_auditor = registro_canonico.get("cnpj_auditor")
    companhia.tipo_emissor = (
        "estrangeira" if registro_canonico["fonte_cadastro"] == FONTE_CADASTRO_ESTRANGEIRA else "aberta"
    )
    companhia.fonte_identidade_principal = registro_canonico["fonte_cadastro"]
    companhia.qualidade_identidade = "alta"
    companhia.arquivo_origem = registro_canonico["arquivo_origem"]
    companhia.ano_origem = registro_canonico.get("ano_origem")
    companhia.linha_origem = registro_canonico.get("linha_origem")
    companhia.hash_origem = registro_canonico["hash_origem"]
    companhia.sincronizado_em = agora
    companhia.alterado_em = agora
    return companhia


def _upsert_registro_cvm(db: Session, companhia: Companhia, registro: dict[str, Any]) -> CompanhiaRegistroCvm:
    cnpj_companhia = registro.get("cnpj_companhia")
    codigo_cvm = registro.get("codigo_cvm")

    existente = db.scalar(
        select(CompanhiaRegistroCvm).where(
            CompanhiaRegistroCvm.companhia_id == companhia.id,
            CompanhiaRegistroCvm.fonte_cadastro == registro["fonte_cadastro"],
            CompanhiaRegistroCvm.cnpj_companhia.is_(None)
            if cnpj_companhia is None
            else CompanhiaRegistroCvm.cnpj_companhia == cnpj_companhia,
            CompanhiaRegistroCvm.codigo_cvm.is_(None)
            if codigo_cvm is None
            else CompanhiaRegistroCvm.codigo_cvm == codigo_cvm,
        )
    )
    if existente is None:
        existente = CompanhiaRegistroCvm(
            companhia_id=companhia.id,
            fonte_cadastro=registro["fonte_cadastro"],
            cnpj_companhia=registro.get("cnpj_companhia"),
            codigo_cvm=registro.get("codigo_cvm"),
            denominacao_social=registro.get("denominacao_social"),
            denominacao_comercial=registro.get("denominacao_comercial"),
            pais_origem=registro.get("pais_origem"),
            situacao_registro=registro.get("situacao_registro"),
            data_registro=registro.get("data_registro"),
            data_constituicao=registro.get("data_constituicao"),
            data_cancelamento=registro.get("data_cancelamento"),
            motivo_cancelamento=registro.get("motivo_cancelamento"),
            data_inicio_situacao=registro.get("data_inicio_situacao"),
            setor_atividade=registro.get("setor_atividade"),
            categoria_registro=registro.get("categoria_registro"),
            data_inicio_categoria=registro.get("data_inicio_categoria"),
            situacao_emissor=registro.get("situacao_emissor"),
            data_inicio_situacao_emissor=registro.get("data_inicio_situacao_emissor"),
            controle_acionario=registro.get("controle_acionario"),
            endereco=registro.get("endereco"),
            responsavel=registro.get("responsavel"),
            auditor=registro.get("auditor"),
            cnpj_auditor=registro.get("cnpj_auditor"),
            hash_sem_mercado=registro["hash_sem_mercado"],
            hash_origem=registro["hash_origem"],
            arquivo_origem=registro["arquivo_origem"],
            linha_origem=registro.get("linha_origem"),
        )
        db.add(existente)
        db.flush()
        return existente

    existente.hash_origem = registro["hash_origem"]
    existente.arquivo_origem = registro["arquivo_origem"]
    existente.linha_origem = registro.get("linha_origem")
    existente.denominacao_social = registro.get("denominacao_social")
    existente.denominacao_comercial = registro.get("denominacao_comercial")
    existente.pais_origem = registro.get("pais_origem")
    existente.situacao_registro = registro.get("situacao_registro")
    existente.data_registro = registro.get("data_registro")
    existente.data_constituicao = registro.get("data_constituicao")
    existente.data_cancelamento = registro.get("data_cancelamento")
    existente.motivo_cancelamento = registro.get("motivo_cancelamento")
    existente.data_inicio_situacao = registro.get("data_inicio_situacao")
    existente.setor_atividade = registro.get("setor_atividade")
    existente.categoria_registro = registro.get("categoria_registro")
    existente.data_inicio_categoria = registro.get("data_inicio_categoria")
    existente.situacao_emissor = registro.get("situacao_emissor")
    existente.data_inicio_situacao_emissor = registro.get("data_inicio_situacao_emissor")
    existente.controle_acionario = registro.get("controle_acionario")
    existente.endereco = registro.get("endereco")
    existente.responsavel = registro.get("responsavel")
    existente.auditor = registro.get("auditor")
    existente.cnpj_auditor = registro.get("cnpj_auditor")
    return existente


def _upsert_mercado(db: Session, registro_cvm: CompanhiaRegistroCvm, registro: dict[str, Any]) -> None:
    tipo_mercado = registro.get("tipo_mercado")
    existente = db.scalar(
        select(CompanhiaMercado).where(
            CompanhiaMercado.companhia_registro_cvm_id == registro_cvm.id,
            CompanhiaMercado.tipo_mercado.is_(None)
            if tipo_mercado is None
            else CompanhiaMercado.tipo_mercado == tipo_mercado,
        )
    )
    if existente is None:
        db.add(
            CompanhiaMercado(
                companhia_registro_cvm_id=registro_cvm.id,
                tipo_mercado=tipo_mercado,
                arquivo_origem=registro["arquivo_origem"],
                linha_origem=registro.get("linha_origem"),
                hash_origem=registro["hash_origem"],
            )
        )


def _upsert_identificador(
    db: Session,
    *,
    companhia: Companhia,
    tipo: str,
    valor: str,
    valor_normalizado: str,
    fonte: str,
    confianca: str = "alta",
) -> None:
    existente = db.scalar(
        select(CompanhiaIdentificador).where(
            CompanhiaIdentificador.companhia_id == companhia.id,
            CompanhiaIdentificador.tipo == tipo,
            CompanhiaIdentificador.valor_normalizado == valor_normalizado,
            CompanhiaIdentificador.fonte == fonte,
        )
    )
    if existente is None:
        db.add(
            CompanhiaIdentificador(
                companhia_id=companhia.id,
                tipo=tipo,
                valor=valor,
                valor_normalizado=valor_normalizado,
                fonte=fonte,
                confianca=confianca,
                ativo=True,
            )
        )
        db.flush()
        return
    existente.ativo = True
    existente.confianca = confianca


def gerar_identificadores_companhia(db: Session, *, companhia: Companhia, registros: Iterable[dict[str, Any]]) -> None:
    for registro in registros:
        cnpj = registro.get("cnpj_companhia")
        codigo_cvm = registro.get("codigo_cvm")
        if cnpj:
            _upsert_identificador(
                db,
                companhia=companhia,
                tipo="cnpj",
                valor=cnpj,
                valor_normalizado=cnpj,
                fonte=registro["fonte_cadastro"],
            )
        if codigo_cvm is not None:
            codigo_texto = str(codigo_cvm)
            _upsert_identificador(
                db,
                companhia=companhia,
                tipo="codigo_cvm",
                valor=codigo_texto,
                valor_normalizado=codigo_texto,
                fonte=registro["fonte_cadastro"],
            )


def promover_registros_cadastro(db: Session, registros: Iterable[dict[str, Any]]) -> dict[str, int]:
    grupos: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for registro in registros:
        grupos.setdefault(_chave_grupo_companhia(registro), []).append(registro)

    contadores = {"companhias": 0, "registros": 0, "mercados": 0, "identificadores": 0}
    for registros_companhia in grupos.values():
        registro_canonico = selecionar_registro_canonico(registros_companhia)
        companhia = _upsert_companhia(db, registro_canonico)
        contadores["companhias"] += 1
        for registro in registros_companhia:
            registro_cvm = _upsert_registro_cvm(db, companhia, registro)
            contadores["registros"] += 1
            if registro.get("tipo_mercado") is not None:
                _upsert_mercado(db, registro_cvm, registro)
                contadores["mercados"] += 1
        gerar_identificadores_companhia(db, companhia=companhia, registros=registros_companhia)
        contadores["identificadores"] += len(
            [
                valor
                for registro in registros_companhia
                for valor in (registro.get("cnpj_companhia"), registro.get("codigo_cvm"))
                if valor is not None
            ]
        )
    db.flush()
    return contadores


def _ler_csv(payload: bytes) -> list[dict[str, str]]:
    import csv
    import io

    return list(csv.DictReader(io.StringIO(_decode_csv(payload)), delimiter=";"))


def _download(url: str, *, timeout: float) -> bytes:
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def pre_processar_cadastro(
    db: Session,
    *,
    execucao_id: uuid.UUID,
    task_id: str | None = None,
    force_reimport: bool = False,
    downloader: Any | None = None,
) -> dict[str, Any]:
    from pathlib import Path

    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.file_manager import (
        count_csv_rows,
        detect_encoding_and_delimiter,
        download_file_to_disk,
        get_csv_header,
    )
    from app.services.ingestion.staging import (
        create_run,
        register_file,
        register_member,
        update_run_state,
    )

    settings = get_settings()
    execucao = db.get(ExecucaoSincronizacao, execucao_id)
    if execucao is None:
        raise ValueError(f"Execution not found: {execucao_id}")

    run = create_run(
        db,
        tipo_fonte="cadastro",
        ano=None,
        status="em_execucao",
        phase="stage",
        execucao_sincronizacao_id=execucao.id,
        requested_by_task_id=task_id,
    )

    url_aberta = f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/{ARQUIVO_CADASTRO_ABERTA}"
    url_estrang = f"{settings.cvm_base_url}/CIA_ESTRANG/CAD/DADOS/{ARQUIVO_CADASTRO_ESTRANGEIRA}"

    storage_path = Path(settings.storage_dir) / str(execucao.id)
    dest_abertas = storage_path / ARQUIVO_CADASTRO_ABERTA
    dest_estrangeiras = storage_path / ARQUIVO_CADASTRO_ESTRANGEIRA

    try:
        if downloader is not None:
            dest_abertas.parent.mkdir(parents=True, exist_ok=True)
            content_ab = downloader(url_aberta)
            dest_abertas.write_bytes(content_ab)
            hash_abertas = hashlib.sha256(content_ab).hexdigest()

            content_es = downloader(url_estrang)
            dest_estrangeiras.write_bytes(content_es)
            hash_estrangeiras = hashlib.sha256(content_es).hexdigest()
        else:
            hash_abertas = download_file_to_disk(url_aberta, str(dest_abertas), timeout=120)
            hash_estrangeiras = download_file_to_disk(url_estrang, str(dest_estrangeiras), timeout=120)

        hash_arquivo = hashlib.sha256(f"{hash_abertas}:{hash_estrangeiras}".encode()).hexdigest()
        execucao.hash_arquivo = hash_arquivo

        anterior = buscar_execucao_hash_existente(
            db,
            tipo_fonte="cadastro",
            ano=None,
            hash_arquivo=hash_arquivo,
            execucao_atual_id=execucao.id,
        )
        if anterior is not None and not force_reimport:
            execucao.status = "skipped"
            execucao.finalizada_em = _agora()
            update_run_state(run, status="skipped", phase="complete", finished_at=_agora())
            db.commit()

            # Clean up disk
            import shutil
            try:
                shutil.rmtree(storage_path)
            except Exception:
                pass

            return {"execucao_id": str(execucao.id), "status": "skipped"}

        # Register abertas
        file_aberta = register_file(
            db,
            ingestion_run=run,
            source_url=url_aberta,
            source_filename=ARQUIVO_CADASTRO_ABERTA,
            content_sha256=hash_abertas,
            content_length_bytes=dest_abertas.stat().st_size,
        )
        enc_aberta, del_aberta = detect_encoding_and_delimiter(str(dest_abertas))
        header_aberta = get_csv_header(str(dest_abertas), enc_aberta, del_aberta)
        rows_aberta = count_csv_rows(str(dest_abertas), enc_aberta, del_aberta)
        register_member(
            db,
            ingestion_file=file_aberta,
            member_name=ARQUIVO_CADASTRO_ABERTA,
            member_sha256=hash_abertas,
            member_size_bytes=dest_abertas.stat().st_size,
            header=header_aberta,
            row_count=rows_aberta,
            encoding=enc_aberta,
            delimiter=del_aberta,
        )

        # Register estrangeiras
        file_estrang = register_file(
            db,
            ingestion_run=run,
            source_url=url_estrang,
            source_filename=ARQUIVO_CADASTRO_ESTRANGEIRA,
            content_sha256=hash_estrangeiras,
            content_length_bytes=dest_estrangeiras.stat().st_size,
        )
        enc_estrang, del_estrang = detect_encoding_and_delimiter(str(dest_estrangeiras))
        header_estrang = get_csv_header(str(dest_estrangeiras), enc_estrang, del_estrang)
        rows_estrang = count_csv_rows(str(dest_estrangeiras), enc_estrang, del_estrang)
        register_member(
            db,
            ingestion_file=file_estrang,
            member_name=ARQUIVO_CADASTRO_ESTRANGEIRA,
            member_sha256=hash_estrangeiras,
            member_size_bytes=dest_estrangeiras.stat().st_size,
            header=header_estrang,
            row_count=rows_estrang,
            encoding=enc_estrang,
            delimiter=del_estrang,
        )

        execucao.status = "aguardando_ingestao"
        update_run_state(run, status="aguardando_ingestao", phase="stage")
        db.commit()
        return {"execucao_id": str(execucao.id), "status": "aguardando_ingestao"}

    except Exception as exc:
        db.rollback()
        execucao_erro = db.get(ExecucaoSincronizacao, execucao.id)
        if execucao_erro is not None:
            execucao_erro.status = "falha"
            execucao_erro.mensagem_erro = str(exc)
            execucao_erro.finalizada_em = _agora()
            db.commit()

        import shutil
        try:
            shutil.rmtree(storage_path)
        except Exception:
            pass
        raise


def ingerir_cadastro(
    db: Session,
    *,
    execucao_id: uuid.UUID,
    downloader: Any | None = None,
) -> dict[str, Any]:
    from pathlib import Path

    from app.models.ingestion import IngestionRun
    from app.services.ingestion.file_manager import (
        detect_encoding_and_delimiter,
        download_file_to_disk,
    )
    from app.services.ingestion.staging import (
        read_staged_csv_rows_from_disk,
        update_run_state,
    )

    settings = get_settings()
    execucao = db.get(ExecucaoSincronizacao, execucao_id)
    if execucao is None:
        raise ValueError(f"Execution not found: {execucao_id}")

    if execucao.status != "aguardando_ingestao":
        return {
            "execucao_id": str(execucao.id),
            "status": execucao.status,
            "message": f"Execution is in state '{execucao.status}', not 'aguardando_ingestao'."
        }

    execucao.status = "em_execucao"
    run = db.scalar(
        select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)
    )
    if run is not None:
        update_run_state(run, status="em_execucao", phase="stage")
    db.commit()

    storage_path = Path(settings.storage_dir) / str(execucao.id)
    dest_abertas = storage_path / ARQUIVO_CADASTRO_ABERTA
    dest_estrangeiras = storage_path / ARQUIVO_CADASTRO_ESTRANGEIRA

    try:
        # Self-healing fallback: make sure both files are on disk
        url_aberta = f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/{ARQUIVO_CADASTRO_ABERTA}"
        url_estrang = f"{settings.cvm_base_url}/CIA_ESTRANG/CAD/DADOS/{ARQUIVO_CADASTRO_ESTRANGEIRA}"

        if not dest_abertas.exists():
            if downloader is not None:
                dest_abertas.parent.mkdir(parents=True, exist_ok=True)
                dest_abertas.write_bytes(downloader(url_aberta))
            else:
                download_file_to_disk(url_aberta, str(dest_abertas), timeout=120)
        if not dest_estrangeiras.exists():
            if downloader is not None:
                dest_estrangeiras.parent.mkdir(parents=True, exist_ok=True)
                dest_estrangeiras.write_bytes(downloader(url_estrang))
            else:
                download_file_to_disk(url_estrang, str(dest_estrangeiras), timeout=120)

        enc_aberta, del_aberta = detect_encoding_and_delimiter(str(dest_abertas))
        _, rows_aberta_tuples, _ = read_staged_csv_rows_from_disk(str(dest_abertas), enc_aberta, delimiter=del_aberta)
        abertas = [row for _, row in rows_aberta_tuples]

        enc_estrang, del_estrang = detect_encoding_and_delimiter(str(dest_estrangeiras))
        _, rows_estrang_tuples, _ = read_staged_csv_rows_from_disk(str(dest_estrangeiras), enc_estrang, delimiter=del_estrang)
        estrangeiras = [row for _, row in rows_estrang_tuples]

        normalizados: list[dict[str, Any]] = []
        rejeitados = 0

        for linha_origem, row in enumerate(abertas, start=2):
            resultado = normalizar_linha_cadastro_aberta(row, linha_origem=linha_origem)
            if resultado.status != "valid" or resultado.data is None:
                rejeitados += 1
                continue
            normalizados.append(resultado.data)

        for linha_origem, row in enumerate(estrangeiras, start=2):
            resultado = normalizar_linha_cadastro_estrangeira(row, linha_origem=linha_origem)
            if resultado.status != "valid" or resultado.data is None:
                rejeitados += 1
                continue
            normalizados.append(resultado.data)

        contadores = promover_registros_cadastro(db, normalizados)

        execucao.total_linhas_lidas = len(abertas) + len(estrangeiras)
        execucao.total_inseridos = contadores["registros"]
        execucao.total_atualizados = 0
        execucao.total_inalterados = 0
        execucao.total_rejeitados = rejeitados
        execucao.status = "sucesso"
        execucao.finalizada_em = _agora()

        if run is not None:
            update_run_state(run, status="sucesso", phase="complete", finished_at=_agora())
        db.commit()

        # Clean up files
        import shutil
        try:
            shutil.rmtree(storage_path)
        except Exception:
            pass

        return {
            "execucao_id": str(execucao.id),
            "status": "sucesso",
            "total_linhas_lidas": execucao.total_linhas_lidas,
            "total_rejeitados": rejeitados,
            "total_companhias_promovidas": contadores["companhias"],
            "total_registros_promovidos": contadores["registros"],
        }

    except Exception as exc:
        db.rollback()
        execucao_erro = db.get(ExecucaoSincronizacao, execucao.id)
        if execucao_erro is not None:
            execucao_erro.status = "falha"
            execucao_erro.mensagem_erro = str(exc)
            execucao_erro.finalizada_em = _agora()
            db.commit()

        # Clean up files
        import shutil
        try:
            shutil.rmtree(storage_path)
        except Exception:
            pass
        raise


def sincronizar_cadastro_companhias(
    db: Session,
    *,
    task_id: str | None = None,
    force_reimport: bool = False,
    downloader: Any | None = None,
) -> dict[str, Any]:
    import uuid

    limpar_caches_resolver()
    settings = get_settings()

    url_aberta = f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/{ARQUIVO_CADASTRO_ABERTA}"
    url_estrang = f"{settings.cvm_base_url}/CIA_ESTRANG/CAD/DADOS/{ARQUIVO_CADASTRO_ESTRANGEIRA}"

    execucao = ExecucaoSincronizacao(
        tipo_fonte="cadastro",
        ano=None,
        id_tarefa=task_id,
        arquivo=f"{ARQUIVO_CADASTRO_ABERTA}+{ARQUIVO_CADASTRO_ESTRANGEIRA}",
        url=f"{url_aberta}|{url_estrang}",
        status="em_execucao",
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    # 1. Pre-process
    phase1_res = pre_processar_cadastro(
        db,
        execucao_id=execucao.id,
        task_id=task_id,
        force_reimport=force_reimport,
        downloader=downloader,
    )
    if phase1_res["status"] == "skipped":
        return phase1_res

    # 2. Ingest
    return ingerir_cadastro(
        db,
        execucao_id=uuid.UUID(phase1_res["execucao_id"]),
        downloader=downloader,
    )
