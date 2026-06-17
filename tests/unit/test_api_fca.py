import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.fca import (
    FcaAuditor,
    FcaDepartamentoAcionistas,
    FcaDocumento,
    FcaDri,
    FcaEndereco,
    FcaGeral,
    FcaValorMobiliario,
)


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
        hash_origem="companhia-fca",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _seed_fca(db: Session, companhia_id: uuid.UUID) -> None:
    agora = datetime.now(UTC)
    comum = {
        "companhia_id": companhia_id,
        "cnpj_companhia": "00000000000191",
        "data_referencia": date(2025, 1, 1),
        "versao": 1,
        "id_documento": 146477,
        "arquivo_origem": "fca_cia_aberta_2025.csv",
        "ano_origem": 2025,
        "linha_origem": 2,
        "hash_origem": "hash",
        "criado_em": agora,
        "sincronizado_em": agora,
        "alterado_em": agora,
    }
    db.add(
        FcaDocumento(
            **comum,
            codigo_cvm=1023,
            denominacao_companhia="BCO BRASIL S.A.",
            categoria_documento="FCA",
            data_recebimento=date(2025, 4, 24),
            link_documento="http://exemplo",
        )
    )
    db.add(
        FcaGeral(
            **comum,
            codigo_cvm=1023,
            nome_empresarial="BCO BRASIL S.A.",
            data_constituicao=date(1808, 10, 12),
            situacao_emissor="Fase Operacional",
            pais_origem="Brasil",
            setor_atividade="Bancos",
            pagina_web="www.bb.com.br",
        )
    )
    db.add(
        FcaEndereco(
            **comum,
            nome_empresarial="BCO BRASIL S.A.",
            tipo_endereco="Endereço da Sede",
            logradouro="Saun Quadra 05, Lote B",
            complemento="Ed. BB",
            bairro="Asa Norte",
            cidade="Brasília",
            sigla_uf="DF",
            pais="Brasil",
            cep="70040912",
            ddd_telefone="61",
            telefone="34939002",
            email="secex@bb.com.br",
        )
    )
    db.add(
        FcaDri(
            **comum,
            nome_empresarial="BCO BRASIL S.A.",
            tipo_responsavel="Diretor de Relações com Investidores",
            nome_dri="Marco Geovanne Tobias da Silva",
            cpf_responsavel="26322579134",
            cidade="Brasília",
            pais="Brasil",
            email_dri="dribb@bb.com.br",
            data_inicio_atuacao=date(2023, 4, 27),
        )
    )
    db.add(
        FcaAuditor(
            **comum,
            nome_empresarial="BCO BRASIL S.A.",
            nome_auditor="KPMG AUDITORES INDEPENDENTES LTDA",
            cpf_cnpj_auditor="57755217001281",
            codigo_cvm_auditor=4189,
            origem_auditor="Nacional",
            data_inicio_atuacao_auditor=date(2024, 1, 1),
            responsavel_tecnico="João Paulo Dal Poz Alouche",
        )
    )
    db.add(
        FcaValorMobiliario(
            **comum,
            nome_empresarial="BCO BRASIL S.A.",
            tipo_valor_mobiliario="Ações Ordinárias",
            codigo_negociacao="BBAS3",
            mercado="Bolsa",
            entidade_administradora="B3 S.A. - Brasil, Bolsa, Balcão.",
            segmento="Novo Mercado",
            data_inicio_negociacao=date(2006, 5, 31),
        )
    )
    db.add(
        FcaDepartamentoAcionistas(
            **comum,
            nome_empresarial="BCO BRASIL S.A.",
            contato="Equipe RI",
            data_inicio_contato=date(2025, 1, 1),
            tipo_endereco="Departamento",
            logradouro="Saun Quadra 05, Lote B",
            complemento="Ed. BB",
            bairro="Asa Norte",
            cidade="Brasília",
            sigla_uf="DF",
            pais="Brasil",
            cep="70040912",
            ddd_telefone="61",
            telefone="34939002",
            email="ri@bb.com.br",
        )
    )
    db.commit()


def test_endpoints_fca(client: TestClient, db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()
    _seed_fca(db_session, companhia.id)

    assert client.get("/fca/documentos?cnpj_companhia=00.000.000/0001-91").json()["paginacao"]["total"] == 1
    assert client.get("/fca/geral?codigo_cvm=1023").json()["paginacao"]["total"] == 1
    assert client.get("/fca/enderecos?tipo_endereco=Endereço%20da%20Sede").json()["paginacao"]["total"] == 1
    assert client.get("/fca/enderecos?tipo_endereco=Inexistente").json()["paginacao"]["total"] == 0
    assert client.get("/fca/dri?email_dri=dribb@bb.com.br").json()["paginacao"]["total"] == 1
    assert client.get("/fca/dri?email_dri=nao@existe").json()["paginacao"]["total"] == 0
    assert client.get("/fca/auditores?codigo_cvm_auditor=4189").json()["paginacao"]["total"] == 1
    assert client.get("/fca/auditores?codigo_cvm_auditor=9999").json()["paginacao"]["total"] == 0
    assert (
        client.get("/fca/valores-mobiliarios?tipo_valor_mobiliario=Ações%20Ordinárias").json()["paginacao"]["total"]
        == 1
    )
    assert client.get("/fca/valores-mobiliarios?tipo_valor_mobiliario=Debenture").json()["paginacao"]["total"] == 0
    assert client.get("/fca/departamento-acionistas?contato=Equipe%20RI").json()["paginacao"]["total"] == 1
    assert client.get("/fca/departamento-acionistas?sigla_uf=RJ").json()["paginacao"]["total"] == 0
    assert client.get("/fca/documentos?ordenar_por=campo_invalido").status_code == 422
    assert client.get("/fca/departamento-acionistas?ordenar_por=campo_invalido").status_code == 422
