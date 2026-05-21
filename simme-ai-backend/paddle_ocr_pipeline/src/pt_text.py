import re


EM_DASH = "\u2014"


DIRECT_REPLACEMENTS = [
    ("Ã¢â‚¬â€", EM_DASH),
    ("ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â", EM_DASH),
    ("CondiÃ§Ãµes", "Condições"),
    ("CondiÃƒÂ§ÃƒÂµes", "Condições"),
    ("DescriÃ§Ã£o", "Descrição"),
    ("DescriÃƒÂ§ÃƒÂ£o", "Descrição"),
    ("MÃ©todo", "Método"),
    ("MÃƒÂ©todo", "Método"),
    ("MÃ©tricas", "Métricas"),
    ("ExtraÃ§Ã£o", "Extração"),
    ("SecÃ§Ãµes", "Secções"),
    ("SecÃƒÂ§ÃƒÂµes", "Secções"),
    ("CalibraÃ§Ã£o", "Calibração"),
    ("Calibracäo", "Calibração"),
    ("Calibracao", "Calibração"),
    ("DesignaÃ§Ã£o", "Designação"),
    ("Designagäo", "Designação"),
    ("Designagao", "Designação"),
    ("InstalaÃ§Ãµes", "Instalações"),
    ("Instalacöes", "Instalações"),
    ("CondiÃ§Ãµes do trabalho realizado", "Condições do trabalho realizado"),
    ("CONDICöES", "CONDIÇÕES"),
    ("DiÃ¢metro", "Diâmetro"),
    ("Diämetro", "Diâmetro"),
    ("Diametro", "Diâmetro"),
    ("PadrÃ£o", "Padrão"),
    ("Padrao", "Padrão"),
    ("NÃ£o", "Não"),
    ("Nao", "Não"),
    ("SÃ©rie", "Série"),
    ("Serie", "Série"),
    ("ResoluÃ§Ã£o", "Resolução"),
    ("Resolugao", "Resolução"),
    ("Resolucao", "Resolução"),
    ("IndicaÃ§Ã£o", "Indicação"),
    ("Indicagao", "Indicação"),
    ("Indicacao", "Indicação"),
    ("AcreditaÃ§Ã£o", "Acreditação"),
    ("Acreditagao", "Acreditação"),
    ("MediÃ§Ã£o", "Medição"),
    ("Medigao", "Medição"),
    ("Descricao", "Descrição"),
    ("Condicoes", "Condições"),
    ("InvestigaciÃ³n", "Investigación"),
    ("Cädiz", "Cádiz"),
    ("Espana", "España"),
    ("Mäquina", "Máquina"),
    ("Nümero", "Número"),
    ("Automacao", "Automação"),
    ("Referéncia", "Referência"),
    ("medices", "medições"),
    ("instalaces", "instalações"),
    ("forca", "força"),
    ("transdutores de forca", "transdutores de força"),
    ("forca verdadeira", "força verdadeira"),
    ("trés", "três"),
]


REGEX_REPLACEMENTS = [
    (r"\bcondices\b", "condições"),
    (r"\bcondic[õo]es\b", "condições"),
    (r"\bdesignagao\b", "designação"),
    (r"\bdesignacao\b", "designação"),
    (r"\bcalibracao\b", "calibração"),
    (r"\binstalacoes\b", "instalações"),
    (r"\binstalaces\b", "instalações"),
    (r"\bresolugao\b", "resolução"),
    (r"\bresolucao\b", "resolução"),
    (r"\bindicagao\b", "indicação"),
    (r"\bindicacao\b", "indicação"),
    (r"\bacreditagao\b", "acreditação"),
    (r"\bmedigao\b", "medição"),
    (r"\bnumero\b", "número"),
    (r"\bmaquina\b", "máquina"),
    (r"\bautomacao\b", "automação"),
    (r"\breferencia\b", "referência"),
    (r"\bforca\b", "força"),
]


def _maybe_fix_double_encoding(text: str) -> str:
    candidate = text
    for encoding in ("latin-1", "cp1252"):
        try:
            decoded = candidate.encode(encoding, errors="strict").decode("utf-8", errors="strict")
        except Exception:
            continue
        if decoded.count("Ã") + decoded.count("Â") < candidate.count("Ã") + candidate.count("Â"):
            candidate = decoded
    return candidate


def repair_portuguese_text(text: str | None) -> str | None:
    if text is None:
        return None
    if not isinstance(text, str):
        return text

    out = _maybe_fix_double_encoding(text)

    for old, new in DIRECT_REPLACEMENTS:
        out = out.replace(old, new)

    for pattern, replacement in REGEX_REPLACEMENTS:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    out = re.sub(r"\s+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def repair_nested_text(value):
    if value is None:
        return None
    if isinstance(value, str):
        return repair_portuguese_text(value)
    if isinstance(value, list):
        return [repair_nested_text(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_nested_text(item) for key, item in value.items()}
    return value
