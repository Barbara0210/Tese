import json
import re
from pathlib import Path
from typing import Dict, List, Any

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

def extract_lab(text: str) -> Dict[str, str]:
    lab_name = find_first([r"^(CATIM.*)$", r"^(EXTRALAB.*)$", r"^(CITC.*)$"], text, flags=re.IGNORECASE | re.MULTILINE)
    lab_unit = find_first([r"(Laborat[oó]rio[^\n]{0,80})"], text)
    return {"lab_name": lab_name, "lab_unit": lab_unit}

def extract_header(text: str) -> Dict[str, str]:
    cert_no = find_first([
        r"Certificado\s*(?:n[ºo]\.?\s*)?:\s*([A-Z0-9_\-\/]+)",
        r"Certificate\s*(?:No\.?\s*)?:\s*([A-Z0-9_\-\/]+)",
        r"\b(LM[D|F]\d{2,}\/\d{2,})\b",
    ], text)
    date = find_first([
        r"Data\s*:\s*(\d{4}-\d{2}-\d{2})",
        r"Data\s*:\s*(\d{2}\/\d{2}\/\d{4})",
        r"Date\s*:\s*(\d{4}-\d{2}-\d{2})",
        r"Date\s*:\s*(\d{2}\/\d{2}\/\d{4})",
    ], text)
    title = find_first([r"^(Certificado[^\n]{0,60})$"], text, flags=re.IGNORECASE | re.MULTILINE)
    return {"certificate_number": cert_no, "date": date, "title": title}

def extract_equipment(text: str) -> Dict[str, str]:
    designation = find_first([r"Designa[cç][aã]o\s*:\s*([^\n]+)", r"Item\s*:\s*([^\n]+)"], text)
    if not designation:
        designation = find_first([r"\bPaqu[ií]metro\b[^\n]{0,60}"], text)

    brand = find_first([r"Marca\s*:\s*([^\n]+)"], text)
    model = find_first([r"Modelo\s*:\s*([^\n]+)"], text)
    serial = find_first([r"(?:N[ºo]\s*de\s*S[eé]rie|S\/N|SN)\s*:\s*([A-Z0-9\-]+)"], text)
    range_ = find_first([r"Alcance\s*:\s*([^\n]+)", r"Range\s*:\s*([^\n]+)"], text)
    resolution = find_first([r"Resolu[cç][aã]o\s*:\s*([^\n]+)", r"Resolution\s*:\s*([^\n]+)"], text)

    return {
        "designation": clean(designation),
        "brand": clean(brand),
        "model": clean(model),
        "serial_number": clean(serial),
        "range": clean(range_),
        "resolution": clean(resolution),
    }

def parse_measurement_rows(text: str) -> List[Dict[str, Any]]:
    rows = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    num_re = re.compile(r"[-+]?\d+(?:[.,]\d+)?")

    for l in lines:
        nums = num_re.findall(l)
        if len(nums) >= 3 and ("mm" in l.lower() or "paqu" in text.lower()):
            vals = [v.replace(",", ".") for v in nums[:8]]
            rows.append({"raw_line": l, "values": vals})

    return rows[:200]

def main():
    files = list(IN_DIR.glob("*.txt"))
    if not files:
        print(f"Sem OCR .txt em: {IN_DIR} (corre 03_ocr_text_cli.py)")
        return

    for f in files:
        doc_id = f.stem
        text = f.read_text(encoding="utf-8", errors="replace")

        out = {
            "doc_id": doc_id,
            "iso17025_min": {
                "header": extract_header(text),
                "laboratory": extract_lab(text),
                "equipment": extract_equipment(text),
                "measurements": parse_measurement_rows(text),
            },
            "raw_text_path": str(f),
        }

        out_path = OUT_DIR / f"{doc_id}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("saved:", out_path)

if __name__ == "__main__":
    main()
