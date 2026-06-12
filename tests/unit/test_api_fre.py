from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.fre import (
    FreAcaoEntregue,
    FreAdministradorDeclaracaoRaca,
    FreAuditor,
    FreCapitalSocial,
    FreCapitalSocialClasseAcao,
    FreCapitalSocialTituloConversivel,
    FreDistribuicaoCapital,
    FreDistribuicaoCapitalClasseAcao,
    FreDocumento,
    FreEmpregadoLocalDeclaracaoGenero,
    FreEmpregadoLocalDeclaracaoRaca,
    FreEmpregadoLocalFaixaEtaria,
    FreEmpregadoPcd,
    FreEmpregadoPosicaoGenero,
    FreEmpregadoPosicaoDeclaracaoRaca,
    FreEmpregadoPosicaoFaixaEtaria,
    FreEmpregadoPosicaoLocal,
    FrePosicaoAcionaria,
    FrePosicaoAcionariaClasseAcao,
    FreParticipacaoSociedade,
    FreRelacaoFamiliar,
    FreRemuneracaoAcao,
    FreRemuneracaoMaximaMinimaMedia,
    FreRemuneracaoTotalOrgao,
    FreRemuneracaoVariavel,
    FreResponsavel,
    FreAdministradorDeclaracaoGenero,
    FreAdministradorPcd,
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


def _seed_fre(db: Session, companhia_id: UUID) -> None:
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
    db.add(
        FreResponsavel(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            nome_responsavel="Fulano",
            cargo_responsavel="Diretor",
            arquivo_origem="fre_cia_aberta_responsavel_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h7",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreCapitalSocialClasseAcao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_capital_social=1,
            tipo_classe_acao_preferencial="A",
            quantidade_acoes=Decimal("50"),
            arquivo_origem="fre_cia_aberta_capital_social_classe_acao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h8",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreCapitalSocialTituloConversivel(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_capital_social=1,
            titulo_conversivel_acao="Debenture",
            condicoes_conversao="Condicoes X",
            arquivo_origem="fre_cia_aberta_capital_social_titulo_conversivel_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h9",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreDistribuicaoCapital(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            data_ultima_assembleia=date(2025, 4, 30),
            quantidade_acoes_ordinarias_circulacao=Decimal("100"),
            percentual_acoes_ordinarias_circulacao=Decimal("10.0"),
            quantidade_acoes_preferenciais_circulacao=Decimal("200"),
            percentual_acoes_preferenciais_circulacao=Decimal("20.0"),
            quantidade_total_acoes_circulacao=Decimal("300"),
            percentual_total_acoes_circulacao=Decimal("30.0"),
            quantidade_acionistas_pf=Decimal("50"),
            quantidade_acionistas_pj=Decimal("5"),
            quantidade_acionistas_investidores_institucionais=Decimal("2"),
            arquivo_origem="fre_cia_aberta_distribuicao_capital_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h10",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreDistribuicaoCapitalClasseAcao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            classe_acoes_preferenciais="A",
            sigla_classe_acoes_preferenciais="PNA",
            quantidade_acoes_preferenciais_circulacao=Decimal("10"),
            percentual_acoes_preferenciais_circulacao=Decimal("1.0"),
            arquivo_origem="fre_cia_aberta_distribuicao_capital_classe_acao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h11",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FrePosicaoAcionariaClasseAcao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_acionista=1,
            tipo_classe_acao_preferencial="A",
            quantidade_acoes=Decimal("20"),
            percentual_acoes=Decimal("2.0"),
            arquivo_origem="fre_cia_aberta_posicao_acionaria_classe_acao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h12",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreRemuneracaoMaximaMinimaMedia(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            data_inicio_exercicio_social=date(2025, 1, 1),
            data_fim_exercicio_social=date(2025, 12, 31),
            orgao_administracao="Conselho",
            numero_membros=Decimal("5"),
            numero_membros_remunerados=Decimal("5"),
            valor_maior_remuneracao=Decimal("100"),
            valor_medio_remuneracao=Decimal("50"),
            valor_menor_remuneracao=Decimal("10"),
            observacao="Obs",
            arquivo_origem="fre_cia_aberta_remuneracao_maxima_minima_media_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h13",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreRemuneracaoVariavel(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            data_inicio_exercicio_social=date(2025, 1, 1),
            data_fim_exercicio_social=date(2025, 12, 31),
            orgao_administracao="Conselho",
            quantidade_total_membros=Decimal("5"),
            quantidade_membros_remunerados=Decimal("5"),
            bonus_valor_minimo=Decimal("10"),
            bonus_valor_maximo=Decimal("50"),
            bonus_valor_metas_atingidas=Decimal("40"),
            bonus_valor_efetivo=Decimal("45"),
            participacao_valor_minimo=Decimal("5"),
            participacao_valor_maximo=Decimal("20"),
            participacao_valor_metas_atingidas=Decimal("15"),
            participacao_valor_efetivo=Decimal("18"),
            arquivo_origem="fre_cia_aberta_remuneracao_variavel_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h14",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreRemuneracaoAcao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            data_inicio_exercicio_social=date(2025, 1, 1),
            data_fim_exercicio_social=date(2025, 12, 31),
            orgao_administracao="Conselho",
            quantidade_total_membros=Decimal("5"),
            quantidade_membros_remunerados=Decimal("5"),
            preco_medio_ponderado_opcoes_em_aberto=Decimal("10"),
            preco_medio_ponderado_opcoes_exercidas=Decimal("12"),
            preco_medio_ponderado_opcoes_perdidas=Decimal("0"),
            diluicao_potencial=Decimal("0.01"),
            arquivo_origem="fre_cia_aberta_remuneracao_acao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h15",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreAcaoEntregue(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            data_inicio_exercicio_social=date(2025, 1, 1),
            data_fim_exercicio_social=date(2025, 12, 31),
            orgao_administracao="Conselho",
            quantidade_total_membros=Decimal("5"),
            quantidade_membros_remunerados=Decimal("5"),
            quantidade_acoes=100,
            preco_medio_ponderado_aquisicao=Decimal("10"),
            preco_medio_ponderado_mercado=Decimal("15"),
            valor_diferenca_aquisicao_mercado=Decimal("5"),
            arquivo_origem="fre_cia_aberta_acao_entregue_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h16",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    # Phase 2
    from app.models.fre import (
        FreCapitalSocialAumento,
        FreCapitalSocialAumentoClasseAcao,
        FreCapitalSocialDesdobramento,
        FreCapitalSocialDesdobramentoClasseAcao,
        FreCapitalSocialReducao,
        FreCapitalSocialReducaoClasseAcao,
        FreDireitoAcao,
    )
    db.add(
        FreCapitalSocialAumento(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_capital_social=1,
            data_deliberacao=date(2025, 6, 1),
            valor_aumento=Decimal("1000"),
            origem_aumento="Incorporacao",
            quantidade_acoes_ordinarias=Decimal("500"),
            quantidade_acoes_preferenciais=Decimal("500"),
            quantidade_total_acoes=Decimal("1000"),
            arquivo_origem="fre_cia_aberta_capital_social_aumento_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h17",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreCapitalSocialAumentoClasseAcao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_capital_social=1,
            tipo_classe_acao_preferencial="Classe A",
            quantidade_acoes=Decimal("500"),
            arquivo_origem="fre_cia_aberta_capital_social_aumento_classe_acao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h18",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreCapitalSocialDesdobramento(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_capital_social=1,
            data_deliberacao=date(2025, 6, 1),
            tipo_desdobramento="Desdobramento",
            proporcao_acoes_novas=Decimal("2"),
            proporcao_acoes_antigas=Decimal("1"),
            quantidade_acoes_ordinarias=Decimal("500"),
            quantidade_acoes_preferenciais=Decimal("500"),
            quantidade_total_acoes=Decimal("1000"),
            arquivo_origem="fre_cia_aberta_capital_social_desdobramento_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h19",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreCapitalSocialDesdobramentoClasseAcao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_capital_social=1,
            tipo_classe_acao_preferencial="Classe A",
            quantidade_acoes=Decimal("500"),
            arquivo_origem="fre_cia_aberta_capital_social_desdobramento_classe_acao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h20",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreCapitalSocialReducao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_capital_social=1,
            data_deliberacao=date(2025, 6, 1),
            valor_reducao=Decimal("500"),
            motivo_reducao="Perdas",
            quantidade_acoes_ordinarias=Decimal("250"),
            quantidade_acoes_preferenciais=Decimal("250"),
            quantidade_total_acoes=Decimal("500"),
            arquivo_origem="fre_cia_aberta_capital_social_reducao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h21",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreCapitalSocialReducaoClasseAcao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_capital_social=1,
            tipo_classe_acao_preferencial="Classe A",
            quantidade_acoes=Decimal("250"),
            arquivo_origem="fre_cia_aberta_capital_social_reducao_classe_acao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h22",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreDireitoAcao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            tipo_classe_acao="Ordinaria",
            direito_voto="Sim",
            outros_direitos="Direito de voto integral",
            arquivo_origem="fre_cia_aberta_direito_acao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h23",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    # Phase 3
    from app.models.fre import (
        FreVolumeValorMobiliario,
        FreOutroValorMobiliario,
        FreTitularValorMobiliario,
        FreMercadoEstrangeiro,
        FreTituloExterior,
        FrePlanoRecompra,
        FrePlanoRecompraClasseAcao,
        FreValorMobiliarioTesourariaMovimentacao,
        FreValorMobiliarioTesourariaUltimoExercicio,
    )
    db.add(
        FreVolumeValorMobiliario(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            classe_valor_mobiliario="Acao",
            sigla_classe_acoes_preferenciais="PN",
            volume_negociacao=Decimal("10000"),
            arquivo_origem="fre_cia_aberta_volume_valor_mobiliario_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h24",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreOutroValorMobiliario(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            nome_valor_mobiliario="Debenture",
            caracteristicas_valor_mobiliario="Debenture conversivel",
            arquivo_origem="fre_cia_aberta_outro_valor_mobiliario_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h25",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreTitularValorMobiliario(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            nome_titular="Titular X",
            cpf_cnpj_titular="12345678900",
            classe_valor_mobiliario="Acao",
            quantidade_valores_mobiliarios=Decimal("100"),
            percentual_classe=Decimal("10.0"),
            arquivo_origem="fre_cia_aberta_titular_valor_mobiliario_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h26",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreMercadoEstrangeiro(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            nome_mercado="NYSE",
            orgao_regulador="SEC",
            data_admissao=date(2020, 1, 1),
            arquivo_origem="fre_cia_aberta_mercado_estrangeiro_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h27",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreTituloExterior(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            nome_titulo="Bond",
            pais_emissao="USA",
            caracteristicas="Yield 5%",
            arquivo_origem="fre_cia_aberta_titulo_exterior_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h28",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FrePlanoRecompra(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_plano_recompra=1,
            data_deliberacao=date(2025, 1, 1),
            objetivo_plano="Tesouraria",
            limite_prazo_aquisicao="365 dias",
            quantidade_total_ordinarias_adquiridas=Decimal("100"),
            quantidade_total_preferenciais_adquiridas=Decimal("200"),
            arquivo_origem="fre_cia_aberta_plano_recompra_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h29",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FrePlanoRecompraClasseAcao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            id_plano_recompra=1,
            tipo_classe_acao_preferencial="PN A",
            quantidade_acoes_adquiridas=Decimal("50"),
            arquivo_origem="fre_cia_aberta_plano_recompra_classe_acao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h30",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreValorMobiliarioTesourariaMovimentacao(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            classe_valor_mobiliario="Acao",
            data_movimentacao=date(2025, 6, 1),
            quantidade_movimentada=Decimal("1000"),
            natureza_movimentacao="Aquisicao",
            arquivo_origem="fre_cia_aberta_valor_mobiliario_tesouraria_movimentacao_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h31",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreValorMobiliarioTesourariaUltimoExercicio(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            classe_valor_mobiliario="Acao",
            historico_exercicio="Saldo final",
            quantidade_acoes_tesouraria=Decimal("1500"),
            arquivo_origem="fre_cia_aberta_valor_mobiliario_tesouraria_ultimo_exercicio_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h32",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        FreAdministradorDeclaracaoGenero(
            companhia_id=companhia_id,
            cnpj_companhia="08773135000100",
            data_referencia=date(2025, 12, 31),
            versao=1,
            id_documento=123,
            nome_companhia="EMPRESA A",
            orgao_administracao="Diretoria",
            quantidade_feminino=10,
            quantidade_masculino=20,
            quantidade_nao_binario=1,
            quantidade_outros=0,
            quantidade_sem_resposta=0,
            nao_aplicavel=False,
            arquivo_origem="fre_cia_aberta_administrador_declaracao_genero_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="h33",
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

    assert client.get("/fre/responsaveis?versao=1").json()["paginacao"]["total"] == 1

    # Test filters that were previously ignored/undeclared (id_capital_social, id_acionista, orgao_administracao)
    # 1. id_capital_social
    assert client.get("/fre/capital-social-classes-acoes?id_capital_social=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/capital-social-classes-acoes?id_capital_social=999").json()["paginacao"]["total"] == 0
    assert client.get("/fre/capital-social-titulos-conversiveis?id_capital_social=1").json()["paginacao"]["total"] == 1
    assert (
        client.get("/fre/capital-social-titulos-conversiveis?id_capital_social=999")
        .json()["paginacao"]["total"] == 0
    )

    # 2. id_acionista
    assert client.get("/fre/posicao-acionaria?id_acionista=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/posicao-acionaria?id_acionista=999").json()["paginacao"]["total"] == 0
    assert client.get("/fre/posicoes-acionarias-classes-acoes?id_acionista=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/posicoes-acionarias-classes-acoes?id_acionista=999").json()["paginacao"]["total"] == 0

    # 3. orgao_administracao
    assert client.get("/fre/remuneracao/total-por-orgao?orgao_administracao=Conselho").json()["paginacao"]["total"] == 1
    assert (
        client.get("/fre/remuneracao/total-por-orgao?orgao_administracao=Inexistente")
        .json()["paginacao"]["total"] == 0
    )
    assert (
        client.get("/fre/remuneracoes-maximas-minimas-medias?orgao_administracao=Conselho")
        .json()["paginacao"]["total"] == 1
    )
    assert (
        client.get("/fre/remuneracoes-maximas-minimas-medias?orgao_administracao=Inexistente")
        .json()["paginacao"]["total"] == 0
    )
    assert client.get("/fre/remuneracoes-variaveis?orgao_administracao=Conselho").json()["paginacao"]["total"] == 1
    assert client.get("/fre/remuneracoes-variaveis?orgao_administracao=Inexistente").json()["paginacao"]["total"] == 0
    assert client.get("/fre/remuneracoes-acoes?orgao_administracao=Conselho").json()["paginacao"]["total"] == 1
    assert client.get("/fre/remuneracoes-acoes?orgao_administracao=Inexistente").json()["paginacao"]["total"] == 0
    assert client.get("/fre/acoes-entregues?orgao_administracao=Conselho").json()["paginacao"]["total"] == 1
    assert client.get("/fre/acoes-entregues?orgao_administracao=Inexistente").json()["paginacao"]["total"] == 0

    # Phase 2 Endpoints
    assert client.get("/fre/capital-social/aumentos?id_capital_social=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/capital-social/aumentos-classes-acoes?id_capital_social=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/capital-social/desdobramentos?id_capital_social=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/capital-social/desdobramentos-classes-acoes?id_capital_social=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/capital-social/reducoes?id_capital_social=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/capital-social/reducoes-classes-acoes?id_capital_social=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/direitos-acoes?versao=1").json()["paginacao"]["total"] == 1

    # Phase 3 Endpoints
    assert client.get("/fre/volume-valor-mobiliario?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/outro-valor-mobiliario?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/titular-valor-mobiliario?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/mercado-estrangeiro?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/titulo-exterior?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/plano-recompra?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/plano-recompra-classes-acoes?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/valor-mobiliario-tesouraria-movimentacao?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/valor-mobiliario-tesouraria-ultimo-exercicio?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/administradores/declaracao-genero?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/administradores/declaracao-genero?orgao_administracao=Diretoria").json()["paginacao"]["total"] == 1
    assert client.get("/fre/administradores/declaracao-genero?orgao_administracao=Inexistente").json()["paginacao"]["total"] == 0

    # Other tests
    url_titulos = "/fre/capital-social-titulos-conversiveis?cnpj_companhia=08.773.135/0001-00"
    assert client.get(url_titulos).json()["paginacao"]["total"] == 1
    assert client.get("/fre/distribuicao-capital?ano_origem=2025").json()["paginacao"]["total"] == 1
    assert client.get("/fre/distribuicao-capital-classes-acoes?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/remuneracoes-variaveis?data_referencia_inicio=2025-01-01").json()["paginacao"]["total"] == 1
    assert client.get("/fre/remuneracoes-acoes?versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/fre/acoes-entregues?id_documento=123").json()["paginacao"]["total"] == 1

    # Test invalid order field returns 422
    assert client.get("/fre/responsaveis?ordenar_por=invalid_field").status_code == 422


def test_endpoints_fre_new_employee_and_sociedade_datasets(client: TestClient, db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()

    agora = datetime.now(UTC)
    db_session.add_all(
        [
            FreRelacaoFamiliar(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                nome_administrador="Administrador X",
                cpf_administrador="12345678900",
                nome_emissor="Emissor A",
                cnpj_emissor="08773135000100",
                cargo_administrador="Diretor",
                nome_pessoa_relacionada="Pessoa Y",
                cpf_pessoa_relacionada="12345678901",
                nome_emissor_pessoa_relacionada="Emissor B",
                cnpj_emissor_pessoa_relacionada="08773135000100",
                cargo_Pessoa_relacionada="Conselheira",
                tipo_parentesco="Conjuge",
                observacao="Obs",
                arquivo_origem="fre_cia_aberta_relacao_familiar_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n1",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreAdministradorPcd(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                orgao_administracao="Diretoria",
                quantidade_pcd=1,
                quantidade_nao_pcd=4,
                quantidade_sem_resposta=0,
                nao_aplicavel=False,
                arquivo_origem="fre_cia_aberta_administrador_PCD_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n1a",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreAdministradorDeclaracaoRaca(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                orgao_administracao="Diretoria",
                quantidade_amarelo=0,
                quantidade_branco=1,
                quantidade_preto=0,
                quantidade_pardo=0,
                quantidade_indigena=0,
                quantidade_outros=0,
                quantidade_sem_resposta=0,
                nao_aplicavel=False,
                arquivo_origem="fre_cia_aberta_administrador_declaracao_raca_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n1b",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreParticipacaoSociedade(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                id_sociedade=10,
                razao_social="Sociedade XPTO",
                cnpj="11111111000111",
                tipo_sociedade="Controlada",
                descricao_atividades="Energia solar",
                pais_sede="Brasil",
                uf_sede="SP",
                municipio_sede="Sao Paulo",
                participacao_emissor=Decimal("75.5"),
                possui_registro_cvm=True,
                codigo_cvm=25224,
                razao_aquisicao_manutencao="Expansao",
                data_valor_mercado=date(2025, 12, 31),
                data_valor_contabil=date(2025, 12, 31),
                valor_mercado=Decimal("1000"),
                valor_contabil=Decimal("900"),
                arquivo_origem="fre_cia_aberta_participacao_sociedade_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n2",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreEmpregadoPosicaoLocal(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                posicao="Diretoria",
                quantidade_norte=1,
                quantidade_nordeste=2,
                quantidade_centro_oeste=3,
                quantidade_sudeste=4,
                quantidade_sul=5,
                quantidade_exterior=6,
                arquivo_origem="fre_cia_aberta_empregado_posicao_local_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n3",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreEmpregadoPosicaoFaixaEtaria(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                posicao="Diretoria",
                quantidade_ate_30_anos=7,
                quantidade_30_a_50_anos=8,
                quantidade_acima_50_anos=9,
                arquivo_origem="fre_cia_aberta_empregado_posicao_faixa_etaria_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n4",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreEmpregadoPosicaoDeclaracaoRaca(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                posicao="Diretoria",
                quantidade_amarelo=1,
                quantidade_branco=2,
                quantidade_preto=3,
                quantidade_pardo=4,
                quantidade_indigena=5,
                quantidade_outros=6,
                quantidade_sem_resposta=7,
                arquivo_origem="fre_cia_aberta_empregado_posicao_declaracao_raca_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n5",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreEmpregadoPcd(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                codigo_posicao=99,
                posicao="Diretoria",
                quantidade_pcd=2,
                quantidade_nao_pcd=20,
                quantidade_sem_resposta=1,
                arquivo_origem="fre_cia_aberta_empregado_PCD_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n6",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreEmpregadoLocalFaixaEtaria(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                local="Brasil",
                quantidade_ate_30_anos=11,
                quantidade_30_a_50_anos=12,
                quantidade_acima_50_anos=13,
                arquivo_origem="fre_cia_aberta_empregado_local_faixa_etaria_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n7",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreEmpregadoLocalDeclaracaoRaca(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                local="Brasil",
                quantidade_amarelo=3,
                quantidade_branco=4,
                quantidade_preto=5,
                quantidade_pardo=6,
                quantidade_indigena=7,
                quantidade_outros=8,
                quantidade_sem_resposta=9,
                arquivo_origem="fre_cia_aberta_empregado_local_declaracao_raca_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n8",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreEmpregadoLocalDeclaracaoGenero(
                companhia_id=companhia.id,
                cnpj_companhia="08773135000100",
                data_referencia=date(2025, 12, 31),
                versao=1,
                id_documento=123,
                nome_companhia="EMPRESA A",
                local="Brasil",
                quantidade_feminino=14,
                quantidade_masculino=15,
                quantidade_nao_binario=1,
                quantidade_outros=0,
                quantidade_sem_resposta=2,
                arquivo_origem="fre_cia_aberta_empregado_local_declaracao_genero_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="n9",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
        ]
    )
    db_session.commit()

    assert client.get("/fre/relacoes-familiares?tipo_parentesco=Conjuge").json()["paginacao"]["total"] == 1
    assert client.get("/fre/administradores/pcd?orgao_administracao=Diretoria").json()["paginacao"]["total"] == 1
    assert client.get("/fre/administradores/declaracao-raca?orgao_administracao=Diretoria").json()["paginacao"]["total"] == 1
    assert client.get("/fre/participacoes-sociedades?id_sociedade=10").json()["paginacao"]["total"] == 1
    assert client.get("/fre/empregados/posicao-local?posicao=Diretoria").json()["paginacao"]["total"] == 1
    assert client.get("/fre/empregados/posicao-faixa-etaria?posicao=Diretoria").json()["paginacao"]["total"] == 1
    assert client.get("/fre/empregados/posicao-declaracao-raca?posicao=Diretoria").json()["paginacao"]["total"] == 1
    assert client.get("/fre/empregados/pcd?posicao=Diretoria").json()["paginacao"]["total"] == 1
    assert client.get("/fre/empregados/local-faixa-etaria?local=Brasil").json()["paginacao"]["total"] == 1
    assert client.get("/fre/empregados/local-declaracao-raca?local=Brasil").json()["paginacao"]["total"] == 1
    assert client.get("/fre/empregados/local-declaracao-genero?local=Brasil").json()["paginacao"]["total"] == 1
