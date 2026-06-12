import uuid
import shutil
import hashlib
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.cadastro import (
    pre_processar_cadastro,
    ingerir_cadastro,
    ARQUIVO_CADASTRO_ABERTA,
    ARQUIVO_CADASTRO_ESTRANGEIRA,
)

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

def test_two_phase_flow_and_self_healing(monkeypatch) -> None:
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
