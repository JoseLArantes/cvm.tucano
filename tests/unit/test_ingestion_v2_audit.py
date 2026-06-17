import os
import io
import zipfile

import pytest

from app.services.ingestion.audit import (
    analyze_cadastro_duplicates,
    analyze_missing_companies,
    build_audit_report,
    build_dataset_discovery_audit,
    build_source_url,
    render_console_summary,
)


def _cadastro_row(
    *,
    cnpj: str,
    codigo_cvm: str,
    tipo_mercado: str,
    situacao: str = "ATIVO",
    denominacao: str = "EMPRESA SA",
    categoria_registro: str = "Categoria A",
) -> dict[str, str]:
    return {
        "CNPJ_CIA": cnpj,
        "DENOM_SOCIAL": denominacao,
        "DENOM_COMERC": denominacao,
        "DT_REG": "2020-01-01",
        "DT_CONST": "2000-01-01",
        "DT_CANCEL": "",
        "MOTIVO_CANCEL": "",
        "SIT": situacao,
        "DT_INI_SIT": "2020-01-01",
        "CD_CVM": codigo_cvm,
        "SETOR_ATIV": "Energia",
        "TP_MERC": tipo_mercado,
        "CATEG_REG": categoria_registro,
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


def _foreign_row(*, cnpj: str, codigo_cvm: str, denominacao: str) -> dict[str, str]:
    return {
        "CNPJ": cnpj,
        "DENOM_SOCIAL": denominacao,
        "DENOM_COMERC": denominacao,
        "PAIS_ORIGEM": "EXTERIOR",
        "DT_REG": "2020-01-01",
        "DT_CONST": "2000-01-01",
        "DT_CANCEL": "",
        "MOTIVO_CANCEL": "",
        "SIT": "ATIVO",
        "DT_INI_SIT": "2020-01-01",
        "CD_CVM": codigo_cvm,
        "SETOR_ATIV": "Tecnologia",
    }


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name, content in files.items():
            archive.writestr(file_name, content.encode("latin1"))
    return buffer.getvalue()


def test_analyze_cadastro_duplicates_categorizes_expected_patterns() -> None:
    rows = [
        _cadastro_row(cnpj="12.528.708/0001-07", codigo_cvm="25283", tipo_mercado="BALCAO ORGANIZADO"),
        _cadastro_row(cnpj="12.528.708/0001-07", codigo_cvm="25283", tipo_mercado="BOLSA"),
        _cadastro_row(cnpj="61.186.680/0001-74", codigo_cvm="1716", tipo_mercado="", situacao="CANCELADA"),
        _cadastro_row(
            cnpj="61.186.680/0001-74",
            codigo_cvm="24600",
            tipo_mercado="BOLSA",
            denominacao="BANCO BMG S/A",
        ),
        _cadastro_row(cnpj="11.111.111/0001-11", codigo_cvm="11111", tipo_mercado="BOLSA"),
        _cadastro_row(
            cnpj="11.111.111/0001-11",
            codigo_cvm="11111",
            tipo_mercado="BOLSA",
            categoria_registro="Categoria B",
        ),
    ]

    report = analyze_cadastro_duplicates(rows)

    assert report["row_count"] == 6
    assert report["duplicate_bucket_count"] == 3
    assert report["duplicate_extra_rows"] == 3
    assert report["categories"] == {
        "different_cd": 1,
        "same_cd_only_tipo_mercado": 1,
        "same_cd_other_diff": 1,
    }


def test_analyze_missing_companies_uses_open_plus_foreign_identity() -> None:
    open_rows = [_cadastro_row(cnpj="08.773.135/0001-00", codigo_cvm="25224", tipo_mercado="BOLSA")]
    foreign_rows = [_foreign_row(cnpj="07.857.093/0001-14", codigo_cvm="80187", denominacao="AURA MINERALS INC.")]
    payload = _zip_bytes(
        {
            "dfp_cia_aberta_2021.csv": (
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                "08.773.135/0001-00;2021-12-31;1;EMPRESA SA;25224;DFP;1;2022-01-01;http://doc\n"
                "07.857.093/0001-14;2021-12-31;1;AURA MINERALS INC.;80187;DFP;2;2022-01-01;http://doc\n"
                "33.066.408/0001-15;2021-12-31;1;EMPRESA FINANCEIRA;3;DFP;3;2022-01-01;http://doc\n"
            )
        }
    )

    report = analyze_missing_companies(
        "dfp",
        payload,
        open_company_rows=open_rows,
        foreign_company_rows=foreign_rows,
    )

    assert report["row_count"] == 3
    assert report["missing_open_only"] == 2
    assert report["missing_open_plus_foreign"] == 1
    assert report["top_missing_names_open_only"][0][0] in {"AURA MINERALS INC.", "EMPRESA FINANCEIRA"}
    assert report["top_missing_names_open_plus_foreign"] == [("EMPRESA FINANCEIRA", 1)]


def test_build_audit_report_with_fake_downloader() -> None:
    cadastro_aberta = (
        "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;DT_REG;DT_CONST;DT_CANCEL;MOTIVO_CANCEL;SIT;DT_INI_SIT;CD_CVM;"
        "SETOR_ATIV;TP_MERC;CATEG_REG;DT_INI_CATEG;SIT_EMISSOR;DT_INI_SIT_EMISSOR;CONTROLE_ACIONARIO;TP_ENDER;"
        "LOGRADOURO;COMPL;BAIRRO;MUN;UF;PAIS;CEP;DDD_TEL;TEL;DDD_FAX;FAX;EMAIL;TP_RESP;RESP;DT_INI_RESP;"
        "LOGRADOURO_RESP;COMPL_RESP;BAIRRO_RESP;MUN_RESP;UF_RESP;PAIS_RESP;CEP_RESP;DDD_TEL_RESP;TEL_RESP;"
        "DDD_FAX_RESP;FAX_RESP;EMAIL_RESP;CNPJ_AUDITOR;AUDITOR\n"
        "08.773.135/0001-00;EMPRESA SA;EMPRESA SA;2020-01-01;2000-01-01;;;ATIVO;2020-01-01;25224;Energia;BOLSA;"
        "Categoria A;2020-01-01;FASE OPERACIONAL;2020-01-01;PRIVADO;SEDE;Rua A;;Centro;SAO PAULO;SP;BRASIL;"
        "01001000;11;11111111;;;;DIRETOR;Fulano;2020-01-01;Rua B;;Centro;SAO PAULO;SP;BRASIL;01001000;11;"
        "11111111;;;;;\n"
    ).encode("latin1")
    cadastro_estrangeira = (
        "CNPJ;DENOM_SOCIAL;DENOM_COMERC;PAIS_ORIGEM;DT_REG;DT_CONST;DT_CANCEL;MOTIVO_CANCEL;SIT;DT_INI_SIT;"
        "CD_CVM;SETOR_ATIV\n"
        "07.857.093/0001-14;AURA MINERALS INC.;AURA MINERALS INC.;EXTERIOR;2020-01-01;2000-01-01;;;ATIVO;"
        "2020-01-01;80187;Mineracao\n"
    ).encode("latin1")
    dfp_payload = _zip_bytes(
        {
            "dfp_cia_aberta_2021.csv": (
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                "07.857.093/0001-14;2021-12-31;1;AURA MINERALS INC.;80187;DFP;1;2022-01-01;http://doc\n"
            )
        }
    )
    payloads = {
        build_source_url("CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"): cadastro_aberta,
        build_source_url("CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv"): cadastro_estrangeira,
        build_source_url("CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip", year=2021): dfp_payload,
    }

    def fake_downloader(url: str) -> bytes:
        return payloads[url]

    report = build_audit_report(year=2021, document_sources=("dfp",), downloader=fake_downloader)

    assert report["year"] == 2021
    assert report["cadastro_duplicates"]["duplicate_extra_rows"] == 0
    assert report["missing_parent"]["dfp"]["missing_open_only"] > 0
    assert report["missing_parent"]["dfp"]["missing_open_plus_foreign"] >= 0
    assert "cadastro_duplicates" in render_console_summary(report)


@pytest.mark.cvm_live
@pytest.mark.skipif(
    os.getenv("RUN_CVM_LIVE") != "1",
    reason="Live CVM network smoke test is opt-in only.",
)
def test_build_audit_report_live_smoke() -> None:
    report = build_audit_report(year=2021, document_sources=("dfp",))

    assert report["year"] == 2021
    assert "cadastro_duplicates" in report
    assert "dfp" in report["missing_parent"]


def test_build_dataset_discovery_audit_with_fake_downloader() -> None:
    cadastro_aberta = (
        "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;DT_REG;DT_CONST;DT_CANCEL;MOTIVO_CANCEL;SIT;DT_INI_SIT;CD_CVM;"
        "SETOR_ATIV;TP_MERC;CATEG_REG;DT_INI_CATEG;SIT_EMISSOR;DT_INI_SIT_EMISSOR;CONTROLE_ACIONARIO;TP_ENDER;"
        "LOGRADOURO;COMPL;BAIRRO;MUN;UF;PAIS;CEP;DDD_TEL;TEL;DDD_FAX;FAX;EMAIL;TP_RESP;RESP;DT_INI_RESP;"
        "LOGRADOURO_RESP;COMPL_RESP;BAIRRO_RESP;MUN_RESP;UF_RESP;PAIS_RESP;CEP_RESP;DDD_TEL_RESP;TEL_RESP;"
        "DDD_FAX_RESP;FAX_RESP;EMAIL_RESP;CNPJ_AUDITOR;AUDITOR\n"
        "08.773.135/0001-00;EMPRESA SA;EMPRESA SA;2020-01-01;2000-01-01;;;ATIVO;2020-01-01;25224;Energia;BOLSA;"
        "Categoria A;2020-01-01;FASE OPERACIONAL;2020-01-01;PRIVADO;SEDE;Rua A;;Centro;SAO PAULO;SP;BRASIL;"
        "01001000;11;11111111;;;;DIRETOR;Fulano;2020-01-01;Rua B;;Centro;SAO PAULO;SP;BRASIL;01001000;11;"
        "11111111;;;;;\n"
    ).encode("latin1")
    cadastro_estrangeira = (
        "CNPJ;DENOM_SOCIAL;DENOM_COMERC;PAIS_ORIGEM;DT_REG;DT_CONST;DT_CANCEL;MOTIVO_CANCEL;SIT;DT_INI_SIT;"
        "CD_CVM;SETOR_ATIV\n"
        "07.857.093/0001-14;AURA MINERALS INC.;AURA MINERALS INC.;EXTERIOR;2020-01-01;2000-01-01;;;ATIVO;"
        "2020-01-01;80187;Mineracao\n"
    ).encode("latin1")
    payloads = {
        build_source_url("CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"): cadastro_aberta,
        build_source_url("CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv"): cadastro_estrangeira,
    }

    def fake_downloader(url: str) -> bytes:
        return payloads[url]

    report = build_dataset_discovery_audit(year=None, fontes=("cadastro",), downloader=fake_downloader)

    assert report["ano"] is None
    assert report["total_fontes"] == 1
    assert report["total_datasets_faltantes"] == 0
    assert report["fontes"][0]["fonte"] == "cadastro"
    assert report["fontes"][0]["datasets_encontrados"] == report["fontes"][0]["datasets_esperados"]
