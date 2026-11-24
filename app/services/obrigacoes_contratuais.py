from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.models.obrigacoes_contratuais import ObrigacaoContratualRegistro
from app.schemas.obrigacoes_contratuais import (
    AcordoPayload,
    BreachPayload,
    CashLegPayload,
    CovenantPayload,
    CovenantTestPayload,
    CoveragePayload,
    CrossDefaultPayload,
    EvidenciaContratual,
    LoteRegistrosContratuaisInput,
    MaturityChangePayload,
    PayloadContratual,
    ProceedingPayload,
    RegistroContratualInput,
    RegistroContratualResposta,
    WaiverPayload,
)


class ConflitoRevisaoContratualError(ValueError):
    """Uma chave de revisão já existe com conteúdo diferente."""


_PAYLOAD_MODELS: dict[str, Any] = {
    "acordo": AcordoPayload,
    "covenant": CovenantPayload,
    "covenant_test": CovenantTestPayload,
    "breach": BreachPayload,
    "waiver": WaiverPayload,
    "cash_leg": CashLegPayload,
    "maturity_change": MaturityChangePayload,
    "cross_default": CrossDefaultPayload,
    "proceeding": ProceedingPayload,
    "coverage": CoveragePayload,
}


def validar_payload_contratual(payload: dict[str, Any]) -> PayloadContratual:
    model = _PAYLOAD_MODELS.get(str(payload.get("record_type")))
    if model is None:
        raise ValueError("tipo_registro_contratual_desconhecido")
    return cast(PayloadContratual, model.model_validate(payload))


def _json_compactado(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _serializar_registro(registro: RegistroContratualInput) -> dict[str, Any]:
    payload = registro.model_dump(mode="json", exclude_none=False)
    if isinstance(registro.payload, CovenantTestPayload):
        payload["payload"]["resultado_calculado"] = _calcular_resultado(registro.payload)
    return payload


def _calcular_resultado(payload: Any) -> str:
    if not isinstance(payload, CovenantTestPayload) or payload.valor_aferido is None:
        return "indisponivel"
    value = payload.valor_aferido
    limit = payload.limite
    passou = {
        "lt": value < limit,
        "lte": value <= limit,
        "gt": value > limit,
        "gte": value >= limit,
        "eq": value == limit,
    }[payload.comparador]
    return "passou" if passou else "falhou"


def _calcular_fingerprint(registro_data: dict[str, Any]) -> str:
    conteudo = _json_compactado(registro_data).encode("utf-8")
    return hashlib.sha256(conteudo).hexdigest()


def _chunks(values: list[str], size: int = 100) -> Iterable[list[str]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def _validar_relacoes_lote(
    db: Session,
    *,
    codigo_cvm: int,
    preparar: dict[tuple[str, str, int], tuple[RegistroContratualInput, dict[str, Any], str]],
) -> None:
    tipos_relacionais = ["acordo", "covenant", "covenant_test", "cash_leg", "cross_default", "proceeding"]
    existentes = db.execute(
        select(
            ObrigacaoContratualRegistro.tipo_registro,
            ObrigacaoContratualRegistro.registro_id,
            ObrigacaoContratualRegistro.acordo_id,
            ObrigacaoContratualRegistro.payload,
            ObrigacaoContratualRegistro.revisao,
        ).where(
            ObrigacaoContratualRegistro.codigo_cvm == codigo_cvm,
            ObrigacaoContratualRegistro.tipo_registro.in_(tipos_relacionais),
        )
    ).all()
    atuais: dict[tuple[str, str], tuple[str | None, dict[str, Any], int]] = {}
    for tipo, registro_id, acordo_id, payload, revisao in existentes:
        chave = (cast(str, tipo), cast(str, registro_id))
        atual = atuais.get(chave)
        revisao_atual = cast(int, revisao)
        if atual is None or revisao_atual > atual[2]:
            atuais[chave] = (cast(str | None, acordo_id), cast(dict[str, Any], payload), revisao_atual)
    for (tipo, registro_id, revisao), (registro, dados, _) in preparar.items():
        chave = (tipo, registro_id)
        atual = atuais.get(chave)
        if atual is None or revisao > atual[2]:
            atuais[chave] = (registro.acordo_id, dados["payload"], revisao)

    acordos = {registro_id for (tipo, registro_id) in atuais if tipo == "acordo"}
    covenants = {
        payload.get("covenant_id"): (acordo_id, payload)
        for (tipo, _), (acordo_id, payload, _) in atuais.items()
        if tipo == "covenant"
    }
    testes = {
        registro_id: (acordo_id, payload)
        for (tipo, registro_id), (acordo_id, payload, _) in atuais.items()
        if tipo == "covenant_test"
    }
    parcelas = {
        registro_id: acordo_id
        for (tipo, registro_id), (acordo_id, _, _) in atuais.items()
        if tipo == "cash_leg"
    }
    cross_defaults = {
        registro_id: (acordo_id, CrossDefaultPayload.model_validate(payload))
        for (tipo, registro_id), (acordo_id, payload, _) in atuais.items()
        if tipo == "cross_default"
    }
    proceeding_event_ids = {registro_id for (tipo, registro_id) in atuais if tipo == "proceeding"}

    for registro, _, _ in preparar.values():
        payload = registro.payload
        if isinstance(payload, AcordoPayload):
            continue
        if isinstance(payload, CoveragePayload):
            continue
        if isinstance(payload, ProceedingPayload):
            if any(
                event_id == registro.registro_id or event_id not in proceeding_event_ids
                for event_id in payload.eventos_relacionados
            ):
                raise ValueError("evento_relacionado_deve_identificar_outro_ato_existente")
            continue
        if registro.acordo_id not in acordos:
            raise ValueError("acordo_referenciado_nao_encontrado")
        if isinstance(payload, CovenantPayload):
            continue
        if isinstance(payload, CovenantTestPayload):
            covenant = covenants.get(payload.covenant_id)
            if covenant is None or covenant[0] != registro.acordo_id:
                raise ValueError("covenant_referenciado_nao_encontrado_no_acordo")
        elif isinstance(payload, BreachPayload):
            covenant = covenants.get(payload.covenant_id)
            teste = testes.get(payload.test_id)
            if (
                covenant is None
                or teste is None
                or covenant[0] != registro.acordo_id
                or teste[0] != registro.acordo_id
                or teste[1].get("covenant_id") != payload.covenant_id
            ):
                raise ValueError("violacao_deve_referenciar_covenant_e_teste_do_acordo")
        elif isinstance(payload, WaiverPayload):
            covenant = covenants.get(payload.covenant_id)
            if covenant is None or covenant[0] != registro.acordo_id:
                raise ValueError("waiver_requer_covenant_do_acordo")
            if any(
                teste_id not in testes
                or testes[teste_id][0] != registro.acordo_id
                or testes[teste_id][1].get("covenant_id") != payload.covenant_id
                for teste_id in payload.test_ids_cobertos
            ):
                raise ValueError("waiver_deve_referenciar_testes_do_covenant")
        elif isinstance(payload, CashLegPayload):
            continue
        elif isinstance(payload, MaturityChangePayload):
            if any(parcelas.get(parcela_id) != registro.acordo_id for parcela_id in payload.cash_leg_ids):
                raise ValueError("alteracao_vencimento_deve_referenciar_parcelas_do_acordo")
            if payload.base_aceleracao == "cross_default":
                cross = cross_defaults.get(payload.cross_default_id or "")
                if (
                    cross is None
                    or cross[0] != cross[1].acordo_origem_id
                    or cross[1].acordo_origem_id not in acordos
                    or registro.acordo_id != cross[1].acordo_afetado_id
                ):
                    raise ValueError("alteracao_cross_default_deve_referenciar_acordo_afetado")
        elif isinstance(payload, CrossDefaultPayload):
            if (
                registro.acordo_id != payload.acordo_origem_id
                or payload.acordo_origem_id not in acordos
                or payload.acordo_afetado_id not in acordos
            ):
                raise ValueError("cross_default_deve_referenciar_acordos_existentes")


def gravar_lote_registros_contratuais(
    db: Session,
    *,
    codigo_cvm: int,
    lote: LoteRegistrosContratuaisInput,
    registrado_por: str,
    _retry_integrity_conflict: bool = True,
) -> tuple[int, int, list[ObrigacaoContratualRegistro]]:
    """Valida conflitos e grava o lote numa única transação."""
    preparar: dict[tuple[str, str, int], tuple[RegistroContratualInput, dict[str, Any], str]] = {}
    duplicados_no_lote = 0
    for registro in lote.registros:
        chave: tuple[str, str, int] = (registro.payload.record_type, registro.registro_id, registro.revisao)
        dados = _serializar_registro(registro)
        fingerprint = _calcular_fingerprint(dados)
        existente_no_lote = preparar.get(chave)
        if existente_no_lote is not None:
            if existente_no_lote[2] != fingerprint:
                raise ConflitoRevisaoContratualError("revisao_duplicada_no_lote_com_conteudo_divergente")
            duplicados_no_lote += 1
            continue
        preparar[chave] = (registro, dados, fingerprint)

    ids = sorted({registro.registro_id for registro, _, _ in preparar.values()})
    tipos = sorted({registro.payload.record_type for registro, _, _ in preparar.values()})
    existentes: dict[tuple[str, str, int], ObrigacaoContratualRegistro] = {}
    for ids_chunk in _chunks(ids):
        encontrados = db.scalars(
            select(ObrigacaoContratualRegistro).where(
                ObrigacaoContratualRegistro.codigo_cvm == codigo_cvm,
                ObrigacaoContratualRegistro.tipo_registro.in_(tipos),
                ObrigacaoContratualRegistro.registro_id.in_(ids_chunk),
            )
        ).all()
        for item in encontrados:
            existentes[(item.tipo_registro, item.registro_id, item.revisao)] = item

    idempotentes = duplicados_no_lote
    novos: list[ObrigacaoContratualRegistro] = []
    respostas: list[ObrigacaoContratualRegistro] = []
    for chave, (registro, dados, fingerprint) in preparar.items():
        existente = existentes.get(chave)
        if existente is not None:
            if existente.fingerprint != fingerprint:
                raise ConflitoRevisaoContratualError("revisao_existente_com_conteudo_divergente")
            idempotentes += 1
            respostas.append(existente)
            continue
        payload = registro.payload
        acordo_id = registro.acordo_id
        novo = ObrigacaoContratualRegistro(
            codigo_cvm=codigo_cvm,
            tipo_registro=payload.record_type,
            registro_id=registro.registro_id,
            revisao=registro.revisao,
            acordo_id=acordo_id,
            disponivel_em=registro.disponivel_em,
            efetivo_em=registro.efetivo_em,
            payload=dados["payload"],
            evidencias=[e.model_dump(mode="json", exclude_none=False) for e in registro.evidencias],
            revisor_id=registro.revisor_id,
            fingerprint=fingerprint,
            registrado_por=registrado_por,
            rationale=registro.rationale,
        )
        novos.append(novo)
        respostas.append(novo)

    _validar_relacoes_lote(db, codigo_cvm=codigo_cvm, preparar=preparar)

    try:
        if novos:
            db.add_all(novos)
            db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _retry_integrity_conflict:
            # Uma requisição idêntica pode vencer uma corrida entre a leitura e
            # a inserção. Recarregue as chaves após o rollback para tratá-la
            # como idempotente; conteúdo divergente segue retornando conflito.
            return gravar_lote_registros_contratuais(
                db,
                codigo_cvm=codigo_cvm,
                lote=lote,
                registrado_por=registrado_por,
                _retry_integrity_conflict=False,
            )
        raise ConflitoRevisaoContratualError("conflito_de_revisao_contratual") from exc
    except Exception:
        db.rollback()
        raise

    return len(novos), idempotentes, respostas


def _resultado_registro(
    row: ObrigacaoContratualRegistro,
    *,
    as_of: date,
    waivers: list[ObrigacaoContratualRegistro],
    maturity_changes: list[ObrigacaoContratualRegistro],
    cross_defaults: dict[str, ObrigacaoContratualRegistro],
) -> RegistroContratualResposta:
    payload: dict[str, Any] = dict(row.payload)
    resultado_calculado: str | None = None
    calculado_em: date | None = None
    waiver_aplicavel = False
    vencimento_efetivo: date | None = None
    projecao_aplicada = False

    if row.tipo_registro == "covenant_test":
        teste = CovenantTestPayload.model_validate(payload)
        calculado_em = teste.data_teste
        if teste.data_teste <= as_of:
            resultado_calculado = _calcular_resultado(teste)
            for item in waivers:
                waiver = WaiverPayload.model_validate(item.payload)
                if (
                    item.acordo_id == row.acordo_id
                    and waiver.covenant_id == teste.covenant_id
                    and row.registro_id in waiver.test_ids_cobertos
                    and waiver.implementado
                    and waiver.inicio_vigencia <= teste.data_teste
                    and (waiver.fim_vigencia is None or waiver.fim_vigencia >= teste.data_teste)
                    and (waiver.implementado_em is None or waiver.implementado_em <= as_of)
                    and (waiver.retirado_em is None or waiver.retirado_em > teste.data_teste)
                ):
                    waiver_aplicavel = True
                    break
        else:
            resultado_calculado = "indisponivel"
        payload["resultado_calculado"] = resultado_calculado

    if row.tipo_registro == "cash_leg":
        cash_leg = CashLegPayload.model_validate(payload)
        vencimento_efetivo = cash_leg.vencimento_original
        mudancas_aplicaveis = []
        for item in maturity_changes:
            mudanca = MaturityChangePayload.model_validate(item.payload)
            if cash_leg.parcela_id not in mudanca.cash_leg_ids or item.acordo_id != row.acordo_id:
                continue
            if mudanca.base_aceleracao == "cross_default":
                gatilho = cross_defaults.get(mudanca.cross_default_id or "")
                if gatilho is None:
                    continue
                dados_gatilho = CrossDefaultPayload.model_validate(gatilho.payload)
                if dados_gatilho.acordo_afetado_id != item.acordo_id or dados_gatilho.acordo_origem_id != gatilho.acordo_id:
                    continue
                if gatilho.efetivo_em is None or gatilho.efetivo_em > as_of:
                    continue
                if not (
                    gatilho.revisor_id
                    and gatilho.payload.get("gatilho_confirmado")
                    and gatilho.payload.get("condicoes_satisfeitas")
                ):
                    continue
            if item.efetivo_em is None or item.efetivo_em > as_of:
                continue
            mudancas_aplicaveis.append(item)
        if mudancas_aplicaveis:
            mudancas_aplicaveis.sort(key=lambda item: (item.efetivo_em or date.min, item.disponivel_em, item.revisao))
            ultima = MaturityChangePayload.model_validate(mudancas_aplicaveis[-1].payload)
            vencimento_efetivo = ultima.vencimento_novo
            projecao_aplicada = True

    if row.tipo_registro == "maturity_change":
        efetiva = row.efetivo_em is not None and row.efetivo_em <= as_of
        if efetiva:
            mudanca = MaturityChangePayload.model_validate(payload)
            gatilho = cross_defaults.get(mudanca.cross_default_id or "")
            if mudanca.base_aceleracao != "cross_default":
                projecao_aplicada = True
            elif gatilho is not None:
                dados_gatilho = CrossDefaultPayload.model_validate(gatilho.payload)
                projecao_aplicada = bool(
                    dados_gatilho.acordo_afetado_id == row.acordo_id
                    and dados_gatilho.acordo_origem_id == gatilho.acordo_id
                    and gatilho.efetivo_em is not None
                    and gatilho.efetivo_em <= as_of
                    and gatilho.revisor_id
                    and dados_gatilho.gatilho_confirmado
                    and dados_gatilho.condicoes_satisfeitas
                )

    return RegistroContratualResposta(
        registro_id=row.registro_id,
        revisao=row.revisao,
        acordo_id=row.acordo_id,
        disponivel_em=row.disponivel_em,
        efetivo_em=row.efetivo_em,
        payload=validar_payload_contratual(payload),
        evidencias=[EvidenciaContratual.model_validate(item) for item in row.evidencias],
        revisor_id=row.revisor_id,
        registrado_por=row.registrado_por,
        rationale=row.rationale,
        registrado_em=row.criado_em,
        calculado_em=calculado_em,
        resultado_calculado=resultado_calculado,  # type: ignore[arg-type]
        vencimento_efetivo=vencimento_efetivo,
        waiver_aplicavel=waiver_aplicavel,
        projecao_aplicada=projecao_aplicada,
    )


def listar_registros_contratuais(
    db: Session,
    *,
    codigo_cvm: int,
    as_of: date,
    historico: bool,
    tipos: list[str] | None,
    acordo_id: str | None,
    pagina: int,
    tamanho_pagina: int,
) -> tuple[int, list[RegistroContratualResposta]]:
    base = select(ObrigacaoContratualRegistro).where(
        ObrigacaoContratualRegistro.codigo_cvm == codigo_cvm,
        ObrigacaoContratualRegistro.disponivel_em <= as_of,
    )
    if tipos:
        base = base.where(ObrigacaoContratualRegistro.tipo_registro.in_(tipos))
    if acordo_id:
        base = base.where(ObrigacaoContratualRegistro.acordo_id == acordo_id)
    if not historico:
        latest = aliased(ObrigacaoContratualRegistro)
        max_revision = (
            select(func.max(latest.revisao))
            .where(
                latest.codigo_cvm == ObrigacaoContratualRegistro.codigo_cvm,
                latest.tipo_registro == ObrigacaoContratualRegistro.tipo_registro,
                latest.registro_id == ObrigacaoContratualRegistro.registro_id,
                latest.disponivel_em <= as_of,
            )
            .correlate(ObrigacaoContratualRegistro)
            .scalar_subquery()
        )
        base = base.where(ObrigacaoContratualRegistro.revisao == max_revision)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    page_rows = db.scalars(
        base.order_by(
            ObrigacaoContratualRegistro.tipo_registro,
            ObrigacaoContratualRegistro.registro_id,
            ObrigacaoContratualRegistro.revisao.desc(),
        )
        .offset((pagina - 1) * tamanho_pagina)
        .limit(tamanho_pagina)
    ).all()

    # As projeções temporais usam apenas fatos divulgados até o corte e a última
    # revisão elegível de cada registro estável, independentemente da paginação.
    eventos = db.scalars(
        select(ObrigacaoContratualRegistro)
        .where(
            ObrigacaoContratualRegistro.codigo_cvm == codigo_cvm,
            ObrigacaoContratualRegistro.disponivel_em <= as_of,
            ObrigacaoContratualRegistro.tipo_registro.in_(["waiver", "maturity_change", "cross_default"]),
        )
        .order_by(ObrigacaoContratualRegistro.revisao.desc())
    ).all()
    ultima_revisao_evento: dict[tuple[str, str], ObrigacaoContratualRegistro] = {}
    for item in eventos:
        chave = (item.tipo_registro, item.registro_id)
        atual = ultima_revisao_evento.get(chave)
        if atual is None or item.revisao > atual.revisao:
            ultima_revisao_evento[chave] = item
    waivers = [item for (tipo, _), item in ultima_revisao_evento.items() if tipo == "waiver"]
    maturity_changes = [item for (tipo, _), item in ultima_revisao_evento.items() if tipo == "maturity_change"]
    cross_defaults = {
        item.registro_id: item for (tipo, _), item in ultima_revisao_evento.items() if tipo == "cross_default"
    }
    return total, [
        _resultado_registro(
            item,
            as_of=as_of,
            waivers=waivers,
            maturity_changes=maturity_changes,
            cross_defaults=cross_defaults,
        )
        for item in page_rows
    ]
