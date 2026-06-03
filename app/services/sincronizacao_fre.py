import csv
import hashlib
import io
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.fre import (
    FreAuditor,
    FreCapitalSocial,
    FreDocumento,
    FreEmpregadoPosicaoGenero,
    FrePosicaoAcionaria,
    FreRemuneracaoTotalOrgao,
)
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo, RegistroQuarentena
from app.services.normalizacao import (
    gerar_hash_canonico,
    normalizar_cnpj,
    normalizar_data,
    normalizar_decimal_cvm,
    normalizar_inteiro,
    normalizar_texto,
)


def _agora() -> datetime:
    return datetime.now(UTC)


def _decode_csv(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "latin1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", payload, 0, 1, "Falha ao decodificar CSV")


def _digitos(valor: Any) -> str | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    numeros = "".join(char for char in texto if char.isdigit())
    return numeros or None


def _normalizar_booleano(valor: Any) -> bool | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    upper = texto.upper()
    if upper in {"S", "SIM", "TRUE", "1"}:
        return True
    if upper in {"N", "NAO", "NÃO", "FALSE", "0"}:
        return False
    return None


def _equivalente(valor_a: Any, valor_b: Any) -> bool:
    if isinstance(valor_a, dict) and isinstance(valor_b, dict):
        chaves = set(valor_a.keys()) | set(valor_b.keys())
        return all(_equivalente(valor_a.get(chave), valor_b.get(chave)) for chave in chaves)
    if isinstance(valor_a, Decimal) or isinstance(valor_b, Decimal):
        if valor_a is None or valor_b is None:
            return valor_a is valor_b
        return Decimal(str(valor_a)) == Decimal(str(valor_b))
    if isinstance(valor_a, str) or isinstance(valor_b, str):
        return normalizar_texto(valor_a) == normalizar_texto(valor_b)
    return valor_a == valor_b


def _registrar_quarentena(
    db: Session,
    *,
    execucao_id: Any,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
    motivo: str,
    dados_originais: dict[str, Any],
) -> None:
    db.add(
        RegistroQuarentena(
            execucao_sincronizacao_id=execucao_id,
            arquivo_origem=arquivo_origem,
            ano_origem=ano_origem,
            linha_origem=linha_origem,
            motivo=motivo,
            dados_originais=dados_originais,
        )
    )


def _resolver_companhia(db: Session, cnpj_companhia: str, codigo_cvm: int | None) -> Companhia | None:
    if normalizar_texto(cnpj_companhia):
        return db.scalar(select(Companhia).where(Companhia.cnpj_companhia == cnpj_companhia))
    if codigo_cvm is None:
        return None
    return db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))


def _upsert(
    db: Session,
    *,
    model: type[Any],
    entidade: str,
    campos_chave: tuple[str, ...],
    campos_negocio: set[str],
    dados: dict[str, Any],
    execucao_id: Any,
    contadores: dict[str, int],
) -> None:
    filtros = [getattr(model, campo) == dados[campo] for campo in campos_chave]
    query: Select[tuple[Any]] = select(model).where(*filtros)
    existente = db.scalar(query)
    agora = _agora()

    dados["hash_origem"] = gerar_hash_canonico({k: v for k, v in dados.items() if k != "linha_origem"})
    if existente is None:
        db.add(model(**dados, criado_em=agora, sincronizado_em=agora, alterado_em=agora))
        contadores["inseridos"] += 1
        return

    alteracoes: dict[str, tuple[Any, Any]] = {}
    for campo in campos_negocio:
        antigo = getattr(existente, campo)
        novo = dados[campo]
        if not _equivalente(antigo, novo):
            alteracoes[campo] = (antigo, novo)

    existente.sincronizado_em = agora
    existente.arquivo_origem = dados["arquivo_origem"]
    existente.ano_origem = dados["ano_origem"]
    existente.linha_origem = dados["linha_origem"]
    existente.hash_origem = dados["hash_origem"]

    if not alteracoes:
        contadores["inalterados"] += 1
        return

    for campo, (_, novo) in alteracoes.items():
        setattr(existente, campo, novo)
    existente.alterado_em = agora
    contadores["atualizados"] += 1
    for campo, (antigo, novo) in alteracoes.items():
        db.add(
            HistoricoAlteracaoCampo(
                entidade=entidade,
                entidade_id=existente.id,
                companhia_id=dados.get("companhia_id"),
                campo=campo,
                valor_anterior=None if antigo is None else str(antigo),
                valor_novo=None if novo is None else str(novo),
                alterado_em=agora,
                execucao_sincronizacao_id=execucao_id,
                arquivo_origem=dados["arquivo_origem"],
                ano_origem=dados["ano_origem"],
            )
        )


def _arquivos_fre_mvp(ano: int) -> dict[str, str]:
    return {
        f"fre_cia_aberta_{ano}.csv": "documentos",
        f"fre_cia_aberta_auditor_{ano}.csv": "auditores",
        f"fre_cia_aberta_capital_social_{ano}.csv": "capital_social",
        f"fre_cia_aberta_posicao_acionaria_{ano}.csv": "posicao_acionaria",
        f"fre_cia_aberta_remuneracao_total_orgao_{ano}.csv": "remuneracao_total_orgao",
        f"fre_cia_aberta_empregado_posicao_declaracao_genero_{ano}.csv": "empregado_posicao_genero",
    }


def _arquivos_fre_opcionais(ano: int) -> set[str]:
    return {f"fre_cia_aberta_empregado_posicao_declaracao_genero_{ano}.csv"}


def sincronizar_fre(db: Session, ano: int, task_id: str | None = None) -> dict[str, Any]:
    if db.query(Companhia).count() == 0:
        raise ValueError("cadastro_companhias_nao_ingestado")

    settings = get_settings()
    arquivo_zip = f"fre_cia_aberta_{ano}.zip"
    url = f"{settings.cvm_base_url}/CIA_ABERTA/DOC/FRE/DADOS/{arquivo_zip}"
    execucao = ExecucaoSincronizacao(
        tipo_fonte="fre",
        ano=ano,
        id_tarefa=task_id,
        arquivo=arquivo_zip,
        url=url,
        status="em_execucao",
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    try:
        resposta = httpx.get(url, timeout=300)
        resposta.raise_for_status()
        payload = resposta.content
        hash_arquivo = hashlib.sha256(payload).hexdigest()
        execucao.hash_arquivo = hash_arquivo

        anterior = db.scalar(
            select(ExecucaoSincronizacao).where(
                ExecucaoSincronizacao.tipo_fonte == "fre",
                ExecucaoSincronizacao.ano == ano,
                ExecucaoSincronizacao.hash_arquivo == hash_arquivo,
                ExecucaoSincronizacao.status == "sucesso",
                ExecucaoSincronizacao.id != execucao.id,
            )
        )
        if anterior is not None:
            execucao.status = "sem_alteracao"
            execucao.finalizada_em = _agora()
            db.commit()
            return {"execucao_id": str(execucao.id), "status": "sem_alteracao"}

        arquivos = _arquivos_fre_mvp(ano)
        arquivos_opcionais = _arquivos_fre_opcionais(ano)
        contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
        with zipfile.ZipFile(io.BytesIO(payload)) as zip_ref:
            nomes = set(zip_ref.namelist())
            faltando = sorted(set(arquivos.keys()) - nomes - arquivos_opcionais)
            if faltando:
                raise ValueError(f"arquivo_nao_esperado_ausente: {','.join(faltando)}")

            for arquivo_csv, tipo in arquivos.items():
                if arquivo_csv not in nomes:
                    continue
                with zip_ref.open(arquivo_csv) as arquivo_handle:
                    texto = _decode_csv(arquivo_handle.read())
                leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
                vistos: set[tuple[Any, ...]] = set()

                for linha_origem, linha in enumerate(leitor, start=2):
                    contadores["lidas"] += 1
                    try:
                        if tipo == "documentos":
                            cnpj_companhia = normalizar_cnpj(str(linha.get("CNPJ_CIA", "")))
                            codigo_cvm = normalizar_inteiro(linha.get("CD_CVM"))
                            data_referencia = normalizar_data(linha.get("DT_REFER"))
                            versao = normalizar_inteiro(linha.get("VERSAO"))
                            id_documento = normalizar_inteiro(linha.get("ID_DOC"))
                            if data_referencia is None or versao is None or id_documento is None:
                                raise ValueError("campo_obrigatorio_ausente")
                            dados = {
                                "cnpj_companhia": cnpj_companhia,
                                "codigo_cvm": codigo_cvm,
                                "data_referencia": data_referencia,
                                "versao": versao,
                                "denominacao_companhia": normalizar_texto(linha.get("DENOM_CIA")),
                                "categoria_documento": normalizar_texto(linha.get("CATEG_DOC")),
                                "id_documento": id_documento,
                                "data_recebimento": normalizar_data(linha.get("DT_RECEB")),
                                "link_documento": normalizar_texto(linha.get("LINK_DOC")),
                                "arquivo_origem": arquivo_csv,
                                "ano_origem": ano,
                                "linha_origem": linha_origem,
                            }
                            chave = (id_documento, versao, data_referencia)
                        else:
                            cnpj_companhia = normalizar_cnpj(str(linha.get("CNPJ_Companhia", "")))
                            codigo_cvm = None
                            data_referencia = normalizar_data(linha.get("Data_Referencia"))
                            versao = normalizar_inteiro(linha.get("Versao"))
                            id_documento = normalizar_inteiro(linha.get("ID_Documento"))
                            if data_referencia is None or versao is None or id_documento is None:
                                raise ValueError("campo_obrigatorio_ausente")

                            if tipo == "auditores":
                                id_auditor = normalizar_inteiro(linha.get("ID_Auditor"))
                                if id_auditor is None:
                                    raise ValueError("campo_obrigatorio_ausente")
                                dados = {
                                    "cnpj_companhia": cnpj_companhia,
                                    "data_referencia": data_referencia,
                                    "versao": versao,
                                    "id_documento": id_documento,
                                    "nome_companhia": normalizar_texto(linha.get("Nome_Companhia")),
                                    "id_auditor": id_auditor,
                                    "auditor": normalizar_texto(linha.get("Auditor")),
                                    "cpf_auditor": _digitos(linha.get("CPF_Auditor")),
                                    "cnpj_auditor": (
                                        normalizar_cnpj(str(linha.get("CNPJ_Auditor")))
                                        if normalizar_texto(linha.get("CNPJ_Auditor"))
                                        else None
                                    ),
                                    "codigo_cvm_auditor": normalizar_inteiro(linha.get("Codigo_CVM_Auditor")),
                                    "tipo_origem_auditor": normalizar_texto(linha.get("Tipo_Origem_Auditor")),
                                    "data_inicio_contratacao": normalizar_data(linha.get("Data_Inicio_Contratacao")),
                                    "data_fim_contratacao": normalizar_data(linha.get("Data_Fim_Contratacao")),
                                    "data_inicio_prestacao_servico": normalizar_data(
                                        linha.get("Data_Inicio_Prestacao_Servico")
                                    ),
                                    "servico_contratado": normalizar_texto(linha.get("Servico_Contratado")),
                                    "remuneracao_auditor": normalizar_decimal_cvm(linha.get("Remuneracao_Auditor")),
                                    "justificativa_substituicao": normalizar_texto(
                                        linha.get("Justificativa_Substituicao")
                                    ),
                                    "razao_apresentada": normalizar_texto(linha.get("Razao_Apresentada")),
                                    "arquivo_origem": arquivo_csv,
                                    "ano_origem": ano,
                                    "linha_origem": linha_origem,
                                }
                                chave = (id_documento, versao, data_referencia, cnpj_companhia, id_auditor)
                            elif tipo == "capital_social":
                                id_capital_social = normalizar_inteiro(linha.get("ID_Capital_Social"))
                                if id_capital_social is None:
                                    raise ValueError("campo_obrigatorio_ausente")
                                dados = {
                                    "cnpj_companhia": cnpj_companhia,
                                    "data_referencia": data_referencia,
                                    "versao": versao,
                                    "id_documento": id_documento,
                                    "nome_companhia": normalizar_texto(linha.get("Nome_Companhia")),
                                    "id_capital_social": id_capital_social,
                                    "tipo_capital": normalizar_texto(linha.get("Tipo_Capital")),
                                    "data_autorizacao_aprovacao": normalizar_data(
                                        linha.get("Data_Autorizacao_Aprovacao")
                                    ),
                                    "valor_capital": normalizar_decimal_cvm(linha.get("Valor_Capital")),
                                    "prazo_integralizacao": normalizar_texto(linha.get("Prazo_Integralizacao")),
                                    "quantidade_acoes_ordinarias": normalizar_decimal_cvm(
                                        linha.get("Quantidade_Acoes_Ordinarias")
                                    ),
                                    "quantidade_acoes_preferenciais": normalizar_decimal_cvm(
                                        linha.get("Quantidade_Acoes_Preferenciais")
                                    ),
                                    "quantidade_total_acoes": normalizar_decimal_cvm(
                                        linha.get("Quantidade_Total_Acoes")
                                    ),
                                    "arquivo_origem": arquivo_csv,
                                    "ano_origem": ano,
                                    "linha_origem": linha_origem,
                                }
                                chave = (id_documento, versao, data_referencia, cnpj_companhia, id_capital_social)
                            elif tipo == "posicao_acionaria":
                                id_acionista = normalizar_inteiro(linha.get("ID_Acionista"))
                                if id_acionista is None:
                                    raise ValueError("campo_obrigatorio_ausente")
                                dados = {
                                    "cnpj_companhia": cnpj_companhia,
                                    "data_referencia": data_referencia,
                                    "versao": versao,
                                    "id_documento": id_documento,
                                    "nome_companhia": normalizar_texto(linha.get("Nome_Companhia")),
                                    "id_acionista": id_acionista,
                                    "acionista": normalizar_texto(linha.get("Acionista")),
                                    "tipo_pessoa_acionista": normalizar_texto(linha.get("Tipo_Pessoa_Acionista")),
                                    "cpf_cnpj_acionista": _digitos(linha.get("CPF_CNPJ_Acionista")),
                                    "id_acionista_relacionado": normalizar_inteiro(
                                        linha.get("ID_Acionista_Relacionado")
                                    ),
                                    "acionista_relacionado": normalizar_texto(linha.get("Acionista_Relacionado")),
                                    "tipo_pessoa_acionista_relacionado": normalizar_texto(
                                        linha.get("Tipo_Pessoa_Acionista_Relacionado")
                                    ),
                                    "cpf_cnpj_acionista_relacionado": _digitos(
                                        linha.get("CPF_CNPJ_Acionista_Relacionado")
                                    ),
                                    "quantidade_acao_ordinaria_circulacao": normalizar_decimal_cvm(
                                        linha.get("Quantidade_Acao_Ordinaria_Circulacao")
                                    ),
                                    "percentual_acao_ordinaria_circulacao": normalizar_decimal_cvm(
                                        linha.get("Percentual_Acao_Ordinaria_Circulacao")
                                    ),
                                    "quantidade_acao_preferencial_circulacao": normalizar_decimal_cvm(
                                        linha.get("Quantidade_Acao_Preferencial_Circulacao")
                                    ),
                                    "percentual_acao_preferencial_circulacao": normalizar_decimal_cvm(
                                        linha.get("Percentual_Acao_Preferencial_Circulacao")
                                    ),
                                    "quantidade_total_acoes_circulacao": normalizar_decimal_cvm(
                                        linha.get("Quantidade_Total_Acoes_Circulacao")
                                    ),
                                    "percentual_total_acoes_circulacao": normalizar_decimal_cvm(
                                        linha.get("Percentual_Total_Acoes_Circulacao")
                                    ),
                                    "nacionalidade": normalizar_texto(linha.get("Nacionalidade")),
                                    "sigla_uf": normalizar_texto(linha.get("Sigla_UF")),
                                    "residente_exterior": _normalizar_booleano(linha.get("Residente_Exterior")),
                                    "representante_legal": normalizar_texto(linha.get("Representante_Legal")),
                                    "tipo_pessoa_representante_legal": normalizar_texto(
                                        linha.get("Tipo_Pessoa_Representante_Legal")
                                    ),
                                    "cpf_cnpj_representante_legal": _digitos(
                                        linha.get("CPF_CNPJ_Representante_legal")
                                    ),
                                    "data_composicao_capital_social": normalizar_data(
                                        linha.get("Data_Composicao_Capital_Social")
                                    ),
                                    "data_ultima_alteracao": normalizar_data(linha.get("Data_Ultima_Alteracao")),
                                    "acionista_controlador": _normalizar_booleano(linha.get("Acionista_Controlador")),
                                    "participante_acordo_acionistas": _normalizar_booleano(
                                        linha.get("Participante_Acordo_Acionistas")
                                    ),
                                    "arquivo_origem": arquivo_csv,
                                    "ano_origem": ano,
                                    "linha_origem": linha_origem,
                                }
                                chave = (id_documento, versao, data_referencia, cnpj_companhia, id_acionista)
                            elif tipo == "remuneracao_total_orgao":
                                orgao = normalizar_texto(linha.get("Orgao_Administracao"))
                                dados = {
                                    "cnpj_companhia": cnpj_companhia,
                                    "data_referencia": data_referencia,
                                    "versao": versao,
                                    "id_documento": id_documento,
                                    "nome_companhia": normalizar_texto(linha.get("Nome_Companhia")),
                                    "data_inicio_exercicio_social": normalizar_data(
                                        linha.get("Data_Inicio_Exercicio_Social")
                                    ),
                                    "data_fim_exercicio_social": normalizar_data(
                                        linha.get("Data_Fim_Exercicio_Social")
                                    ),
                                    "total_remuneracao": normalizar_decimal_cvm(linha.get("Total_Remuneracao")),
                                    "orgao_administracao": orgao,
                                    "numero_membros": normalizar_inteiro(linha.get("Numero_Membros")),
                                    "total_remuneracao_orgao": normalizar_decimal_cvm(
                                        linha.get("Total_Remuneracao_Orgao")
                                    ),
                                    "numero_membros_remunerados": normalizar_inteiro(
                                        linha.get("Numero_Membros_Remunerados")
                                    ),
                                    "salario": normalizar_decimal_cvm(linha.get("Salario")),
                                    "beneficios_diretos_indiretos": normalizar_decimal_cvm(
                                        linha.get("Beneficios_Diretos_Indiretos")
                                    ),
                                    "participacoes_comites": normalizar_decimal_cvm(linha.get("Participacoes_Comites")),
                                    "outros_valores_fixos": normalizar_decimal_cvm(linha.get("Outros_Valores_Fixos")),
                                    "descricao_outros_remuneracoes_fixas": normalizar_texto(
                                        linha.get("Descricao_Outros_Remuneracoes_Fixas")
                                    ),
                                    "bonus": normalizar_decimal_cvm(linha.get("Bonus")),
                                    "participacao_resultados": normalizar_decimal_cvm(
                                        linha.get("Participacao_Resultados")
                                    ),
                                    "participacao_reunioes": normalizar_decimal_cvm(linha.get("Participacao_Reunioes")),
                                    "outros_valores_variaveis": normalizar_decimal_cvm(
                                        linha.get("Outros_Valores_Variaveis")
                                    ),
                                    "comissoes": normalizar_decimal_cvm(linha.get("Comissoes")),
                                    "descricao_outros_remuneracoes_variaveis": normalizar_texto(
                                        linha.get("Descricao_Outros_Remuneracoes_Variaveis")
                                    ),
                                    "pos_emprego": normalizar_decimal_cvm(linha.get("Pos_emprego")),
                                    "cessacao_cargo": normalizar_decimal_cvm(linha.get("Cessacao_Cargo")),
                                    "baseada_acoes": normalizar_decimal_cvm(linha.get("Baseada_Acoes")),
                                    "observacao": normalizar_texto(linha.get("Observacao")),
                                    "arquivo_origem": arquivo_csv,
                                    "ano_origem": ano,
                                    "linha_origem": linha_origem,
                                }
                                chave = (
                                    id_documento,
                                    versao,
                                    data_referencia,
                                    cnpj_companhia,
                                    orgao,
                                    dados["data_inicio_exercicio_social"],
                                    dados["data_fim_exercicio_social"],
                                )
                            else:
                                posicao = normalizar_texto(linha.get("Posicao"))
                                if posicao is None:
                                    raise ValueError("campo_obrigatorio_ausente")
                                dados = {
                                    "cnpj_companhia": cnpj_companhia,
                                    "data_referencia": data_referencia,
                                    "versao": versao,
                                    "id_documento": id_documento,
                                    "nome_companhia": normalizar_texto(linha.get("Nome_Companhia")),
                                    "posicao": posicao,
                                    "quantidade_feminino": normalizar_inteiro(linha.get("Quantidade_Feminino")),
                                    "quantidade_masculino": normalizar_inteiro(linha.get("Quantidade_Masculino")),
                                    "quantidade_nao_binario": normalizar_inteiro(linha.get("Quantidade_Nao_Binario")),
                                    "quantidade_outros": normalizar_inteiro(linha.get("Quantidade_Outros")),
                                    "quantidade_sem_resposta": normalizar_inteiro(
                                        linha.get("Quantidade_Sem_Resposta")
                                    ),
                                    "arquivo_origem": arquivo_csv,
                                    "ano_origem": ano,
                                    "linha_origem": linha_origem,
                                }
                                chave = (id_documento, versao, data_referencia, cnpj_companhia, posicao)

                    except Exception as exc:
                        _registrar_quarentena(
                            db,
                            execucao_id=execucao.id,
                            arquivo_origem=arquivo_csv,
                            ano_origem=ano,
                            linha_origem=linha_origem,
                            motivo=f"normalizacao_invalida: {exc}",
                            dados_originais=linha,
                        )
                        contadores["rejeitados"] += 1
                        continue

                    if chave in vistos:
                        _registrar_quarentena(
                            db,
                            execucao_id=execucao.id,
                            arquivo_origem=arquivo_csv,
                            ano_origem=ano,
                            linha_origem=linha_origem,
                            motivo="chave_natural_duplicada_no_arquivo",
                            dados_originais=linha,
                        )
                        contadores["rejeitados"] += 1
                        continue
                    vistos.add(chave)

                    companhia = _resolver_companhia(db, cnpj_companhia, codigo_cvm)
                    if companhia is None:
                        _registrar_quarentena(
                            db,
                            execucao_id=execucao.id,
                            arquivo_origem=arquivo_csv,
                            ano_origem=ano,
                            linha_origem=linha_origem,
                            motivo="companhia_nao_encontrada",
                            dados_originais=linha,
                        )
                        contadores["rejeitados"] += 1
                        continue

                    dados["companhia_id"] = companhia.id
                    if tipo == "documentos":
                        _upsert(
                            db,
                            model=FreDocumento,
                            entidade="fre_documentos",
                            campos_chave=("id_documento", "versao", "data_referencia"),
                            campos_negocio={
                                "companhia_id",
                                "cnpj_companhia",
                                "codigo_cvm",
                                "data_referencia",
                                "versao",
                                "denominacao_companhia",
                                "categoria_documento",
                                "id_documento",
                                "data_recebimento",
                                "link_documento",
                            },
                            dados=dados,
                            execucao_id=execucao.id,
                            contadores=contadores,
                        )
                    elif tipo == "auditores":
                        _upsert(
                            db,
                            model=FreAuditor,
                            entidade="fre_auditores",
                            campos_chave=(
                                "id_documento",
                                "versao",
                                "data_referencia",
                                "cnpj_companhia",
                                "id_auditor",
                            ),
                            campos_negocio=set(dados.keys())
                            - {"arquivo_origem", "ano_origem", "linha_origem", "hash_origem"},
                            dados=dados,
                            execucao_id=execucao.id,
                            contadores=contadores,
                        )
                    elif tipo == "capital_social":
                        _upsert(
                            db,
                            model=FreCapitalSocial,
                            entidade="fre_capital_social",
                            campos_chave=(
                                "id_documento",
                                "versao",
                                "data_referencia",
                                "cnpj_companhia",
                                "id_capital_social",
                            ),
                            campos_negocio=set(dados.keys())
                            - {"arquivo_origem", "ano_origem", "linha_origem", "hash_origem"},
                            dados=dados,
                            execucao_id=execucao.id,
                            contadores=contadores,
                        )
                    elif tipo == "posicao_acionaria":
                        _upsert(
                            db,
                            model=FrePosicaoAcionaria,
                            entidade="fre_posicoes_acionarias",
                            campos_chave=(
                                "id_documento",
                                "versao",
                                "data_referencia",
                                "cnpj_companhia",
                                "id_acionista",
                            ),
                            campos_negocio=set(dados.keys())
                            - {"arquivo_origem", "ano_origem", "linha_origem", "hash_origem"},
                            dados=dados,
                            execucao_id=execucao.id,
                            contadores=contadores,
                        )
                    elif tipo == "remuneracao_total_orgao":
                        _upsert(
                            db,
                            model=FreRemuneracaoTotalOrgao,
                            entidade="fre_remuneracoes_totais_orgaos",
                            campos_chave=(
                                "id_documento",
                                "versao",
                                "data_referencia",
                                "cnpj_companhia",
                                "orgao_administracao",
                                "data_inicio_exercicio_social",
                                "data_fim_exercicio_social",
                            ),
                            campos_negocio=set(dados.keys())
                            - {"arquivo_origem", "ano_origem", "linha_origem", "hash_origem"},
                            dados=dados,
                            execucao_id=execucao.id,
                            contadores=contadores,
                        )
                    else:
                        _upsert(
                            db,
                            model=FreEmpregadoPosicaoGenero,
                            entidade="fre_empregados_posicao_genero",
                            campos_chave=(
                                "id_documento",
                                "versao",
                                "data_referencia",
                                "cnpj_companhia",
                                "posicao",
                            ),
                            campos_negocio=set(dados.keys())
                            - {"arquivo_origem", "ano_origem", "linha_origem", "hash_origem"},
                            dados=dados,
                            execucao_id=execucao.id,
                            contadores=contadores,
                        )

        execucao.total_linhas_lidas = contadores["lidas"]
        execucao.total_inseridos = contadores["inseridos"]
        execucao.total_atualizados = contadores["atualizados"]
        execucao.total_inalterados = contadores["inalterados"]
        execucao.total_rejeitados = contadores["rejeitados"]
        execucao.status = "sucesso"
        execucao.finalizada_em = _agora()
        db.commit()
        return {
            "execucao_id": str(execucao.id),
            "status": "sucesso",
            "total_linhas_lidas": contadores["lidas"],
            "total_inseridos": contadores["inseridos"],
            "total_atualizados": contadores["atualizados"],
            "total_inalterados": contadores["inalterados"],
            "total_rejeitados": contadores["rejeitados"],
        }
    except Exception as exc:
        db.rollback()
        execucao_erro = db.get(ExecucaoSincronizacao, execucao.id)
        if execucao_erro is not None:
            execucao_erro.status = "falha"
            execucao_erro.mensagem_erro = str(exc)
            execucao_erro.finalizada_em = _agora()
            db.commit()
        raise
