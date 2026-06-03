from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.models.sincronizacao import ExecucaoSincronizacao
from app.worker.bootstrap import agendar_sincronizacoes_iniciais
from app.worker.celery_app import construir_beat_schedule


def test_agendar_sincronizacoes_iniciais_agenda_fontes_pendentes(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "anos_iniciais_dfp", "2024")
    monkeypatch.setattr(settings, "anos_iniciais_itr", "2025")
    monkeypatch.setattr(settings, "anos_iniciais_fre", "2026")
    monkeypatch.setattr("app.worker.bootstrap.SessionLocal", lambda: db_session)

    chamadas: list[tuple[str, int | None]] = []

    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_cadastro_companhias_task.delay",
        lambda: chamadas.append(("cadastro", None)) or SimpleNamespace(id="cadastro"),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_dfp_task.delay",
        lambda ano: chamadas.append(("dfp", ano)) or SimpleNamespace(id=f"dfp-{ano}"),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_itr_task.delay",
        lambda ano: chamadas.append(("itr", ano)) or SimpleNamespace(id=f"itr-{ano}"),
    )
    agendadas = agendar_sincronizacoes_iniciais()

    assert agendadas == chamadas
    assert agendadas == [
        ("cadastro", None),
        ("dfp", 2024),
        ("itr", 2025),
    ]


def test_agendar_sincronizacoes_iniciais_pula_execucoes_validas_existentes(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "anos_iniciais_dfp", "2024")
    monkeypatch.setattr(settings, "anos_iniciais_itr", "2025")
    monkeypatch.setattr(settings, "anos_iniciais_fre", "2026")
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
        ]
    )
    db_session.commit()

    chamadas: list[tuple[str, int | None]] = []
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_cadastro_companhias_task.delay",
        lambda: chamadas.append(("cadastro", None)) or SimpleNamespace(id="cadastro"),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_dfp_task.delay",
        lambda ano: chamadas.append(("dfp", ano)) or SimpleNamespace(id=f"dfp-{ano}"),
    )
    monkeypatch.setattr(
        "app.worker.bootstrap.sincronizar_itr_task.delay",
        lambda ano: chamadas.append(("itr", ano)) or SimpleNamespace(id=f"itr-{ano}"),
    )
    agendadas = agendar_sincronizacoes_iniciais()

    assert agendadas == []
    assert chamadas == []


def test_construir_beat_schedule_inclui_fontes_configuradas(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "anos_iniciais_dfp", "2024,2025")
    monkeypatch.setattr(settings, "anos_iniciais_itr", "2026")
    monkeypatch.setattr(settings, "anos_iniciais_fre", "")

    schedule = construir_beat_schedule()

    assert "sincronizar-cadastro-diario" in schedule
    assert schedule["sincronizar-dfp-2024-diario"]["args"] == (2024,)
    assert schedule["sincronizar-dfp-2025-diario"]["args"] == (2025,)
    assert schedule["sincronizar-itr-2026-diario"]["args"] == (2026,)
    assert all(not chave.startswith("sincronizar-fre-") for chave in schedule)
