from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.fre import (
    FreAuditor,
    FreCapitalSocial,
    FreDocumento,
    FreEmpregadoPosicaoGenero,
    FrePosicaoAcionaria,
    FreRemuneracaoTotalOrgao,
)


def _companhia() -> Companhia:
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


def _seed_fre(db: Session, companhia_id: str) -> None:
    agora = datetime.now(UTC)
    db.add(
        FreDocumento(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="EMPRESA A",
            categoria_documento="FRE",
            id_documento=123,
            data_recebimento=date(2026, 1, 1),
            link_documento="http://doc",
            arquivo_origem="fre_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h1",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreAuditor(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_auditor=1,
            auditor="Auditor X",
            cpf_auditor="12345678900",
            cnpj_auditor="10830108000165",
            codigo_cvm_auditor=100,
            tipo_origem_auditor="ORIGEM",
            data_inicio_contratacao=date(2020, 1, 1),
            data_fim_contratacao=None,
            data_inicio_prestacao_servico=date(2020, 1, 1),
            servico_contratado="SERVICO",
            remuneracao_auditor=Decimal("1000"),
            justificativa_substituicao=None,
            razao_apresentada=None,
            arquivo_origem="fre_cia_aberta_auditor_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h2",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreCapitalSocial(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_capital_social=1,
            tipo_capital="SUBSCRITO",
            data_autorizacao_aprovacao=date(2025, 1, 1),
            valor_capital=Decimal("1000"),
            prazo_integralizacao="12M",
            quantidade_acoes_ordinarias=Decimal("100"),
            quantidade_acoes_preferenciais=Decimal("200"),
            quantidade_total_acoes=Decimal("300"),
            arquivo_origem="fre_cia_aberta_capital_social_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h3",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FrePosicaoAcionaria(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_acionista=1,
            acionista="Acionista X",
            tipo_pessoa_acionista="PF",
            cpf_cnpj_acionista="12345678900",
            id_acionista_relacionado=None,
            acionista_relacionado=None,
            tipo_pessoa_acionista_relacionado=None,
            cpf_cnpj_acionista_relacionado=None,
            quantidade_acao_ordinaria_circulacao=Decimal("10"),
            percentual_acao_ordinaria_circulacao=Decimal("1.5"),
            quantidade_acao_preferencial_circulacao=Decimal("20"),
            percentual_acao_preferencial_circulacao=Decimal("2.5"),
            quantidade_total_acoes_circulacao=Decimal("30"),
            percentual_total_acoes_circulacao=Decimal("4.0"),
            nacionalidade="BRASIL",
            sigla_uf="SP",
            residente_exterior=False,
            representante_legal="Rep",
            tipo_pessoa_representante_legal="PF",
            cpf_cnpj_representante_legal="12345678901",
            data_composicao_capital_social=date(2025, 1, 1),
            data_ultima_alteracao=date(2025, 12, 31),
            acionista_controlador=True,
            participante_acordo_acionistas=False,
            arquivo_origem="fre_cia_aberta_posicao_acionaria_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h4",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreRemuneracaoTotalOrgao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            data_inicio_exercicio_social=date(2025, 1, 1),
            data_fim_exercicio_social=date(2025, 12, 31),
            total_remuneracao=Decimal("1000"),
            orgao_administracao="Conselho",
            numero_membros=5,
            total_remuneracao_orgao=Decimal("1000"),
            numero_membros_remunerados=5,
            salario=Decimal("500"),
            beneficios_diretos_indiretos=Decimal("100"),
            participacoes_comites=Decimal("10"),
            outros_valores_fixos=Decimal("5"),
            descricao_outros_remuneracoes_fixas="",
            bonus=Decimal("50"),
            participacao_resultados=Decimal("20"),
            participacao_reunioes=Decimal("10"),
            outros_valores_variaveis=Decimal("5"),
            comissoes=Decimal("1"),
            descricao_outros_remuneracoes_variaveis="",
            pos_emprego=Decimal("0"),
            cessacao_cargo=Decimal("0"),
            baseada_acoes=Decimal("0"),
            observacao="",
            arquivo_origem="fre_cia_aberta_remuneracao_total_orgao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h5",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreEmpregadoPosicaoGenero(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            posicao="Diretoria",
            quantidade_feminino=10,
            quantidade_masculino=20,
            quantidade_nao_binario=1,
            quantidade_outros=0,
            quantidade_sem_resposta=0,
            arquivo_origem="fre_cia_aberta_empregado_posicao_declaracao_genero_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h6",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.commit()


def test_endpoints_fre_mvp(client: TestClient, db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()
    _seed_fre(db_session, companhia.id)

    assert client.get("/fre/documentos?cnpj_companhia=08.773.135/0001-00").status_code == 200
    assert client.get("/fre/auditores?id_documento=123").json()["paginacao"]["total"] == 1
    assert client.get("/fre/capital-social?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/posicao-acionaria?data_referencia_inicio=2025-01-01").json()["paginacao"]["total"] == 1
    assert client.get("/fre/remuneracao/total-por-orgao?ano_origem=2025").json()["paginacao"]["total"] == 1
    assert client.get("/fre/empregados/posicao-genero?versao=1").json()["paginacao"]["total"] == 1
