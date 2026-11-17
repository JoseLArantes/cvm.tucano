import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.ingestion import (
    IngestionOperationAudit,
    IngestionRun,
    SourceArtifactSnapshot,
)
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.file_centric import (
    build_file_id,
    build_member_id,
    listar_arquivos_logicos,
    parse_file_id,
    parse_member_id,
)


def test_build_and_parse_ids() -> None:
    # Annual package file
    fid = build_file_id("dfp", 2022, "dfp_cia_aberta_2022.zip")
    assert fid == "dfp:2022:dfp_cia_aberta_2022.zip"
    fonte, ano, arq = parse_file_id(fid)
    assert fonte == "dfp"
    assert ano == 2022
    assert arq == "dfp_cia_aberta_2022.zip"

    # Simple file without year
    cid = build_file_id("cadastro", None, "cad_cia_aberta.csv")
    assert cid == "cadastro:cad_cia_aberta.csv"
    fonte_c, ano_c, arq_c = parse_file_id(cid)
    assert fonte_c == "cadastro"
    assert ano_c is None
    assert arq_c == "cad_cia_aberta.csv"

    # Member ID
    mid = build_member_id(fid, "dfp_cia_aberta_BPA_con_2022.csv")
    assert mid == "dfp:2022:dfp_cia_aberta_2022.zip:dfp_cia_aberta_BPA_con_2022.csv"
    pfid, mname = parse_member_id(mid)
    assert pfid == fid
    assert mname == "dfp_cia_aberta_BPA_con_2022.csv"


def test_cenario_1_zip_com_membro_obrigatorio_faltante(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)
    parent_id = uuid.uuid4()
    run_id = uuid.uuid4()

    # Cria execucao pai para DFP 2022 com apenas 1 membro (faltando os outros obrigatorios como parecer, composicao_capital)
    parent_exec = ExecucaoSincronizacao(
        id=parent_id,
        tipo_execucao="arquivo_zip",
        tipo_fonte="dfp",
        ano=2022,
        arquivo="dfp_cia_aberta_2022.zip",
        url="http://exemplo/dfp_2022.zip",
        status="sucesso",
        iniciada_em=now - timedelta(minutes=10),
        finalizada_em=now - timedelta(minutes=5),
    )
    run = IngestionRun(
        id=run_id,
        execucao_sincronizacao_id=parent_id,
        tipo_fonte="dfp",
        ano=2022,
        status="sucesso",
        phase="complete",
        started_at=now - timedelta(minutes=10),
        finished_at=now - timedelta(minutes=5),
        change_summary={"required_member_missing": ["dfp_cia_aberta_parecer_2022.csv"]},
    )
    # Apenas o documento principal esta presente
    child_exec = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        parent_execucao_id=parent_id,
        tipo_execucao="arquivo_membro",
        tipo_fonte="dfp",
        ano=2022,
        arquivo="dfp_cia_aberta_2022.csv",
        url="http://exemplo/dfp_2022.zip",
        status="sucesso",
        total_linhas_lidas=100,
        total_inseridos=100,
        iniciada_em=now - timedelta(minutes=8),
        finalizada_em=now - timedelta(minutes=6),
    )
    db_session.add_all([parent_exec, run, child_exec])
    db_session.commit()

    res = client.get("/ingestion/files/dfp:2022:dfp_cia_aberta_2022.zip")
    assert res.status_code == 200
    data = res.json()

    assert data["file_id"] == "dfp:2022:dfp_cia_aberta_2022.zip"
    assert data["is_container"] is True
    # Integridade calculada e parcial pois faltam membros obrigatorios
    assert data["integridade_em_uso"] == "parcial"
    detalhe = data["integridade_detalhe"]
    assert detalhe["status"] == "parcial"
    assert len(detalhe["membros_faltantes"]) > 0
    assert any("parecer" in m for m in detalhe["membros_faltantes"])
    assert data["falha_relevante"] is not None
    assert data["falha_relevante"]["codigo_erro"] == "REQUIRED_MEMBER_MISSING"


def test_cenario_2_atualizacao_falha_com_versao_anterior_integra(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)

    # Versao 1: sucesso completo
    exec_v1_id = uuid.uuid4()
    exec_v1 = ExecucaoSincronizacao(
        id=exec_v1_id,
        tipo_execucao="arquivo_zip",
        tipo_fonte="dfp",
        ano=2021,
        arquivo="dfp_cia_aberta_2021.zip",
        url="http://exemplo/dfp_2021.zip",
        hash_arquivo="sha_v1_antiga",
        status="sucesso",
        total_linhas_lidas=500,
        total_inseridos=500,
        iniciada_em=now - timedelta(days=30),
        finalizada_em=now - timedelta(days=30, minutes=-10),
    )
    snap_v1 = SourceArtifactSnapshot(
        id=uuid.uuid4(),
        ingestion_run_id=uuid.uuid4(),
        tipo_fonte="dfp",
        ano=2021,
        resource_url="http://exemplo/dfp_2021.zip",
        source_filename="dfp_cia_aberta_2021.zip",
        content_sha256="sha_v1_antiga",
        status="sucesso",
        created_at=now - timedelta(days=30),
    )

    # Versao 2: update detectado com falha de ingestao
    exec_v2_id = uuid.uuid4()
    exec_v2 = ExecucaoSincronizacao(
        id=exec_v2_id,
        tipo_execucao="arquivo_zip",
        tipo_fonte="dfp",
        ano=2021,
        arquivo="dfp_cia_aberta_2021.zip",
        url="http://exemplo/dfp_2021.zip",
        hash_arquivo="sha_v2_nova",
        status="falha",
        mensagem_erro="Erro durante promocao do novo lote CVM.",
        iniciada_em=now - timedelta(hours=2),
        finalizada_em=now - timedelta(hours=1),
    )
    snap_v2 = SourceArtifactSnapshot(
        id=uuid.uuid4(),
        ingestion_run_id=uuid.uuid4(),
        tipo_fonte="dfp",
        ano=2021,
        resource_url="http://exemplo/dfp_2021.zip",
        source_filename="dfp_cia_aberta_2021.zip",
        content_sha256="sha_v2_nova",
        status="falha",
        created_at=now - timedelta(hours=2),
    )

    db_session.add_all([exec_v1, snap_v1, exec_v2, snap_v2])
    db_session.commit()

    res = client.get("/ingestion/files/dfp:2021:dfp_cia_aberta_2021.zip")
    assert res.status_code == 200
    data = res.json()

    # Versao em uso continua integra (sha_v1_antiga)
    assert data["versao_em_uso"] is not None
    assert data["versao_em_uso"]["sha256"] == "sha_v1_antiga"
    assert data["versao_em_uso"]["role"] == "em_uso"

    # Versao alvo aponta a falha mais recente (sha_v2_nova)
    assert data["versao_alvo"] is not None
    assert data["versao_alvo"]["sha256"] == "sha_v2_nova"
    assert data["versao_alvo"]["status"] == "falha"
    assert data["resultado_alvo"] == "falha"

    # Falha relevante reportada no arquivo alvo sem invalidar que a versao em uso existe
    assert data["falha_relevante"] is not None
    assert data["falha_relevante"]["target_type"] == "file"
    assert data["falha_relevante"]["mensagem_erro"] == "Erro durante promocao do novo lote CVM."


def test_cenario_3_falha_antes_do_download(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)
    exec_id = uuid.uuid4()

    # Dispatch falhou antes de efetuar download (ex: timeout de conexao CVM)
    exec_falha = ExecucaoSincronizacao(
        id=exec_id,
        tipo_execucao="arquivo_zip",
        tipo_fonte="itr",
        ano=2023,
        arquivo="itr_cia_aberta_2023.zip",
        url="https://dados.cvm.gov.br/itr_2023.zip",
        status="falha",
        mensagem_erro="Falha de rede pre-download: conexao recusada.",
        iniciada_em=now - timedelta(minutes=15),
        finalizada_em=now - timedelta(minutes=14),
    )
    db_session.add(exec_falha)
    db_session.commit()

    res = client.get("/ingestion/files/itr:2023:itr_cia_aberta_2023.zip")
    assert res.status_code == 200
    data = res.json()

    assert data["file_id"] == "itr:2023:itr_cia_aberta_2023.zip"
    assert data["integridade_em_uso"] == "nao_aplicado"
    # Falha atribuida ao arquivo principal, sem inventar membros
    assert data["falha_relevante"] is not None
    assert data["falha_relevante"]["target_type"] == "file"
    assert data["falha_relevante"]["target_name"] == "itr_cia_aberta_2023.zip"
    assert data["falha_relevante"]["etapa"] == "pre_download"
    assert data["total_membros"] == 0
    assert len(data["membros"]) == 0


def test_cenario_4_espera_automatica_awaiting_parent_window(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    parent_exec = ExecucaoSincronizacao(
        id=parent_id,
        tipo_execucao="arquivo_zip",
        tipo_fonte="dfp",
        ano=2022,
        arquivo="dfp_cia_aberta_2022.zip",
        url="http://exemplo/dfp_2022.zip",
        status="em_execucao",
        iniciada_em=now - timedelta(minutes=5),
    )
    child_exec = ExecucaoSincronizacao(
        id=child_id,
        parent_execucao_id=parent_id,
        tipo_execucao="arquivo_membro",
        tipo_fonte="dfp",
        ano=2022,
        arquivo="dfp_cia_aberta_BPA_con_2022.csv",
        url="http://exemplo/dfp_2022.zip",
        status="aguardando_ingestao",
        iniciada_em=now - timedelta(minutes=3),
    )
    db_session.add_all([parent_exec, child_exec])
    db_session.commit()

    res = client.get("/ingestion/files/dfp:2022:dfp_cia_aberta_2022.zip")
    assert res.status_code == 200
    data = res.json()

    # Atividade atual reconhece a execucao em andamento do pai / membros
    assert data["atividade_atual"] in ("em_processamento", "aguardando_parent_window")
    assert data["next_action"] == "wait"
    # Nao contabiliza como pendencia manual de operador
    assert data["requires_operator"] is False


def test_cenario_5_e_6_replay_que_restaura_e_que_nao_restaura(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)
    # Caso 5: Replay que restaura com evidencia
    run1_id = uuid.uuid4()
    run1 = IngestionRun(
        id=run1_id,
        tipo_fonte="fca",
        ano=2022,
        status="sucesso",
        phase="complete",
        started_at=now - timedelta(hours=1),
        finished_at=now - timedelta(minutes=50),
    )
    audit_replay = IngestionOperationAudit(
        id=uuid.uuid4(),
        scope_type="run",
        scope_id=str(run1_id),
        operation="replay",
        reason="Reprocessamento para corrigir lacuna anterior",
        consequence={"status": "lacuna_restaurada"},
        requested_by="operator",
    )
    exec1 = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        tipo_execucao="arquivo_zip",
        tipo_fonte="fca",
        ano=2022,
        arquivo="fca_cia_aberta_2022.zip",
        url="http://exemplo/fca_2022.zip",
        status="sucesso",
        total_linhas_lidas=200,
        total_inseridos=200,
        iniciada_em=now - timedelta(hours=1),
        finalizada_em=now - timedelta(minutes=50),
    )
    db_session.add_all([run1, audit_replay, exec1])
    db_session.commit()

    res1 = client.get("/ingestion/files/fca:2022:fca_cia_aberta_2022.zip")
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["tentativas"]) >= 1
    assert data1["tentativas"][0]["correlacao"] == "replay"

    # Caso 6: Replay que ainda falhou
    run2_id = uuid.uuid4()
    run2 = IngestionRun(
        id=run2_id,
        tipo_fonte="ipe",
        ano=2022,
        status="falha",
        phase="stage",
        started_at=now - timedelta(hours=1),
        finished_at=now - timedelta(minutes=50),
    )
    exec2 = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        tipo_execucao="arquivo_zip",
        tipo_fonte="ipe",
        ano=2022,
        arquivo="ipe_cia_aberta_2022.zip",
        url="http://exemplo/ipe_2022.zip",
        status="falha",
        mensagem_erro="Erro persistente no replay.",
        iniciada_em=now - timedelta(hours=1),
        finalizada_em=now - timedelta(minutes=50),
    )
    audit2 = IngestionOperationAudit(
        id=uuid.uuid4(),
        scope_type="run",
        scope_id=str(run2_id),
        operation="replay",
        reason="Tentativa de replay",
        consequence={"status": "falha"},
        requested_by="operator",
    )
    db_session.add_all([run2, exec2, audit2])
    db_session.commit()

    res2 = client.get("/ingestion/files/ipe:2022:ipe_cia_aberta_2022.zip")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["falha_relevante"] is not None
    # Falha continua aberta
    assert data2["falha_relevante"]["resolucao"] == "aberta"


def test_cenario_7_falha_reconhecida_sem_reparo(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)
    run_id = uuid.uuid4()
    exec_id = uuid.uuid4()

    run = IngestionRun(
        id=run_id,
        tipo_fonte="cgvn",
        ano=2022,
        status="falha",
        phase="stage",
        started_at=now - timedelta(hours=3),
        finished_at=now - timedelta(hours=2),
    )
    execucao = ExecucaoSincronizacao(
        id=exec_id,
        tipo_execucao="arquivo_zip",
        tipo_fonte="cgvn",
        ano=2022,
        arquivo="cgvn_cia_aberta_2022.zip",
        url="http://exemplo/cgvn_2022.zip",
        status="falha",
        mensagem_erro="Falha de schema em CGVN.",
        iniciada_em=now - timedelta(hours=3),
        finalizada_em=now - timedelta(hours=2),
    )
    audit_ack = IngestionOperationAudit(
        id=uuid.uuid4(),
        scope_type="run",
        scope_id=str(run_id),
        operation="acknowledge-failure",
        reason="Falha operacional reconhecida sem restauracao",
        consequence={"status": "acknowledged"},
        requested_by="operator@empresa.com",
    )
    db_session.add_all([run, execucao, audit_ack])
    db_session.commit()

    res = client.get("/ingestion/files/cgvn:2022:cgvn_cia_aberta_2022.zip")
    assert res.status_code == 200
    data = res.json()

    assert data["falha_relevante"] is not None
    # acknowledge-failure encerra a investigacao
    assert data["falha_relevante"]["resolucao"] == "encerrada_sem_restauracao"
    # Porem NAO repara a integridade
    assert data["integridade_em_uso"] in ("parcial", "nao_aplicado")


def test_cenario_8_sucesso_posterior_em_outra_versao(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)

    # Versao 1 falhou
    exec1 = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        tipo_execucao="arquivo_zip",
        tipo_fonte="vlmo",
        ano=2022,
        arquivo="vlmo_cia_aberta_2022.zip",
        url="http://exemplo/vlmo_2022.zip",
        hash_arquivo="sha_v1_quebrada",
        status="falha",
        mensagem_erro="Erro versao 1",
        iniciada_em=now - timedelta(days=5),
        finalizada_em=now - timedelta(days=5, minutes=-5),
    )
    snap1 = SourceArtifactSnapshot(
        id=uuid.uuid4(),
        ingestion_run_id=uuid.uuid4(),
        tipo_fonte="vlmo",
        ano=2022,
        resource_url="http://exemplo/vlmo_2022.zip",
        source_filename="vlmo_cia_aberta_2022.zip",
        content_sha256="sha_v1_quebrada",
        status="falha",
        created_at=now - timedelta(days=5),
    )

    # Versao 2 (novo SHA) sucede com integridade
    exec2 = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        tipo_execucao="arquivo_zip",
        tipo_fonte="vlmo",
        ano=2022,
        arquivo="vlmo_cia_aberta_2022.zip",
        url="http://exemplo/vlmo_2022.zip",
        hash_arquivo="sha_v2_sadia",
        status="sucesso",
        total_linhas_lidas=300,
        total_inseridos=300,
        iniciada_em=now - timedelta(days=1),
        finalizada_em=now - timedelta(days=1, minutes=-10),
    )
    snap2 = SourceArtifactSnapshot(
        id=uuid.uuid4(),
        ingestion_run_id=uuid.uuid4(),
        tipo_fonte="vlmo",
        ano=2022,
        resource_url="http://exemplo/vlmo_2022.zip",
        source_filename="vlmo_cia_aberta_2022.zip",
        content_sha256="sha_v2_sadia",
        status="sucesso",
        created_at=now - timedelta(days=1),
    )

    db_session.add_all([exec1, snap1, exec2, snap2])
    db_session.commit()

    res = client.get("/ingestion/files/vlmo:2022:vlmo_cia_aberta_2022.zip")
    assert res.status_code == 200
    data = res.json()

    assert data["versao_em_uso"] is not None
    assert data["versao_em_uso"]["sha256"] == "sha_v2_sadia"
    # A versao 1 foi substituida pela versao 2
    versoes_shas = {v["sha256"]: v for v in data["versoes"]}
    assert "sha_v1_quebrada" in versoes_shas
    assert "sha_v2_sadia" in versoes_shas


def test_cenario_9_membros_homonimos_em_pacotes_diferentes(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)

    # Pacote 2021
    p2021_id = uuid.uuid4()
    exec_p2021 = ExecucaoSincronizacao(
        id=p2021_id,
        tipo_execucao="arquivo_zip",
        tipo_fonte="fre",
        ano=2021,
        arquivo="fre_cia_aberta_2021.zip",
        url="http://exemplo/fre_2021.zip",
        status="sucesso",
        iniciada_em=now - timedelta(days=10),
        finalizada_em=now - timedelta(days=10, minutes=-5),
    )
    # Pacote 2022
    p2022_id = uuid.uuid4()
    exec_p2022 = ExecucaoSincronizacao(
        id=p2022_id,
        tipo_execucao="arquivo_zip",
        tipo_fonte="fre",
        ano=2022,
        arquivo="fre_cia_aberta_2022.zip",
        url="http://exemplo/fre_2022.zip",
        status="sucesso",
        iniciada_em=now - timedelta(days=2),
        finalizada_em=now - timedelta(days=2, minutes=-5),
    )

    # Ambos possuem um membro com mesmo nome conceitual ou arquivo: "manifest.csv"
    child_2021 = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        parent_execucao_id=p2021_id,
        tipo_execucao="arquivo_membro",
        tipo_fonte="fre",
        ano=2021,
        arquivo="manifest.csv",
        url="http://exemplo/fre_2021.zip",
        status="sucesso",
        total_linhas_lidas=10,
        iniciada_em=now - timedelta(days=10),
        finalizada_em=now - timedelta(days=10, minutes=-2),
    )
    child_2022 = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        parent_execucao_id=p2022_id,
        tipo_execucao="arquivo_membro",
        tipo_fonte="fre",
        ano=2022,
        arquivo="manifest.csv",
        url="http://exemplo/fre_2022.zip",
        status="falha",
        mensagem_erro="Falha especifica no 2022",
        iniciada_em=now - timedelta(days=2),
        finalizada_em=now - timedelta(days=2, minutes=-2),
    )

    db_session.add_all([exec_p2021, exec_p2022, child_2021, child_2022])
    db_session.commit()

    # Consulta timeline delimitada pelo arquivo pai 2021
    res2021 = client.get("/ingestion/files/fre:2021:fre_cia_aberta_2021.zip/members/manifest.csv/timeline")
    assert res2021.status_code == 200
    data2021 = res2021.json()
    assert data2021["member_id"] == "fre:2021:fre_cia_aberta_2021.zip:manifest.csv"
    assert data2021["parent_file_id"] == "fre:2021:fre_cia_aberta_2021.zip"
    assert data2021["ano"] == 2021
    assert data2021["execucoes"][0]["status"] == "sucesso"

    # Consulta timeline delimitada pelo arquivo pai 2022
    res2022 = client.get("/ingestion/files/fre:2022:fre_cia_aberta_2022.zip/members/manifest.csv/timeline")
    assert res2022.status_code == 200
    data2022 = res2022.json()
    assert data2022["member_id"] == "fre:2022:fre_cia_aberta_2022.zip:manifest.csv"
    assert data2022["parent_file_id"] == "fre:2022:fre_cia_aberta_2022.zip"
    assert data2022["ano"] == 2022
    assert data2022["execucoes"][0]["status"] == "falha"


def test_cenario_10_cadastro_sem_ano(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)

    # Cadastro global: sem ano ficticio, sem ZIP, sem membro artificial
    exec_cad = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        tipo_execucao="arquivo_simples",
        tipo_fonte="cadastro",
        ano=None,
        arquivo="cad_cia_aberta.csv",
        url="https://dados.cvm.gov.br/cad_cia_aberta.csv",
        status="sucesso",
        total_linhas_lidas=2500,
        total_inseridos=2500,
        iniciada_em=now - timedelta(hours=5),
        finalizada_em=now - timedelta(hours=4),
    )
    db_session.add(exec_cad)
    db_session.commit()

    res = client.get("/ingestion/files/cadastro:cad_cia_aberta.csv")
    assert res.status_code == 200
    data = res.json()

    assert data["file_id"] == "cadastro:cad_cia_aberta.csv"
    assert data["tipo_fonte"] == "cadastro"
    assert data["ano"] is None
    assert data["is_container"] is False
    assert data["total_membros"] == 0
    assert len(data["membros"]) == 0
    assert data["integridade_em_uso"] == "completo"


def test_paginacao_e_filtros_server_side(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)

    # Cria múltiplos arquivos de diferentes fontes e anos
    for ano in (2020, 2021, 2022, 2023):
        db_session.add(
            ExecucaoSincronizacao(
                id=uuid.uuid4(),
                tipo_execucao="arquivo_zip",
                tipo_fonte="dfp",
                ano=ano,
                arquivo=f"dfp_cia_aberta_{ano}.zip",
                url=f"http://exemplo/dfp_{ano}.zip",
                status="sucesso",
                iniciada_em=now - timedelta(days=ano - 2000),
                finalizada_em=now - timedelta(days=ano - 2000, minutes=-5),
            )
        )
    db_session.commit()

    # Listagem sem filtros
    res = client.get("/ingestion/files?pagina=1&tamanho_pagina=2")
    assert res.status_code == 200
    data = res.json()
    assert data["total_arquivos"] >= 4
    assert len(data["dados"]) == 2
    assert data["pagina"] == 1
    assert data["tamanho_pagina"] == 2

    # Filtro por ano
    res_ano = client.get("/ingestion/files?ano=2022")
    assert res_ano.status_code == 200
    data_ano = res_ano.json()
    assert all(item["ano"] == 2022 for item in data_ano["dados"])
    assert any(item["file_id"] == "dfp:2022:dfp_cia_aberta_2022.zip" for item in data_ano["dados"])

    # Filtro por fonte
    res_fonte = client.get("/ingestion/files?fonte=dfp")
    assert res_fonte.status_code == 200
    data_fonte = res_fonte.json()
    assert all(item["tipo_fonte"] == "dfp" for item in data_fonte["dados"])

    # Filtro por intervalo de datas naive (concluido_antes e concluido_apos)
    res_datas = client.get(
        "/ingestion/files?concluido_antes=2026-11-08T23:59:59&concluido_apos=2026-10-10T00:00:00&pagina=1&tamanho_pagina=25"
    )
    assert res_datas.status_code == 200
    data_datas = res_datas.json()
    assert "total_arquivos" in data_datas


def test_filtro_em_processamento_ignora_execucao_antiga_ativa_e_busca_filho_atual(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)
    root_old = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        tipo_execucao="arquivo_zip",
        tipo_fonte="dfp",
        ano=2021,
        arquivo="dfp_cia_aberta_2021.zip",
        url="http://exemplo/dfp_2021.zip",
        status="em_execucao",
        iniciada_em=now - timedelta(hours=2),
    )
    root_latest = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        tipo_execucao="arquivo_zip",
        tipo_fonte="dfp",
        ano=2021,
        arquivo="dfp_cia_aberta_2021.zip",
        url="http://exemplo/dfp_2021.zip",
        status="sucesso",
        iniciada_em=now - timedelta(hours=1),
    )
    stale_child = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        parent_execucao_id=root_old.id,
        tipo_execucao="arquivo_membro",
        tipo_fonte="dfp",
        ano=2021,
        arquivo="dfp_cia_aberta_BPA_con_2021.csv",
        url="http://exemplo/dfp_2021.zip",
        status="em_execucao",
        iniciada_em=now - timedelta(hours=2),
    )
    root_current = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        tipo_execucao="arquivo_zip",
        tipo_fonte="dfp",
        ano=2022,
        arquivo="dfp_cia_aberta_2022.zip",
        url="http://exemplo/dfp_2022.zip",
        status="sucesso",
        iniciada_em=now - timedelta(minutes=10),
    )
    active_child = ExecucaoSincronizacao(
        id=uuid.uuid4(),
        parent_execucao_id=root_current.id,
        tipo_execucao="arquivo_membro",
        tipo_fonte="dfp",
        ano=2022,
        arquivo="dfp_cia_aberta_BPA_con_2022.csv",
        url="http://exemplo/dfp_2022.zip",
        status="em_execucao",
        iniciada_em=now - timedelta(minutes=5),
    )
    db_session.add_all([root_old, root_latest, stale_child, root_current, active_child])
    db_session.commit()

    total, files = listar_arquivos_logicos(db_session, atividade="em_processamento")

    assert total == 1
    assert [item.file_id for item in files] == ["dfp:2022:dfp_cia_aberta_2022.zip"]


def test_listar_arquivos_membros_e_detalhe_direto(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    db_session.add(
        ExecucaoSincronizacao(
            id=parent_id,
            tipo_execucao="arquivo_zip",
            tipo_fonte="fre",
            ano=2021,
            arquivo="fre_cia_aberta_2021.zip",
            url="http://exemplo/fre_2021.zip",
            status="sucesso",
            iniciada_em=now - timedelta(minutes=15),
            finalizada_em=now - timedelta(minutes=5),
        )
    )
    db_session.add(
        ExecucaoSincronizacao(
            id=child_id,
            parent_execucao_id=parent_id,
            tipo_execucao="arquivo_membro",
            tipo_fonte="fre",
            ano=2021,
            arquivo="fre_cia_aberta_distribuicao_dividendos_classe_acao_2021.csv",
            url="http://exemplo/fre_2021.zip",
            status="sucesso",
            hash_arquivo="sha-div-2021",
            total_linhas_lidas=150,
            total_inseridos=150,
            iniciada_em=now - timedelta(minutes=10),
            finalizada_em=now - timedelta(minutes=6),
        )
    )
    db_session.commit()

    # 1. Listar membros com busca por substring
    res_list = client.get("/ingestion/members?busca=dividendos&ano=2021")
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert data_list["total_membros"] >= 1
    assert any(m["member_name"] == "fre_cia_aberta_distribuicao_dividendos_classe_acao_2021.csv" for m in data_list["dados"])
    membro = next(m for m in data_list["dados"] if m["member_name"] == "fre_cia_aberta_distribuicao_dividendos_classe_acao_2021.csv")
    assert membro["tipo_fonte"] == "fre"
    assert membro["ano"] == 2021
    assert membro["status"] == "sucesso"
    assert membro["total_linhas"] == 150

    # 2. Consultar detalhes ancorado diretamente pelo nome do membro (sem /timeline)
    res_detail = client.get("/ingestion/members/fre_cia_aberta_distribuicao_dividendos_classe_acao_2021.csv")
    assert res_detail.status_code == 200
    data_detail = res_detail.json()
    assert data_detail["member_name"] == "fre_cia_aberta_distribuicao_dividendos_classe_acao_2021.csv"
    assert data_detail["tipo_fonte"] == "fre"
    assert data_detail["ano"] == 2021
    assert data_detail["total_execucoes"] >= 1
    assert data_detail["execucoes"][0]["status"] == "sucesso"

    # 3. Consultar detalhes ancorado delimitado pelo pacote pai
    parent_fid = "fre:2021:fre_cia_aberta_2021.zip"
    res_parent_detail = client.get(
        f"/ingestion/files/{parent_fid}/members/fre_cia_aberta_distribuicao_dividendos_classe_acao_2021.csv"
    )
    assert res_parent_detail.status_code == 200
    assert res_parent_detail.json()["member_name"] == "fre_cia_aberta_distribuicao_dividendos_classe_acao_2021.csv"
