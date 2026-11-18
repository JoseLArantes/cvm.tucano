from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.obrigacoes_contratuais import ObrigacaoContratualRegistro


def _companhia(db: Session, codigo_cvm: int = 9512) -> Companhia:
    companhia = Companhia(
        cnpj_companhia="12345678000195",
        codigo_cvm=codigo_cvm,
        denominacao_social="Companhia de Teste S.A.",
        arquivo_origem="cad_cia_aberta.csv",
        hash_origem="company-hash",
    )
    db.add(companhia)
    db.commit()
    return companhia


def _evidencia(documento_id: int = 123, *, versao: int = 1, secao: str = "clausula 4.2") -> dict[str, object]:
    return {
        "fonte": "FRE",
        "documento_id": documento_id,
        "versao": versao,
        "secao": secao,
        "url": f"https://dados.cvm.gov.br/documentos/{documento_id}",
    }


def _registro(
    registro_id: str,
    record_type: str,
    payload: dict[str, object],
    *,
    acordo_id: str | None = "AC1",
    disponivel_em: str = "2025-01-01",
    efetivo_em: str | None = None,
    revisao: int = 1,
    revisor_id: str | None = None,
    documento_id: int = 123,
) -> dict[str, object]:
    item: dict[str, object] = {
        "registro_id": registro_id,
        "revisao": revisao,
        "acordo_id": acordo_id,
        "disponivel_em": disponivel_em,
        "payload": {"record_type": record_type, **payload},
        "evidencias": [_evidencia(documento_id)],
        "revisor_id": revisor_id,
    }
    if efetivo_em:
        item["efetivo_em"] = efetivo_em
    return item


def _lote_completo() -> list[dict[str, object]]:
    return [
        _registro(
            "AC1",
            "acordo",
            {"emissor_cnpj": "12345678000195", "instrumento": "Debênture simples", "moeda": "BRL"},
            acordo_id="AC1",
            revisor_id="reviewer-7",
        ),
        _registro(
            "AC2",
            "acordo",
            {"emissor_cnpj": "12345678000195", "instrumento": "CCB", "moeda": "BRL"},
            acordo_id="AC2",
        ),
        _registro(
            "C1",
            "covenant",
            {
                "covenant_id": "C1",
                "definicao_financeira": "Dívida líquida / EBITDA",
                "escopo": "consolidado",
                "unidade": "vezes",
                "janela_agregacao": "exercício anual",
                "comparador": "lte",
                "limite": "3.0",
                "datas_teste": ["2025-01-10", "2025-04-10"],
            },
        ),
        _registro(
            "T1",
            "covenant_test",
            {
                "covenant_id": "C1",
                "data_teste": "2025-01-10",
                "comparador": "lte",
                "limite": "3.0",
                "valor_aferido": "3.2",
                "resultado_verificado": "falhou",
            },
            disponivel_em="2025-01-15",
            revisor_id="reviewer-7",
        ),
        _registro(
            "T2",
            "covenant_test",
            {
                "covenant_id": "C1",
                "data_teste": "2025-04-10",
                "comparador": "lte",
                "limite": "3.0",
                "valor_aferido": "3.0",
            },
            disponivel_em="2025-04-12",
        ),
        _registro(
            "B1",
            "breach",
            {"covenant_id": "C1", "test_id": "T1", "status": "breach", "descricao": "Violação original"},
            disponivel_em="2025-01-20",
            revisor_id="reviewer-9",
        ),
        _registro(
            "W1",
            "waiver",
            {
                "covenant_id": "C1",
                "test_ids_cobertos": ["T1"],
                "inicio_vigencia": "2025-01-10",
                "fim_vigencia": "2025-01-31",
                "implementado": True,
                "implementado_em": "2025-03-01",
            },
            disponivel_em="2025-03-01",
            revisor_id="reviewer-8",
        ),
        _registro(
            "L1",
            "cash_leg",
            {"parcela_id": "L1", "vencimento_original": "2025-12-31", "valor": "100.25", "moeda": "BRL"},
        ),
        _registro(
            "L2",
            "cash_leg",
            {"parcela_id": "L2", "vencimento_original": "2026-12-31", "valor": "200.0", "moeda": "BRL"},
            acordo_id="AC2",
        ),
        _registro(
            "M1",
            "maturity_change",
            {
                "cash_leg_ids": ["L1"],
                "vencimento_original": "2025-12-31",
                "vencimento_novo": "2025-10-31",
                "base_aceleracao": "aditamento",
            },
            disponivel_em="2025-03-20",
            efetivo_em="2025-04-01",
            revisor_id="reviewer-10",
        ),
        _registro(
            "CD1",
            "cross_default",
            {
                "acordo_origem_id": "AC1",
                "acordo_afetado_id": "AC2",
                "condicao_contratual": "inadimplemento material no acordo de origem",
                "gatilho_confirmado": False,
                "condicoes_satisfeitas": False,
            },
            acordo_id="AC1",
            disponivel_em="2025-03-20",
        ),
        _registro(
            "M2",
            "maturity_change",
            {
                "cash_leg_ids": ["L2"],
                "vencimento_original": "2026-12-31",
                "vencimento_novo": "2026-08-31",
                "base_aceleracao": "cross_default",
                "cross_default_id": "CD1",
            },
            acordo_id="AC2",
            disponivel_em="2025-03-20",
            efetivo_em="2025-04-01",
            revisor_id="reviewer-10",
        ),
        _registro(
            "EVT1",
            "proceeding",
            {
                "event_id": "EVT1",
                "case_id": "CASE1",
                "orgao": "Tribunal de Justiça",
                "entidade_afetada_cnpj": "12345678000195",
                "etapa": "peticao",
                "exposicoes": ["AC1"],
            },
            acordo_id=None,
            disponivel_em="2025-06-01",
        ),
        _registro(
            "EVT2",
            "proceeding",
            {
                "event_id": "EVT2",
                "case_id": "CASE1",
                "orgao": "Tribunal de Justiça",
                "entidade_afetada_cnpj": "12345678000195",
                "etapa": "admissao_ou_decisao",
                "exposicoes": ["AC1"],
                "eventos_relacionados": ["EVT1"],
            },
            acordo_id=None,
            disponivel_em="2025-06-10",
            efetivo_em="2025-05-20",
        ),
        _registro(
            "COV1",
            "coverage",
            {
                "formulario_referencia": "DFP",
                "documento_id": 345,
                "versao": 2,
                "data_referencia": "2024-12-31",
                "acordos_divulgados": ["AC1", "AC2"],
                "acordos_revisados": ["AC1"],
                "exposicoes_omitidas": ["AC2: termos não revisados"],
                "clausulas_desconhecidas": ["data de teste do covenant C1"],
                "responsavel_lacuna": "Agente fiduciário da emissão",
            },
            acordo_id=None,
            disponivel_em="2025-05-10",
            revisor_id="reviewer-11",
        ),
    ]


def test_obrigacoes_contratuais_replay_covenant_waiver_vencimento_e_processos(
    client: TestClient,
    db_session: Session,
) -> None:
    companhia = _companhia(db_session)
    payload = {"registros": _lote_completo()}
    gravacao = client.post(f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais", json=payload)
    assert gravacao.status_code == 201, gravacao.text
    assert gravacao.json()["aceitos"] == 15
    assert gravacao.json()["idempotentes"] == 0

    corte_antes_waiver = client.get(
        f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais",
        params={"as_of": "2025-02-01", "tipo_registro": ["covenant_test", "waiver", "breach"]},
    )
    assert corte_antes_waiver.status_code == 200, corte_antes_waiver.text
    antes = {item["registro_id"]: item for item in corte_antes_waiver.json()["dados"]}
    assert "W1" not in antes
    assert antes["T1"]["resultado_calculado"] == "falhou"
    assert antes["T1"]["payload"]["resultado_verificado"] == "falhou"
    assert antes["B1"]["payload"]["status"] == "breach"

    corte_depois_waiver = client.get(
        f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais",
        params={"as_of": "2025-04-15", "tipo_registro": ["covenant_test", "waiver", "breach"]},
    )
    depois = {item["registro_id"]: item for item in corte_depois_waiver.json()["dados"]}
    assert depois["T1"]["waiver_aplicavel"] is True
    assert depois["T2"]["resultado_calculado"] == "passou"
    assert depois["T2"]["waiver_aplicavel"] is False
    assert depois["B1"]["payload"]["status"] == "breach"

    antes_mudanca = client.get(
        f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais",
        params={"as_of": "2025-03-31", "tipo_registro": "cash_leg"},
    )
    assert {row["registro_id"]: row["vencimento_efetivo"] for row in antes_mudanca.json()["dados"]} == {
        "L1": "2025-12-31",
        "L2": "2026-12-31",
    }
    depois_mudanca = client.get(
        f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais",
        params={"as_of": "2025-04-15", "tipo_registro": "cash_leg"},
    )
    parcelas = {row["registro_id"]: row for row in depois_mudanca.json()["dados"]}
    assert parcelas["L1"]["vencimento_efetivo"] == "2025-10-31"
    assert parcelas["L1"]["projecao_aplicada"] is True
    assert parcelas["L2"]["vencimento_efetivo"] == "2026-12-31"
    assert parcelas["L2"]["projecao_aplicada"] is False

    corte_anterior_ao_processo = client.get(
        f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais",
        params={"as_of": "2025-05-31", "tipo_registro": "proceeding"},
    )
    assert corte_anterior_ao_processo.json()["dados"] == []
    corte_do_processo = client.get(
        f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais",
        params={"as_of": "2025-06-05", "tipo_registro": "proceeding"},
    )
    assert {item["registro_id"] for item in corte_do_processo.json()["dados"]} == {"EVT1"}
    corte_apos_decisao = client.get(
        f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais",
        params={"as_of": "2025-06-10", "tipo_registro": "proceeding"},
    )
    assert {item["registro_id"] for item in corte_apos_decisao.json()["dados"]} == {"EVT1", "EVT2"}

    cobertura = client.get(
        f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais",
        params={"as_of": "2025-06-01", "tipo_registro": "coverage"},
    ).json()["dados"][0]["payload"]
    assert cobertura["clausulas_desconhecidas"] == ["data de teste do covenant C1"]
    assert cobertura["responsavel_lacuna"] == "Agente fiduciário da emissão"


def test_lote_contratual_eh_atomico_idempotente_e_conflitante_por_revisao(
    client: TestClient,
    db_session: Session,
) -> None:
    companhia = _companhia(db_session, codigo_cvm=9513)
    registro = _registro(
        "AC-IDEMPOTENTE",
        "acordo",
        {"emissor_cnpj": companhia.cnpj_companhia, "instrumento": "Debênture"},
        acordo_id="AC-IDEMPOTENTE",
    )
    caminho = f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais"
    primeira = client.post(caminho, json={"registros": [registro]})
    repetida = client.post(caminho, json={"registros": [registro]})
    assert primeira.status_code == 201
    assert primeira.json()["aceitos"] == 1
    assert repetida.status_code == 201
    assert repetida.json()["aceitos"] == 0
    assert repetida.json()["idempotentes"] == 1

    divergente = _registro(
        "AC-IDEMPOTENTE",
        "acordo",
        {"emissor_cnpj": companhia.cnpj_companhia, "instrumento": "Aditamento"},
        acordo_id="AC-IDEMPOTENTE",
    )
    extra = _registro(
        "AC-ATOMICIDADE",
        "acordo",
        {"emissor_cnpj": companhia.cnpj_companhia, "instrumento": "CCB"},
        acordo_id="AC-ATOMICIDADE",
    )
    conflito = client.post(caminho, json={"registros": [extra, divergente]})
    assert conflito.status_code == 409
    ids = db_session.scalars(
        select(ObrigacaoContratualRegistro.registro_id).where(
            ObrigacaoContratualRegistro.codigo_cvm == companhia.codigo_cvm
        )
    ).all()
    assert ids == ["AC-IDEMPOTENTE"]


def test_ato_processual_requer_vinculos_com_eventos_existentes(client: TestClient, db_session: Session) -> None:
    companhia = _companhia(db_session, codigo_cvm=9515)
    lote = [
        _registro(
            "EVT1",
            "proceeding",
            {
                "event_id": "EVT1",
                "case_id": "CASE1",
                "orgao": "Tribunal de Justiça",
                "entidade_afetada_cnpj": companhia.cnpj_companhia,
                "etapa": "peticao",
            },
            acordo_id=None,
        ),
        _registro(
            "EVT2",
            "proceeding",
            {
                "event_id": "EVT2",
                "case_id": "CASE1",
                "orgao": "Tribunal de Justiça",
                "entidade_afetada_cnpj": companhia.cnpj_companhia,
                "etapa": "encerramento",
                "eventos_relacionados": ["EVT-NAO-EXISTE"],
            },
            acordo_id=None,
        ),
    ]

    resposta = client.post(
        f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais",
        json={"registros": lote},
    )

    assert resposta.status_code == 422
    assert db_session.scalar(select(ObrigacaoContratualRegistro.id)) is None


def test_gravacao_contratual_requer_admin_e_openapi_documenta_replay(client: TestClient, db_session: Session) -> None:
    companhia = _companhia(db_session, codigo_cvm=9514)
    criado = client.post(
        "/usuarios",
        json={
            "username": "analista-sem-admin",
            "password": "senha-analista",
            "nome": "Analista",
            "is_admin": False,
            "ativo": True,
        },
    )
    assert criado.status_code == 201
    login = client.post("/auth/login", json={"username": "analista-sem-admin", "password": "senha-analista"})
    assert login.status_code == 200
    response = client.post(
        f"/analise/companhias/{companhia.codigo_cvm}/obrigacoes-contratuais",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={"registros": _lote_completo()[:1]},
    )
    assert response.status_code == 403

    openapi = client.get("/openapi.json").json()
    path = openapi["paths"]["/analise/companhias/{codigo_cvm}/obrigacoes-contratuais"]
    assert path["get"]["operationId"] == "listarObrigacoesContratuais"
    assert path["post"]["operationId"] == "registrarLoteObrigacoesContratuais"
    serialized = str(path["get"]["description"])
    assert "disponivel_em" in serialized
    assert "resultado verificado" in serialized
