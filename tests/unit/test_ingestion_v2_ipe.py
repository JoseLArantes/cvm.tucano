import io
import zipfile
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.ingestion import IngestionRow, QuarantineItem
from app.models.ipe import IpeDocumento
from app.services.ingestion.ipe import sincronizar_ipe


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
        hash_origem="companhia-ipe",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _build_zip(
    *,
    assunto: str = "Assunto X",
    protocolo: str = "123456",
    extra_column: bool = True,
    missing_categoria_header: bool = False,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        header = [
            "CNPJ_Companhia",
            "Nome_Companhia",
            "Codigo_CVM",
            "Data_Referencia",
            "Categoria",
            "Tipo",
            "Especie",
            "Assunto",
            "Data_Entrega",
            "Tipo_Apresentacao",
            "Protocolo_Entrega",
            "Versao",
            "Link_Download",
        ]
        if missing_categoria_header:
            header.remove("Categoria")
        if extra_column:
            header.append("Coluna_Extra")
        valores = [
            "00.000.000/0001-91",
            "Banco do Brasil S.A.",
            "1023",
            "2025-01-01",
            "Categoria X",
            "Tipo X",
            "Especie X",
            assunto,
            "2025-01-15",
            "Apresentacao",
            protocolo,
            "1",
            "http://ipe",
        ]
        if extra_column:
            valores.append("extra")
        if missing_categoria_header:
            valores.pop(4)
        zinfo = zipfile.ZipInfo("ipe_cia_aberta_2025.csv")
        zinfo.date_time = (2026, 6, 10, 12, 0, 0)
        zip_file.writestr(
            zinfo,
            (";".join(header) + "\n" + ";".join(valores) + "\n").encode("latin1"),
        )
    return buffer.getvalue()


def test_sincronizar_ipe_idempotency_and_quarantine(db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()

    resultado1 = sincronizar_ipe(db_session, 2025, downloader=lambda _: _build_zip())
    assert resultado1["status"] == "sucesso"
    documento = db_session.scalar(select(IpeDocumento))
    assert documento is not None
    alterado_inicial = documento.alterado_em

    resultado2 = sincronizar_ipe(db_session, 2025, downloader=lambda _: _build_zip())
    assert resultado2["status"] == "skipped"
    documento_igual = db_session.scalar(select(IpeDocumento))
    assert documento_igual is not None
    assert documento_igual.alterado_em == alterado_inicial

    resultado2_forcado = sincronizar_ipe(db_session, 2025, force_reimport=True, downloader=lambda _: _build_zip())
    assert resultado2_forcado["status"] == "sucesso"

    resultado3 = sincronizar_ipe(
        db_session,
        2025,
        downloader=lambda _: _build_zip(assunto="Assunto Alterado", protocolo="123456"),
    )
    assert resultado3["status"] == "sucesso"
    documento_alterado = db_session.scalar(select(IpeDocumento))
    assert documento_alterado is not None
    assert documento_alterado.assunto == "Assunto Alterado"
    assert documento_alterado.alterado_em != alterado_inicial

    staged = list(db_session.execute(select(IngestionRow).where(IngestionRow.row_kind == "ipe_documento")).scalars())
    assert staged
    assert all(item.promoted_entity == "ipe_documentos" for item in staged)

    resultado_quarentena = sincronizar_ipe(
        db_session,
        2025,
        downloader=lambda _: _build_zip(missing_categoria_header=True),
    )
    assert resultado_quarentena["status"] == "sucesso"
    assert db_session.scalar(select(QuarantineItem).where(QuarantineItem.row_kind == "ipe_documento")) is not None
