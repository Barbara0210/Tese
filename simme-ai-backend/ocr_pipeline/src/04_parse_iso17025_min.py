import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

BASE = Path(__file__).resolve().parents[1]
IN_DIR = BASE / "data" / "ocr_text"
OUT_DIR = BASE / "data" / "parsed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def find_first(patterns: List[str], text: str, flags=re.IGNORECASE) -> str:
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            return clean(m.group(1) if m.lastindex else m.group(0))
    return ""

def split_pages(ocr_text: str) -> List[Tuple[str, str]]:
    parts = re.split(r"\n\s*===\s*(page_\d+\.\w+)\s*===\s*\n", ocr_text, flags=re.IGNORECASE)
    if len(parts) == 1:
        return [("page_01", ocr_text)]
    pages = []
    for i in range(1, len(parts), 2):
        name = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        pages.append((name, body))
    return pages

def parse_page_limit(text: str) -> Optional[int]:
    # aceita PAGINA/PÁGINA e variações de espaços
    m = re.search(r"P[ÁA]GINA\s+\d+\s+DE\s+(\d+)", text, flags=re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except:
            return None
    return None

def extract_lab(text: str) -> Dict[str, str]:
    # mais robusto: procura CATIM em qualquer lugar + unidade
    lab_name = "CATIM" if re.search(r"\bCATIM\b", text, flags=re.IGNORECASE) else ""
    lab_unit = find_first([r"(Laborat[oó]rio[^\n]{0,120})"], text, flags=re.IGNORECASE)
    return {"lab_name": lab_name, "lab_unit": lab_unit}

def extract_header(text: str) -> Dict[str, Any]:
    # aceita n°, nº, n.º, N.º, etc (º ou °)
    cert_no = find_first([
        r"Certificado\s*(?:n\s*[\.\-]?\s*[º°o]?\s*)?:\s*([A-Z]{2,5}\d{6,}\/\d{1,3})",
        r"CERTIFICADO\s*(?:N\s*[\.\-]?\s*[º°o]?\s*)?:\s*([A-Z]{2,5}\d{6,}\/\d{1,3})",
        r"\b(LMD\d{8,}\/\d{1,3})\b",
    ], text)

    issue_date = find_first([
        r"DATA\s+DE\s+EMISS[ÃA]O\s+(\d{4}-\d{2}-\d{2})",
        r"DATA\s*:\s*(\d{4}-\d{2}-\d{2})",
        r"DATA\s*:\s*(\d{2}\/\d{2}\/\d{4})",
    ], text)

    calibration_date = find_first([
        r"DATA\s+CALIBRA[CÇ][ÃA]O\s+(\d{4}-\d{2}-\d{2})",
        r"Data\s+de\s+calibra[cç][aã]o\s*:\s*(\d{4}-\d{2}-\d{2})",
        r"Data\s+de\s+calibra[cç][aã]o\s*:\s*(\d{2}\/\d{2}\/\d{4})",
    ], text)

    title = find_first([r"^(Certificado\s+de\s+Calibra[cç][aã]o)$"], text, flags=re.IGNORECASE | re.MULTILINE)
    page_count = parse_page_limit(text) or 0

    return {
        "certificate_number": cert_no,
        "issue_date": issue_date,
        "calibration_date": calibration_date,
        "title": title,
        "page_count": page_count,
    }

def extract_client(text: str) -> Dict[str, str]:
    name = ""
    address = ""

    m = re.search(r"CLIENTE\s*(?:\n|.){0,120}?\bNome\b\s*([^\n]+)", text, flags=re.IGNORECASE)
    if m:
        name = clean(m.group(1))
        m2 = re.search(r"Morada\s*([^\n]+(?:\n[^\n]+){0,4})", text, flags=re.IGNORECASE)
        if m2:
            address = clean(m2.group(1))
        return {"name": name, "address": address}

    m = re.search(r"CLIENTE\s*\n(.+?)(?:\nDESCRI[CÇ][AÃ]O|\nOPERA[CÇ][OÕ]ES|\nEQUIPAMENTO|\nEXAME|\nINCERTEZA)", text,
                  flags=re.IGNORECASE | re.DOTALL)
    if m:
        block = [clean(x) for x in m.group(1).splitlines() if clean(x)]
        if block:
            name = block[0]
            address = clean(" ".join(block[1:])) if len(block) > 1 else ""
    return {"name": name, "address": address}

def extract_equipment(text: str) -> Dict[str, str]:
    designation = find_first([r"Designa[cç][aã]o\s*([^\n]+)", r"Equipamento\s*:\s*([^\n]+)"], text)
    if not designation:
        designation = "Paquimetro" if re.search(r"\bPaqu[ií]metro\b", text, flags=re.IGNORECASE) else ""

    brand = find_first([r"Marca\s*[:\-]?\s*([^\n]+)"], text)
    model = find_first([r"Modelo\s*[:\-]?\s*([^\n]+)"], text)
    serial = find_first([r"(?:N[º°o]?\s*(?:S[eé]rie)?|N[úu]mero\s+de\s+S[eé]rie|SN|S\/N)\s*[:\-]?\s*([A-Z0-9\-]+)"], text)
    range_ = find_first([r"(?:Alcance\s+de\s+medi[cç][aã]o|Intervalo\s+de\s+medi[cç][aã]o)\s*[:\-]?\s*([^\n]+)"], text)
    resolution = find_first([r"Resolu[cç][aã]o\s*[:\-]?\s*([^\n]+)"], text)
    indication = find_first([r"Indica[cç][aã]o\s*[:\-]?\s*([^\n]+)"], text)

    return {
        "designation": clean(designation),
        "brand": clean(brand),
        "model": clean(model),
        "serial_number": clean(serial),
        "range": clean(range_),
        "resolution": clean(resolution),
        "indication": clean(indication),
    }

def extract_standards(text: str) -> List[str]:
    standards = set()
    for m in re.finditer(r"\bISO\s+\d{3,6}(?:-\d+)?(?::\d{4})?\b", text, flags=re.IGNORECASE):
        standards.add(clean(m.group(0)))
    if re.search(r"\bEA-4\/02M?\b", text, flags=re.IGNORECASE):
        standards.add("EA-4/02M")
    return sorted(standards)

def extract_signatures(text: str) -> Dict[str, str]:
    tech = find_first([r"T[eé]cnico\s*\(?([^\n\)]+)\)?"], text)
    resp = find_first([r"Respons[aá]vel\s+T[eé]cnico\s*\(?([^\n\)]+)\)?"], text)
    return {"technician": tech, "technical_manager": resp}

_num = r"[-+]?\d+(?:[.,]\d+)?"
def _to_float(s: str) -> float:
    return float(s.replace(",", "."))

def parse_table_E(page_text: str) -> List[Dict[str, Any]]:
    rows = []
    for line in page_text.splitlines():
        line = line.strip()
        m = re.match(rf"^({_num})\s+({_num})\s+({_num})\s+({_num})\s+({_num})\s+({_num})\s+(\d+)\s+({_num})$", line)
        if m:
            rows.append({
                "standard_mm": _to_float(m.group(1)),
                "zone1_mm": _to_float(m.group(2)),
                "zone2_mm": _to_float(m.group(3)),
                "zone3_mm": _to_float(m.group(4)),
                "E_mm": _to_float(m.group(5)),
                "k_prime": _to_float(m.group(6)),
                "v_eff": int(m.group(7)),
                "U_mm": _to_float(m.group(8)),
            })
    return rows

def parse_table_S(page_text: str) -> List[Dict[str, Any]]:
    rows = []
    current_jaw = ""
    for line in page_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(re.findall(_num, line)) <= 1 and any(k in line.lower() for k in ["interiores", "haste", "degrau", "faca", "tipo"]):
            current_jaw = clean(line)
            continue
        m = re.match(rf"^({_num})\s+({_num})\s+({_num})\s+({_num})\s+(\d+)\s+({_num})$", line)
        if m:
            rows.append({
                "jaw": current_jaw,
                "standard_mm": _to_float(m.group(1)),
                "reading_mm": _to_float(m.group(2)),
                "S_mm": _to_float(m.group(3)),
                "k_prime": _to_float(m.group(4)),
                "v_eff": int(m.group(5)),
                "U_mm": _to_float(m.group(6)),
            })
    return rows

def parse_table_L(page_text: str) -> List[Dict[str, Any]]:
    rows = []
    current_jaw = ""
    for line in page_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(re.findall(_num, line)) <= 1 and "maxilas" in line.lower():
            current_jaw = clean(line)
            continue
        m = re.match(rf"^({_num})\s+({_num})\s+({_num})\s+({_num})\s+({_num})\s+(\d+)\s+({_num})$", line)
        if m:
            rows.append({
                "jaw": current_jaw,
                "standard_mm": _to_float(m.group(1)),
                "max_mm": _to_float(m.group(2)),
                "min_mm": _to_float(m.group(3)),
                "L_mm": _to_float(m.group(4)),
                "k_prime": _to_float(m.group(5)),
                "v_eff": int(m.group(6)),
                "U_mm": _to_float(m.group(7)),
            })
    return rows

def main():
    files = list(IN_DIR.glob("*.txt"))
    if not files:
        print(f"Sem OCR .txt em: {IN_DIR}")
        return

    for f in files:
        doc_id = f.stem
        full = f.read_text(encoding="utf-8", errors="replace")

        pages = split_pages(full)

        page_limit = None
        for _, ptxt in pages[:2]:
            pl = parse_page_limit(ptxt)
            if pl:
                page_limit = pl
                break

        kept_pages = []
        for name, ptxt in pages:
            m = re.search(r"page_(\d+)", name, flags=re.IGNORECASE)
            idx = int(m.group(1)) if m else None
            if page_limit and idx and idx > page_limit:
                continue
            kept_pages.append((name, ptxt))

        cover_text = kept_pages[0][1] if kept_pages else full

        out = {
            "doc_id": doc_id,
            "iso17025_min": {
                "header": extract_header(cover_text),
                "laboratory": extract_lab(cover_text),
                "client": extract_client(cover_text),
                "equipment": extract_equipment(cover_text),
                "standards": extract_standards(full),
                "signatures": extract_signatures(cover_text),
                "results": {
                    "E_partial_contact": [],
                    "S_scale_change": [],
                    "L_line_contact": [],
                },
            },
            "raw_text_path": str(f),
            "notes": {
                "page_limit_detected": page_limit,
                "pages_kept": [n for n, _ in kept_pages],
            },
        }

        for _, ptxt in kept_pages:
            low = ptxt.lower()
            if "contacto parcial" in low and "valor padr" in low:
                out["iso17025_min"]["results"]["E_partial_contact"].extend(parse_table_E(ptxt))
            if "troca de escala" in low:
                out["iso17025_min"]["results"]["S_scale_change"].extend(parse_table_S(ptxt))
            if "contacto em linha" in low:
                out["iso17025_min"]["results"]["L_line_contact"].extend(parse_table_L(ptxt))

        out_path = OUT_DIR / f"{doc_id}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("saved:", out_path)

if __name__ == "__main__":
    main()