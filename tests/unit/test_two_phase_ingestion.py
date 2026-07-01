import hashlib
import io
import shutil
import uuid
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.models.companhia import Companhia
from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.cadastro import (
    ARQUIVO_CADASTRO_ABERTA,
    ARQUIVO_CADASTRO_ESTRANGEIRA,
    ingerir_cadastro,
    pre_processar_cadastro,
)
from app.services.ingestion.staging import create_run, register_file, register_member
from app.worker.tasks import pre_processar_sincronizacao_zip


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

def _row_aberta(cnpj: str, codigo_cvm: str) -> dict[str, str]:
    return {
        "CNPJ_CIA": cnpj,
        "DENOM_SOCIAL": "EMPRESA SA",
        "DENOM_COMERC": "EMPRESA SA",
        "DT_REG": "2020-01-01",
        "DT_CONST": "2000-01-01",
        "DT_CANCEL": "",
        "MOTIVO_CANCEL": "",
        "SIT": "ATIVO",
        "DT_INI_SIT": "2020-01-01",
        "CD_CVM": codigo_cvm,
        "SETOR_ATIV": "Energia",
        "TP_MERC": "BOLSA",
        "CATEG_REG": "Categoria A",
        "DT_INI_CATEG": "2020-01-01",
        "SIT_EMISSOR": "FASE OPERACIONAL",
        "DT_INI_SIT_EMISSOR": "2020-01-01",
        "CONTROLE_ACIONARIO": "PRIVADO",
        "TP_ENDER": "SEDE",
        "LOGRADOURO": "Rua A",
        "COMPL": "",
        "BAIRRO": "Centro",
        "MUN": "SAO PAULO",
        "UF": "SP",
        "PAIS": "BRASIL",
        "CEP": "01001000",
        "DDD_TEL": "11",
        "TEL": "11111111",
        "DDD_FAX": "",
        "FAX": "",
        "EMAIL": "",
        "TP_RESP": "DIRETOR",
        "RESP": "Fulano",
        "DT_INI_RESP": "2020-01-01",
        "LOGRADOURO_RESP": "Rua B",
        "COMPL_RESP": "",
        "BAIRRO_RESP": "Centro",
        "MUN_RESP": "SAO PAULO",
        "UF_RESP": "SP",
        "PAIS_RESP": "BRASIL",
        "CEP_RESP": "01001000",
        "DDD_TEL_RESP": "11",
        "TEL_RESP": "11111111",
        "DDD_FAX_RESP": "",
        "FAX_RESP": "",
        "EMAIL_RESP": "",
        "CNPJ_AUDITOR": "",
        "AUDITOR": "",
    }

def _row_estrangeira(cnpj: str, codigo_cvm: str) -> dict[str, str]:
    return {
        "CNPJ": cnpj,
        "DENOM_SOCIAL": "AURA MINERALS INC.",
        "DENOM_COMERC": "AURA MINERALS INC.",
        "PAIS_ORIGEM": "EXTERIOR",
        "DT_REG": "2020-01-01",
        "DT_CONST": "2000-01-01",
        "DT_CANCEL": "",
        "MOTIVO_CANCEL": "",
        "SIT": "ATIVO",
        "DT_INI_SIT": "2020-01-01",
        "CD_CVM": codigo_cvm,
        "SETOR_ATIV": "Mineracao",
    }

def _csv_content(rows: list[dict[str, str]]) -> bytes:
    header = list(rows[0].keys())
    lines = [";".join(header)]
    for row in rows:
        lines.append(";".join(row.get(column, "") for column in header))
    return ("\n".join(lines) + "\n").encode("latin1")

def test_two_phase_flow_and_self_healing(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    settings = get_settings()
    
    # Configure a mock storage dir
    test_storage = Path("data/test_storage_two_phase")
    monkeypatch.setattr(settings, "storage_dir", str(test_storage))
    
    aberta_payload = _csv_content([_row_aberta("08.773.135/0001-00", "25224")])
    estrangeira_payload = _csv_content([_row_estrangeira("07.857.093/0001-14", "80187")])
    
    payloads = {
        f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/{ARQUIVO_CADASTRO_ABERTA}": aberta_payload,
        f"{settings.cvm_base_url}/CIA_ESTRANG/CAD/DADOS/{ARQUIVO_CADASTRO_ESTRANGEIRA}": estrangeira_payload,
    }
    
    def downloader(url: str) -> bytes:
        return payloads[url]

    # Create initial Execution
    execucao = ExecucaoSincronizacao(
        tipo_fonte="cadastro",
        ano=None,
        arquivo=f"{ARQUIVO_CADASTRO_ABERTA}+{ARQUIVO_CADASTRO_ESTRANGEIRA}",
        url="mock_url",
        status="em_execucao",
    )
    session.add(execucao)
    session.commit()
    session.refresh(execucao)

    # 1. Trigger Phase 1 (Pre-processing)
    res_phase1 = pre_processar_cadastro(
        session,
        execucao_id=execucao.id,
        downloader=downloader,
    )
    assert res_phase1["status"] == "aguardando_ingestao"
    session.refresh(execucao)
    assert execucao.status == "aguardando_ingestao"
    
    # Assert metadata directory exists and files are present on disk
    exec_dir = test_storage / str(execucao.id)
    assert (exec_dir / ARQUIVO_CADASTRO_ABERTA).exists()
    assert (exec_dir / ARQUIVO_CADASTRO_ESTRANGEIRA).exists()
    
    # 2. Trigger Phase 2 (Ingestion)
    res_phase2 = ingerir_cadastro(
        session,
        execucao_id=execucao.id,
        downloader=downloader,
    )
    assert res_phase2["status"] == "sucesso"
    session.refresh(execucao)
    assert execucao.status == "sucesso"
    assert execucao.total_linhas_lidas == 2
    
    # Assert database got the records
    assert session.query(Companhia).count() == 2
    
    # 3. Test self-healing fallback:
    # Clear DB table and reset exec status to "aguardando_ingestao"
    session.query(Companhia).delete()
    execucao.status = "aguardando_ingestao"
    session.commit()
    
    # Delete unzipped files from disk to force fallback
    if exec_dir.exists():
        shutil.rmtree(exec_dir)
    assert not exec_dir.exists()
    
    # Call ingestion again - it should self-heal (redownload via downloader) and succeed
    res_self_heal = ingerir_cadastro(
        session,
        execucao_id=execucao.id,
        downloader=downloader,
    )
    assert res_self_heal["status"] == "sucesso"
    session.refresh(execucao)
    assert execucao.status == "sucesso"
    assert session.query(Companhia).count() == 2

    # Clean up test storage dir
    if test_storage.exists():
        shutil.rmtree(test_storage)
    session.close()


def test_pre_processar_zip_reusa_members_bem_sucedidos_de_pai_falhado(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = _session()
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    monkeypatch.setattr("app.worker.tasks.SessionLocal", lambda: session)

    member_reused = "itr_cia_aberta_DRE_ind_2025.csv"
    member_retry = "itr_cia_aberta_DRA_ind_2025.csv"
    zip_name = "itr_cia_aberta_2025.zip"
    zip_url = f"{settings.cvm_base_url}/CIA_ABERTA/DOC/ITR/DADOS/{zip_name}"

    previous_parent = ExecucaoSincronizacao(
        tipo_fonte="itr",
        ano=2025,
        arquivo=zip_name,
        url=zip_url,
        status="falha",
        tipo_execucao="arquivo_zip",
        hash_arquivo="zip-antigo",
    )
    session.add(previous_parent)
    session.flush()

    previous_parent_run = create_run(
        session,
        tipo_fonte="itr",
        ano=2025,
        execucao_sincronizacao_id=previous_parent.id,
        status="falha",
        phase="complete",
    )
    previous_ingestion_file = register_file(
        session,
        ingestion_run=previous_parent_run,
        source_url=zip_url,
        source_filename=zip_name,
        content_sha256="zip-antigo",
        content_length_bytes=123,
        is_zip=True,
    )

    reused_payload = b"A;B\n1;2\n"
    retry_payload = b"A;B\n9;8\n"
    register_member(
        session,
        ingestion_file=previous_ingestion_file,
        member_name=member_reused,
        payload=reused_payload,
        member_sha256=hashlib.sha256(reused_payload).hexdigest(),
        member_size_bytes=len(reused_payload),
        header=["A", "B"],
        row_count=1,
        encoding="latin1",
        delimiter=";",
    )
    register_member(
        session,
        ingestion_file=previous_ingestion_file,
        member_name=member_retry,
        payload=retry_payload,
        member_sha256=hashlib.sha256(retry_payload).hexdigest(),
        member_size_bytes=len(retry_payload),
        header=["A", "B"],
        row_count=1,
        encoding="latin1",
        delimiter=";",
    )

    session.add_all(
        [
            ExecucaoSincronizacao(
                parent_execucao_id=previous_parent.id,
                tipo_execucao="arquivo_membro",
                tipo_fonte="itr",
                ano=2025,
                arquivo=member_reused,
                url=zip_url,
                status="sucesso",
                hash_arquivo=hashlib.sha256(reused_payload).hexdigest(),
            ),
            ExecucaoSincronizacao(
                parent_execucao_id=previous_parent.id,
                tipo_execucao="arquivo_membro",
                tipo_fonte="itr",
                ano=2025,
                arquivo=member_retry,
                url=zip_url,
                status="falha",
                hash_arquivo=hashlib.sha256(retry_payload).hexdigest(),
            ),
        ]
    )
    session.commit()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr(member_reused, reused_payload)
        archive.writestr(member_retry, retry_payload)
    zip_payload = zip_buffer.getvalue()
    zip_sha = hashlib.sha256(zip_payload).hexdigest()

    def _fake_download(url: str, destination: str, timeout: int = 300) -> str:
        assert url == zip_url
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(zip_payload)
        return zip_sha

    monkeypatch.setattr("app.services.ingestion.file_manager.download_file_to_disk", _fake_download)

    resultado = pre_processar_sincronizacao_zip(tipo_fonte="itr", ano=2025, task_id="task-rerun")

    assert resultado["status"] == "aguardando_ingestao"

    nova_execucao = session.get(ExecucaoSincronizacao, uuid.UUID(resultado["execucao_id"]))
    assert nova_execucao is not None
    assert nova_execucao.status == "aguardando_ingestao"

    children = session.query(ExecucaoSincronizacao).filter(
        ExecucaoSincronizacao.parent_execucao_id == nova_execucao.id
    ).all()
    child_by_file = {item.arquivo: item for item in children}

    assert child_by_file[member_reused].status == "skipped"
    assert child_by_file[member_retry].status == "aguardando_ingestao"

    reused_run = session.query(IngestionRun).filter(
        IngestionRun.execucao_sincronizacao_id == child_by_file[member_reused].id
    ).one()
    assert reused_run.quality_summary is not None
    assert reused_run.quality_summary["skip_reason"] == "member_sha256_reused"
    assert reused_run.quality_summary["reused_from_failed_parent"] is True

    new_parent_run = session.query(IngestionRun).filter(
        IngestionRun.execucao_sincronizacao_id == nova_execucao.id
    ).one()
    members = (
        session.query(IngestionFileMember)
        .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
        .filter(IngestionFile.ingestion_run_id == new_parent_run.id)
        .all()
    )
    assert {member.member_name for member in members} == {member_reused, member_retry}
