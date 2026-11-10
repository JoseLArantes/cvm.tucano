from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache as redis_cache
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
from app.schemas.setores import AgregacaoSetorialRequest, AgregacaoSetorialResposta
from app.services import setores as setores_service
from app.services.analise import CALCULATION_VERSION
from app.services.setores import agregar_margens, normalizar_chave_setor, publicar_taxonomia_cvm


def _companhia(cnpj: str, codigo_cvm: int, setor: str | None, *, categoria: str = "Categoria A") -> Companhia:
    return Companhia(
        cnpj_companhia=cnpj,
        codigo_cvm=codigo_cvm,
        denominacao_social=f"Companhia {codigo_cvm}",
        setor_atividade=setor,
        categoria_registro=categoria,
        tipo_emissor="CIA_ABERTA",
        arquivo_origem="cad_cia_aberta.csv",
        hash_origem=f"hash-{codigo_cvm}",
    )


def _fato(
    *,
    execucao_id: UUID,
    codigo_cvm: int,
    metrica: str,
    valor: str,
) -> AnaliseFatoRevision:
    return AnaliseFatoRevision(
        execucao_id=execucao_id,
        codigo_cvm=codigo_cvm,
        escopo="consolidated",
        calculation_version=CALCULATION_VERSION,
        periodicidade="annual",
        base_periodo="fy",
        metric_id=metrica,
        period_id="FY2024",
        fiscal_year=2024,
        status="available",
        known_from=date(2025, 3, 1),
        observation_payload={"value": valor, "unit": "BRL"},
        fingerprint=f"{codigo_cvm}-{metrica}",
    )


def _publicar_companhias_teste(db_session: Session) -> tuple[Setor, Setor, list[Companhia]]:
    companhias = [
        _companhia("00000000001091", 301, "Energia Elétrica"),
        _companhia("00000000001172", 302, "Bancos"),
    ]
    db_session.add_all(companhias)
    db_session.flush()
    publicar_taxonomia_cvm(db_session, referencia_fonte="cadastro-teste")
    setor_energia = db_session.scalar(
        select(Setor).where(Setor.taxonomia == "cvm_cadastro", Setor.nome == "Energia Elétrica")
    )
    setor_bancos = db_session.scalar(select(Setor).where(Setor.taxonomia == "cvm_cadastro", Setor.nome == "Bancos"))
    assert setor_energia is not None
    assert setor_bancos is not None
    return setor_energia, setor_bancos, companhias


def test_normalizar_chave_setor_preserva_distincoes_semanticas() -> None:
    assert normalizar_chave_setor("  ENERGIA   ELÉTRICA ") == normalizar_chave_setor("Energia Elétrica")
    assert normalizar_chave_setor("Energia Ele\u0301trica") == normalizar_chave_setor("Energia Elétrica")
    assert normalizar_chave_setor("Energia Elétrica") != normalizar_chave_setor("Energia Eletrica")
    assert normalizar_chave_setor("A/B") != normalizar_chave_setor("A-B")
    assert normalizar_chave_setor("Straße") != normalizar_chave_setor("Strasse")


def test_publicar_taxonomia_registra_atribuicoes_e_reclassificacao(db_session: Session) -> None:
    companhia = _companhia("00000000000191", 101, "Energia Elétrica")
    db_session.add(companhia)
    db_session.flush()

    primeira = publicar_taxonomia_cvm(db_session, referencia_fonte="cadastro-v1")
    db_session.flush()
    atribuicao = db_session.query(SetorClassificacaoCompanhia).filter_by(companhia_id=companhia.id).one()
    setor_id = atribuicao.setor_id

    repeticao = publicar_taxonomia_cvm(db_session, referencia_fonte="cadastro-v1-repetido")
    companhia.setor_atividade = "Petróleo e Gás"
    segunda = publicar_taxonomia_cvm(db_session, referencia_fonte="cadastro-v2")

    assert primeira["publicada"] is True
    assert repeticao["publicada"] is False
    assert segunda["publicada"] is True
    assert segunda["versao"] == 2
    historico = (
        db_session.query(SetorClassificacaoCompanhia)
        .filter_by(companhia_id=companhia.id)
        .order_by(SetorClassificacaoCompanhia.versao_inicio)
        .all()
    )
    assert historico[0].setor_id == setor_id
    assert historico[0].versao_fim == 2
    assert historico[1].rotulo_origem == "Petróleo e Gás"
    assert db_session.query(SetorTaxonomiaVersao).filter_by(taxonomia="cvm_cadastro").count() == 2
    taxonomia_b3 = db_session.get(SetorTaxonomia, "b3")
    assert taxonomia_b3 is not None
    assert taxonomia_b3.versao_atual is None


def test_agregar_margens_usa_media_mediana_e_razao_das_somas(db_session: Session) -> None:
    companhias = [
        _companhia("00000000000272", 201, "Bancos"),
        _companhia("00000000000353", 202, "Bancos"),
    ]
    db_session.add_all(companhias)
    db_session.flush()
    publicar_taxonomia_cvm(db_session, referencia_fonte="teste")

    execucao = AnaliseMaterializacaoExecucao(
        codigo_cvm=201,
        escopo="consolidated",
        calculation_version=CALCULATION_VERSION,
        status="success",
        coverage_complete=True,
        finished_at=datetime(2025, 3, 2),
    )
    db_session.add(execucao)
    db_session.flush()
    for codigo, receita, lucro in ((201, "100", "20"), (202, "900", "90")):
        db_session.add_all(
            [
                _fato(execucao_id=execucao.id, codigo_cvm=codigo, metrica="receita_liquida", valor=receita),
                _fato(execucao_id=execucao.id, codigo_cvm=codigo, metrica="lucro_liquido", valor=lucro),
            ]
        )
    db_session.flush()

    pedido = AgregacaoSetorialRequest(
        categorias_registro=["Categoria A"],
        anos=[2024],
        metricas=["margem_liquida"],
        agrupar_por=["setor"],
    )
    resultado = agregar_margens(db_session, pedido)
    celula = resultado.celulas[0]

    assert celula.grupo["setor"] == "Bancos"
    assert celula.cobertura.selecionadas == 2
    assert celula.cobertura.elegiveis == 2
    assert celula.estatisticas.media_simples == Decimal("0.15")
    assert celula.estatisticas.mediana == Decimal("0.15")
    assert celula.estatisticas.razao_das_somas == Decimal("0.11")
    assert resultado.atualidade == "indeterminada"

    media_apenas = agregar_margens(
        db_session,
        AgregacaoSetorialRequest(
            categorias_registro=["Categoria A"],
            anos=[2024],
            metricas=["margem_liquida"],
            estatisticas=["media_simples"],
        ),
    )
    assert media_apenas.celulas[0].estatisticas.media_simples == Decimal("0.15")
    assert media_apenas.celulas[0].estatisticas.mediana is None


def test_openapi_expoe_endpoints_e_corpo_fechado(client: TestClient) -> None:
    openapi = client.get("/openapi.json").json()

    assert "/setores" in openapi["paths"]
    assert "/setores/taxonomias" in openapi["paths"]
    assert "/analise/companhias/agregacoes" in openapi["paths"]
    schema = openapi["components"]["schemas"]["AgregacaoSetorialRequest"]
    assert schema["additionalProperties"] is False
    assert "codigos_cvm" in schema["properties"]


def test_agregacao_explicitamente_selecionada_sem_taxonomia_publicada_retorna_409(
    client: TestClient,
    db_session: Session,
) -> None:
    publicar_taxonomia_cvm(db_session, referencia_fonte="teste")
    db_session.commit()

    response = client.post(
        "/analise/companhias/agregacoes",
        json={"taxonomia": "b3", "todas": True, "anos": [2024], "metricas": ["margem_liquida"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["codigo"] == "TAXONOMIA_SEM_PUBLICACAO"


def test_rotas_de_catalogo_setor_companhias_e_filtro_por_setor(
    client: TestClient,
    db_session: Session,
) -> None:
    setor_energia, _, companhias = _publicar_companhias_teste(db_session)

    taxonomias = client.get("/setores/taxonomias")
    versoes = client.get("/setores/taxonomias/cvm_cadastro/versoes")
    lista = client.get("/setores", params={"nome": "Energia"})
    detalhe = client.get(f"/setores/{setor_energia.id}")
    companhias_setor = client.get(f"/setores/{setor_energia.id}/companhias")
    filtro_companhias = client.get(
        "/companhias",
        params={"setor_id": str(setor_energia.id), "taxonomia": "cvm_cadastro"},
    )

    assert taxonomias.status_code == 200
    assert {item["codigo"] for item in taxonomias.json()} == {"cvm_cadastro", "b3"}
    assert next(item for item in taxonomias.json() if item["codigo"] == "b3")["versao_atual"] is None
    assert versoes.status_code == 200
    assert len(versoes.json()) == 1
    assert lista.status_code == 200
    assert lista.json()["paginacao"]["total"] == 1
    assert lista.json()["dados"][0]["total_companhias"] == 1
    assert detalhe.status_code == 200
    assert detalhe.json()["nome"] == "Energia Elétrica"
    assert companhias_setor.status_code == 200
    assert [item["codigo_cvm"] for item in companhias_setor.json()["dados"]] == [301]
    assert filtro_companhias.status_code == 200
    assert [item["codigo_cvm"] for item in filtro_companhias.json()["dados"]] == [301]
    assert filtro_companhias.json()["dados"][0]["setor_id"] == str(setor_energia.id)
    assert len(companhias) == 2


def test_alias_setorial_e_auditado_e_incrementa_versao(
    client: TestClient,
    db_session: Session,
) -> None:
    setor_energia, _, _ = _publicar_companhias_teste(db_session)

    response = client.post(
        "/setores/aliases",
        json={
            "taxonomia": "cvm_cadastro",
            "setor_id": str(setor_energia.id),
            "rotulo_origem": "Energia Alternativa",
            "evidencias": {"documento": "cadastro revisado"},
            "justificativa": "Grafia alternativa confirmada em fonte oficial.",
            "revisado_por": "equipe-dados",
        },
    )
    detalhe = client.get(f"/setores/{setor_energia.id}")
    duplicado = client.post(
        "/setores/aliases",
        json={
            "taxonomia": "cvm_cadastro",
            "setor_id": str(setor_energia.id),
            "rotulo_origem": "Energia Alternativa",
            "evidencias": {"documento": "cadastro revisado"},
            "justificativa": "Duplicata de teste.",
            "revisado_por": "equipe-dados",
        },
    )

    assert response.status_code == 200
    assert response.json()["rotulo_origem"] == "Energia Alternativa"
    assert detalhe.status_code == 200
    assert detalhe.json()["versao_taxonomia"] == 2
    assert detalhe.json()["aliases"] == ["Energia Alternativa"]
    assert db_session.query(SetorAlias).count() == 1
    assert db_session.query(SetorTaxonomiaMudanca).filter_by(tipo="alias_adicionado").count() == 1
    assert duplicado.status_code == 409


def test_correspondencia_entre_taxonomias_exige_publicacao_e_fica_auditada(
    client: TestClient,
    db_session: Session,
) -> None:
    setor_energia, _, _ = _publicar_companhias_teste(db_session)
    taxonomia_b3 = db_session.get(SetorTaxonomia, "b3")
    assert taxonomia_b3 is not None
    b3_publicada_em = datetime(2025, 1, 1)
    taxonomia_b3.ativa = True
    taxonomia_b3.versao_atual = 1
    taxonomia_b3.checksum_atual = "b" * 64
    taxonomia_b3.publicada_em = b3_publicada_em
    setor_b3 = Setor(
        taxonomia="b3",
        chave_normalizada="energia",
        nome="Energia",
        nivel="setor",
    )
    db_session.add(setor_b3)
    db_session.add(
        SetorTaxonomiaVersao(
            taxonomia="b3",
            versao=1,
            checksum_semantico="b" * 64,
            publicada_em=b3_publicada_em,
            resumo={"fonte": "fixture autorizado"},
        )
    )
    db_session.flush()

    response = client.post(
        "/setores/correspondencias",
        json={
            "taxonomia_origem": "cvm_cadastro",
            "setor_origem_id": str(setor_energia.id),
            "taxonomia_destino": "b3",
            "setor_destino_id": str(setor_b3.id),
            "tipo": "equivalente",
            "evidencias": {"referencia": "revisao manual"},
            "justificativa": "Correspondencia revisada entre as classificacoes.",
            "revisado_por": "equipe-dados",
        },
    )
    detalhe = client.get(f"/setores/{setor_energia.id}")

    assert response.status_code == 200
    assert response.json()["versao_mapeamento"] == 1
    assert response.json()["setor_destino_nome"] == "Energia"
    assert detalhe.status_code == 200
    assert detalhe.json()["versao_taxonomia"] == 2
    assert detalhe.json()["correspondencias"][0]["taxonomia_destino"] == "b3"
    assert db_session.query(SetorCorrespondencia).count() == 1
    assert db_session.query(SetorTaxonomiaMudanca).filter_by(tipo="correspondencia_adicionada").count() == 1


def test_agregacao_http_usa_cache_versionado_e_retorna_fatos_canonicos(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _publicar_companhias_teste(db_session)
    execucao = AnaliseMaterializacaoExecucao(
        codigo_cvm=301,
        escopo="consolidated",
        calculation_version=CALCULATION_VERSION,
        status="success",
        coverage_complete=True,
        finished_at=datetime(2025, 3, 2),
    )
    db_session.add(execucao)
    db_session.flush()
    db_session.add_all(
        [
            _fato(execucao_id=execucao.id, codigo_cvm=301, metrica="receita_liquida", valor="100"),
            _fato(execucao_id=execucao.id, codigo_cvm=301, metrica="lucro_liquido", valor="20"),
        ]
    )
    db_session.flush()

    cache_payloads: dict[str, str] = {}
    cache_reads: list[str] = []
    cache_writes: list[str] = []
    lock_acquires: list[str] = []
    lock_releases: list[str] = []
    aggregations = 0
    aggregate_original = setores_service.agregar_margens

    def cache_get(key: str) -> str | None:
        cache_reads.append(key)
        return cache_payloads.get(key)

    def cache_set(key: str, value: str, ttl_seconds: int) -> bool:
        assert ttl_seconds > 0
        cache_writes.append(key)
        cache_payloads[key] = value
        return True

    def acquire_lock(key: str, ttl_seconds: int) -> str:
        assert ttl_seconds > 0
        lock_acquires.append(key)
        return "token-teste"

    def release_lock(key: str, token: str) -> None:
        assert token == "token-teste"
        lock_releases.append(key)

    def aggregate(db: Session, pedido: AgregacaoSetorialRequest) -> AgregacaoSetorialResposta:
        nonlocal aggregations
        aggregations += 1
        return aggregate_original(db, pedido)

    monkeypatch.setattr(redis_cache, "get", cache_get)
    monkeypatch.setattr(redis_cache, "set", cache_set)
    monkeypatch.setattr(redis_cache, "acquire_lock", acquire_lock)
    monkeypatch.setattr(redis_cache, "release_lock", release_lock)
    monkeypatch.setattr(setores_service, "agregar_margens", aggregate)
    pedido = {
        "codigos_cvm": [301],
        "anos": [2024],
        "metricas": ["margem_liquida"],
        "estatisticas": ["media_simples"],
    }

    primeira = client.post("/analise/companhias/agregacoes", json=pedido)
    segunda = client.post("/analise/companhias/agregacoes", json=pedido)

    assert primeira.status_code == 200
    assert primeira.json()["celulas"][0]["estatisticas"]["media_simples"] == "0.2"
    assert primeira.json()["celulas"][0]["cobertura"]["elegiveis"] == 1
    assert segunda.status_code == 200
    assert segunda.json()["fingerprint"] == primeira.json()["fingerprint"]
    assert aggregations == 1
    assert len(cache_reads) == 2
    assert len(cache_writes) == 1
    assert len(lock_acquires) == 1
    assert lock_releases == lock_acquires
