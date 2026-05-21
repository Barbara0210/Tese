import json
import re
from pathlib import Path
from datetime import datetime
from pt_text import repair_nested_text, repair_portuguese_text

BASE = Path(__file__).resolve().parents[1]

IN_DIR = BASE / "data" / "sections"
OUT_DIR = BASE / "data" / "parsed"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------
# Helpers
# -------------------------
def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_spaces(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"\[region:[^\]]+\]", " ", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    s = repair_portuguese_text(s.strip())
    return s or None


def normalize(s: str | None) -> str:
    if not s:
        return ""
    s = s.upper()
    repl = {
        "Ç": "C",
        "Ã": "A",
        "Á": "A",
        "Â": "A",
        "À": "A",
        "Õ": "O",
        "Ó": "O",
        "Ô": "O",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ú": "U",
        "Ö": "O",
        "Ä": "A",
        "Ü": "U",
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def safe_date(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass
    return s


def split_lines(text: str) -> list[str]:
    out = []
    for ln in (text or "").splitlines():
        stripped = repair_portuguese_text(re.sub(r"\[region:[^\]]+\]", " ", ln).strip())
        if stripped:
            out.append(stripped)
    return out


def truncate_at_section_markers(text: str, markers: list[str]) -> str:
    lines = split_lines(text)
    out = []
    marker_norms = {normalize(marker) for marker in markers}

    for ln in lines:
        if normalize(ln) in marker_norms:
            break
        out.append(ln)

    return "\n".join(out).strip()


def strip_footer_noise(text: str) -> str:
    bad_prefixes = [
        "RUA DOS PLATANOS",
        "RUA CIDADE DO PORTO",
        "ESTRADA DO PACO DO LUMIAR",
        "4100-414 PORTO",
        "4705-086 BRAGA",
        "1649-038 LISBOA",
        "OS RESULTADOS APRESENTADOS REFER",
        "ESTE DOCUMENTO NAO PODE SER REPRODUZIDO",
        "AUTORIZACAO POR ESCRITO DO CATIM",
        "A AUTORIZAGAO POR ESCRITO DO CATIM",
        "S ITENS CALIBRADOS OU ENSAIADOS",
        ": ITENS CALIBRADOS OU ENSAIADOS",
    ]
    out = []
    for ln in split_lines(text):
        n = normalize(ln)
        if any(n.startswith(p) for p in bad_prefixes):
            continue
        out.append(ln)
    return "\n".join(out).strip()


def first_date_in_text(text: str) -> str | None:
    m = re.search(r"\b(20\d{2}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b", text or "")
    return m.group(1) if m else None


def extract_certificate_number(text: str) -> str | None:
    patterns = [
        r"(?i)CERTIFICADO\s*(?:N[º°O\*]?\s*[:\-]?\s*)([A-Z]{1,6}\s*\d{6,}[0-9/\.\-]*)",
        r"\b([A-Z]{2,5}\d{8,}/\d{1,3})\b",
        r"\b([A-Z]{2,5}\s*\d{8,}/\d{1,3})\b",
    ]
    for p in patterns:
        m = re.search(p, text or "")
        if m:
            return re.sub(r"\s+", "", m.group(1).strip())
    return None


def extract_lab_unit(text: str) -> str | None:
    for ln in split_lines(text):
        n = normalize(ln)
        if "LABORATORIO DE METROLOGIA" in n:
            return clean_spaces(ln)
    return None


def extract_lab_name(text: str) -> str | None:
    for ln in split_lines(text):
        if normalize(ln) == "CATIM":
            return "CATIM"
    for ln in split_lines(text):
        if "CENTRO DE APOIO TECNOLOGICO" in normalize(ln):
            return clean_spaces(ln)
    return None


# -------------------------
# Label parsing por linhas
# -------------------------
def canonical_label(line: str) -> str | None:
    n = normalize(line)

    mapping = {
        "NOME": "name",
        "MORADA": "address",

        "DESIGNAGAO": "designation",
        "DESIGNACAO": "designation",
        "DESIGNAÇÃO": "designation",

        "MARCA": "brand",
        "MODELO": "model",

        "N SERIE": "serial_number",
        "N° SERIE": "serial_number",
        "Nº SERIE": "serial_number",
        "NUMERO DE SERIE": "serial_number",

        "ALCANCE": "range",
        "ALCANCE DE MEDICAO": "range",
        "ALCANCE DE MEDIGAO": "range",
        "ALCANCE DE MEDIÇÃO": "range",
        "INTERVALO DE INDICACAO": "range",
        "INTERVALO DE INDICAGAO": "range",
        "INTERVALO DE INDICAÇÃO": "range",
        "INTERVALO DE MEDICAO": "range",
        "INTERVALO DE MEDIÇÃO": "range",

        "RESOLUCAO": "resolution",
        "RESOLUGAO": "resolution",
        "RESOLUÇÃO": "resolution",
        "RESOLUCAO ESTIMADA": "estimated_resolution",
        "RESOLUGAO ESTIMADA": "estimated_resolution",
        "RESOLUÇÃO ESTIMADA": "estimated_resolution",

        "INDICACAO": "indication",
        "INDICAGAO": "indication",
        "INDICAÇÃO": "indication",

        "REF INTERNA": "internal_ref",
        "REF. INTERNA": "internal_ref",
        "REF INTERNA ": "internal_ref",
        "REF INTERNA.": "internal_ref",
        "REF INTERNA:": "internal_ref",
        "REF INTERNA -": "internal_ref",
        "REF INTERNA. ": "internal_ref",
        "REF INTERNA ": "internal_ref",
        "REF INTERNA": "internal_ref",
        "REF INTERNA.": "internal_ref",
        "REF INTERNA:": "internal_ref",
        "REF INTERNA -": "internal_ref",
        "REF INTERNA  ": "internal_ref",
        "REF INTERNA\t": "internal_ref",
        "REF INTERNA\r": "internal_ref",
        "REF INTERNA\n": "internal_ref",
        "REF INTERNA\f": "internal_ref",
        "REF INTERNA\v": "internal_ref",
        "REF INTERNA\b": "internal_ref",
        "REF INTERNA\0": "internal_ref",
        "REF INTERNA\u00A0": "internal_ref",
        "REF INTERNA\u2009": "internal_ref",
        "REF INTERNA\u202F": "internal_ref",
        "REF INTERNA\u3000": "internal_ref",
        "REF INTERNA\uFEFF": "internal_ref",
        "REF INTERNA\u2060": "internal_ref",
        "REF INTERNA\u200B": "internal_ref",
        "REF INTERNA\u200C": "internal_ref",
        "REF INTERNA\u200D": "internal_ref",
        "REF INTERNA\u200E": "internal_ref",
        "REF INTERNA\u200F": "internal_ref",
        "REF INTERNA\u202A": "internal_ref",
        "REF INTERNA\u202B": "internal_ref",
        "REF INTERNA\u202C": "internal_ref",
        "REF INTERNA\u202D": "internal_ref",
        "REF INTERNA\u202E": "internal_ref",
        "REF INTERNA\u2066": "internal_ref",
        "REF INTERNA\u2067": "internal_ref",
        "REF INTERNA\u2068": "internal_ref",
        "REF INTERNA\u2069": "internal_ref",
        "REF INTERNA\u061C": "internal_ref",
        "REF INTERNA\u180E": "internal_ref",
        "REF INTERNA\u2000": "internal_ref",
        "REF INTERNA\u2001": "internal_ref",
        "REF INTERNA\u2002": "internal_ref",
        "REF INTERNA\u2003": "internal_ref",
        "REF INTERNA\u2004": "internal_ref",
        "REF INTERNA\u2005": "internal_ref",
        "REF INTERNA\u2006": "internal_ref",
        "REF INTERNA\u2007": "internal_ref",
        "REF INTERNA\u2008": "internal_ref",
        "REF INTERNA\u200A": "internal_ref",
        "REF INTERNA\u205F": "internal_ref",
        "REF INTERNA\u1680": "internal_ref",
        "REF INTERNA\u00AD": "internal_ref",

        "CLASSE": "class",
        "ESTADO DO EQUIPAMENTO": "state",

        "LOCAL": "location",
        "TEMPERATURA": "temperature",
        "HUMIDADE": "humidity",
        "UMIDADE": "humidity",
        "ANEXO TECNICO DE ACREDITACAO": "accreditation_annex",
        "ANEXO TÉCNICO DE ACREDITAÇÃO": "accreditation_annex",
        "ANEXO TECNICO DE ACREDITAGAO": "accreditation_annex",
    }

    return mapping.get(n)


def parse_key_value_block(text: str) -> dict:
    """
    Lê blocos OCR do tipo:
      Label
      valor
      Label
      valor
    mas permite também valores multi-linha.
    """
    lines = split_lines(strip_footer_noise(text))
    parsed = {}

    i = 0
    while i < len(lines):
        key = canonical_label(lines[i])

        if key is None:
            i += 1
            continue

        vals = []
        j = i + 1

        while j < len(lines):
            next_key = canonical_label(lines[j])
            if next_key is not None:
                break
            vals.append(lines[j])
            j += 1

        value = clean_spaces(" | ".join(vals)) if vals else None

        if key not in parsed:
            parsed[key] = value

        i = j

    return parsed


# -------------------------
# Parsers por bloco
# -------------------------
def extract_customer_name_and_address(text: str) -> tuple[str | None, str | None]:
    pruned = truncate_at_section_markers(
        text,
        [
            "EQUIPAMENTO CALIBRADO",
            "CONDICOES DO TRABALHO REALIZADO",
            "DESCRICAO",
            "RASTREABILIDADE",
        ],
    )
    kv = parse_key_value_block(pruned or text)
    return clean_spaces(kv.get("name")), clean_spaces(kv.get("address"))


def extract_equipment_fields(text: str) -> dict:
    pruned = truncate_at_section_markers(
        text,
        [
            "CONDICOES DO TRABALHO REALIZADO",
            "DESCRICAO",
            "RASTREABILIDADE",
        ],
    )
    kv = parse_key_value_block(pruned or text)

    internal_ref = clean_spaces(kv.get("internal_ref"))
    if internal_ref and (
        "RESULTADOS APRESENTADOS" in normalize(internal_ref) or
        normalize(internal_ref).startswith("JS RESUITADOS")
    ):
        internal_ref = None

    return {
        "designation": clean_spaces(kv.get("designation")),
        "brand": clean_spaces(kv.get("brand")),
        "model": clean_spaces(kv.get("model")),
        "serial_number": clean_spaces(kv.get("serial_number")),
        "range": clean_spaces(kv.get("range")),
        "resolution": clean_spaces(kv.get("resolution")),
        "estimated_resolution": clean_spaces(kv.get("estimated_resolution")),
        "indication": clean_spaces(kv.get("indication")),
        "internal_ref": internal_ref,
        "class": clean_spaces(kv.get("class")),
        "state": clean_spaces(kv.get("state")),
    }


def extract_work_conditions(text: str) -> dict:
    kv = parse_key_value_block(text)
    lines = split_lines(strip_footer_noise(text))

    location = clean_spaces(kv.get("location"))
    temperature = clean_spaces(kv.get("temperature"))
    humidity = clean_spaces(kv.get("humidity"))
    accreditation_annex = clean_spaces(kv.get("accreditation_annex"))

    # temperatura fallback
    if not temperature:
        for ln in lines:
            m = re.search(r"(\(\s*\d{1,2}\s*[^\)]*\)\s*°?C|\b\d{1,2}[.,]?\d*\s*°?C\b)", ln, re.IGNORECASE)
            if m:
                temperature = clean_spaces(m.group(1))
                break

    # humidade fallback
    if not humidity:
        for ln in lines:
            m = re.search(r"(\(\s*\d{1,2}\s*e\s*\d{1,2}\s*\)\s*%(?:hr)?|\b\d{1,2}[.,]?\d*\s*%(?:hr)?\b)", ln, re.IGNORECASE)
            if m:
                humidity = clean_spaces(m.group(1))
                break

    # anexo fallback
    if not accreditation_annex:
        for ln in lines:
            m = re.search(r"\b(M\d{4}-\d+)\b", ln, re.IGNORECASE)
            if m:
                accreditation_annex = clean_spaces(m.group(1))
                break

    # location fallback mais forte
    # se location vier vazia ou com temperatura, procurar a melhor linha "solta"
    if not location or re.search(r"°?C|%", location or "", re.IGNORECASE):
        for idx, ln in enumerate(lines):
            n = normalize(ln)

            # caso clássico OCR trocado:
            # Porto / Temperatura / Local / (20 2)°C
            if n == "LOCAL":
                if idx > 0:
                    prev = clean_spaces(lines[idx - 1])
                    if prev and canonical_label(prev) is None and not re.search(r"°?C|%", prev, re.IGNORECASE):
                        location = prev
                        break

                if idx + 1 < len(lines):
                    nxt = clean_spaces(lines[idx + 1])
                    if nxt and canonical_label(nxt) is None and not re.search(r"°?C|%", nxt, re.IGNORECASE):
                        location = nxt
                        break

        # fallback final: primeira linha não-label que não seja temperatura/humidade/anexo
        if not location or re.search(r"°?C|%", location or "", re.IGNORECASE):
            for ln in lines:
                n = normalize(ln)
                if canonical_label(ln) is not None:
                    continue
                if re.search(r"°?C|%", ln, re.IGNORECASE):
                    continue
                if re.search(r"\bM\d{4}-\d+\b", ln, re.IGNORECASE):
                    continue
                location = clean_spaces(ln)
                break

    if location and "|" in location:
        parts = [clean_spaces(part) for part in location.split("|")]
        for part in parts:
            if not part:
                continue
            if "CONDICOES DO TRABALHO" in normalize(part):
                continue
            location = part
            break

    return {
        "location": location,
        "temperature": temperature,
        "humidity": humidity,
        "accreditation_annex": accreditation_annex,
    }

def extract_reference_from_description(text: str) -> str | None:
    text = strip_footer_noise(text or "")

    plain_lines = split_lines(text)
    for idx, ln in enumerate(plain_lines):
        n = normalize(ln)
        if n in {"DESCRICAO", "DESIGNACAO"}:
            continue
        if "NORMATIV" in n:
            continue
        if re.search(r"\b[A-Z]{2,6}\s*[A-Z]?\s*\d{1,4}(?:[-/]\d+)?\b", ln):
            return clean_spaces(ln)

    patterns = [
        r"(?i)\b(NP\s*EN\s*\d{2,6}(?:[-–]\d+)?\s*:\s*\d{4})\b",
        r"(?i)\b(ISO\s*\d{2,6}(?:[-–]\d+)?\s*:\s*\d{4})\b",
        r"(?i)\b(EN\s*\d{2,6}(?:[-–]\d+)?\s*:\s*\d{4})\b",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return clean_spaces(m.group(1))

    return None


def extract_equipment_state(text: str) -> str | None:
    lines = split_lines(strip_footer_noise(text))
    if not lines:
        return None

    filtered = []
    for ln in lines:
        if normalize(ln) == "ESTADO DO EQUIPAMENTO":
            continue
        filtered.append(ln)

    return clean_spaces(" ".join(filtered))


def extract_header_fields(text: str) -> dict:
    text = strip_footer_noise(text or "")

    issue_date = first_date_in_text(text)
    certificate_number = extract_certificate_number(text)
    lab_name = extract_lab_name(text)
    lab_unit = extract_lab_unit(text)

    return {
        "issue_date": safe_date(issue_date),
        "certificate_number": clean_spaces(certificate_number),
        "calibration_date": None,
        "lab_name": clean_spaces(lab_name),
        "lab_unit": clean_spaces(lab_unit),
    }


# -------------------------
# Document parse
# -------------------------
def parse_document(section_json: dict) -> dict:
    page_sections = section_json.get("page_sections", {})
    page01 = page_sections.get("page_01.png", {})

    header_meta = page01.get("header_meta", "")
    calibration_meta = page01.get("calibration_meta", "")
    customer_block = page01.get("customer", "")
    equipment_block = page01.get("equipment", "")
    equipment_state_block = page01.get("equipment_state", "")
    work_conditions_block = page01.get("work_conditions", "")
    description_block = page01.get("description", "")

    header = extract_header_fields("\n".join([header_meta, calibration_meta]).strip())
    header["calibration_date"] = safe_date(first_date_in_text(calibration_meta))
    customer_name, customer_address = extract_customer_name_and_address(customer_block)
    equipment = extract_equipment_fields(equipment_block)
    if not equipment.get("state"):
        equipment["state"] = extract_equipment_state(equipment_state_block)
    work_conditions = extract_work_conditions(work_conditions_block)
    reference = {
        "standard_or_procedure": extract_reference_from_description(description_block)
    }

    raw_blocks = {
        "header_meta": clean_spaces(header_meta),
        "calibration_meta": clean_spaces(calibration_meta),
        "customer": clean_spaces(customer_block),
        "equipment": clean_spaces(equipment_block),
        "equipment_state": clean_spaces(equipment_state_block),
        "work_conditions": clean_spaces(work_conditions_block),
        "description": clean_spaces(description_block),
    }

    return repair_nested_text({
        "source_file": section_json.get("source_file"),
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "header": header,
        "customer": {
            "name": customer_name,
            "address": customer_address,
        },
        "equipment": equipment,
        "work_conditions": work_conditions,
        "reference": reference,
        "raw_blocks": raw_blocks,
    })


# -------------------------
# Main
# -------------------------
def main():
    files = sorted(IN_DIR.glob("*_sections.json"))

    if not files:
        print(f"Sem ficheiros de secções em: {IN_DIR}")
        return

    for fp in files:
        data = read_json(fp)
        parsed = parse_document(data)

        out = OUT_DIR / fp.name.replace("_sections.json", ".json")
        out.write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print("saved:", out)


if __name__ == "__main__":
    main()
