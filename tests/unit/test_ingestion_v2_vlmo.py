import io
import zipfile
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.ingestion import IngestionRow, QuarantineItem
from app.models.vlmo import VlmoConsolidado, VlmoDocumento
from app.services.ingestion.vlmo import sincronizar_vlmo


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
        hash_origem="companhia-vlmo",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _build_zip(
    *,
    tipo_operacao: str = "Compra",
    extra_column: bool = True,
    missing_categoria_header: bool = False,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        header_documento = [
            "CNPJ_Companhia",
            "Nome_Companhia",
            "Codigo_CVM",
            "Data_Referencia",
            "Categoria",
            "Tipo",
            "Data_Entrega",
            "Tipo_Apresentacao",
            "Motivo_Reapresentacao",
            "Protocolo_Entrega",
            "Versao",
            "Link_Download",
        ]
        if missing_categoria_header:
            header_documento.remove("Categoria")
        if extra_column:
            header_documento.append("Coluna_Extra")
        valores_documento = [
            "00.000.000/0001-91",
            "Banco do Brasil S.A.",
            "1023",
            "2025-01-01",
            "Negociacao Administradores",
            "Consolidado",
            "2025-01-15",
            "Original",
            "",
            "123456",
            "1",
            "http://vlmo/documento",
        ]
        if missing_categoria_header:
            valores_documento.pop(4)
        if extra_column:
            valores_documento.append("extra")
        zip_file.writestr(
            "vlmo_cia_aberta_2025.csv",
            (";".join(header_documento) + "\n" + ";".join(valores_documento) + "\n").encode("latin1"),
        )

        header_consolidado = [
            "CNPJ_Companhia",
            "Nome_Companhia",
            "Data_Referencia",
            "Versao",
            "Tipo_Empresa",
            "Empresa",
            "Tipo_Cargo",
            "Tipo_Movimentacao",
            "Descricao_Movimentacao",
            "Tipo_Operacao",
            "Tipo_Ativo",
            "Caracteristica_Valor_Mobiliario",
            "Intermediario",
            "Data_Movimentacao",
            "Quantidade",
            "Preco_Unitario",
            "Volume",
        ]
        if extra_column:
            header_consolidado.append("Coluna_Extra")
        valores_consolidado = [
            "00.000.000/0001-91",
            "Banco do Brasil S.A.",
            "2025-01-01",
            "1",
            "Pessoa Vinculada",
            "Controlador",
            "Diretor",
            "Negociacao",
            "Compra em mercado",
            tipo_operacao,
            "Acao Ordinaria",
            "ON",
            "Corretora X",
            "2025-01-10",
            "100",
            "10,50",
            "1050,00",
        ]
        if extra_column:
            valores_consolidado.append("extra")
        zip_file.writestr(
            "vlmo_cia_aberta_con_2025.csv",
            (";".join(header_consolidado) + "\n" + ";".join(valores_consolidado) + "\n").encode("latin1"),
        )
    return buffer.getvalue()


def test_sincronizar_vlmo_idempotency_and_quarantine(db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()

    resultado1 = sincronizar_vlmo(db_session, 2025, downloader=lambda _: _build_zip())
    assert resultado1["status"] == "sucesso"

    documento = db_session.scalar(select(VlmoDocumento))
    consolidado = db_session.scalar(select(VlmoConsolidado))
    assert documento is not None
    assert consolidado is not None
    alterado_documento = documento.alterado_em
    alterado_consolidado = consolidado.alterado_em

    resultado2 = sincronizar_vlmo(db_session, 2025, downloader=lambda _: _build_zip())
    assert resultado2["status"] == "skipped"
    documento_igual = db_session.scalar(select(VlmoDocumento))
    consolidado_igual = db_session.scalar(select(VlmoConsolidado))
    assert documento_igual is not None and documento_igual.alterado_em == alterado_documento
    assert consolidado_igual is not None and consolidado_igual.alterado_em == alterado_consolidado

    resultado2_forcado = sincronizar_vlmo(db_session, 2025, force_reimport=True, downloader=lambda _: _build_zip())
    assert resultado2_forcado["status"] == "sucesso"

    resultado3 = sincronizar_vlmo(db_session, 2025, downloader=lambda _: _build_zip(tipo_operacao="Venda"))
    assert resultado3["status"] == "sucesso"
    consolidado_alterado = db_session.scalar(select(VlmoConsolidado))
    assert consolidado_alterado is not None
    assert consolidado_alterado.tipo_operacao == "Venda"
    assert consolidado_alterado.alterado_em != alterado_consolidado

    staged = list(db_session.execute(select(IngestionRow).where(IngestionRow.row_kind.like("vlmo_%"))).scalars())
    assert staged
    assert {item.promoted_entity for item in staged} == {"vlmo_documentos", "vlmo_consolidado"}

    resultado_quarentena = sincronizar_vlmo(
        db_session,
        2025,
        downloader=lambda _: _build_zip(missing_categoria_header=True),
    )
    assert resultado_quarentena["status"] == "sucesso"
    assert db_session.scalar(select(QuarantineItem).where(QuarantineItem.row_kind == "vlmo_documento")) is not None
