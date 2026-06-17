from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.sincronizacao import ExecucaoSincronizacao
from app.worker.bootstrap import agendar_sincronizacoes_iniciais
from app.worker.celery_app import construir_beat_schedule


def test_agendar_sincronizacoes_iniciais_agenda_fontes_pendentes(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "anos_iniciais_dfp", "2024")
    monkeypatch.setattr(settings, "anos_iniciais_itr", "2025")
    monkeypatch.setattr(settings, "anos_iniciais_fre", "2026")
    monkeypatch.setattr(settings, "anos_iniciais_fca", "2027")
    monkeypatch.setattr(settings, "anos_iniciais_ipe", "2028")
    monkeypatch.setattr(settings, "anos_iniciais_vlmo", "2029")
    monkeypatch.setattr(settings, "anos_iniciais_cgvn", "2030")
    monkeypatch.setattr("app.worker.bootstrap.SessionLocal", lambda: db_session)

    chamadas: list[tuple[str, int | None]] = []

    def registrar_chamada(tipo_fonte: str, ano: int | None) -> SimpleNamespace:
        chamadas.append((tipo_fonte, ano))
        suffix = "cadastro" if ano is None else f"{tipo_fonte}-{ano}"
        return SimpleNamespace(id=suffix)

    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_cadastro_companhias_task.delay",
        lambda: registrar_chamada("cadastro", None),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_dfp_task.delay",
        lambda ano: registrar_chamada("dfp", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_itr_task.delay",
        lambda ano: registrar_chamada("itr", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_fre_task.delay",
        lambda ano: registrar_chamada("fre", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_fca_task.delay",
        lambda ano: registrar_chamada("fca", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_ipe_task.delay",
        lambda ano: registrar_chamada("ipe", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_vlmo_task.delay",
        lambda ano: registrar_chamada("vlmo", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_cgvn_task.delay",
        lambda ano: registrar_chamada("cgvn", ano),
    )
    agendadas = agendar_sincronizacoes_iniciais()

    assert agendadas == chamadas
    assert agendadas == [
        ("cadastro", None),
        ("dfp", 2024),
        ("itr", 2025),
        ("fre", 2026),
        ("fca", 2027),
        ("ipe", 2028),
        ("vlmo", 2029),
        ("cgvn", 2030),
    ]


def test_agendar_sincronizacoes_iniciais_pula_execucoes_validas_existentes(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "anos_iniciais_dfp", "2024")
    monkeypatch.setattr(settings, "anos_iniciais_itr", "2025")
    monkeypatch.setattr(settings, "anos_iniciais_fre", "2026")
    monkeypatch.setattr(settings, "anos_iniciais_fca", "2027")
    monkeypatch.setattr(settings, "anos_iniciais_ipe", "2028")
    monkeypatch.setattr(settings, "anos_iniciais_vlmo", "2029")
    monkeypatch.setattr(settings, "anos_iniciais_cgvn", "2030")
    monkeypatch.setattr("app.worker.bootstrap.SessionLocal", lambda: db_session)

    db_session.add_all(
        [
            ExecucaoSincronizacao(
                tipo_fonte="cadastro",
                ano=None,
                arquivo="cad_cia_aberta.csv",
                url="http://exemplo/cad",
                status="sucesso",
            ),
            ExecucaoSincronizacao(
                tipo_fonte="dfp",
                ano=2024,
                arquivo="dfp_cia_aberta_2024.zip",
                url="http://exemplo/dfp",
                status="sem_alteracao",
            ),
            ExecucaoSincronizacao(
                tipo_fonte="itr",
                ano=2025,
                arquivo="itr_cia_aberta_2025.zip",
                url="http://exemplo/itr",
                status="em_execucao",
            ),
            ExecucaoSincronizacao(
                tipo_fonte="fre",
                ano=2026,
                arquivo="fre_cia_aberta_2026.zip",
                url="http://exemplo/fre",
                status="sucesso",
            ),
            ExecucaoSincronizacao(
                tipo_fonte="fca",
                ano=2027,
                arquivo="fca_cia_aberta_2027.zip",
                url="http://exemplo/fca",
                status="sucesso",
            ),
            ExecucaoSincronizacao(
                tipo_fonte="ipe",
                ano=2028,
                arquivo="ipe_cia_aberta_2028.zip",
                url="http://exemplo/ipe",
                status="sucesso",
            ),
            ExecucaoSincronizacao(
                tipo_fonte="vlmo",
                ano=2029,
                arquivo="vlmo_cia_aberta_2029.zip",
                url="http://exemplo/vlmo",
                status="sucesso",
            ),
            ExecucaoSincronizacao(
                tipo_fonte="cgvn",
                ano=2030,
                arquivo="cgvn_cia_aberta_2030.zip",
                url="http://exemplo/cgvn",
                status="sucesso",
            ),
        ]
    )
    db_session.commit()

    chamadas: list[tuple[str, int | None]] = []

    def registrar_chamada(tipo_fonte: str, ano: int | None) -> SimpleNamespace:
        chamadas.append((tipo_fonte, ano))
        suffix = "cadastro" if ano is None else f"{tipo_fonte}-{ano}"
        return SimpleNamespace(id=suffix)

    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_cadastro_companhias_task.delay",
        lambda: registrar_chamada("cadastro", None),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_dfp_task.delay",
        lambda ano: registrar_chamada("dfp", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_itr_task.delay",
        lambda ano: registrar_chamada("itr", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_fre_task.delay",
        lambda ano: registrar_chamada("fre", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_fca_task.delay",
        lambda ano: registrar_chamada("fca", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_ipe_task.delay",
        lambda ano: registrar_chamada("ipe", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_vlmo_task.delay",
        lambda ano: registrar_chamada("vlmo", ano),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_cgvn_task.delay",
        lambda ano: registrar_chamada("cgvn", ano),
    )
    agendadas = agendar_sincronizacoes_iniciais()

    assert agendadas == []
    assert chamadas == []


def test_construir_beat_schedule_inclui_fontes_configuradas(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "anos_iniciais_dfp", "2024,2025")
    monkeypatch.setattr(settings, "anos_iniciais_itr", "2026")
    monkeypatch.setattr(settings, "anos_iniciais_fre", "2027")
    monkeypatch.setattr(settings, "anos_iniciais_fca", "2028")
    monkeypatch.setattr(settings, "anos_iniciais_ipe", "2029")
    monkeypatch.setattr(settings, "anos_iniciais_vlmo", "2030")
    monkeypatch.setattr(settings, "anos_iniciais_cgvn", "2031")

    schedule = construir_beat_schedule()

    assert "sincronizar-cadastro-diario" in schedule
    assert schedule["sincronizar-dfp-2024-diario"]["args"] == (2024,)
    assert schedule["sincronizar-dfp-2025-diario"]["args"] == (2025,)
    assert schedule["sincronizar-itr-2026-diario"]["args"] == (2026,)
    assert schedule["sincronizar-fre-2027-diario"]["args"] == (2027,)
    assert schedule["sincronizar-fca-2028-diario"]["args"] == (2028,)
    assert schedule["sincronizar-ipe-2029-diario"]["args"] == (2029,)
    assert schedule["sincronizar-vlmo-2030-diario"]["args"] == (2030,)
    assert schedule["sincronizar-cgvn-2031-diario"]["args"] == (2031,)
