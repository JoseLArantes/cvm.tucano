from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from sqlalchemy import func, literal, or_, select
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.config import get_settings
from app.models.analise import AnaliseFatoRevision, AnaliseMaterializacaoExecucao
from app.models.companhia import Companhia
from app.models.setores import (
    Setor,
    SetorAlias,
    SetorClassificacaoCompanhia,
    SetorCorrespondencia,
    SetorTaxonomia,
    SetorTaxonomiaMudanca,
    SetorTaxonomiaVersao,
)
from app.schemas.analise import AnaliseProvenienciaItem
from app.schemas.setores import (
    AgregacaoSetorialCelula,
    AgregacaoSetorialCobertura,
    AgregacaoSetorialComponente,
    AgregacaoSetorialEstatisticas,
    AgregacaoSetorialRequest,
    AgregacaoSetorialResposta,
)
from app.services.analise import CALCULATION_VERSION

TAXONOMIA_CVM = "cvm_cadastro"
TAXONOMIA_B3 = "b3"
_ESPACOS = re.compile(r"\s+")
_FORMULAS: dict[str, tuple[str, str]] = {
    "margem_bruta": ("lucro_bruto", "receita_liquida"),
    "margem_ebit": ("ebit", "receita_liquida"),
    "margem_liquida": ("lucro_liquido", "receita_liquida"),
}


class TaxonomiaSemPublicacao(ValueError):
    pass


class FatoCanonicoInconsistente(ValueError):
    pass


class SeletorNaoEncontrado(ValueError):
    pass


def normalizar_chave_setor(rotulo: str) -> str:
    """Normaliza apenas equivalências tipográficas; acentos e pontuação são preservados."""
    compactado = _ESPACOS.sub(" ", unicodedata.normalize("NFC", rotulo).strip())
    return unicodedata.normalize("NFC", compactado.lower())


def _agora() -> datetime:
    return datetime.now(UTC)


def _garantir_taxonomias(db: Session) -> None:
    cvm = db.get(SetorTaxonomia, TAXONOMIA_CVM)
    if cvm is None:
        db.add(
            SetorTaxonomia(
                codigo=TAXONOMIA_CVM,
                nome="Setor de atividade CVM",
                fonte="Cadastro de companhias da CVM",
                ativa=True,
            )
        )
    b3 = db.get(SetorTaxonomia, TAXONOMIA_B3)
    if b3 is None:
        db.add(
            SetorTaxonomia(
                codigo=TAXONOMIA_B3,
                nome="Classificação setorial B3",
                fonte="Fonte oficial autorizada pendente",
                ativa=False,
            )
        )
    db.flush()


def publicar_taxonomia_cvm(
    db: Session,
    *,
    referencia_fonte: str | None = None,
    checksum_fonte: str | None = None,
    observada_em: datetime | None = None,
    rotulos_originais: dict[uuid.UUID, str | None] | None = None,
) -> dict[str, int | bool]:
    """Publica um snapshot do cadastro CVM e registra apenas mudanças semânticas."""
    _garantir_taxonomias(db)
    taxonomia = db.get(SetorTaxonomia, TAXONOMIA_CVM)
    assert taxonomia is not None

    companhias = list(db.scalars(select(Companhia).order_by(Companhia.id)).all())
    rotulos_por_chave: dict[str, str] = {}
    chave_por_companhia: dict[uuid.UUID, str | None] = {}
    rotulo_por_companhia: dict[uuid.UUID, str | None] = {}
    originais = rotulos_originais or {}
    for companhia in companhias:
        rotulo_origem = originais.get(companhia.id) or companhia.setor_atividade
        rotulo = (companhia.setor_atividade or "").strip()
        chave = normalizar_chave_setor(rotulo) if rotulo else None
        chave_por_companhia[companhia.id] = chave
        rotulo_por_companhia[companhia.id] = rotulo_origem
        if chave is not None:
            display = rotulo_origem if rotulo_origem is not None else rotulo
            rotulos_por_chave.setdefault(
                chave,
                unicodedata.normalize("NFC", _ESPACOS.sub(" ", display.strip())),
            )

    setores_existentes = {
        item.chave_normalizada: item
        for item in db.scalars(select(Setor).where(Setor.taxonomia == TAXONOMIA_CVM)).all()
    }
    aliases = {
        item.chave_normalizada: item
        for item in db.scalars(select(SetorAlias).where(SetorAlias.taxonomia == TAXONOMIA_CVM)).all()
    }
    setor_por_chave: dict[str, Setor] = {}
    setores_novos = 0
    setores_novos_refs: list[Setor] = []
    renomes: list[tuple[Setor, str, str]] = []
    for chave, rotulo in rotulos_por_chave.items():
        alias = aliases.get(chave)
        setor = setores_existentes.get(chave)
        if alias is not None:
            setor = db.get(Setor, alias.setor_id)
        if setor is None:
            setor = Setor(
                taxonomia=TAXONOMIA_CVM,
                chave_normalizada=chave,
                nome=rotulo,
                nivel="setor",
                ativo=True,
            )
            db.add(setor)
            setores_novos += 1
            setores_novos_refs.append(setor)
        else:
            setor.ativo = True
            if alias is None and setor.nome != rotulo:
                renomes.append((setor, setor.nome, rotulo))
                setor.nome = rotulo
        setor_por_chave[chave] = setor
    db.flush()
    ids_setores_novos = {setor.id for setor in setores_novos_refs}

    atual = list(
        db.scalars(
            select(SetorClassificacaoCompanhia).where(
                SetorClassificacaoCompanhia.taxonomia == TAXONOMIA_CVM,
                SetorClassificacaoCompanhia.versao_fim.is_(None),
            )
        ).all()
    )
    atual_por_companhia = {item.companhia_id: item for item in atual}
    destino_por_companhia: dict[uuid.UUID, tuple[Setor, str, Companhia]] = {}
    companhias_por_id = {item.id: item for item in companhias}
    for companhia_id, chave in chave_por_companhia.items():
        if chave is None:
            continue
        companhia = companhias_por_id[companhia_id]
        rotulo_destino = rotulo_por_companhia[companhia_id]
        if rotulo_destino is None:
            rotulo_destino = companhia.setor_atividade or ""
        destino_por_companhia[companhia_id] = (
            setor_por_chave[chave],
            rotulo_destino,
            companhia,
        )
    setores_em_uso = {item[0].id for item in destino_por_companhia.values()}
    for setor in setores_existentes.values():
        setor.ativo = setor.id in setores_em_uso

    semantica = sorted(
        (str(companhia_id), str(item[0].id) if item else None, rotulo_por_companhia[companhia_id])
        for companhia_id, item in (
            (companhia_id, destino_por_companhia.get(companhia_id)) for companhia_id in chave_por_companhia
        )
    )
    payload_semantico = {
        "atribuicoes": semantica,
        "rotulos": sorted((str(setor.id), setor.nome) for setor in setor_por_chave.values()),
    }
    checksum_semantico = hashlib.sha256(
        json.dumps(payload_semantico, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if taxonomia.checksum_atual == checksum_semantico:
        # A referência de entrega continua auditável sem republicar a mesma semântica.
        return {"publicada": False, "versao": taxonomia.versao_atual or 0, "setores_novos": 0, "classificacoes_alteradas": 0}

    versao = (taxonomia.versao_atual or 0) + 1
    publicada_em = _agora()
    mudancas_previstas: list[str] = []
    for companhia_id in chave_por_companhia:
        antigo = atual_por_companhia.get(companhia_id)
        destino = destino_por_companhia.get(companhia_id)
        if antigo is not None and destino is not None and antigo.setor_id == destino[0].id and antigo.rotulo_origem == destino[1]:
            continue
        if antigo is None and destino is None:
            continue
        mudancas_previstas.append(
            "adicionada" if antigo is None else "removida" if destino is None else "alterada"
        )
    publicacao = SetorTaxonomiaVersao(
        taxonomia=TAXONOMIA_CVM,
        versao=versao,
        checksum_fonte=checksum_fonte,
        checksum_semantico=checksum_semantico,
        referencia_fonte=referencia_fonte,
        observada_em=observada_em,
        publicada_em=publicada_em,
        resumo={
            "companhias": len(companhias),
            "setores": len(rotulos_por_chave),
            "classificacoes_alteradas": len(mudancas_previstas),
            "classificacoes_adicionadas": mudancas_previstas.count("adicionada"),
            "classificacoes_removidas": mudancas_previstas.count("removida"),
        },
    )
    db.add(publicacao)
    db.flush()

    alteradas = 0
    for companhia_id in chave_por_companhia:
        antigo = atual_por_companhia.get(companhia_id)
        destino = destino_por_companhia.get(companhia_id)
        setor_novo = destino[0] if destino else None
        if (
            antigo is not None
            and destino is not None
            and antigo.setor_id == destino[0].id
            and antigo.rotulo_origem == destino[1]
        ):
            continue
        if antigo is None and setor_novo is None:
            continue
        alteradas += 1
        antes = None
        if antigo is not None:
            antes = {"setor_id": str(antigo.setor_id), "rotulo_origem": antigo.rotulo_origem}
            antigo.versao_fim = versao
            antigo.fim_vigencia = publicada_em
        depois = None
        if destino is not None:
            setor, rotulo, companhia = destino
            depois = {"setor_id": str(setor.id), "rotulo_origem": rotulo}
            db.add(
                SetorClassificacaoCompanhia(
                    companhia_id=companhia_id,
                    taxonomia=TAXONOMIA_CVM,
                    setor_id=setor.id,
                    rotulo_origem=rotulo[:255],
                    fonte="cvm_cadastro",
                    referencia_fonte=referencia_fonte,
                    arquivo_origem=companhia.arquivo_origem[:255] if companhia.arquivo_origem else None,
                    linha_origem=companhia.linha_origem,
                    versao_inicio=versao,
                    inicio_vigencia=publicada_em,
                )
            )
        db.add(
            SetorTaxonomiaMudanca(
                publicacao_id=publicacao.id,
                tipo="classificacao_alterada" if antigo and destino else "classificacao_removida" if antigo else "classificacao_adicionada",
                companhia_id=companhia_id,
                setor_id=setor_novo.id if setor_novo else (antigo.setor_id if antigo else None),
                antes=antes,
                depois=depois,
            )
        )

    for chave, setor in setor_por_chave.items():
        if setor.id in ids_setores_novos:
            db.add(
                SetorTaxonomiaMudanca(
                    publicacao_id=publicacao.id,
                    tipo="setor_novo",
                    setor_id=setor.id,
                    depois={"nome": setor.nome, "chave_normalizada": chave},
                )
            )
    for setor, nome_anterior, nome_novo in renomes:
        db.add(
            SetorTaxonomiaMudanca(
                publicacao_id=publicacao.id,
                tipo="setor_renomeado",
                setor_id=setor.id,
                antes={"nome": nome_anterior},
                depois={"nome": nome_novo},
            )
        )

    taxonomia.versao_atual = versao
    taxonomia.checksum_atual = checksum_semantico
    taxonomia.referencia_fonte_atual = referencia_fonte
    taxonomia.publicada_em = publicada_em
    taxonomia.ativa = True
    db.flush()
    return {
        "publicada": True,
        "versao": versao,
        "setores_novos": setores_novos,
        "classificacoes_alteradas": alteradas,
    }


def versao_publicada(db: Session, taxonomia: str) -> SetorTaxonomia:
    catalogo = db.get(SetorTaxonomia, taxonomia)
    if catalogo is None or catalogo.versao_atual is None:
        raise TaxonomiaSemPublicacao(taxonomia)
    return catalogo


def obter_geracao_financeira(db: Session, escopo: str) -> str | None:
    geracao = db.scalar(
        select(func.max(AnaliseMaterializacaoExecucao.finished_at)).where(
            AnaliseMaterializacaoExecucao.escopo == escopo,
            AnaliseMaterializacaoExecucao.calculation_version == CALCULATION_VERSION,
            AnaliseMaterializacaoExecucao.status == "success",
            AnaliseMaterializacaoExecucao.coverage_complete.is_(True),
        )
    )
    return geracao.isoformat() if geracao is not None else None


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise FatoCanonicoInconsistente("Valor de fato canônico inválido.") from exc


def _sort_median(values: list[Decimal]) -> Decimal:
    ordenados = sorted(values)
    centro = len(ordenados) // 2
    if len(ordenados) % 2:
        return ordenados[centro]
    return (ordenados[centro - 1] + ordenados[centro]) / Decimal(2)


def _valor_grupo(companhia: Companhia, setor: Setor | None, campo: str) -> str | None:
    if campo == "setor":
        return None if setor is None else str(setor.id)
    if campo == "categoria_registro":
        return companhia.categoria_registro
    if campo == "tipo_emissor":
        return companhia.tipo_emissor
    return companhia.situacao_registro


def agregar_margens(db: Session, pedido: AgregacaoSetorialRequest) -> AgregacaoSetorialResposta:
    catalogo = versao_publicada(db, pedido.taxonomia)
    if pedido.setores:
        conhecidos = set(
            db.scalars(
                select(Setor.id).where(Setor.taxonomia == pedido.taxonomia, Setor.id.in_(pedido.setores))
            ).all()
        )
        if conhecidos != set(pedido.setores):
            raise SeletorNaoEncontrado("Um ou mais setores informados não existem nessa taxonomia.")
    stmt = (
        select(Companhia, Setor)
        .outerjoin(
            SetorClassificacaoCompanhia,
            (SetorClassificacaoCompanhia.companhia_id == Companhia.id)
            & (SetorClassificacaoCompanhia.taxonomia == pedido.taxonomia)
            & SetorClassificacaoCompanhia.versao_fim.is_(None),
        )
        .outerjoin(Setor, Setor.id == SetorClassificacaoCompanhia.setor_id)
    )
    identidade_filtros = []
    if pedido.companhia_ids:
        identidade_filtros.append(Companhia.id.in_(pedido.companhia_ids))
    if pedido.codigos_cvm:
        identidade_filtros.append(Companhia.codigo_cvm.in_(pedido.codigos_cvm))
    if identidade_filtros:
        stmt = stmt.where(or_(*identidade_filtros))
    if pedido.setores:
        stmt = stmt.where(Setor.id.in_(pedido.setores))
    if pedido.categorias_registro:
        stmt = stmt.where(Companhia.categoria_registro.in_(pedido.categorias_registro))
    if pedido.tipos_emissor:
        stmt = stmt.where(Companhia.tipo_emissor.in_(pedido.tipos_emissor))
    if pedido.situacoes_registro:
        stmt = stmt.where(Companhia.situacao_registro.in_(pedido.situacoes_registro))
    rows = db.execute(stmt.order_by(Companhia.id)).all()
    companhias = [(row[0], row[1]) for row in rows]
    if len(companhias) > 5000:
        raise ValueError("O universo selecionado excede o limite de 5.000 companhias.")
    if pedido.companhia_ids:
        ids_cadastrados = set(db.scalars(select(Companhia.id).where(Companhia.id.in_(pedido.companhia_ids))).all())
        if ids_cadastrados != set(pedido.companhia_ids):
            raise SeletorNaoEncontrado("Uma ou mais companhias informadas não existem.")
    if pedido.codigos_cvm:
        codigos_cadastrados = set(
            db.scalars(select(Companhia.codigo_cvm).where(Companhia.codigo_cvm.in_(pedido.codigos_cvm))).all()
        )
        if codigos_cadastrados != set(pedido.codigos_cvm):
            raise SeletorNaoEncontrado("Um ou mais códigos CVM informados não existem.")
    if pedido.incluir_detalhamento and len(companhias) > 500:
        raise ValueError("Detalhamento limitado a 500 companhias por requisição.")

    ids_setor = {str(value) for value in pedido.setores}
    if ids_setor and any(setor is None or str(setor.id) not in ids_setor for _, setor in companhias):
        raise ValueError("Um ou mais setores informados não pertencem à taxonomia solicitada.")

    formula_ids = {mid: _FORMULAS[mid] for mid in pedido.metricas}
    metric_ids = sorted({component for formula in formula_ids.values() for component in formula})
    codigos = [companhia.codigo_cvm for companhia, _ in companhias if companhia.codigo_cvm is not None]
    stmt_fatos = select(AnaliseFatoRevision).where(
        AnaliseFatoRevision.codigo_cvm.in_(codigos or [-1]),
        AnaliseFatoRevision.escopo == pedido.escopo,
        AnaliseFatoRevision.calculation_version == CALCULATION_VERSION,
        AnaliseFatoRevision.periodicidade == "annual",
        AnaliseFatoRevision.base_periodo == "fy",
        AnaliseFatoRevision.metric_id.in_(metric_ids),
        AnaliseFatoRevision.fiscal_year.in_(pedido.anos),
    )
    if pedido.as_of is None:
        stmt_fatos = stmt_fatos.where(AnaliseFatoRevision.known_to.is_(None))
    else:
        stmt_fatos = stmt_fatos.where(
            AnaliseFatoRevision.known_from <= pedido.as_of,
            or_(AnaliseFatoRevision.known_to.is_(None), AnaliseFatoRevision.known_to > pedido.as_of),
        )
    payload_completo = AnaliseFatoRevision.observation_payload if pedido.incluir_detalhamento else literal(None)
    fatos_compactos = db.execute(
        stmt_fatos.with_only_columns(
            AnaliseFatoRevision.codigo_cvm,
            AnaliseFatoRevision.fiscal_year,
            AnaliseFatoRevision.metric_id,
            AnaliseFatoRevision.status,
            AnaliseFatoRevision.observation_payload["value"].as_string(),
            AnaliseFatoRevision.observation_payload["unit"].as_string(),
            payload_completo,
            maintain_column_froms=True,
        )
        .order_by(AnaliseFatoRevision.codigo_cvm, AnaliseFatoRevision.fiscal_year, AnaliseFatoRevision.metric_id)
    ).all()
    valores: dict[tuple[int, int, str], tuple[Decimal, str, list[AnaliseProvenienciaItem]]] = {}
    for codigo_cvm, ano_fiscal, metric_id, status_fato, valor_fato, unidade_fato, payload in fatos_compactos:
        if status_fato != "available" or valor_fato is None:
            continue
        if not isinstance(codigo_cvm, int) or not isinstance(ano_fiscal, int) or not isinstance(metric_id, str):
            raise FatoCanonicoInconsistente("Dimensões do fato canônico têm tipos inválidos.")
        value = _decimal(valor_fato)
        unit = str(unidade_fato or "")
        key = (codigo_cvm, ano_fiscal, metric_id)
        if key in valores:
            raise FatoCanonicoInconsistente("Há mais de um fato canônico vigente para a mesma companhia, período e métrica.")
        valores[key] = (
            value,
            unit,
            [
                AnaliseProvenienciaItem.model_validate(item)
                for item in (payload if isinstance(payload, dict) else {}).get("provenance", [])
            ],
        )

    agrupadas: dict[tuple[str | None, ...], list[tuple[Companhia, Setor | None]]] = defaultdict(list)
    if not pedido.agrupar_por:
        agrupadas[()].extend(companhias)
    else:
        for companhia, setor in companhias:
            chave = tuple(_valor_grupo(companhia, setor, campo) for campo in pedido.agrupar_por)
            agrupadas[chave].append((companhia, setor))
        if not agrupadas:
            agrupadas[tuple(None for _ in pedido.agrupar_por)] = []
    quantidade_celulas = len(agrupadas) * len(set(pedido.anos)) * len(pedido.metricas)
    if quantidade_celulas > 5000:
        raise ValueError("O recorte excede o limite de 5.000 células; reduza anos, métricas ou dimensões.")

    celulas: list[AgregacaoSetorialCelula] = []
    detalhes: list[AgregacaoSetorialComponente] = []
    for chave, membros in sorted(agrupadas.items(), key=lambda item: tuple(value or "" for value in item[0])):
        grupo: dict[str, str | None] = {}
        for campo, valor in zip(pedido.agrupar_por, chave, strict=True):
            if campo == "setor":
                grupo["setor_id"] = valor
                grupo["setor"] = next((s.nome for _, s in membros if s is not None and str(s.id) == valor), None)
            else:
                grupo[campo] = valor
        for ano in sorted(set(pedido.anos)):
            period_id = f"FY{ano}"
            for metric_id in pedido.metricas:
                numerador_metric, denominador_metric = formula_ids[metric_id]
                margens: list[Decimal] = []
                soma_numeradores = Decimal(0)
                soma_denominadores = Decimal(0)
                motivos: Counter[str] = Counter()
                selecionadas = len(membros)
                for companhia, _ in membros:
                    codigo = companhia.codigo_cvm
                    if codigo is None:
                        motivos["sem_codigo_cvm"] += 1
                        continue
                    numerador = valores.get((codigo, ano, numerador_metric))
                    denominador = valores.get((codigo, ano, denominador_metric))
                    if numerador is None or denominador is None:
                        motivos["fato_ausente"] += 1
                        continue
                    if numerador[1] != "BRL" or denominador[1] != "BRL" or numerador[1] != denominador[1]:
                        motivos["unidade_incompativel"] += 1
                        continue
                    if denominador[0] <= 0:
                        motivos["receita_nao_positiva"] += 1
                        continue
                    margem = numerador[0] / denominador[0]
                    margens.append(margem)
                    soma_numeradores += numerador[0]
                    soma_denominadores += denominador[0]
                    if pedido.incluir_detalhamento:
                        detalhe_grupo = dict(grupo)
                        if not pedido.agrupar_por:
                            detalhe_grupo = {}
                        detalhes.append(
                            AgregacaoSetorialComponente(
                                companhia_id=companhia.id,
                                codigo_cvm=codigo,
                                denominacao_social=companhia.denominacao_social,
                                grupo=detalhe_grupo,
                                period_id=period_id,
                                metric_id=metric_id,
                                numerador=numerador[0],
                                denominador=denominador[0],
                                margem=margem,
                                proveniencia_numerador=numerador[2],
                                proveniencia_denominador=denominador[2],
                            )
                        )
                elegiveis = len(margens)
                status: Literal["disponivel", "parcial", "indisponivel"] = (
                    "indisponivel" if elegiveis == 0 else "disponivel" if elegiveis == selecionadas else "parcial"
                )
                celulas.append(
                    AgregacaoSetorialCelula(
                        grupo=grupo,
                        period_id=period_id,
                        metric_id=metric_id,
                        status=status,
                        estatisticas=AgregacaoSetorialEstatisticas(
                            media_simples=(sum(margens, Decimal(0)) / elegiveis if elegiveis else None)
                            if "media_simples" in pedido.estatisticas
                            else None,
                            mediana=(_sort_median(margens) if elegiveis else None)
                            if "mediana" in pedido.estatisticas
                            else None,
                            razao_das_somas=(soma_numeradores / soma_denominadores if soma_denominadores > 0 else None)
                            if "razao_das_somas" in pedido.estatisticas
                            else None,
                        ),
                        cobertura=AgregacaoSetorialCobertura(
                            selecionadas=selecionadas,
                            elegiveis=elegiveis,
                            excluidas=selecionadas - elegiveis,
                            motivos=dict(motivos),
                        ),
                    )
                )

    geracao_dt = db.scalar(
        select(func.max(AnaliseMaterializacaoExecucao.finished_at)).where(
            AnaliseMaterializacaoExecucao.escopo == pedido.escopo,
            AnaliseMaterializacaoExecucao.calculation_version == CALCULATION_VERSION,
            AnaliseMaterializacaoExecucao.status == "success",
            AnaliseMaterializacaoExecucao.coverage_complete.is_(True),
        )
    )
    geracao = geracao_dt.isoformat() if geracao_dt is not None else None
    request_canonico = pedido.model_dump(mode="json")
    fingerprint = hashlib.sha256(
        json.dumps(
            {"request": request_canonico, "taxonomia": catalogo.versao_atual, "financeiro": geracao},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return AgregacaoSetorialResposta(
        taxonomia=pedido.taxonomia,
        versao_taxonomia=catalogo.versao_atual or 0,
        escopo=pedido.escopo,
        calculation_version=CALCULATION_VERSION,
        as_of=pedido.as_of,
        geracao_financeira=geracao,
        fingerprint=fingerprint,
        selecionadas=len(companhias),
        celulas=celulas,
        detalhamento=detalhes if pedido.incluir_detalhamento else None,
    )


def agregar_margens_com_cache(db: Session, pedido: AgregacaoSetorialRequest) -> AgregacaoSetorialResposta:
    settings = get_settings()
    catalogo = versao_publicada(db, pedido.taxonomia)
    geracao_dt = db.scalar(
        select(func.max(AnaliseMaterializacaoExecucao.finished_at)).where(
            AnaliseMaterializacaoExecucao.escopo == pedido.escopo,
            AnaliseMaterializacaoExecucao.calculation_version == CALCULATION_VERSION,
            AnaliseMaterializacaoExecucao.status == "success",
            AnaliseMaterializacaoExecucao.coverage_complete.is_(True),
        )
    )
    versao_financeira = geracao_dt.isoformat() if geracao_dt else None
    corpo = pedido.model_dump(mode="json")
    chave_hash = hashlib.sha256(
        json.dumps(
            {"request": corpo, "taxonomia": catalogo.versao_atual, "financeiro": versao_financeira},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    cache_key = f"setores:agregacao:v1:{chave_hash}"
    cacheable = settings.setores_cache_enabled and not pedido.incluir_detalhamento
    lock_key = f"{cache_key}:lock"
    lock_token: str | None = None
    if cacheable:
        cached = cache.get(cache_key)
        if cached:
            try:
                return AgregacaoSetorialResposta.model_validate_json(cached)
            except ValueError:
                pass
        lock_token = cache.acquire_lock(lock_key, settings.setores_cache_lock_seconds)
        if lock_token == "":
            aguardado = cache.wait_for(cache_key, settings.setores_cache_wait_seconds)
            if aguardado:
                try:
                    return AgregacaoSetorialResposta.model_validate_json(aguardado)
                except ValueError:
                    pass
            lock_token = None
    try:
        resposta = agregar_margens(db, pedido)
        if cacheable:
            cache.set(cache_key, resposta.model_dump_json(), settings.setores_cache_ttl_seconds)
        return resposta
    finally:
        if lock_token:
            cache.release_lock(lock_key, lock_token)


def listar_correspondencias(db: Session, setor_id: uuid.UUID) -> list[SetorCorrespondencia]:
    stmt = select(SetorCorrespondencia).where(
        or_(SetorCorrespondencia.setor_origem_id == setor_id, SetorCorrespondencia.setor_destino_id == setor_id)
    )
    return list(db.scalars(stmt.order_by(SetorCorrespondencia.versao_mapeamento.desc())).all())
