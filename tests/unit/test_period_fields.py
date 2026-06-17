from datetime import date
from app.schemas.comum import PeriodicModel
from app.schemas.financeiro import DocumentoFinanceiroResposta


def test_periodic_model_autopopulate() -> None:
    # Test with ITR (TRIMESTRAL)
    doc_itr = DocumentoFinanceiroResposta(
        id="bbf228f5-5627-4fc5-a490-318b8ba31e43",
        companhia_id=None,
        tipo_formulario="ITR",
        cnpj_companhia="08773135000100",
        codigo_cvm=25224,
        data_referencia=date(2024, 9, 30),
        versao=1,
        denominacao_companhia="BCO BRASIL S.A.",
        categoria_documento="ITR",
        id_documento=123,
        data_recebimento=date(2024, 10, 15),
        link_documento="http://exemplo",
        arquivo_origem="itr_cia_aberta_2024.csv",
        ano_origem=2024,
        linha_origem=1,
        criado_em="2026-05-30T14:30:00Z",
        sincronizado_em="2026-05-30T14:30:00Z",
        alterado_em="2026-05-30T14:30:00Z"
    )

    assert doc_itr.ano == 2024
    assert doc_itr.trimestre == 3
    assert doc_itr.periodo_tipo == "TRIMESTRAL"
    assert doc_itr.periodo_label == "2024-3T"

    # Test with DFP (ANUAL)
    doc_dfp = DocumentoFinanceiroResposta(
        id="bbf228f5-5627-4fc5-a490-318b8ba31e43",
        companhia_id=None,
        tipo_formulario="DFP",
        cnpj_companhia="08773135000100",
        codigo_cvm=25224,
        data_referencia=date(2024, 12, 31),
        versao=1,
        denominacao_companhia="BCO BRASIL S.A.",
        categoria_documento="DFP",
        id_documento=123,
        data_recebimento=date(2025, 3, 20),
        link_documento="http://exemplo",
        arquivo_origem="dfp_cia_aberta_2024.csv",
        ano_origem=2024,
        linha_origem=1,
        criado_em="2026-05-30T14:30:00Z",
        sincronizado_em="2026-05-30T14:30:00Z",
        alterado_em="2026-05-30T14:30:00Z"
    )

    assert doc_dfp.ano == 2024
    assert doc_dfp.trimestre == 4
    assert doc_dfp.periodo_tipo == "ANUAL"
    assert doc_dfp.periodo_label == "2024"
