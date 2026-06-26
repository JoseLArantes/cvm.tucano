from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analise import (
    AnaliseMaterializacaoCampanha,
    AnaliseMaterializacaoCampanhaItem,
    AnaliseMaterializacaoChunkExecucao,
    AnaliseMaterializacaoExecucao,
)
from app.models.companhia import Companhia
from app.models.financeiro import DemonstracaoFinanceira, DocumentoFinanceiro
from app.models.ingestion import IngestionRun
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.analise import (
    campanha_tem_requeue_em_transito,
    claim_materializacao_campanha_chunk,
    classificar_recuperacao_materializacao_campanha,
    criar_materializacao_campanha,
    obter_estado_gate_materializacao,
    pausar_controle_materializacao,
    reativar_materializacao_campanha,
    recuperar_chunks_materializacao_stale,
    recuperar_materializacao_pendente,
)
from app.worker import tasks as worker_tasks


def _companhia(db_session: Session, codigo_cvm: int = 9512, situacao_registro: str = "ATIVO") -> Companhia:
    agora = datetime.now(UTC)
    cia = Companhia(
        cnpj_companhia=f"{codigo_cvm:014d}",
        codigo_cvm=codigo_cvm,
        denominacao_social="PETROBRAS",
        denominacao_comercial="PETROBRAS",
        situacao_registro=situacao_registro,
        arquivo_origem="cadastro.csv",
        hash_origem=f"cia-{codigo_cvm}",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )
    db_session.add(cia)
    db_session.commit()
    return cia


def test_criar_materializacao_campanha_deduplica_trabalho_ativo(db_session: Session) -> None:
    cia = _companhia(db_session)
    campanha_ativa = AnaliseMaterializacaoCampanha(
        source="post_ingestion",
        status="running",
        chunk_size=25,
        total_items=1,
        pending_items=0,
        running_items=1,
        success_items=0,
        failed_items=0,
        skipped_items=0,
        summary={},
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(campanha_ativa)
    db_session.flush()
    db_session.add(
        AnaliseMaterializacaoCampanhaItem(
            campanha_id=campanha_ativa.id,
            codigo_cvm=cia.codigo_cvm,
            companhia_id=cia.id,
            escopo="consolidated",
            status="running",
            ordem=1,
            attempts=1,
            started_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[9512],
        source="post_ingestion",
    )

    itens = list(
        db_session.scalars(
            select(AnaliseMaterializacaoCampanhaItem)
            .where(AnaliseMaterializacaoCampanhaItem.campanha_id == campanha.id)
            .order_by(AnaliseMaterializacaoCampanhaItem.ordem.asc())
        ).all()
    )
    assert campanha.total_items == 2
    assert campanha.pending_items == 1
    assert campanha.skipped_items == 1
    assert {item.escopo for item in itens} == {"consolidated", "individual"}
    skipped = next(item for item in itens if item.status == "skipped")
    pending = next(item for item in itens if item.status == "pending")
    assert skipped.escopo == "consolidated"
    assert skipped.reason == "ALREADY_COVERED_BY_ACTIVE_CAMPAIGN"
    assert pending.escopo == "individual"


def test_claim_materializacao_campanha_chunk_marca_itens_como_running(db_session: Session) -> None:
    _companhia(db_session)
    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[9512],
        source="post_ingestion",
    )

    claimed = claim_materializacao_campanha_chunk(db_session, campanha.id, chunk_size=1)
    assert claimed is not None
    chunk, items = claimed
    assert len(items) == 1

    db_session.refresh(campanha)
    assert campanha.running_items == 1
    assert campanha.pending_items == 1
    assert chunk.status == "queued"
    assert chunk.item_count == 1
    assert items[0].status == "running"
    assert items[0].enqueued_at is not None
    assert items[0].chunk_execucao_id == chunk.id


def test_criar_materializacao_campanha_exclui_companhias_canceladas_por_padrao(db_session: Session) -> None:
    _companhia(db_session, codigo_cvm=9512, situacao_registro="ATIVO")
    _companhia(db_session, codigo_cvm=1716, situacao_registro="CANCELADA")

    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[9512, 1716],
        source="post_ingestion",
    )

    itens = list(
        db_session.scalars(
            select(AnaliseMaterializacaoCampanhaItem)
            .where(AnaliseMaterializacaoCampanhaItem.campanha_id == campanha.id)
            .order_by(AnaliseMaterializacaoCampanhaItem.ordem.asc())
        ).all()
    )

    assert campanha.total_items == 2
    assert {item.codigo_cvm for item in itens} == {9512}
    assert campanha.summary is not None
    assert campanha.summary["selection"]["excluded_cancelled_codigo_cvm_count"] == 1
    assert campanha.summary["selection"]["incluir_canceladas"] is False


def test_criar_materializacao_campanha_define_invalidated_from_por_execucao_origem(db_session: Session) -> None:
    cia = _companhia(db_session)
    execucao = ExecucaoSincronizacao(
        tipo_fonte="dfp",
        ano=2025,
        arquivo="dfp_2025.zip",
        url="http://exemplo/dfp",
        status="sucesso",
        iniciada_em=datetime.now(UTC),
    )
    db_session.add(execucao)
    db_session.flush()
    db_session.add(
        DocumentoFinanceiro(
            companhia_id=cia.id,
            tipo_formulario="DFP",
            cnpj_companhia=cia.cnpj_companhia,
            codigo_cvm=cia.codigo_cvm,
            data_referencia=datetime(2025, 12, 31, tzinfo=UTC).date(),
            versao=2,
            denominacao_companhia=cia.denominacao_social,
            categoria_documento="DFP",
            id_documento=123,
            data_recebimento=datetime(2026, 3, 10, tzinfo=UTC).date(),
            link_documento="http://exemplo/dfp-v2.zip",
            arquivo_origem="dfp.csv",
            ano_origem=2025,
            linha_origem=1,
            hash_origem="doc-1",
            criado_em=datetime.now(UTC),
            sincronizado_em=datetime.now(UTC),
            alterado_em=datetime.now(UTC),
        )
    )
    db_session.commit()
    assert cia.codigo_cvm is not None

    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        source_execucao_id=str(execucao.id),
    )
    itens = list(
        db_session.scalars(
            select(AnaliseMaterializacaoCampanhaItem).where(AnaliseMaterializacaoCampanhaItem.campanha_id == campanha.id)
        ).all()
    )

    assert itens
    assert {item.invalidated_from for item in itens} == {datetime(2026, 3, 10, tzinfo=UTC).date()}


def test_criar_materializacao_campanha_pode_incluir_companhias_canceladas_quando_explicito(db_session: Session) -> None:
    cia = _companhia(db_session, codigo_cvm=1716, situacao_registro="CANCELADA")
    assert cia.codigo_cvm is not None

    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="manual",
        incluir_canceladas=True,
    )
    itens = list(
        db_session.scalars(
            select(AnaliseMaterializacaoCampanhaItem).where(AnaliseMaterializacaoCampanhaItem.campanha_id == campanha.id)
        ).all()
    )

    assert campanha.total_items == 2
    assert {item.codigo_cvm for item in itens} == {cia.codigo_cvm}
    assert campanha.summary is not None
    assert campanha.summary["selection"]["excluded_cancelled_codigo_cvm_count"] == 0
    assert campanha.summary["selection"]["incluir_canceladas"] is True


def test_finalizar_sincronizacao_zip_cria_campanha_e_dispara_dispatcher(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cia = _companhia(db_session)
    agora = datetime.now(UTC)
    execucao = ExecucaoSincronizacao(
        tipo_fonte="dfp",
        ano=2025,
        arquivo="dfp_cia_aberta_2025.zip",
        url="http://exemplo/dfp",
        status="em_execucao",
        iniciada_em=agora,
    )
    db_session.add(execucao)
    db_session.flush()
    db_session.add(
        IngestionRun(
            execucao_sincronizacao_id=execucao.id,
            tipo_fonte="dfp",
            ano=2025,
            status="em_execucao",
            phase="ingest",
            started_at=agora,
        )
    )
    db_session.add(
        DemonstracaoFinanceira(
            companhia_id=cia.id,
            tipo_formulario="DFP",
            tipo_demonstracao="demonstracao_resultado",
            escopo_demonstracao="consolidado",
            cnpj_companhia=cia.cnpj_companhia,
            codigo_cvm=cia.codigo_cvm,
            data_referencia=datetime(2025, 12, 31, tzinfo=UTC).date(),
            versao=1,
            codigo_conta="3.01",
            valor_conta=Decimal("1"),
            escala_moeda="MIL",
            ordem_exercicio="ÚLTIMO",
            coluna_df="VALOR",
            arquivo_origem="dfp.csv",
            hash_origem="dfp-row",
            ano_origem=2025,
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db_session.commit()

    captured: dict[str, object] = {}

    def _fake_apply_async(*, countdown: int, queue: str) -> None:
        captured["countdown"] = countdown
        captured["queue"] = queue

    monkeypatch.setattr(worker_tasks.despachar_materializacao_pendente_task, "apply_async", _fake_apply_async)
    monkeypatch.setattr("app.db.session.SessionLocal", lambda: db_session)

    resultado = worker_tasks.finalizar_sincronizacao_zip_task.run(str(execucao.id))

    campanha = db_session.scalar(select(AnaliseMaterializacaoCampanha).order_by(AnaliseMaterializacaoCampanha.created_at.desc()))
    assert resultado["status"] == "sucesso"
    assert campanha is not None
    assert campanha.source == "post_ingestion"
    assert campanha.source_execucao_id == execucao.id
    assert captured["countdown"] == 0
    assert captured["queue"] == "analise_materializacao"


def test_materializar_analise_campanha_reagenda_sem_consumir_retry_quando_sem_slot(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campanha_running = AnaliseMaterializacaoCampanha(
        source="post_ingestion",
        status="running",
        chunk_size=25,
        total_items=1,
        pending_items=0,
        running_items=1,
        success_items=0,
        failed_items=0,
        skipped_items=0,
        summary={},
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    campanha_pending = AnaliseMaterializacaoCampanha(
        source="post_ingestion",
        status="pending",
        chunk_size=25,
        total_items=1,
        pending_items=1,
        running_items=0,
        success_items=0,
        failed_items=0,
        skipped_items=0,
        summary={},
        updated_at=datetime.now(UTC),
    )
    db_session.add_all([campanha_running, campanha_pending])
    db_session.commit()

    captured: dict[str, object] = {}

    def _fake_apply_async(*, args: tuple[str], countdown: int, queue: str) -> None:
        captured["args"] = args
        captured["countdown"] = countdown
        captured["queue"] = queue

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_tasks.materializar_analise_campanha_task, "apply_async", _fake_apply_async)

    resultado = worker_tasks.materializar_analise_campanha_task.run(str(campanha_pending.id))
    campanha_pending_atualizada = db_session.get(AnaliseMaterializacaoCampanha, campanha_pending.id)

    assert resultado["status"] == "waiting_for_slot"
    assert resultado["campanha_id"] == str(campanha_pending.id)
    assert captured["args"] == (str(campanha_pending.id),)
    assert captured["countdown"] == 30
    assert captured["queue"] == "analise_materializacao"
    assert campanha_pending_atualizada is not None
    assert campanha_pending_atualizada.status == "pending"
    assert campanha_pending_atualizada.summary is not None
    assert campanha_pending_atualizada.summary["wait_reason"] == "MAX_ACTIVE_CAMPAIGNS_REACHED"


def test_obter_estado_gate_materializacao_detecta_ingestao_ativa(db_session: Session) -> None:
    agora = datetime.now(UTC)
    execucao = ExecucaoSincronizacao(
        tipo_fonte="itr",
        ano=2025,
        arquivo="itr_2025.zip",
        url="http://exemplo/itr",
        status="em_execucao",
        iniciada_em=agora,
    )
    db_session.add(execucao)
    db_session.commit()

    gate = obter_estado_gate_materializacao(db_session)

    assert gate.status == "red"
    assert gate.reason_code == "INGESTION_ACTIVE"
    assert gate.blocking_ingestions == 1
    assert gate.blockers[0].source_type == "itr"


def test_obter_estado_gate_materializacao_ignora_execucoes_nao_ativas(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agora = datetime.now(UTC)
    monkeypatch.setattr(
        "app.services.analise._settings.analise_materializacao_blocking_sync_statuses",
        "em_execucao,agendada,cancelada",
    )
    db_session.add_all(
        [
            ExecucaoSincronizacao(
                tipo_fonte="itr",
                ano=2025,
                arquivo="itr_2025.zip",
                url="http://exemplo/itr",
                status="cancelada",
                iniciada_em=agora,
            ),
            ExecucaoSincronizacao(
                tipo_fonte="dfp",
                ano=2025,
                arquivo="dfp_2025.zip",
                url="http://exemplo/dfp",
                status="agendada",
                iniciada_em=agora,
            ),
        ]
    )
    db_session.commit()

    gate = obter_estado_gate_materializacao(db_session)

    assert gate.status == "green"
    assert gate.reason_code == "NO_BLOCKERS"
    assert gate.blocking_ingestions == 0
    assert gate.blockers == ()


def test_obter_estado_gate_materializacao_respeita_pausa_manual(db_session: Session) -> None:
    pausar_controle_materializacao(db_session, reason="janela de carga")

    gate = obter_estado_gate_materializacao(db_session)

    assert gate.status == "red"
    assert gate.reason_code == "MANUAL_PAUSE"
    assert gate.manual_control == "paused"
    assert gate.manual_reason == "janela de carga"


def test_materializar_analise_campanha_aguarda_gate_vermelho(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campanha = AnaliseMaterializacaoCampanha(
        source="post_ingestion",
        status="pending",
        chunk_size=25,
        total_items=1,
        pending_items=1,
        running_items=0,
        success_items=0,
        failed_items=0,
        skipped_items=0,
        summary={},
        updated_at=datetime.now(UTC),
    )
    db_session.add(campanha)
    db_session.flush()
    db_session.add(
        AnaliseMaterializacaoCampanhaItem(
            campanha_id=campanha.id,
            codigo_cvm=9512,
            escopo="consolidated",
            status="pending",
            ordem=1,
            attempts=0,
            updated_at=datetime.now(UTC),
        )
    )
    db_session.add(
        ExecucaoSincronizacao(
            tipo_fonte="dfp",
            ano=2025,
            arquivo="dfp_2025.zip",
            url="http://exemplo/dfp",
            status="em_execucao",
            iniciada_em=datetime.now(UTC),
        )
    )
    db_session.commit()

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)

    resultado = worker_tasks.materializar_analise_campanha_task.run(str(campanha.id))
    campanha_atualizada = db_session.get(AnaliseMaterializacaoCampanha, campanha.id)

    assert resultado["status"] == "waiting_for_gate"
    assert campanha_atualizada is not None
    assert campanha_atualizada.status == "pending"
    assert campanha_atualizada.summary is not None
    assert campanha_atualizada.summary["wait_reason"] == "INGESTION_ACTIVE"


def test_despachar_materializacao_pendente_nao_enfileira_quando_gate_vermelho(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        chunk_size=1,
    )
    db_session.add(
        ExecucaoSincronizacao(
            tipo_fonte="dfp",
            ano=2025,
            arquivo="dfp_2025.zip",
            url="http://exemplo/dfp",
            status="em_execucao",
            iniciada_em=datetime.now(UTC),
        )
    )
    db_session.commit()

    called = False

    def _fake_delay(_campanha_id: str) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_tasks.materializar_analise_campanha_task, "delay", _fake_delay)

    resultado = worker_tasks.despachar_materializacao_pendente_task.run()

    assert resultado["status"] == "waiting_for_gate"
    assert called is False


def test_materializar_analise_campanha_enfileira_um_chunk_por_invocacao(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        chunk_size=1,
    )
    captured: dict[str, str] = {}

    def _fake_delay(campanha_id: str, chunk_execucao_id: str) -> None:
        captured["campanha_id"] = campanha_id
        captured["chunk_execucao_id"] = chunk_execucao_id

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_tasks.materializar_analise_chunk_task, "delay", _fake_delay)

    resultado = worker_tasks.materializar_analise_campanha_task.run(str(campanha.id))
    campanha_atualizada = db_session.get(AnaliseMaterializacaoCampanha, campanha.id)

    assert resultado["status"] == "enqueued"
    assert resultado["chunk_count"] == 1
    assert resultado["claimed_items"] == 1
    assert captured["campanha_id"] == str(campanha.id)
    assert captured["chunk_execucao_id"] == resultado["chunk_execucao_id"]
    assert campanha_atualizada is not None
    assert campanha_atualizada.running_items == 1
    assert campanha_atualizada.pending_items == 1


def test_materializar_analise_campanha_enfileira_multiplos_chunks_quando_habilitado(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    codigo_cvm_secundario = cia.codigo_cvm + 1
    _companhia(db_session, codigo_cvm=codigo_cvm_secundario)
    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm, codigo_cvm_secundario],
        source="post_ingestion",
        chunk_size=1,
    )
    captured: list[tuple[str, str]] = []

    def _fake_delay(campanha_id: str, chunk_execucao_id: str) -> None:
        captured.append((campanha_id, chunk_execucao_id))

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        worker_tasks._settings,
        "analise_materializacao_max_active_chunks_per_campaign",
        2,
    )
    monkeypatch.setattr(worker_tasks.materializar_analise_chunk_task, "delay", _fake_delay)

    resultado = worker_tasks.materializar_analise_campanha_task.run(str(campanha.id))
    campanha_atualizada = db_session.get(AnaliseMaterializacaoCampanha, campanha.id)

    assert resultado["status"] == "enqueued"
    assert resultado["chunk_count"] == 2
    assert resultado["claimed_items"] == 2
    assert len(resultado["chunk_execucao_ids"]) == 2
    assert len(captured) == 2
    assert {campanha_id for campanha_id, _chunk_id in captured} == {str(campanha.id)}
    assert campanha_atualizada is not None
    assert campanha_atualizada.running_items == 2
    assert campanha_atualizada.pending_items == 2


def test_materializar_analise_campanha_aguarda_slot_de_chunk_por_campanha(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        chunk_size=1,
    )
    claimed = claim_materializacao_campanha_chunk(db_session, campanha.id, chunk_size=1)
    assert claimed is not None
    chunk, _items = claimed

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        worker_tasks._settings,
        "analise_materializacao_max_active_chunks_per_campaign",
        1,
    )

    resultado = worker_tasks.materializar_analise_campanha_task.run(str(campanha.id))
    campanha_atualizada = db_session.get(AnaliseMaterializacaoCampanha, campanha.id)

    assert resultado["status"] == "waiting_for_chunk_slot"
    assert resultado["active_chunks"] == 1
    assert resultado["max_active_chunks_per_campaign"] == 1
    assert resultado["active_chunk_ids_preview"] == [str(chunk.id)]
    assert campanha_atualizada is not None
    assert campanha_atualizada.summary is not None
    assert campanha_atualizada.summary["wait_reason"] == "MAX_ACTIVE_CHUNKS_PER_CAMPAIGN_REACHED"


def test_recuperar_chunks_materializacao_stale_devolve_itens_para_pending(db_session: Session) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        chunk_size=1,
    )
    claimed = claim_materializacao_campanha_chunk(db_session, campanha.id, chunk_size=1)
    assert claimed is not None
    chunk, items = claimed
    item = items[0]
    chunk.status = "running"
    chunk.lease_expires_at = datetime.now(UTC)
    chunk.updated_at = datetime.now(UTC)
    item.started_at = datetime.now(UTC)
    execucao = AnaliseMaterializacaoExecucao(
        companhia_id=cia.id,
        codigo_cvm=cia.codigo_cvm,
        escopo="consolidated",
        calculation_version="2026.2",
        status="running",
        coverage_complete=False,
        source="post_ingestion",
        campanha_id=campanha.id,
        campanha_item_id=item.id,
        chunk_execucao_id=chunk.id,
        summary={},
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(execucao)
    db_session.commit()

    chunk.lease_expires_at = datetime.now(UTC) - timedelta(seconds=120)
    db_session.commit()

    resultado = recuperar_chunks_materializacao_stale(db_session)
    item_atualizado = db_session.get(AnaliseMaterializacaoCampanhaItem, item.id)
    chunk_atualizado = db_session.get(AnaliseMaterializacaoChunkExecucao, chunk.id)
    execucao_atualizada = db_session.get(AnaliseMaterializacaoExecucao, execucao.id)
    campanha_atualizada = db_session.get(AnaliseMaterializacaoCampanha, campanha.id)

    assert resultado.recovered_chunks == 1
    assert resultado.recovered_items == 1
    assert item_atualizado is not None
    assert item_atualizado.status == "pending"
    assert item_atualizado.chunk_execucao_id is None
    assert chunk_atualizado is not None
    assert chunk_atualizado.status == "stale"
    assert execucao_atualizada is not None
    assert execucao_atualizada.status == "failed"
    assert campanha_atualizada is not None
    assert campanha_atualizada.status == "pending"
    assert campanha_atualizada.summary is not None
    assert campanha_atualizada.summary["wait_reason"] == "STALE_CHUNK_RECOVERED"


def test_recuperar_chunks_materializacao_stale_preserva_itens_ja_concluidos(db_session: Session) -> None:
    cia = _companhia(db_session)
    campanha = AnaliseMaterializacaoCampanha(
        source="post_ingestion",
        status="running",
        chunk_size=25,
        total_items=1,
        pending_items=0,
        running_items=0,
        success_items=1,
        failed_items=0,
        skipped_items=0,
        summary={},
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(campanha)
    db_session.flush()
    chunk = AnaliseMaterializacaoChunkExecucao(
        campanha_id=campanha.id,
        status="running",
        item_count=1,
        processed_items=1,
        success_items=1,
        failed_items=0,
        lease_expires_at=datetime.now(UTC) - timedelta(seconds=120),
        heartbeat_at=datetime.now(UTC) - timedelta(seconds=120),
        started_at=datetime.now(UTC) - timedelta(minutes=5),
        updated_at=datetime.now(UTC) - timedelta(seconds=120),
        summary={},
    )
    db_session.add(chunk)
    db_session.flush()
    item = AnaliseMaterializacaoCampanhaItem(
        campanha_id=campanha.id,
        codigo_cvm=cia.codigo_cvm,
        companhia_id=cia.id,
        escopo="consolidated",
        status="success",
        ordem=1,
        attempts=1,
        chunk_execucao_id=chunk.id,
        materializacao_execucao_id=None,
        started_at=datetime.now(UTC) - timedelta(minutes=5),
        finished_at=datetime.now(UTC) - timedelta(minutes=4),
        updated_at=datetime.now(UTC) - timedelta(minutes=4),
    )
    db_session.add(item)
    db_session.commit()

    resultado = recuperar_chunks_materializacao_stale(db_session)
    item_atualizado = db_session.get(AnaliseMaterializacaoCampanhaItem, item.id)
    chunk_atualizado = db_session.get(AnaliseMaterializacaoChunkExecucao, chunk.id)

    assert resultado.recovered_chunks == 1
    assert resultado.recovered_items == 0
    assert item_atualizado is not None
    assert item_atualizado.status == "success"
    assert item_atualizado.chunk_execucao_id == chunk.id
    assert chunk_atualizado is not None
    assert chunk_atualizado.status == "stale"


def test_materializar_analise_campanha_recupera_stale_inline_e_reenfileira(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        chunk_size=1,
    )
    claimed = claim_materializacao_campanha_chunk(db_session, campanha.id, chunk_size=1)
    assert claimed is not None
    chunk, items = claimed
    item = items[0]
    chunk.status = "running"
    chunk.lease_expires_at = datetime.now(UTC) - timedelta(seconds=120)
    chunk.heartbeat_at = datetime.now(UTC) - timedelta(seconds=120)
    item.status = "running"
    db_session.commit()

    captured: dict[str, object] = {}

    def _fake_apply_async(*, args: tuple[str], countdown: int, queue: str) -> None:
        captured["args"] = args
        captured["countdown"] = countdown
        captured["queue"] = queue

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_tasks.materializar_analise_campanha_task, "apply_async", _fake_apply_async)

    resultado = worker_tasks.materializar_analise_campanha_task.run(str(campanha.id))

    chunk_atualizado = db_session.get(AnaliseMaterializacaoChunkExecucao, chunk.id)
    item_atualizado = db_session.get(AnaliseMaterializacaoCampanhaItem, item.id)
    campanha_atualizada = db_session.get(AnaliseMaterializacaoCampanha, campanha.id)

    assert resultado["status"] == "recovered_stale_and_requeued"
    assert resultado["recovered_chunks"] == 1
    assert resultado["recovered_items"] == 1
    assert captured["args"] == (str(campanha.id),)
    assert captured["countdown"] == 0
    assert captured["queue"] == "analise_materializacao"
    assert chunk_atualizado is not None
    assert chunk_atualizado.status == "stale"
    assert item_atualizado is not None
    assert item_atualizado.status == "pending"
    assert campanha_atualizada is not None
    assert campanha_atualizada.summary is not None
    assert campanha_atualizada.summary["wait_reason"] == "STALE_CHUNK_RECOVERED"


def test_reconciliar_materializacao_stale_task_reagenda_campanha(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        chunk_size=1,
    )
    claimed = claim_materializacao_campanha_chunk(db_session, campanha.id, chunk_size=1)
    assert claimed is not None
    chunk, _items = claimed
    chunk.lease_expires_at = datetime.now(UTC) - timedelta(seconds=120)
    db_session.commit()

    captured: dict[str, object] = {}

    def _fake_apply_async(*, args: tuple[str], countdown: int, queue: str) -> None:
        captured["args"] = args
        captured["countdown"] = countdown
        captured["queue"] = queue

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_tasks.materializar_analise_campanha_task, "apply_async", _fake_apply_async)

    resultado = worker_tasks.reconciliar_materializacao_stale_task.run(str(campanha.id))

    assert resultado["status"] == "recovered"
    assert resultado["recovered_chunks"] == 1
    assert captured["args"] == (str(campanha.id),)
    assert captured["countdown"] == 60
    assert captured["queue"] == "analise_materializacao"


def test_classificar_recuperacao_materializacao_campanha_detecta_pending_undispatched(db_session: Session) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        chunk_size=1,
    )

    classificacao = classificar_recuperacao_materializacao_campanha(
        db_session,
        campanha,
    )

    assert classificacao.reason_code == "PENDING_UNDISPATCHED"
    assert classificacao.recoverable is True


def test_reativar_materializacao_campanha_recupera_stale_e_reenfileira(db_session: Session) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        chunk_size=1,
    )
    claimed = claim_materializacao_campanha_chunk(db_session, campanha.id, chunk_size=1)
    assert claimed is not None
    chunk, _items = claimed
    chunk.lease_expires_at = datetime.now(UTC) - timedelta(seconds=120)
    db_session.commit()

    resultado = reativar_materializacao_campanha(db_session, campanha.id)

    assert resultado.status == "recovered"
    assert resultado.reason_code == "STALE_CHUNK"
    assert resultado.recovered_chunks == 1
    assert str(campanha.id) in resultado.requeued_campaigns
    campanha_atualizada = db_session.get(AnaliseMaterializacaoCampanha, campanha.id)
    assert campanha_atualizada is not None
    assert campanha_atualizada.summary is not None
    assert campanha_atualizada.summary["recovery_state"] == "requeued"
    assert campanha_tem_requeue_em_transito(campanha_atualizada) is True


def test_recuperar_materializacao_pendente_reenfileira_apenas_pending_undispatched(
    db_session: Session,
) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    campanha_recuperavel = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        chunk_size=1,
    )
    campanha_bloqueada = AnaliseMaterializacaoCampanha(
        source="post_ingestion",
        status="pending",
        chunk_size=25,
        total_items=1,
        pending_items=1,
        running_items=0,
        success_items=0,
        failed_items=0,
        skipped_items=0,
        summary={"wait_reason": "INGESTION_ACTIVE"},
        updated_at=datetime.now(UTC),
    )
    db_session.add(campanha_bloqueada)
    db_session.flush()
    db_session.add(
        AnaliseMaterializacaoCampanhaItem(
            campanha_id=campanha_bloqueada.id,
            codigo_cvm=cia.codigo_cvm,
            companhia_id=cia.id,
            escopo="consolidated",
            status="pending",
            ordem=1,
            attempts=0,
            updated_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    resultado = recuperar_materializacao_pendente(
        db_session,
        max_campaigns=10,
        max_requeues=10,
        min_age_seconds=0,
    )

    assert resultado.status == "triggered"
    assert resultado.reason_code == "PENDING_UNDISPATCHED"
    assert list(resultado.requeued_campaigns) == [str(campanha_recuperavel.id)]
    assert str(campanha_bloqueada.id) not in resultado.requeued_campaigns


def test_recuperar_materializacao_pendente_task_reenfileira_campanhas(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cia = _companhia(db_session)
    assert cia.codigo_cvm is not None
    campanha = criar_materializacao_campanha(
        db_session,
        codigos_cvm=[cia.codigo_cvm],
        source="post_ingestion",
        chunk_size=1,
    )
    campanha.created_at = datetime.now(UTC) - timedelta(minutes=10)
    db_session.commit()
    captured: dict[str, object] = {}

    def _fake_apply_async(*, args: tuple[str], countdown: int, queue: str) -> None:
        captured["args"] = args
        captured["countdown"] = countdown
        captured["queue"] = queue

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_tasks.materializar_analise_campanha_task, "apply_async", _fake_apply_async)

    resultado = worker_tasks.recuperar_materializacao_pendente_task.run()

    assert resultado["status"] == "triggered"
    assert resultado["reason_code"] == "PENDING_UNDISPATCHED"
    assert captured["args"] == (str(campanha.id),)
    assert captured["countdown"] == 0
    assert captured["queue"] == "analise_materializacao"
