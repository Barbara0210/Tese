import json
import re
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]
IN_DIR = BASE / "data" / "ocr_text"
OUT_DIR = BASE / "data" / "parsed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------
# Helpers: IO
# -------------------------
def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


# -------------------------
# Helpers: text cleanup
# -------------------------
def normalize_text(raw: str) -> str:
    """
    Normalização leve para facilitar extração por rótulos.
    - normaliza quebras de linha
    - separa tokens colados comuns ("PAGINA1DE3" -> "PAGINA 1 DE 3")
    - colapsa espaços
    - remove algum "spam" repetido (watermark OCR)
    """
    t = raw.replace("\r\n", "\n")

    # separar coisas coladas frequentes
    t = re.sub(r"(PAGINA)\s*([0-9])", r"\1 \2", t, flags=re.IGNORECASE)
    t = re.sub(r"([0-9])DE([0-9])", r"\1 DE \2", t, flags=re.IGNORECASE)

    # DATA:2022-05-18 -> DATA: 2022-05-18
    t = re.sub(r"(DATA)\s*:\s*(20\d{2}-\d{2}-\d{2})", r"\1: \2", t, flags=re.IGNORECASE)

    # colapsar espaços/tabs (mantém \n)
    t = re.sub(r"[ \t]+", " ", t)

    # remover alguns blocos repetidos do watermark quando o OCR enlouquece
    t = remove_watermark_spam(t)

    return t


def remove_watermark_spam(t: str) -> str:
    patterns = [
        r"(CENTRO\s*DE\s*APOIO\s*TECNOL[ÓO]GICO.*?METALOMEC[ÂA]NICA){2,}",
        r"(CENTRODEAPOIOTECNOLOGICOAINDUSTRIAMETALOMECANICACEN){2,}",
        r"(AINDUSTRIAMETALOMECANICACENTRODEAPOIOTECNOLOGICO){2,}",
    ]
    out = t
    for p in patterns:
        out = re.sub(p, " ", out, flags=re.IGNORECASE | re.DOTALL)
    return out


# -------------------------
# Helpers: regex extraction
# -------------------------
def safe_date(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass
    return s  # devolve raw se não bater


def extract_first(pattern: str, text: str, flags=0) -> str | None:
    """
    Extrai o primeiro match.
    - Se o regex tiver grupos, devolve o grupo(1)
    - Se não tiver grupos, devolve o match inteiro (group(0))
    """
    m = re.search(pattern, text, flags)
    if not m:
        return None
    return (m.group(1) if m.lastindex else m.group(0)).strip()


# -------------------------
# Helpers: label/value extraction (GENÉRICO)
# -------------------------
def clean_spaces(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _label_regex(label: str) -> str:
    """
    Gera um regex tolerante a OCR para um rótulo:
    - aceita ":" "-" opcionais
    - aceita espaços variados
    - tenta ser robusto a acentos (não perfeito, mas ajuda)
    """
    # escape básico
    lab = re.escape(label.strip())
    # permitir espaços onde havia espaços
    lab = lab.replace(r"\ ", r"\s*")
    # aceitar ':' '-' opcionais
    return rf"(?i)\b{lab}\b\s*[:\-]?\s*"


def extract_label_value(label: str, text: str, *, max_lines: int = 4) -> str | None:
    """
    Extrai valor para um rótulo (label) de forma genérica.
    Suporta:
      - "LABEL: valor"
      - "LABEL\nvalor"
      - "LABEL - valor"
    Também tenta apanhar valores multi-linha (até max_lines).
    """
    lines = [ln.strip() for ln in text.splitlines()]
    if not lines:
        return None

    lab_pat = re.compile(_label_regex(label))

    stop_words = {
        # secções comuns
        "EQUIPAMENTO CALIBRADO",
        "CONDICOES DO TRABALHO REALIZADO",
        "CONDIÇÕES DO TRABALHO REALIZADO",
        "DESCRICAO",
        "DESCRIÇÃO",
        "RESULTADOS",
        "RASTREABILIDADE",
        "INCERTEZA",
        "OBSERVACOES",
        "OBSERVAÇÕES",
        "CLIENTE",
        # páginas
        "PAGINA",
        "PÁGINA",
    }

    for i, ln in enumerate(lines):
        m = lab_pat.search(ln)
        if not m:
            continue

        # 1) tenta valor na MESMA linha
        after = ln[m.end():].strip()
        if after:
            # cortar caso a linha tenha “outros rótulos” colados
            return clean_spaces(after)

        # 2) tenta nas linhas seguintes (multi-linha)
        out = []
        for j in range(i + 1, min(i + 1 + max_lines, len(lines))):
            cur = lines[j].strip()
            if not cur:
                continue

            cur_up = re.sub(r"[:\-]\s*$", "", cur).strip().upper()
            if cur_up in stop_words:
                break

            # se a linha PARECE outro rótulo (ex: "Marca", "Modelo", "Local"), pára
            if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÁÀÂÃÉÊÍÓÔÕÚÇ0-9 ()/%\.\-]{0,25}\s*[:\-]?$", cur) and len(cur) <= 28:
                break

            out.append(cur)

        return clean_spaces(" | ".join(out)) if out else None

    return None


# -------------------------
# Header parsing (GENÉRICO)
# -------------------------
def parse_header_fields(text: str, source_name: str | None = None) -> dict:
    # certificado: tentar padrões típicos mas sem amarrar a LMD/LMP
    # Ex: "Certificado n: LMD 20255006594/10" ou "CERTIFICADO N.º: XXX"
    cert = extract_first(
        r"(?i)\bCertificado\s*(?:n[º°o\*]?\s*[:\-]?\s*)\s*([A-Z]{1,6}\s*\d{6,}[0-9/.\-]*)\b",
        text,
    )
    if cert:
        cert = re.sub(r"\s+", "", cert)

    # datas (universais)
    issue = extract_first(r"(?i)\bDATA\s+DE\s+EMISS[ÃA]O\s*[:\-]?\s*(20\d{2}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b", text)
    calib = extract_first(r"(?i)\bDATA\s+CALIBRAC[AÃ]O\s*[:\-]?\s*(20\d{2}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b", text)

    # fallback: se não encontrar "DATA DE EMISSÃO", apanhar a 1ª data ISO no header
    if not issue:
        issue = extract_first(r"\b(20\d{2}-\d{2}-\d{2})\b", text)

    # cliente / morada (por rótulo)
    customer_name = extract_label_value("Cliente", text) or extract_label_value("Nome", text)
    customer_address = extract_label_value("Morada", text) or extract_label_value("Endereço", text) or extract_label_value("Endereco", text)

    # fallback leve: nome do cliente pelo nome do ficheiro (sem inventar moradas)
    # Ex: "... - SYMINGTON"
    if not customer_name and source_name:
        m = re.search(r"\-\s*([A-Za-z0-9 .,&\-]+)$", source_name)
        if m:
            customer_name = clean_spaces(m.group(1))

    # equipamento: por rótulos genéricos
    designation = (
        extract_label_value("Designação", text)
        or extract_label_value("Designacao", text)
        or extract_label_value("Equipamento", text)
        or extract_label_value("Instrumento", text)
    )
    brand = extract_label_value("Marca", text)
    model = extract_label_value("Modelo", text)
    serial = (
        extract_label_value("Nº Série", text)
        or extract_label_value("N° Série", text)
        or extract_label_value("No Série", text)
        or extract_label_value("Número de Série", text)
        or extract_label_value("Numero de Serie", text)
        or extract_label_value("Serial", text)
    )
    meas_range = extract_label_value("Alcance", text) or extract_label_value("Intervalo de medição", text) or extract_label_value("Intervalo de medicao", text)
    resolution = extract_label_value("Resolução", text) or extract_label_value("Resolucao", text)
    indication = extract_label_value("Indicação", text) or extract_label_value("Indicacao", text)

    # condições: por rótulos
    location = extract_label_value("Local", text)
    temperature = extract_label_value("Temperatura", text)
    humidity = extract_label_value("Humidade", text) or extract_label_value("Umidade", text)

    # norma / procedimento: por rótulo (e só fallback universal para ISO/EN)
    standard = (
        extract_label_value("Norma", text)
        or extract_label_value("Procedimento", text)
        or extract_label_value("Calibração segundo", text)
        or extract_label_value("Calibracao segundo", text)
        or extract_first(r"(?i)\b(ISO|EN)\s*\d{3,6}[-–]?\d*\s*(?::\s*\d{4})?\b", text)
    )
    standard = clean_spaces(standard)

    return {
        "certificate_number": cert,
        "issue_date": safe_date(issue),
        "calibration_date": safe_date(calib),
        "customer_name": clean_spaces(customer_name),
        "customer_address": clean_spaces(customer_address),
        "equipment": {
            "designation": clean_spaces(designation),
            "brand": clean_spaces(brand),
            "model": clean_spaces(model),
            "serial_number": clean_spaces(serial),
            "range": clean_spaces(meas_range),
            "resolution": clean_spaces(resolution),
            "indication": clean_spaces(indication),
        },
        "conditions": {
            "location": clean_spaces(location),
            "temperature": clean_spaces(temperature),
            "humidity": clean_spaces(humidity),
        },
        "reference": {
            "standard_or_procedure": standard,
        },
    }


# -------------------------
# Results parsing (Fase 0 simples)
# -------------------------
def parse_results(text: str) -> dict:
    """
    Fase 0: só coleciona linhas "tabelares" com muitos números.
    Depois, na próxima fase, fazemos parsing real de tabelas.
    """
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

        for ln in lines[idx: idx + 500]:
            nums = re.findall(r"[-+]?\d+\.\d+|[-+]?\d+", ln)
            if len(nums) >= 6:
                out.append(ln)
                if len(out) >= max_rows:
                    break
        return out

    return {
        "rows_near_results": collect_after("RESULTADOS", max_rows=60),
    }


# -------------------------
# Page split (mantém o teu formato)
# -------------------------
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

    # Header candidate: normalmente na página 1; em casos chatos junta página 2
    header_candidate = "\n".join([
        pages.get("page_01.png", ""),
        pages.get("page_02.png", ""),
    ]).strip() or raw

    header_text = normalize_text(header_candidate)
    header = parse_header_fields(header_text, source_name=txt_path.stem)

    # Results candidate: páginas 2 e 3 (ou tudo)
    results_candidate = "\n".join([
        pages.get("page_02.png", ""),
        pages.get("page_03.png", ""),
    ]).strip() or raw

    results_text = normalize_text(results_candidate)
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