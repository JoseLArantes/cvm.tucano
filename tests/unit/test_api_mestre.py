import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.financeiro import ComposicaoCapital, DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro
from app.models.fre import FreDocumento
from app.models.ipe import IpeDocumento


def _companhia_base() -> Companhia:
    agora = datetime.now(UTC)
    return Companhia(
        cnpj_companhia="08773135000100",
        codigo_cvm=25224,
        denominacao_social="Empresa A",
        denominacao_comercial="Empresa A",
        situacao_registro="ATIVA",
        data_registro=date(2020, 1, 1),
        data_constituicao=date(2000, 1, 1),
        data_cancelamento=None,
        motivo_cancelamento=None,
        data_inicio_situacao=date(2020, 1, 1),
        setor_atividade="Energia",
        tipo_mercado="Categoria A",
        categoria_registro="Categoria A",
        data_inicio_categoria=date(2020, 1, 1),
        situacao_emissor="ATIVO",
        data_inicio_situacao_emissor=date(2020, 1, 1),
        controle_acionario="PRIVADO",
        endereco={"municipio": "Sao Paulo"},
        responsavel={"nome_responsavel": "Fulano"},
        auditor="Auditoria X",
        cnpj_auditor="10830108000165",
        arquivo_origem="cad_cia_aberta.csv",
        ano_origem=None,
        linha_origem=2,
        hash_origem="hash",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _seed_dados(db: Session, companhia_id: uuid.UUID) -> None:
    agora = datetime.now(UTC)
    db.add(
        DocumentoFinanceiro(
            companhia_id=companhia_id,
            tipo_formulario="DFP",
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="EMPRESA A",
            categoria_documento="DFP",
            id_documento=100,
            data_recebimento=date(2026, 1, 1),
            link_documento="http://doc",
            arquivo_origem="dfp_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-doc",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        DemonstracaoFinanceira(
            companhia_id=companhia_id,
            tipo_formulario="DFP",
            tipo_demonstracao="demonstracao_resultado",
            escopo_demonstracao="consolidado",
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="EMPRESA A",
            grupo_demonstracao="GRUPO",
            moeda="REAL",
            escala_moeda="UNIDADE",
            ordem_exercicio="ULTIMO",
            data_inicio_exercicio=date(2025, 1, 1),
            data_fim_exercicio=date(2025, 12, 31),
            codigo_conta="3.01",
            descricao_conta="Lucro",
            valor_conta=Decimal("123.45"),
            conta_fixa=True,
            arquivo_origem="dfp_cia_aberta_DRE_con_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-dem",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        ComposicaoCapital(
            companhia_id=companhia_id,
            tipo_formulario="DFP",
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="EMPRESA A",
            quantidade_acoes_ordinarias_capital_integralizado=Decimal("1"),
            quantidade_acoes_preferenciais_capital_integralizado=Decimal("2"),
            quantidade_total_acoes_capital_integralizado=Decimal("3"),
            quantidade_acoes_ordinarias_tesouraria=Decimal("0"),
            quantidade_acoes_preferenciais_tesouraria=Decimal("0"),
            quantidade_total_acoes_tesouraria=Decimal("0"),
            arquivo_origem="dfp_cia_aberta_composicao_capital_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-comp",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        ParecerFinanceiro(
            companhia_id=companhia_id,
            tipo_formulario="DFP",
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="EMPRESA A",
            tipo_relatorio_auditor="SEM RESSALVA",
            tipo_parecer_declaracao="PARECER",
            numero_item_parecer_declaracao="1",
            texto_parecer_declaracao="Texto",
            arquivo_origem="dfp_cia_aberta_parecer_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-par",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreDocumento(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="EMPRESA A",
            categoria_documento="FRE",
            id_documento=333,
            data_recebimento=date(2026, 1, 1),
            link_documento="http://fre",
            arquivo_origem="fre_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-fre",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        IpeDocumento(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            nome_companhia="Empresa A",
            data_referencia=date(2025, 1, 1),
            categoria="Categoria X",
            tipo="Tipo X",
            especie="Espécie X",
            assunto="Assunto X",
            data_entrega=date(2025, 1, 15),
            tipo_apresentacao="Apresentacao",
            protocolo_entrega="123456",
            versao=1,
            link_download="http://ipe",
            arquivo_origem="ipe_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-ipe",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.commit()


def test_endpoint_mestre_unifica_respostas(client: TestClient, db_session: Session) -> None:
    companhia = _companhia_base()
    db_session.add(companhia)
    db_session.commit()
    _seed_dados(db_session, companhia.id)

    resposta = client.get("/companhias/mestre?cnpj_companhia=08.773.135/0001-00&limite_por_endpoint=100")
    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["companhia"]["codigo_cvm"] == 25224
    assert payload["documentos_dfp"]["paginacao"]["total"] == 1
    assert payload["composicao_capital_dfp"]["paginacao"]["total"] == 1
    assert payload["pareceres_dfp"]["paginacao"]["total"] == 1
    assert payload["demonstracoes"]["dfp_demonstracao_resultado_consolidado"]["paginacao"]["total"] == 1
    assert payload["fre_documentos"]["paginacao"]["total"] == 1
    assert payload["ipe_documentos"]["paginacao"]["total"] == 1
