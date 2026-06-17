from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo
from app.services.sincronizacao_cadastro import sincronizar_cadastro_companhias


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def _csv_cadastro(denominacao_social: str) -> bytes:
    cabecalho = (
        "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;DT_REG;DT_CONST;DT_CANCEL;MOTIVO_CANCEL;SIT;"
        "DT_INI_SIT;CD_CVM;SETOR_ATIV;TP_MERC;CATEG_REG;DT_INI_CATEG;SIT_EMISSOR;"
        "DT_INI_SIT_EMISSOR;CONTROLE_ACIONARIO;TP_ENDER;LOGRADOURO;COMPL;BAIRRO;MUN;UF;"
        "PAIS;CEP;DDD_TEL;TEL;DDD_FAX;FAX;EMAIL;TP_RESP;RESP;DT_INI_RESP;LOGRADOURO_RESP;"
        "COMPL_RESP;BAIRRO_RESP;MUN_RESP;UF_RESP;PAIS_RESP;CEP_RESP;DDD_TEL_RESP;TEL_RESP;"
        "DDD_FAX_RESP;FAX_RESP;EMAIL_RESP;CNPJ_AUDITOR;AUDITOR\n"
    )
    linha = (
        f"08.773.135/0001-00;{denominacao_social};COMP;2020-10-29;2007-03-23;;;ATIVA;2020-10-29;"
        "25224;Energia Elétrica;;Categoria A;2020-10-29;ATIVO;2020-10-29;PRIVADO;SEDE;Rua A;;Centro;"
        "SÃO PAULO;SP;BRASIL;01001000;11;11111111;;;;DIRETOR;Fulano;2020-10-29;Rua B;;Centro;"
        "SÃO PAULO;SP;BRASIL;01001000;11;11111111;;;fulano@email.com;10.830.108/0001-65;Auditoria X\n"
    )
    return (cabecalho + linha).encode("latin1")


def test_sincronizacao_idempotencia_e_historico(db_session: Session, monkeypatch: Any) -> None:
    respostas = [
        FakeResponse(_csv_cadastro("EMPRESA SA")),
        FakeResponse(_csv_cadastro("EMPRESA SA")),
        FakeResponse(_csv_cadastro(" EMPRESA   SA ")),
        FakeResponse(_csv_cadastro("EMPRESA S.A.")),
    ]

    def fake_get(*_: Any, **__: Any) -> FakeResponse:
        return respostas.pop(0)

    monkeypatch.setattr("app.services.sincronizacao_cadastro.httpx.get", fake_get)

    resultado_1 = sincronizar_cadastro_companhias(db_session)
    assert resultado_1["status"] == "sucesso"
    assert resultado_1["total_inseridos"] == 1

    companhia = db_session.scalar(select(Companhia).where(Companhia.cnpj_companhia == "08773135000100"))
    assert companhia is not None
    primeiro_alterado = companhia.alterado_em
    primeiro_sincronizado = companhia.sincronizado_em

    resultado_2 = sincronizar_cadastro_companhias(db_session)
    assert resultado_2["status"] == "skipped"

    resultado_3 = sincronizar_cadastro_companhias(db_session)
    assert resultado_3["status"] == "sucesso"
    assert resultado_3["total_inalterados"] == 1

    db_session.refresh(companhia)
    assert companhia.alterado_em == primeiro_alterado
    assert companhia.sincronizado_em > primeiro_sincronizado

    sincronizado_sem_alteracao = companhia.sincronizado_em
    resultado_4 = sincronizar_cadastro_companhias(db_session)
    assert resultado_4["status"] == "sucesso"
    assert resultado_4["total_atualizados"] == 1

    db_session.refresh(companhia)
    assert companhia.denominacao_social == "EMPRESA S.A."
    assert companhia.alterado_em > primeiro_alterado
    assert companhia.sincronizado_em > sincronizado_sem_alteracao

    historicos = (
        db_session.execute(select(HistoricoAlteracaoCampo).where(HistoricoAlteracaoCampo.entidade == "companhias"))
        .scalars()
        .all()
    )
    assert any(item.campo == "denominacao_social" for item in historicos)

    execucoes = db_session.execute(select(ExecucaoSincronizacao)).scalars().all()
    assert len(execucoes) == 4
    assert any(item.status == "skipped" for item in execucoes)
    assert any(item.status == "sucesso" for item in execucoes)
    assert all(isinstance(item.iniciada_em, datetime) for item in execucoes)
