from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.setores import (
    Setor,
    SetorTaxonomia,
    SetorTaxonomiaImportacao,
    SetorTaxonomiaMudanca,
    SetorTaxonomiaVersao,
)
from app.services.setores import normalizar_chave_setor

TAXONOMIA_B3 = "b3"
URL_CLASSIFICACAO_B3 = (
    "https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/acoes/consultas/classificacao-setorial/"
)
MAX_ARQUIVO_B3_BYTES = 10 * 1024 * 1024
MAX_LINHAS_PLANILHA_B3 = 10_000
_ESPACOS = re.compile(r"\s+")
_NIVEIS = {"setor": 0, "subsetor": 1, "segmento": 2}


@dataclass(frozen=True)
class NoHierarquiaB3:
    chave_normalizada: str
    nome: str
    nivel: str
    chave_pai: str | None


def _texto_celula(value: Any) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFC", _ESPACOS.sub(" ", str(value).strip()))


def _cabecalho(value: str) -> str:
    return _texto_celula(value).upper()


def _linha_cabecalho(setor: str, subsetor: str, segmento: str) -> bool:
    return (
        _cabecalho(setor) in {"SETOR", "SETOR ECONÔMICO"}
        and _cabecalho(subsetor) == "SUBSETOR"
        and _cabecalho(segmento) == "SEGMENTO"
    )


def _chave_no(nivel: str, componentes: tuple[str, ...]) -> str:
    return json.dumps(
        [nivel, *(normalizar_chave_setor(componente) for componente in componentes)],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _ler_caminhos_aba(worksheet: Any) -> set[tuple[str, str, str]] | None:
    if worksheet.max_row is not None and worksheet.max_row > MAX_LINHAS_PLANILHA_B3:
        raise ValueError(f"A aba {worksheet.title!r} excede o limite de {MAX_LINHAS_PLANILHA_B3} linhas.")

    cabecalho_encontrado = False
    setor_atual = ""
    subsetor_atual = ""
    caminhos: set[tuple[str, str, str]] = set()
    for numero_linha, linha in enumerate(worksheet.iter_rows(max_col=4, values_only=True), start=1):
        setor = _texto_celula(linha[1] if len(linha) > 1 else None)
        subsetor = _texto_celula(linha[2] if len(linha) > 2 else None)
        segmento = _texto_celula(linha[3] if len(linha) > 3 else None)
        if _linha_cabecalho(setor, subsetor, segmento):
            cabecalho_encontrado = True
            setor_atual = ""
            subsetor_atual = ""
            continue
        if not cabecalho_encontrado or not (setor or subsetor or segmento):
            continue
        if setor:
            setor_atual = setor
            subsetor_atual = ""
        if subsetor:
            subsetor_atual = subsetor
        if segmento:
            if not setor_atual or not subsetor_atual:
                raise ValueError(f"A linha {numero_linha} da aba {worksheet.title!r} não tem hierarquia completa.")
            caminhos.add((setor_atual, subsetor_atual, segmento))
    return caminhos if cabecalho_encontrado else None


def extrair_hierarquia_b3(conteudo: bytes) -> list[NoHierarquiaB3]:
    if not conteudo:
        raise ValueError("O arquivo enviado está vazio.")
    if len(conteudo) > MAX_ARQUIVO_B3_BYTES:
        raise ValueError(f"O arquivo excede o limite de {MAX_ARQUIVO_B3_BYTES} bytes.")

    try:
        workbook = load_workbook(
            filename=BytesIO(conteudo),
            read_only=True,
            data_only=True,
            keep_links=False,
        )
    except (BadZipFile, InvalidFileException, KeyError, OSError, ValueError) as exc:
        raise ValueError("O arquivo não é uma planilha XLSX válida.") from exc

    try:
        abas_com_hierarquia: list[set[tuple[str, str, str]]] = []
        for worksheet in workbook.worksheets:
            caminhos = _ler_caminhos_aba(worksheet)
            if caminhos is not None:
                abas_com_hierarquia.append(caminhos)
        if len(abas_com_hierarquia) != 1:
            raise ValueError("A planilha deve conter exatamente uma aba com a hierarquia B3 esperada.")
        caminhos = abas_com_hierarquia[0]
        if not caminhos:
            raise ValueError("A planilha não contém segmentos B3 com setor e subsetor.")

        nos: dict[str, NoHierarquiaB3] = {}
        for setor, subsetor, segmento in caminhos:
            chave_setor = _chave_no("setor", (setor,))
            chave_subsetor = _chave_no("subsetor", (setor, subsetor))
            chave_segmento = _chave_no("segmento", (setor, subsetor, segmento))
            nos.setdefault(chave_setor, NoHierarquiaB3(chave_setor, setor, "setor", None))
            nos.setdefault(chave_subsetor, NoHierarquiaB3(chave_subsetor, subsetor, "subsetor", chave_setor))
            nos.setdefault(chave_segmento, NoHierarquiaB3(chave_segmento, segmento, "segmento", chave_subsetor))

        if any(len(no.chave_normalizada) > 255 for no in nos.values()):
            raise ValueError("Um caminho hierárquico B3 excede o limite de 255 caracteres.")
        return sorted(nos.values(), key=lambda no: (_NIVEIS[no.nivel], no.chave_normalizada))
    finally:
        workbook.close()


def _checksum_semantico(nos: list[NoHierarquiaB3]) -> str:
    payload = [
        {
            "chave": no.chave_normalizada,
            "nome": no.nome,
            "nivel": no.nivel,
            "pai": no.chave_pai,
        }
        for no in nos
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _garantir_taxonomia_b3(db: Session) -> SetorTaxonomia:
    taxonomia = db.get(SetorTaxonomia, TAXONOMIA_B3)
    if taxonomia is None:
        taxonomia = SetorTaxonomia(
            codigo=TAXONOMIA_B3,
            nome="Classificação setorial B3",
            fonte="ClassifSetorial.xlsx (importação manual pendente)",
            ativa=False,
        )
        db.add(taxonomia)
        db.flush()
    return taxonomia


def importar_taxonomia_b3(
    db: Session,
    *,
    conteudo: bytes,
    nome_arquivo: str,
    data_atualizacao_fonte: date | None,
    importado_por: str,
    referencia_fonte: str = URL_CLASSIFICACAO_B3,
    observacao: str | None = None,
) -> SetorTaxonomiaImportacao:
    if len(conteudo) > MAX_ARQUIVO_B3_BYTES:
        raise ValueError(f"O arquivo excede o limite de {MAX_ARQUIVO_B3_BYTES} bytes.")
    nome = Path(nome_arquivo).name[:255] or "ClassifSetorial.xlsx"
    checksum_fonte = hashlib.sha256(conteudo).hexdigest()
    caminho = Path(get_settings().storage_dir) / "setores" / TAXONOMIA_B3 / f"{checksum_fonte}.xlsx"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not caminho.exists():
        caminho.write_bytes(conteudo)

    taxonomia = _garantir_taxonomia_b3(db)
    importacao = SetorTaxonomiaImportacao(
        taxonomia=TAXONOMIA_B3,
        nome_arquivo=nome,
        caminho_artefato=str(caminho),
        checksum_sha256=checksum_fonte,
        tamanho_bytes=len(conteudo),
        data_atualizacao_fonte=data_atualizacao_fonte,
        importado_por=importado_por[:128],
        status="processando",
        resumo={"referencia_fonte": referencia_fonte, "observacao": observacao},
    )
    db.add(importacao)
    db.flush()
    agora = datetime.now(UTC)
    try:
        nos = extrair_hierarquia_b3(conteudo)
    except ValueError as exc:
        importacao.status = "rejeitada"
        importacao.erro = str(exc)
        importacao.resumo = {"referencia_fonte": referencia_fonte, "observacao": observacao}
        importacao.concluida_em = agora
        db.flush()
        return importacao

    resumo = {
        "referencia_fonte": referencia_fonte,
        "observacao": observacao,
        "setores": sum(no.nivel == "setor" for no in nos),
        "subsetores": sum(no.nivel == "subsetor" for no in nos),
        "segmentos": sum(no.nivel == "segmento" for no in nos),
        "classificacoes_de_emissores_importadas": 0,
    }
    checksum_semantico = _checksum_semantico(nos)
    if taxonomia.checksum_atual == checksum_semantico and taxonomia.versao_atual is not None:
        importacao.status = "sem_alteracao"
        importacao.versao_taxonomia = taxonomia.versao_atual
        importacao.resumo = resumo
        importacao.concluida_em = agora
        db.flush()
        return importacao

    existentes = {
        item.chave_normalizada: item
        for item in db.scalars(select(Setor).where(Setor.taxonomia == TAXONOMIA_B3)).all()
    }
    por_chave: dict[str, Setor] = {}
    ids_ativos: set[uuid.UUID] = set()
    mudancas: list[tuple[str, Setor, dict[str, Any] | None, dict[str, Any] | None]] = []
    for nivel in ("setor", "subsetor", "segmento"):
        for no in (item for item in nos if item.nivel == nivel):
            pai = por_chave.get(no.chave_pai) if no.chave_pai is not None else None
            setor = existentes.get(no.chave_normalizada)
            if setor is None:
                setor = Setor(
                    taxonomia=TAXONOMIA_B3,
                    chave_normalizada=no.chave_normalizada,
                    nome=no.nome,
                    nivel=no.nivel,
                    setor_pai_id=pai.id if pai else None,
                    ativo=True,
                )
                db.add(setor)
                db.flush()
                mudancas.append(
                    ("setor_novo", setor, None, {"nome": no.nome, "nivel": no.nivel, "chave": no.chave_normalizada})
                )
            else:
                estado_anterior: dict[str, Any] = {
                    "nome": setor.nome,
                    "nivel": setor.nivel,
                    "setor_pai_id": str(setor.setor_pai_id) if setor.setor_pai_id else None,
                }
                estado_novo: dict[str, Any] = {
                    "nome": no.nome,
                    "nivel": no.nivel,
                    "setor_pai_id": str(pai.id) if pai else None,
                }
                if setor.nome != no.nome:
                    setor.nome = no.nome
                    mudancas.append(("setor_renomeado", setor, estado_anterior, estado_novo))
                elif setor.nivel != no.nivel or setor.setor_pai_id != (pai.id if pai else None):
                    mudancas.append(("setor_rehierarquizado", setor, estado_anterior, estado_novo))
                setor.nivel = no.nivel
                setor.setor_pai_id = pai.id if pai else None
                setor.ativo = True
            por_chave[no.chave_normalizada] = setor
            ids_ativos.add(setor.id)
        db.flush()

    for setor in existentes.values():
        if setor.id not in ids_ativos and setor.ativo:
            setor.ativo = False
            mudancas.append(
                (
                    "setor_desativado",
                    setor,
                    {"nome": setor.nome, "nivel": setor.nivel, "chave": setor.chave_normalizada},
                    None,
                )
            )

    versao = (taxonomia.versao_atual or 0) + 1
    observada_em = (
        datetime.combine(data_atualizacao_fonte, time.min, tzinfo=UTC) if data_atualizacao_fonte is not None else None
    )
    publicacao = SetorTaxonomiaVersao(
        taxonomia=TAXONOMIA_B3,
        versao=versao,
        checksum_fonte=checksum_fonte,
        checksum_semantico=checksum_semantico,
        referencia_fonte=referencia_fonte[:255],
        observada_em=observada_em,
        publicada_em=agora,
        resumo={**resumo, "arquivo": nome, "importacao_id": str(importacao.id)},
    )
    db.add(publicacao)
    db.flush()
    for tipo, setor, mudanca_antes, mudanca_depois in mudancas:
        db.add(
            SetorTaxonomiaMudanca(
                publicacao_id=publicacao.id,
                tipo=tipo,
                setor_id=setor.id,
                antes=mudanca_antes,
                depois=mudanca_depois,
            )
        )

    taxonomia.fonte = "Classificação setorial da B3 (arquivo manual)"
    taxonomia.ativa = True
    taxonomia.versao_atual = versao
    taxonomia.checksum_atual = checksum_semantico
    taxonomia.referencia_fonte_atual = referencia_fonte[:255]
    taxonomia.publicada_em = agora
    importacao.status = "sucesso"
    importacao.versao_taxonomia = versao
    importacao.resumo = {**resumo, "nos_publicados": len(nos), "mudancas": len(mudancas)}
    importacao.concluida_em = agora
    db.flush()
    return importacao
