import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun
from app.models.sincronizacao import ExecucaoSincronizacao


def test_hierarchy_api_filtering_and_details(client: TestClient, db_session: Session) -> None:
    agora = datetime.now(UTC)

    # 1. Create a parent execution
    parent_id = uuid.uuid4()
    parent = ExecucaoSincronizacao(
        id=parent_id,
        tipo_fonte="fre",
        ano=2025,
        arquivo="fre_cia_aberta_2025.zip",
        url="http://example.com/fre_2025.zip",
        status="sucesso",
        tipo_execucao="arquivo_zip",
        iniciada_em=agora,
        finalizada_em=agora,
    )
    db_session.add(parent)
    db_session.flush()

    # Create parent IngestionRun and IngestionFile
    parent_run = IngestionRun(
        id=uuid.uuid4(),
        execucao_sincronizacao_id=parent_id,
        tipo_fonte="fre",
        ano=2025,
        status="sucesso",
        phase="complete",
    )
    db_session.add(parent_run)
    db_session.flush()

    parent_file = IngestionFile(
        id=uuid.uuid4(),
        ingestion_run_id=parent_run.id,
        source_url=parent.url,
        source_filename=parent.arquivo,
        content_sha256="abc",
        content_length_bytes=1000,
    )
    db_session.add(parent_file)
    db_session.flush()

    # Register member inside the parent's file
    member = IngestionFileMember(
        id=uuid.uuid4(),
        ingestion_file_id=parent_file.id,
        member_name="fre_cia_aberta_2025.csv",
        member_sha256="def",
        member_size_bytes=5000,
        encoding="utf-8",
        delimiter=";",
        header=["CNPJ_CIA", "DT_REFER", "VERSAO"],
        row_count=10,
        schema_status="ok",
    )
    db_session.add(member)
    db_session.flush()

    # 2. Create child execution
    child_id = uuid.uuid4()
    child = ExecucaoSincronizacao(
        id=child_id,
        parent_execucao_id=parent_id,
        tipo_fonte="fre",
        ano=2025,
        arquivo="fre_cia_aberta_2025.csv",
        url=parent.url,
        status="sucesso",
        tipo_execucao="arquivo_membro",
        iniciada_em=agora,
        finalizada_em=agora,
        total_linhas_lidas=10,
        total_inseridos=8,
        total_atualizados=2,
    )
    db_session.add(child)
    
    # 3. Create an independent simple execution (like cadastro)
    simple_id = uuid.uuid4()
    simple = ExecucaoSincronizacao(
        id=simple_id,
        tipo_fonte="cadastro",
        ano=None,
        arquivo="cad_cia_aberta.csv",
        url="http://example.com/cadastro.csv",
        status="sucesso",
        tipo_execucao="arquivo_simples",
        iniciada_em=agora,
        finalizada_em=agora,
    )
    db_session.add(simple)
    db_session.commit()

    # Test GET /ingestion/sincronizacoes listing
    # No filters
    res = client.get("/ingestion/sincronizacoes")
    assert res.status_code == 200
    dados = res.json()["dados"]
    assert len(dados) >= 3

    # Filter by tipo_execucao = arquivo_membro
    res = client.get("/ingestion/sincronizacoes?tipo_execucao=arquivo_membro")
    assert res.status_code == 200
    dados = res.json()["dados"]
    assert all(d["tipo_execucao"] == "arquivo_membro" for d in dados)
    # The child execution should show the parent's ZIP file name as arquivo_principal
    child_summary = next(d for d in dados if d["id"] == str(child_id))
    assert child_summary["arquivo_principal"] == "fre_cia_aberta_2025.zip"

    # Filter somente_pais = True
    res = client.get("/ingestion/sincronizacoes?somente_pais=true")
    assert res.status_code == 200
    dados = res.json()["dados"]
    assert all(d["id_execucao_pai"] is None for d in dados)
    # The parent execution should show the correct children counters
    parent_summary = next(d for d in dados if d["id"] == str(parent_id))
    assert parent_summary["filhos_total"] == 1
    assert parent_summary["filhos_concluidos"] == 1
    assert parent_summary["filhos_falha"] == 0
    assert parent_summary["filhos_em_andamento"] == 0

    # Filter somente_filhos = True
    res = client.get("/ingestion/sincronizacoes?somente_filhos=true")
    assert res.status_code == 200
    dados = res.json()["dados"]
    assert all(d["id_execucao_pai"] is not None for d in dados)

    # Filter by id_execucao_pai
    res = client.get(f"/ingestion/sincronizacoes?id_execucao_pai={parent_id}")
    assert res.status_code == 200
    dados = res.json()["dados"]
    assert len(dados) == 1
    assert dados[0]["id"] == str(child_id)

    # Test GET /ingestion/sincronizacoes/{id} detail
    # Parent detail should return the child list in execucoes_filhas
    res = client.get(f"/ingestion/sincronizacoes/{parent_id}")
    assert res.status_code == 200
    detalhe = res.json()
    assert detalhe["tipo_execucao"] == "arquivo_zip"
    assert detalhe["filhos_total"] == 1
    assert detalhe["filhos_concluidos"] == 1
    assert len(detalhe["execucoes_filhas"]) == 1
    assert detalhe["execucoes_filhas"][0]["id"] == str(child_id)

    # Child detail should return the parent zip as arquivo_principal
    res = client.get(f"/ingestion/sincronizacoes/{child_id}")
    assert res.status_code == 200
    detalhe = res.json()
    assert detalhe["tipo_execucao"] == "arquivo_membro"
    assert detalhe["arquivo_principal"] == "fre_cia_aberta_2025.zip"
    assert detalhe["id_execucao_pai"] == str(parent_id)
    assert len(detalhe["analise_arquivos"]) == 1
    assert detalhe["analise_arquivos"][0]["file_name"] == "fre_cia_aberta_2025.csv"
