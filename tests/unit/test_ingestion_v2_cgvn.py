import io
import zipfile
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cgvn import CgvnDocumento, CgvnPratica
from app.models.companhia import Companhia
from app.models.ingestion import IngestionRow, QuarantineItem
from app.services.ingestion.cgvn import sincronizar_cgvn


def _companhia() -> Companhia:
    agora = datetime.now(UTC)
    return Companhia(
        cnpj_companhia="00000000000191",
        codigo_cvm=1023,
        denominacao_social="Banco do Brasil",
        denominacao_comercial="Banco do Brasil",
        situacao_registro="ATIVA",
        data_registro=date(2020, 1, 1),
        data_constituicao=date(1808, 10, 12),
        data_inicio_situacao=date(2020, 1, 1),
        setor_atividade="Bancos",
        tipo_mercado="Categoria A",
        categoria_registro="Categoria A",
        data_inicio_categoria=date(2020, 1, 1),
        situacao_emissor="ATIVO",
        data_inicio_situacao_emissor=date(2020, 1, 1),
        controle_acionario="ESTATAL",
        endereco={"municipio": "Brasilia"},
        responsavel={"nome_responsavel": "Fulano"},
        auditor="KPMG",
        cnpj_auditor="57755217001281",
        arquivo_origem="cad_cia_aberta.csv",
        ano_origem=None,
        linha_origem=2,
        hash_origem="companhia-cgvn",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _build_zip(
    *,
    pratica_adotada: str = "Sim",
    extra_column: bool = True,
    missing_versao_header: bool = False,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        header_documento = [
            "CNPJ_Companhia",
            "Nome_Empresarial",
            "Codigo_CVM",
            "Data_Referencia",
            "Categoria",
            "Data_Entrega",
            "Data_Inicio_Exercicio_Social",
            "Data_Fim_Exercicio_Social",
            "ID_Documento",
            "Versao",
            "Link_Download",
            "Motivo_Reapresentacao",
        ]
        if missing_versao_header:
            header_documento.remove("Versao")
        if extra_column:
            header_documento.append("Coluna_Extra")
        valores_documento = [
            "00.000.000/0001-91",
            "Banco do Brasil S.A.",
            "1023",
            "2025-01-01",
            "Informe de Governança",
            "2025-01-15",
            "2025-01-01",
            "2025-12-31",
            "123456",
            "1",
            "http://cgvn/documento",
            "",
        ]
        if missing_versao_header:
            valores_documento.pop(9)
        if extra_column:
            valores_documento.append("extra")
        zip_file.writestr(
            "cgvn_cia_aberta_2025.csv",
            (";".join(header_documento) + "\n" + ";".join(valores_documento) + "\n").encode("latin1"),
        )

        header_consolidado = [
            "CNPJ_Companhia",
            "Nome_Empresarial",
            "Data_Referencia",
            "ID_Documento",
            "Versao",
            "ID_Item",
            "Pratica_Recomendada",
            "Pratica_Adotada",
            "Capitulo",
            "Principio",
            "Explicacao",
        ]
        if extra_column:
            header_consolidado.append("Coluna_Extra")
        valores_consolidado = [
            "00.000.000/0001-91",
            "Banco do Brasil S.A.",
            "2025-01-01",
            "123456",
            "1",
            "1.1.1",
            "Recomendacao 1.1.1",
            pratica_adotada,
            "Capitulo 1",
            "Principio 1",
            "Adotado integralmente.",
        ]
        if extra_column:
            valores_consolidado.append("extra")
        zip_file.writestr(
            "cgvn_cia_aberta_praticas_2025.csv",
            (";".join(header_consolidado) + "\n" + ";".join(valores_consolidado) + "\n").encode("latin1"),
        )
    return buffer.getvalue()


def test_sincronizar_cgvn_idempotency_and_quarantine(db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()

    payload_igual = _build_zip()
    resultado1 = sincronizar_cgvn(db_session, 2025, downloader=lambda _: payload_igual)
    assert resultado1["status"] == "sucesso"

    documento = db_session.scalar(select(CgvnDocumento))
    pratica = db_session.scalar(select(CgvnPratica))
    assert documento is not None
    assert pratica is not None
    assert documento.versao == 1
    assert pratica.pratica_adotada == "Sim"
    alterado_documento = documento.alterado_em
    alterado_pratica = pratica.alterado_em

    resultado2 = sincronizar_cgvn(db_session, 2025, downloader=lambda _: payload_igual)
    assert resultado2["status"] == "sem_alteracao"
    documento_igual = db_session.scalar(select(CgvnDocumento))
    pratica_igual = db_session.scalar(select(CgvnPratica))
    assert documento_igual is not None and documento_igual.alterado_em == alterado_documento
    assert pratica_igual is not None and pratica_igual.alterado_em == alterado_pratica

    resultado2_forcado = sincronizar_cgvn(db_session, 2025, force_reimport=True, downloader=lambda _: payload_igual)
    assert resultado2_forcado["status"] == "sucesso"

    resultado3 = sincronizar_cgvn(db_session, 2025, downloader=lambda _: _build_zip(pratica_adotada="Não"))
    assert resultado3["status"] == "sucesso"
    pratica_alterada = db_session.scalar(select(CgvnPratica))
    assert pratica_alterada is not None
    assert pratica_alterada.pratica_adotada == "Não"
    assert pratica_alterada.alterado_em != alterado_pratica

    staged = list(db_session.execute(select(IngestionRow).where(IngestionRow.row_kind.like("cgvn_%"))).scalars())
    assert staged == []

    resultado_quarentena = sincronizar_cgvn(
        db_session,
        2025,
        downloader=lambda _: _build_zip(missing_versao_header=True),
    )
    assert resultado_quarentena["status"] == "sucesso"
    assert db_session.scalar(select(QuarantineItem).where(QuarantineItem.row_kind == "cgvn_documento")) is not None
