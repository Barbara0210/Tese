# 04_parse_fields.py

import json
import re
from pathlib import Path
from datetime import datetime

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
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    s = s.strip()
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
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def looks_like_label(line: str) -> bool:
    n = normalize(line)
    if not n:
        return False
    if len(n) > 40:
        return False

    known_starts = [
        "NOME", "MORADA",
        "DESIGNACAO", "DESIGNAÇÃO",
        "MARCA", "MODELO",
        "N SERIE", "N SERIE", "Nº SERIE", "N° SERIE",
        "NUMERO DE SERIE", "NUMERO DE SÉRIE",
        "INDICACAO", "INDICAÇÃO",
        "RESOLUCAO", "RESOLUÇÃO",
        "RESOLUCAO ESTIMADA", "RESOLUÇÃO ESTIMADA",
        "ALCANCE", "ALCANCE DE MEDICAO", "ALCANCE DE MEDIÇÃO",
        "INTERVALO DE INDICACAO", "INTERVALO DE INDICAÇÃO",
        "INTERVALO DE MEDICAO", "INTERVALO DE MEDIÇÃO",
        "REF INTERNA", "REF. INTERNA", "REF INTERNA",
        "CLASSE",
        "LOCAL", "TEMPERATURA", "HUMIDADE", "UMIDADE",
        "ANEXO TECNICO DE ACREDITACAO", "ANEXO TÉCNICO DE ACREDITAÇÃO",
    ]

    return any(n.startswith(x) for x in known_starts)


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


def is_probably_bad_value(v: str | None) -> bool:
    if not v:
        return True
    n = normalize(v)

    bad_exact = {
        "MODELO",
        "MARCA",
        "DESIGNACAO",
        "INDICACAO",
        "RESOLUCAO",
        "RESOLUCAO ESTIMADA",
        "N SERIE",
        "INTERVALO DE INDICACAO",
        "ALCANCE DE MEDICAO",
        "REF INTERNA",
        "CLASSE",
        "LOCAL",
        "TEMPERATURA",
        "HUMIDADE",
        "ANEXO TECNICO DE ACREDITACAO",
        "ESTADO DO EQUIPAMENTO",
    }
    return n in bad_exact


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
    lines = split_lines(text)
    for ln in lines:
        n = normalize(ln)
        if "LABORATORIO DE METROLOGIA" in n or "LABORATÓRIO DE METROLOGIA" in n:
            return clean_spaces(ln)
    return None


def extract_lab_name(text: str) -> str | None:
    lines = split_lines(text)

    # preferir linha com CATIM
    for ln in lines:
        n = normalize(ln)
        if n == "CATIM":
            return "CATIM"

    # fallback: centro de apoio tecnológico...
    for ln in lines:
        n = normalize(ln)
        if "CENTRO DE APOIO TECNOLOGICO" in n:
            return clean_spaces(ln)

    return None


def collect_value_after_label_lines(lines: list[str], label_variants: list[str], max_lines: int = 3) -> str | None:
    norm_labels = [normalize(x) for x in label_variants]

    for i, ln in enumerate(lines):
        n = normalize(ln)

        # caso 1: label sozinho na linha
        if any(n == lbl for lbl in norm_labels):
            vals = []
            for j in range(i + 1, min(i + 1 + max_lines, len(lines))):
                cur = lines[j].strip()
                if not cur:
                    continue
                if looks_like_label(cur):
                    break
                vals.append(cur)
            v = clean_spaces(" | ".join(vals))
            if not is_probably_bad_value(v):
                return v

        # caso 2: label e valor na mesma linha
        for lbl in label_variants:
            pat = rf"(?i)^{re.escape(lbl)}\s*[:\-]?\s*(.+)$"
            m = re.match(pat, ln.strip())
            if m:
                v = clean_spaces(m.group(1))
                if not is_probably_bad_value(v):
                    return v

    return None


def collect_temperature(lines: list[str]) -> str | None:
    # por label
    v = collect_value_after_label_lines(lines, ["Temperatura"], max_lines=4)
    if v and re.search(r"°?C", v, re.IGNORECASE):
        return v

    # fallback por padrão
    for ln in lines:
        m = re.search(r"(\(\s*\d{1,2}\s*[^\)]*\)\s*°?C|\b\d{1,2}[.,]?\d*\s*°?C\b)", ln, re.IGNORECASE)
        if m:
            return clean_spaces(m.group(1))
    return None


def collect_humidity(lines: list[str]) -> str | None:
    v = collect_value_after_label_lines(lines, ["Humidade", "Umidade"], max_lines=4)
    if v and "%" in v:
        return v

    for ln in lines:
        m = re.search(r"(\(\s*\d{1,2}\s*e\s*\d{1,2}\s*\)\s*%(?:hr)?|\b\d{1,2}[.,]?\d*\s*%(?:hr)?\b)", ln, re.IGNORECASE)
        if m:
            return clean_spaces(m.group(1))
    return None


def collect_location(lines: list[str]) -> str | None:
    # primeiro tenta pelo label
    v = collect_value_after_label_lines(lines, ["Local"], max_lines=3)
    if v and not is_probably_bad_value(v):
        if not re.search(r"°?C|%", v, re.IGNORECASE):
            return v

    # fallback: procurar primeira linha que não seja label, não seja temperatura nem humidade
    for ln in lines:
        n = normalize(ln)
        if not n:
            continue
        if looks_like_label(ln):
            continue
        if re.search(r"°?C|%", ln, re.IGNORECASE):
            continue
        if "M0003" in n:
            continue
        return clean_spaces(ln)

    return None


def extract_reference_from_description(text: str) -> str | None:
    text = strip_footer_noise(text or "")

    patterns = [
        r"(?i)\b(NP\s*EN\s*\d{2,6}(?:[-–]\d+)?\s*:\s*\d{4})\b",
        r"(?i)\b(ISO\s*\d{2,6}(?:[-–]\d+)?\s*:\s*\d{4})\b",
        r"(?i)\b(EN\s*\d{2,6}(?:[-–]\d+)?\s*:\s*\d{4})\b",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return clean_spaces(m.group(1))

    # fallback: 1ª linha útil
    for ln in split_lines(text):
        if len(ln) >= 8:
            return clean_spaces(ln)

    return None


def compact_multiline_address(text: str) -> str | None:
    lines = split_lines(text)
    if not lines:
        return None
    return clean_spaces(" | ".join(lines))


def extract_customer_name_and_address(text: str) -> tuple[str | None, str | None]:
    lines = split_lines(strip_footer_noise(text))

    name = collect_value_after_label_lines(lines, ["Nome"], max_lines=2)
    address = collect_value_after_label_lines(lines, ["Morada", "Endereço", "Endereco"], max_lines=4)

    # fallback simples
    if not name and lines:
        for i, ln in enumerate(lines):
            if normalize(ln) == "NOME" and i + 1 < len(lines):
                name = clean_spaces(lines[i + 1])
                break

    if not address:
        # se houver "Morada", junta o que vem a seguir até aparecer outro label
        for i, ln in enumerate(lines):
            if normalize(ln) in {"MORADA", "ENDERECO", "ENDEREÇO"}:
                vals = []
                for j in range(i + 1, len(lines)):
                    cur = lines[j]
                    if looks_like_label(cur):
                        break
                    vals.append(cur)
                address = clean_spaces(" | ".join(vals))
                break

    return clean_spaces(name), clean_spaces(address)


def cleanup_equipment_value(value: str | None) -> str | None:
    value = clean_spaces(value)
    if not value:
        return None

    # cortar cadeias onde o OCR colou outros labels
    bad_splitters = [
        "Marca", "Modelo", "N° Série", "Nº Série", "No Série",
        "Número de Série", "Numero de Serie", "Indicação", "Indicacao",
        "Resolução", "Resolucao", "Resolução estimada", "Resolucao estimada",
        "Alcance", "Alcance de medição", "Alcance de medicao",
        "Intervalo de indicação", "Intervalo de indicacao",
        "Ref Interna", "Ref. Interna", "Classe", "Estado do equipamento"
    ]
    for splitter in bad_splitters:
        parts = re.split(rf"(?i)\b{re.escape(splitter)}\b", value)
        if parts and parts[0].strip() and parts[0].strip() != value:
            value = parts[0].strip()
            break

    return clean_spaces(value)


def extract_equipment_fields(text: str) -> dict:
    text = strip_footer_noise(text or "")
    lines = split_lines(text)

    designation = cleanup_equipment_value(
        collect_value_after_label_lines(lines, ["Designação", "Designacao", "Equipamento", "Instrumento"], max_lines=2)
    )
    brand = cleanup_equipment_value(
        collect_value_after_label_lines(lines, ["Marca"], max_lines=2)
    )
    model = cleanup_equipment_value(
        collect_value_after_label_lines(lines, ["Modelo"], max_lines=2)
    )
    serial_number = cleanup_equipment_value(
        collect_value_after_label_lines(lines, ["Nº Série", "N° Série", "No Série", "Número de Série", "Numero de Serie", "Serial"], max_lines=2)
    )
    meas_range = cleanup_equipment_value(
        collect_value_after_label_lines(
            lines,
            ["Alcance", "Alcance de medição", "Alcance de medicao", "Intervalo de indicação", "Intervalo de indicacao", "Intervalo de medição", "Intervalo de medicao"],
            max_lines=2,
        )
    )
    resolution = cleanup_equipment_value(
        collect_value_after_label_lines(lines, ["Resolução", "Resolucao", "Resolução estimada", "Resolucao estimada"], max_lines=2)
    )
    indication = cleanup_equipment_value(
        collect_value_after_label_lines(lines, ["Indicação", "Indicacao"], max_lines=2)
    )
    internal_ref = cleanup_equipment_value(
        collect_value_after_label_lines(lines, ["Ref Interna", "Ref. Interna", "Ref Interna", "Ref"], max_lines=2)
    )
    accuracy_class = cleanup_equipment_value(
        collect_value_after_label_lines(lines, ["Classe"], max_lines=2)
    )
    equipment_state = cleanup_equipment_value(
        collect_value_after_label_lines(lines, ["Estado do equipamento"], max_lines=3)
    )

    return {
        "designation": designation,
        "brand": brand,
        "model": model,
        "serial_number": serial_number,
        "range": meas_range,
        "resolution": resolution,
        "indication": indication,
        "internal_ref": internal_ref,
        "class": accuracy_class,
        "state": equipment_state,
    }


def extract_work_conditions(text: str) -> dict:
    text = strip_footer_noise(text or "")
    lines = split_lines(text)

    location = collect_location(lines)
    temperature = collect_temperature(lines)
    humidity = collect_humidity(lines)
    accreditation_annex = collect_value_after_label_lines(
        lines,
        ["Anexo Técnico de Acreditação", "Anexo Tecnico de Acreditacao"],
        max_lines=2,
    )

    return {
        "location": clean_spaces(location),
        "temperature": clean_spaces(temperature),
        "humidity": clean_spaces(humidity),
        "accreditation_annex": clean_spaces(accreditation_annex),
    }


def extract_header_fields(text: str) -> dict:
    text = strip_footer_noise(text or "")

    issue_date = first_date_in_text(text)
    certificate_number = extract_certificate_number(text)
    lab_name = extract_lab_name(text)
    lab_unit = extract_lab_unit(text)

    return {
        "issue_date": safe_date(issue_date),
        "certificate_number": clean_spaces(certificate_number),
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
    customer_block = page01.get("customer", "")
    equipment_block = page01.get("equipment", "")
    work_conditions_block = page01.get("work_conditions", "")
    description_block = page01.get("description", "")

    header = extract_header_fields(header_meta)
    customer_name, customer_address = extract_customer_name_and_address(customer_block)
    equipment = extract_equipment_fields(equipment_block)
    work_conditions = extract_work_conditions(work_conditions_block)
    reference = {"standard_or_procedure": extract_reference_from_description(description_block)}

    # opcional: guardar também os blocos crus úteis para debugging/tese
    raw_blocks = {
        "header_meta": clean_spaces(header_meta),
        "customer": clean_spaces(customer_block),
        "equipment": clean_spaces(equipment_block),
        "work_conditions": clean_spaces(work_conditions_block),
        "description": clean_spaces(description_block),
    }

    return {
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
    }


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