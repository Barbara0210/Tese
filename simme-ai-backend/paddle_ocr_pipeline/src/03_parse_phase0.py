import json
import re
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[1]
IN_DIR = BASE / "data" / "ocr_text"
OUT_DIR = BASE / "data" / "parsed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------
# Helpers
# -------------------------
def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def normalize_text(raw: str) -> str:
    """
    Normalização leve para ajudar regex, especialmente no SYMINGTON.
    - colapsa espaços
    - injeta espaços em alguns padrões colados (ex: CERTIFICADON -> CERTIFICADO N)
    - garante que 'DATA:' e 'PAGINA' ficam separáveis
    """
    t = raw.replace("\r\n", "\n")
    # separar "CERTIFICADON" / "CERTIFICADON°" etc
    t = re.sub(r"(CERTIFICADO)\s*([Nn][°o]?\s*:?)", r"\1 \2", t)
    t = re.sub(r"(CERTIFICADO)(N)", r"\1 \2", t)
    # separar "PAGINA1DE3" etc
    t = re.sub(r"(PAGINA)\s*([0-9])", r"\1 \2", t)
    t = re.sub(r"([0-9])DE([0-9])", r"\1 DE \2", t)
    # "DATA:2022-05-18" -> "DATA: 2022-05-18"
    t = re.sub(r"(DATA)\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", r"\1: \2", t)

    # muitas linhas do SYMINGTON vêm coladas sem espaços:
    # colocar espaço entre letras e números quando claramente colado
    t = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", t)
    t = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", t)

    # colapsar espaços e tabs mas manter \n
    t = re.sub(r"[ \t]+", " ", t)
    return t

def extract_first(pattern: str, text: str, flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None

def extract_block(after_label: str, text: str, max_lines=6):
    stop_words = {
        "EQUIPAMENTO CALIBRADO", "CONDICÕES DO TRABALHO REALIZADO", "DESCRICAO",
        "RESULTADOS", "RASTREABILIDADE", "INCERTEZA", "CLIENTE"
    }
    lines = [ln.strip() for ln in text.splitlines()]
    for i, ln in enumerate(lines):
        if ln.lower() == after_label.lower():
            out = []
            for j in range(i + 1, len(lines)):
                if len(out) >= max_lines:
                    break
                cur = lines[j].strip()
                if not cur:
                    continue
                if cur.upper() in stop_words:
                    break
                out.append(cur)
            return " | ".join(out).strip() if out else None
    return None

def safe_date(s: str):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass
    return s  # devolve raw se não bater

# -------------------------
# Field extraction
# -------------------------
def parse_header_fields(text: str) -> dict:
    # datas e certificado (funciona bem no MA SILVA e razoavelmente no SYMINGTON)
    cert = (
    extract_first(r"Certificado\s*(?:n[°o\*]?\s*:\s*)\s*([A-Z]{2,}\s*[0-9]{6,}[0-9/.\-]+)", text, re.IGNORECASE)
    or extract_first(r"CERTIFICADO\s*N\W*\s*([A-Z]{2,}\s*[0-9]{6,}[0-9/.\-]+)", text, re.IGNORECASE)
)
    if cert:
        cert = re.sub(r"\s+", "", cert)  # "LMD 202550..." -> "LMD202550..."
    issue = (
        extract_first(r"DATA\s+DE\s+EMISS[ÃA]O\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, re.IGNORECASE)
        or extract_first(r"DATA\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, re.IGNORECASE)
    )
    calib = extract_first(r"DATA\s+CALIBRAC[AÃ]O\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, re.IGNORECASE)

    # cliente
    cliente_nome = extract_first(r"CLIENTE\s*\n(?:.*\n)?Nome\s*\n([^\n]+)", text, re.IGNORECASE)
    if not cliente_nome:
        cliente_nome = extract_first(r"\b([A-Z0-9 .,&\-]{6,}?(?:SA|S\.A\.|LDA|LDA\.))\b", text)

    cliente_morada = extract_block("Morada", text, max_lines=3)
    # se o OCR vier muito “flat”, tenta só apanhar a linha com SA / LDA
    if not cliente_nome:
        cliente_nome = extract_first(r"\b([A-Z0-9 .,&\-]{6,}?(?:SA|S\.A\.|LDA|LDA\.|S A))\b", text)

    cliente_morada = extract_block("Morada", text, max_lines=4)

    # equipamento
    designacao = extract_first(r"Designa[cç][aã]o\s*\n\s*([^\n]+)", text, re.IGNORECASE) or extract_first(r"Equipamento\s*[:\-]?\s*([^\n]+)", text, re.IGNORECASE)
    marca = extract_first(r"Marca\s*\n\s*([^\n]+)", text, re.IGNORECASE)
    modelo = extract_first(r"Modelo\s*\n\s*([^\n]+)", text, re.IGNORECASE) or extract_first(r"Modelo\s*:\s*([^\n]+)", text, re.IGNORECASE)
    serie = extract_first(r"N[°o]\s*S[ée]rie\s*\n\s*([A-Z0-9\-]+)", text, re.IGNORECASE) or extract_first(r"N[°o]\s*S[ée]rie\s*[:\-]?\s*([A-Z0-9\-]+)", text, re.IGNORECASE)

    alcance = extract_first(r"Alcance\s+de\s+medi[cç][aã]o\s*\n\s*([^\n]+)", text, re.IGNORECASE)
    resolucao = extract_first(r"Resolu[cç][aã]o\s*\n\s*([^\n]+)", text, re.IGNORECASE)
    indicacao = extract_first(r"Indica[cç][aã]o\s*\n\s*([^\n]+)", text, re.IGNORECASE)

    # condições / local
    local = extract_first(r"Local\s*\n\s*([^\n]+)", text, re.IGNORECASE)
    temp = extract_first(r"Temperatura\s*\n\s*([^\n]+)", text, re.IGNORECASE)
    hum = extract_first(r"Humidade\s*\n\s*([^\n]+)", text, re.IGNORECASE)

    # norma / procedimento
    norma = extract_first(r"Calibra[cç][aã]o\s+segundo.*?\n\s*([^\n]+)", text, re.IGNORECASE)
    # alternativa (apanhar ISO 13385 etc em qualquer parte)
    if not norma:
        norma = extract_first(r"\b(ISO\s*13385[-–]?\s*[0-9]?:?\s*[0-9]{4})\b", text, re.IGNORECASE)

    return {
        "certificate_number": cert,
        "issue_date": safe_date(issue),
        "calibration_date": safe_date(calib),
        "customer_name": cliente_nome.strip() if cliente_nome else None,
        "customer_address": cliente_morada,
        "equipment": {
            "designation": designacao.strip() if designacao else None,
            "brand": marca.strip() if marca else None,
            "model": modelo.strip() if modelo else None,
            "serial_number": serie.strip() if serie else None,
            "range": alcance.strip() if alcance else None,
            "resolution": resolucao.strip() if resolucao else None,
            "indication": indicacao.strip() if indicacao else None,
        },
        "conditions": {
            "location": local.strip() if local else None,
            "temperature": temp.strip() if temp else None,
            "humidity": hum.strip() if hum else None,
        },
        "reference": {
            "standard_or_procedure": norma.strip() if norma else None,
        }
    }

def parse_results(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    def collect_after(hint: str, max_rows=30):
        out = []
        idx = None
        for i, ln in enumerate(lines):
            if hint.lower() in ln.lower():
                idx = i
                break
        if idx is None:
            return out

        for ln in lines[idx: idx + 400]:
            nums = re.findall(r"[-+]?\d+\.\d+|[-+]?\d+", ln)
            # nas tabelas tens normalmente 6-9 números por linha
            if len(nums) >= 6:
                out.append(ln)
                if len(out) >= max_rows:
                    break
        return out

    return {
        "E_contact_partial_rows": collect_after("Erro de Indic", max_rows=30),
        "S_scale_change_rows": collect_after("troca de escala", max_rows=30),
        "L_line_contact_rows": collect_after("contacto em linha", max_rows=10),
    }

def split_pages(raw: str) -> dict:
    parts = re.split(r"\n===\s*(page_\d+\.png)\s*===\n", raw)
    if len(parts) < 3:
        return {"__all__": raw}

    pages = {}
    for i in range(1, len(parts), 2):
        key = parts[i].strip()
        content = parts[i + 1]
        pages[key] = content
    return pages

def parse_document(txt_path: Path) -> dict:
    raw = read_text(txt_path)
    pages = split_pages(raw)

    # header: normalmente vem na página 1
    header_text = normalize_text(pages.get("page_01.png", raw))
    header = parse_header_fields(header_text)

    # resultados: procurar nas páginas 2 e 3 (se existirem), senão no resto
    results_text = "\n".join([
        pages.get("page_02.png", ""),
        pages.get("page_03.png", "")
    ]).strip()
    if not results_text:
        results_text = raw

    results_text = normalize_text(results_text)
    results = parse_results(results_text)

    return {
        "source_file": txt_path.name,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "header": header,
        "results": results,
    }

def main():
    txt_files = sorted(IN_DIR.glob("*.txt"))
    if not txt_files:
        print(f"Sem TXT em {IN_DIR}")
        return

    for txt in txt_files:
        data = parse_document(txt)
        out = OUT_DIR / (txt.stem + ".json")
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("saved:", out)

if __name__ == "__main__":
    main()