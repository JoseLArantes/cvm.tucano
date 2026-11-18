from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.comum import BrazilianDateTime, CanonicalDecimal, Paginacao


class EvidenciaContratual(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fonte: Literal["FRE", "IPE", "DFP", "ITR", "documento_externo", "revisao"] = Field(description="Tipo de fonte que sustenta o fato registrado.")
    formulario: str | None = Field(default=None, description="Formulário de origem, por exemplo FRE, IPE, DFP ou ITR.")
    documento_id: int | None = Field(default=None, description="Identificador do documento na fonte, quando aplicável.")
    versao: int | None = Field(default=None, ge=1, description="Versão do documento ou da evidência revisada.")
    url: str | None = Field(default=None, description="URL direta ou autorizada que resolve a evidência original.")
    secao: str | None = Field(default=None, description="Seção, item, cláusula ou tabela da fonte.")
    pagina: int | None = Field(default=None, ge=1, description="Página do documento original, iniciando em 1.")
    linha: int | None = Field(default=None, ge=1, description="Linha de CSV/planilha de origem, iniciando em 1.")
    hash: str | None = Field(default=None, description="Hash do conteúdo consultado para fixar a versão da evidência.")
    descricao: str | None = Field(default=None, description="Contexto curto do localizador ou da evidência.")

    @model_validator(mode="after")
    def validar_localizador(self) -> "EvidenciaContratual":
        tem_localizador_documental = self.documento_id is not None and any((self.secao, self.pagina, self.linha))
        tem_localizador_hash = bool(self.url and self.hash)
        if not tem_localizador_documental and not tem_localizador_hash:
            raise ValueError("evidencia_requer_localizador_documental_ou_url_e_hash")
        return self


class AcordoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: Literal["acordo"] = Field(description="Discriminador do payload de acordo, contrato ou emissão.")
    instrumento: str | None = Field(default=None, description="Tipo/denominação do instrumento, por exemplo debênture, CCB ou financiamento.")
    serie: str | None = Field(default=None, description="Série da emissão ou do instrumento, se divulgada.")
    emissor_cnpj: str = Field(description="CNPJ do emissor que deve corresponder à companhia da rota.")
    devedor_cnpj: str | None = Field(default=None, description="CNPJ do devedor contratual quando diferente do emissor.")
    garantidores_cnpj: list[str] = Field(default_factory=list, description="CNPJs dos garantidores identificados na fonte.")
    moeda: str | None = Field(default=None, description="Moeda contratual no código informado pela fonte.")
    escopo_divida: str | None = Field(default=None, description="Escopo da exposição, incluindo individual, consolidado ou entidade específica.")
    responsavel_testes: str | None = Field(default=None, description="Parte responsável por apurar ou certificar os testes contratuais.")
    vigencia_inicio: date | None = Field(default=None, description="Início de vigência conhecido do acordo.")
    vigencia_fim: date | None = Field(default=None, description="Fim de vigência conhecido do acordo.")
    clausula: str | None = Field(default=None, description="Texto ou transcrição revisada da cláusula contratual relevante.")


class CovenantPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: Literal["covenant"] = Field(description="Discriminador do payload de cláusula financeira.")
    covenant_id: str = Field(description="ID estável do covenant; igual a `registro_id`.")
    definicao_financeira: str = Field(description="Fórmula e definição contratual, incluindo os termos ajustados.")
    escopo: str = Field(description="Entidade e base contábil consideradas no teste.")
    contas_especificadas: list[str] = Field(default_factory=list, description="Contas explicitamente incluídas ou excluídas pelo contrato.")
    ajustes: list[str] = Field(default_factory=list, description="Ajustes à fórmula, como itens extraordinários ou pro forma.")
    unidade: str = Field(description="Unidade do limite e do valor aferido, por exemplo vezes ou BRL.")
    janela_agregacao: str = Field(description="Janela temporal contratual usada na medição.")
    comparador: Literal["lt", "lte", "gt", "gte", "eq"] = Field(description="Operador exato do teste: menor, menor/igual, maior, maior/igual ou igual.")
    limite: CanonicalDecimal = Field(description="Limite numérico preservado como decimal canônico.")
    datas_teste: list[date] = Field(default_factory=list, description="Datas de teste previstas no texto conhecido.")
    proxima_data_teste: date | None = Field(default=None, description="Próxima data de teste divulgada.")


class CovenantTestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: Literal["covenant_test"] = Field(description="Discriminador do payload de teste datado.")
    covenant_id: str = Field(description="ID do covenant testado.")
    data_teste: date = Field(description="Data à qual a medição contratual se aplica.")
    comparador: Literal["lt", "lte", "gt", "gte", "eq"] = Field(description="Operador aplicado à medição e ao limite.")
    limite: CanonicalDecimal = Field(description="Limite contratual vigente nesta revisão do teste.")
    valor_aferido: CanonicalDecimal | None = Field(default=None, description="Valor medido com escopo e unidade conforme o contrato.")
    resultado_calculado: Literal["passou", "falhou", "indisponivel"] = Field(default="indisponivel", description="Comparação aritmética recalculada pelo serviço; o valor recebido no POST é substituído.")
    resultado_verificado: Literal["passou", "falhou", "indisponivel"] = Field(default="indisponivel", description="Conclusão independente revisada, sustentada por revisor e evidência versionada.")
    proxima_data_teste: date | None = Field(default=None, description="Próxima data de teste informada com o resultado.")


class BreachPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: Literal["breach"] = Field(description="Discriminador do incidente contratual.")
    covenant_id: str = Field(description="ID do covenant associado à violação.")
    test_id: str = Field(description="ID do teste que originou o incidente.")
    status: Literal["breach", "disputed", "cured", "withdrawn"] = Field(description="Estado revisado do incidente, preservado como evento histórico.")
    prazo_cura_inicio: date | None = Field(default=None, description="Início do prazo contratual de cura, quando divulgado.")
    prazo_cura_fim: date | None = Field(default=None, description="Fim do prazo contratual de cura, quando divulgado.")
    retirada_em: date | None = Field(default=None, description="Data efetiva de retirada da declaração de violação, se publicada.")
    descricao: str | None = Field(default=None, description="Resumo factual do incidente e sua situação.")


class WaiverPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: Literal["waiver"] = Field(description="Discriminador do waiver ou dispensa contratual.")
    covenant_id: str = Field(description="ID do covenant coberto pela dispensa.")
    test_ids_cobertos: list[str] = Field(min_length=1, description="IDs exatos dos testes aos quais a dispensa se aplica.")
    inicio_vigencia: date = Field(description="Primeiro dia em que o waiver cobre os testes indicados.")
    fim_vigencia: date | None = Field(default=None, description="Último dia de cobertura, inclusivo; nulo quando não informado.")
    condicoes: list[str] = Field(default_factory=list, description="Condições contratuais para concessão ou manutenção do waiver.")
    implementado: bool = Field(default=False, description="Indica que a implementação do waiver foi confirmada.")
    implementado_em: date | None = Field(default=None, description="Data de implementação; obrigatória quando `implementado=true`.")
    retirado_em: date | None = Field(default=None, description="Data efetiva de retirada publicada; não apaga cobertura histórica anterior.")

    @model_validator(mode="after")
    def validar_implementacao(self) -> "WaiverPayload":
        if self.implementado and self.implementado_em is None:
            raise ValueError("waiver_implementado_requer_data")
        return self


class CashLegPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: Literal["cash_leg"] = Field(description="Discriminador de parcela contratual individual.")
    parcela_id: str = Field(description="ID estável da parcela; igual a `registro_id`.")
    vencimento_original: date = Field(description="Data contratual original de pagamento.")
    valor: CanonicalDecimal = Field(description="Valor da parcela, sem conversão de moeda.")
    moeda: str = Field(description="Código da moeda em que o valor foi contratado.")
    descricao: str | None = Field(default=None, description="Descrição ou classificação da parcela.")


class MaturityChangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: Literal["maturity_change"] = Field(description="Discriminador de alteração de datas de pagamento.")
    cash_leg_ids: list[str] = Field(min_length=1, description="IDs das parcelas originais afetadas pela revisão.")
    vencimento_original: date = Field(description="Data anterior à alteração, conforme a evidência.")
    vencimento_novo: date = Field(description="Nova data contratual informada.")
    valor_afetado: CanonicalDecimal | None = Field(default=None, description="Valor associado à alteração, se divulgado.")
    condicoes: list[str] = Field(default_factory=list, description="Condições e gatilhos documentados para efetivação.")
    base_aceleracao: Literal["aditamento", "cross_default", "decisao"] = Field(description="Base documental que sustenta a mudança de vencimento.")
    cross_default_id: str | None = Field(default=None, description="ID do gatilho cross-default; obrigatório quando essa for a base.")


class CrossDefaultPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: Literal["cross_default"] = Field(description="Discriminador de vínculo de cross-default.")
    acordo_origem_id: str = Field(description="ID do acordo em que ocorreu o gatilho inicial.")
    acordo_afetado_id: str = Field(description="ID do acordo que pode receber efeito de cross-default.")
    condicao_contratual: str = Field(description="Texto da condição e do vínculo entre acordos.")
    gatilho_confirmado: bool = Field(default=False, description="Indica confirmação revisada do gatilho previsto na cláusula.")
    condicoes_satisfeitas: bool = Field(default=False, description="Indica confirmação revisada das demais condições para ativação.")


class ProceedingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: Literal["proceeding"] = Field(description="Discriminador de processo, recuperação, falência ou intervenção.")
    event_id: str = Field(description="ID estável do ato publicado; deve corresponder ao `registro_id`.")
    case_id: str = Field(description="ID estável do processo/caso que pode agrupar vários atos publicados.")
    orgao: str = Field(description="Tribunal, regulador ou autoridade responsável pelo ato publicado.")
    entidade_afetada_cnpj: str = Field(description="CNPJ da entidade à qual o ato ou processo se refere.")
    etapa: Literal["peticao", "admissao_ou_decisao", "intervencao_confirmada", "encerramento"] = Field(description="Estágio publicado, sem inferir estágio processual não divulgado.")
    exposicoes: list[str] = Field(default_factory=list, description="Acordos, instrumentos ou exposições associados ao caso.")
    valor_divulgado: CanonicalDecimal | None = Field(default=None, description="Valor expressamente divulgado no ato.")
    resolucao: str | None = Field(default=None, description="Decisão ou forma de encerramento publicada.")
    eventos_relacionados: list[str] = Field(default_factory=list, description="IDs de outros atos publicados já registrados, ligados ao mesmo caso ou a evento relacionado.")


class CoveragePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: Literal["coverage"] = Field(description="Discriminador de avaliação de cobertura contratual.")
    formulario_referencia: Literal["DFP", "ITR"] = Field(description="Formulário contábil que define a população de dívida comparada.")
    documento_id: int = Field(description="ID do documento DFP/ITR usado na reconciliação.")
    versao: int = Field(ge=1, description="Versão do documento DFP/ITR elegível no corte.")
    data_referencia: date = Field(description="Data de referência do documento de dívida comparável.")
    acordos_divulgados: list[str] = Field(default_factory=list, description="Acordos identificados na fonte financeira de referência.")
    acordos_revisados: list[str] = Field(default_factory=list, description="Acordos efetivamente revisados, com seus termos e fonte.")
    exposicoes_declaradas: CanonicalDecimal | None = Field(default=None, description="Exposição total declarada para a população comparada.")
    exposicoes_reconciliadas: CanonicalDecimal | None = Field(default=None, description="Exposição coberta pelos acordos revisados em escopo comparável.")
    escopos_divergentes: list[str] = Field(default_factory=list, description="Diferenças de escopo que impedem comparação direta.")
    exposicoes_omitidas: list[str] = Field(default_factory=list, description="Exposições sem contrato revisado ou sem termos disponíveis.")
    clausulas_desconhecidas: list[str] = Field(default_factory=list, description="Cláusulas materiais que não puderam ser determinadas.")
    responsavel_lacuna: str | None = Field(default=None, description="Companhia, agente fiduciário ou revisor autorizado que pode resolver as cláusulas desconhecidas.")

    @model_validator(mode="after")
    def validar_responsavel_lacuna(self) -> "CoveragePayload":
        if self.clausulas_desconhecidas and not self.responsavel_lacuna:
            raise ValueError("clausula_desconhecida_requer_responsavel_pela_lacuna")
        return self


PayloadContratual = Annotated[
    AcordoPayload | CovenantPayload | CovenantTestPayload | BreachPayload | WaiverPayload | CashLegPayload | MaturityChangePayload | CrossDefaultPayload | ProceedingPayload | CoveragePayload,
    Field(discriminator="record_type"),
]


def _possui_evidencia_versionada(evidencias: list[EvidenciaContratual]) -> bool:
    return any(
        evidencia.versao is not None
        and (evidencia.documento_id is not None or evidencia.hash is not None)
        for evidencia in evidencias
    )


class RegistroContratualInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registro_id: str = Field(min_length=1, max_length=200, description="ID estável do fato dentro do tipo de registro.")
    revisao: int = Field(ge=1, description="Revisão imutável do registro; conteúdo divergente para a mesma chave retorna 409.")
    acordo_id: str | None = Field(default=None, max_length=200, description="ID do acordo relacionado; obrigatório para registros contratuais vinculados.")
    disponivel_em: date = Field(description="Data em que a evidência se tornou publicamente disponível; governa o replay `as_of`.")
    efetivo_em: date | None = Field(default=None, description="Data em que o efeito contratual ou processual começou, quando conhecida.")
    payload: PayloadContratual = Field(description="Corpo tipado de acordo, covenant, teste, medida, parcela, evento ou cobertura.")
    evidencias: list[EvidenciaContratual] = Field(default_factory=list, description="Localizadores da fonte e sua versão. Todo registro requer ao menos uma evidência.")
    revisor_id: str | None = Field(default=None, description="Identidade do revisor que classificou ou verificou o registro; separada do autor da gravação.")
    rationale: str | None = Field(default=None, max_length=2000, description="Justificativa concisa para normalizações ou decisões de revisão.")

    @model_validator(mode="after")
    def validar_revisao_e_relacoes(self) -> "RegistroContratualInput":
        if not self.evidencias:
            raise ValueError("registro_requer_evidencia_com_localizador")
        if isinstance(self.payload, AcordoPayload) and self.acordo_id != self.registro_id:
            raise ValueError("acordo_id_deve_corresponder_ao_registro_id")
        if isinstance(self.payload, CovenantPayload) and self.payload.covenant_id != self.registro_id:
            raise ValueError("covenant_id_deve_corresponder_ao_registro_id")
        if isinstance(self.payload, CashLegPayload) and self.payload.parcela_id != self.registro_id:
            raise ValueError("parcela_id_deve_corresponder_ao_registro_id")
        if isinstance(self.payload, ProceedingPayload) and self.payload.event_id != self.registro_id:
            raise ValueError("event_id_deve_corresponder_ao_registro_id")
        if isinstance(
            self.payload,
            (CovenantPayload, CovenantTestPayload, BreachPayload, WaiverPayload, CashLegPayload, MaturityChangePayload, CrossDefaultPayload),
        ) and not self.acordo_id:
            raise ValueError("registro_requer_acordo_id")
        if isinstance(self.payload, CovenantTestPayload) and self.payload.resultado_verificado != "indisponivel":
            evidencia_versionada = _possui_evidencia_versionada(self.evidencias)
            if not self.revisor_id or not evidencia_versionada:
                raise ValueError("resultado_verificado_requer_revisor_e_evidencia_versionada")
        if isinstance(self.payload, BreachPayload) and not self.revisor_id:
            raise ValueError("violacao_requer_revisor")
        if isinstance(self.payload, CrossDefaultPayload) and self.payload.gatilho_confirmado and self.payload.condicoes_satisfeitas:
            evidencia_versionada = _possui_evidencia_versionada(self.evidencias)
            if not self.revisor_id or not evidencia_versionada:
                raise ValueError("gatilho_cross_default_requer_revisor_e_evidencia_versionada")
        if isinstance(self.payload, WaiverPayload) and self.payload.implementado:
            if not self.revisor_id or not _possui_evidencia_versionada(self.evidencias):
                raise ValueError("waiver_implementado_requer_revisor_e_evidencia_versionada")
        if isinstance(self.payload, MaturityChangePayload):
            if self.payload.base_aceleracao == "cross_default" and not self.payload.cross_default_id:
                raise ValueError("cross_default_id_obrigatorio")
            if not self.revisor_id or not _possui_evidencia_versionada(self.evidencias):
                raise ValueError("alteracao_vencimento_requer_revisor_e_evidencia_versionada")
        if isinstance(self.payload, CoveragePayload):
            if not self.revisor_id or not _possui_evidencia_versionada(self.evidencias):
                raise ValueError("cobertura_requer_revisor_e_evidencia_versionada")
        return self


class RegistroContratualResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registro_id: str = Field(description="ID estável do registro.")
    revisao: int = Field(description="Revisão consultada, determinada pelo corte e pelo filtro `historico`.")
    acordo_id: str | None = Field(description="ID do acordo relacionado, quando aplicável.")
    disponivel_em: date = Field(description="Data de disponibilidade pública da evidência.")
    efetivo_em: date | None = Field(description="Data efetiva conhecida para o fato ou alteração.")
    payload: PayloadContratual = Field(description="Dados tipados do registro, incluindo conclusão verificada independente do cálculo.")
    evidencias: list[EvidenciaContratual] = Field(description="Localizadores versionados da fonte original.")
    revisor_id: str | None = Field(description="Identidade registrada do revisor, quando fornecida.")
    registrado_por: str = Field(description="Identidade do usuário/token que gravou o lote.")
    rationale: str | None = Field(description="Justificativa de revisão ou normalização.")
    registrado_em: BrazilianDateTime = Field(description="Data e hora de auditoria da gravação no Tucano CVM.")
    calculado_em: date | None = Field(default=None, description="Data do teste usada para a comparação aritmética.")
    resultado_calculado: Literal["passou", "falhou", "indisponivel"] | None = Field(default=None, description="Resultado matemático calculado pelo serviço; indisponível quando falta medida ou o teste ainda não é efetivo no corte.")
    vencimento_efetivo: date | None = Field(default=None, description="Vencimento projetado para uma parcela após aplicar alterações efetivas e disponíveis no corte.")
    waiver_aplicavel: bool = Field(default=False, description="Indica se waiver implementado cobre este teste, sem remover o registro de violação.")
    projecao_aplicada: bool = Field(default=False, description="Indica se a mudança contratual foi aplicada à projeção no corte.")


class LoteRegistrosContratuaisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registros: list[RegistroContratualInput] = Field(min_length=1, max_length=500, description="Registros versionados gravados de forma atômica.")


class LoteRegistrosContratuaisResposta(BaseModel):
    aceitos: int = Field(description="Quantidade de revisões novas persistidas.")
    idempotentes: int = Field(description="Quantidade de revisões repetidas com conteúdo idêntico.")
    registros: list[RegistroContratualResposta] = Field(description="Registros persistidos ou confirmados como idempotentes.")


class ListaRegistrosContratuaisResposta(BaseModel):
    companhia_codigo_cvm: int = Field(description="Código CVM da companhia consultada.")
    as_of: date = Field(description="Corte informacional aplicado à data de disponibilidade dos registros.")
    historico: bool = Field(description="Indica se revisões anteriores disponíveis no corte foram incluídas.")
    dados: list[RegistroContratualResposta] = Field(description="Registros filtrados, ordenados por tipo, ID e revisão.")
    paginacao: Paginacao = Field(description="Total antes do recorte da página e tamanho efetivamente aplicado.")
