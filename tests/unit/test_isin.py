import csv
import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import AutenticacaoApi, autenticar_requisicao
from app.main import app
from app.models.companhia import Companhia
from app.models.ingestion import IngestionRun
from app.models.isin import ReferenciaIsin
from app.models.sincronizacao import ExecucaoSincronizacao
from app.models.usuario import Usuario
from app.services.ingestion.isin import _isin_valido, importar_isin, materializar_isin, registrar_materializacao_isin


def test_isin_digit() -> None:
    assert _isin_valido("BRPETRACNOR9")
    assert not _isin_valido("BRPETRACNOR8")


def test_materializacao_e_idempotente(db_session: Session) -> None:
    companhia = Companhia(cnpj_companhia="33000167000101", codigo_cvm=9512, arquivo_origem="cad.csv", hash_origem="x")
    db_session.add(companhia)
    db_session.flush()
    assert materializar_isin(db_session) == 0
    db_session.add_all([
        ReferenciaIsin(cnpj_companhia=companhia.cnpj_companhia, codigo_isin="BRPETRACNPR6"),
        ReferenciaIsin(cnpj_companhia=companhia.cnpj_companhia, codigo_isin="BRPETRACNOR9"),
    ])
    db_session.flush()
    assert materializar_isin(db_session) == 1
    assert companhia.codigos_isin == ["BRPETRACNOR9", "BRPETRACNPR6"]
    assert materializar_isin(db_session) == 0
    registro = db_session.scalar(select(ReferenciaIsin).where(ReferenciaIsin.codigo_isin == "BRPETRACNOR9"))
    assert registro is not None
    db_session.delete(registro)
    db_session.flush()
    assert materializar_isin(db_session) == 1
    assert companhia.codigos_isin == ["BRPETRACNPR6"]


def test_consulta_isin_e_companhia(client: TestClient, db_session: Session) -> None:
    db_session.add(Companhia(cnpj_companhia="33000167000101", codigo_cvm=9512, arquivo_origem="cad.csv", hash_origem="x",
                             codigos_isin=["BRPETRACNOR9", "BRPETRACNPR6"]))
    db_session.add(ReferenciaIsin(cnpj_companhia="33000167000101", codigo_isin="BRPETRACNOR9"))
    db_session.commit()
    assert client.get("/companhias/codigo-cvm/9512").json()["codigos_isin"] == ["BRPETRACNOR9", "BRPETRACNPR6"]
    resposta = client.get("/isin", params={"cnpj_companhia": "33000167000101"})
    assert resposta.status_code == 200
    assert resposta.json()["dados"] == [{"codigo_isin": "BRPETRACNOR9", "cnpj_companhia": "33000167000101"}]
    assert "codigos_isin" in client.get("/openapi.json").json()["components"]["schemas"]["CompanhiaResposta"]["properties"]


def test_openapi_exibe_disparo_isin_no_grupo_ingestion(client: TestClient) -> None:
    swagger = client.get("/docs")
    assert swagger.status_code == 200
    assert "/openapi.json" in swagger.text
    schema = client.get("/openapi.json").json()
    post = schema["paths"]["/ingestion/sincronizacoes/isin"]["post"]
    assert "ingestion" in post["tags"]
    assert "isin" in post["tags"]
    assert post["operationId"] == "dispararSincronizacaoIsin"
    assert post["security"]
    assert "requestBody" not in post
    assert {"202", "401", "403", "409"}.issubset(post["responses"])
    assert post["responses"]["409"]["content"]["application/json"]["example"]["detail"]["execucao_id"]
    referencia = schema["paths"]["/isin"]["get"]
    assert referencia["security"]
    assert {p["name"] for p in referencia["parameters"]} == {"pagina", "tamanho_pagina", "cnpj_companhia", "codigo_isin"}
    assert schema["components"]["schemas"]["IsinAgendamento"]["example"]["status"] == "agendada"


def test_disparo_isin_exige_admin_e_recusa_execucao_concorrente(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.routers.isin.despachar_fila_ingestao_task.delay", lambda: None)
    app.dependency_overrides[autenticar_requisicao] = lambda: AutenticacaoApi(
        usuario=Usuario(username="leitor", senha_hash="x", is_admin=False), token_sistema=False
    )
    try:
        assert client.post("/ingestion/sincronizacoes/isin").status_code == 403
    finally:
        app.dependency_overrides.pop(autenticar_requisicao, None)
    resposta = client.post("/ingestion/sincronizacoes/isin")
    assert resposta.status_code == 202
    resposta_conflito = client.post("/ingestion/sincronizacoes/isin")
    assert resposta_conflito.status_code == 409
    assert resposta_conflito.json()["detail"]["execucao_id"] == resposta.json()["execucao_id"]


def test_importacao_preserva_referencia_em_falha(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    class Body:
        def __init__(self, data: bytes) -> None:
            self.data = data

        def iter_chunks(self, chunk_size: int) -> Any:
            yield self.data

        def close(self) -> None:
            pass

    row = [""] * 45
    row[1], row[2], row[3], row[4], row[20], row[42] = "N", "BRPETRACNOR9", "PETR", "ESVUFR", "ACN", "A"
    stream = io.StringIO(newline="")
    csv.writer(stream).writerow(row)
    dados = {"emissores/EMISSOR.txt": b'"PETR","Petrobras","33000167000101","20180628"\n',
             "emissores/NUMERACA.TXT": stream.getvalue().encode()}

    class Cliente:
        def get_object(self, *, Bucket: str, Key: str) -> dict[str, Body]:
            return {"Body": Body(dados[Key])}

    monkeypatch.setattr("app.services.ingestion.isin.boto3.client", lambda *args, **kwargs: Cliente())
    execucao = ExecucaoSincronizacao(tipo_fonte="isin", arquivo="isin", url="s3://bucket", status="agendada")
    db_session.add(execucao)
    db_session.commit()
    assert importar_isin(db_session, execucao)["status"] == "sucesso"
    assert db_session.get(ReferenciaIsin, "BRPETRACNOR9") is not None
    dados["emissores/NUMERACA.TXT"] = b"invalid\n"
    with pytest.raises(ValueError):
        importar_isin(db_session, execucao)
    assert db_session.get(ReferenciaIsin, "BRPETRACNOR9") is not None
    dados["emissores/NUMERACA.TXT"] = stream.getvalue().encode()
    assert importar_isin(db_session, execucao)["status"] == "sem_alteracao"
    runs = db_session.scalars(select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)).all()
    assert len(runs) == 1
    assert runs[0].status == "sem_alteracao"


def test_materializacao_registra_fonte(db_session: Session) -> None:
    fonte = IngestionRun(tipo_fonte="isin", status="sucesso", phase="complete")
    cadastro = IngestionRun(tipo_fonte="cadastro", status="em_execucao", phase="promote")
    db_session.add_all([fonte, cadastro, ReferenciaIsin(codigo_isin="BRPETRACNOR9", cnpj_companhia="33000167000101")])
    db_session.flush()
    assert registrar_materializacao_isin(db_session, cadastro) == 0
    assert cadastro.quality_summary == {"companhias_isin_alteradas": 0, "isin_ingestion_run_id": str(fonte.id)}
