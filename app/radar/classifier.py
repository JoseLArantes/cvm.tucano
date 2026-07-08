import re
from dataclasses import dataclass

from app.radar.models import RadarRelevance


@dataclass(frozen=True)
class TagRule:
    tag: str
    terms: tuple[str, ...]


TAG_RULES: tuple[TagRule, ...] = (
    TagRule("normativa", ("resolucao", "instrução", "instrucao", "deliberação", "deliberacao", "parecer de orientação", "parecer de orientacao", "audiência pública", "audiencia publica", "consulta pública", "consulta publica")),
    TagRule("dados_abertos", ("portal de dados", "dados abertos", "dataset", "arquivo", "csv", "zip")),
    TagRule("layout", ("layout", "leiaute", "coluna", "campo", "schema", "estrutura", "dicionario", "dicionário")),
    TagRule("atividade_sancionadora", ("termo de compromisso", "multa", "sancionador", "inabilitação", "inabilitacao", "suspensão", "suspensao")),
    TagRule("mercado_capitais", ("oferta pública", "oferta publica", "intermediário", "intermediario", "companhia aberta", "fundo", "valores mobiliários", "valores mobiliarios")),
    TagRule("agenda_evento", ("agenda", "evento", "curso", "treinamento", "reunião", "reuniao")),
)


def classify_text(text: str, title: str = "") -> tuple[list[str], RadarRelevance, list[str]]:
    normalized = text.lower()
    tags: list[str] = []
    signals: list[str] = []
    for rule in TAG_RULES:
        matches = [term for term in rule.terms if term in normalized]
        if matches:
            tags.append(rule.tag)
            signals.extend(f"{rule.tag}:{term}" for term in matches[:3])

    relevance: RadarRelevance = "normal"
    if any(tag in tags for tag in ("layout", "normativa", "atividade_sancionadora")):
        relevance = "alta"
    elif any(tag in tags for tag in ("dados_abertos", "mercado_capitais")):
        relevance = "media"
    elif "agenda_evento" in tags:
        relevance = "baixa"

    if "resolução" in title.lower() or "resolucao" in title.lower():
        relevance = "media"
        if "resolução" not in tags:
            tags.append("resolução")

    resolucao_numbers = re.findall(r"\bresolu[cç][aã]o\s+(?:n[oºª\.]\s*)?(\d+)\b", f"{title} {text}", re.IGNORECASE)
    for num in resolucao_numbers:
        if num not in tags:
            tags.append(num)

    return sorted(set(tags)), relevance, sorted(set(signals))

