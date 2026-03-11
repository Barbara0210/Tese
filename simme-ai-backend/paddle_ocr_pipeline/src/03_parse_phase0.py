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

    t = remove_watermark_spam(t)
    return t


# -------------------------
# Helpers: generic utils
# -------------------------
def clean_spaces(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


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
# Section extraction
# -------------------------
def _norm_key(s: str) -> str:
    # normalização leve para comparar headers (tolerante ao OCR)
    s = s.upper()
    s = s.replace("Ç", "C").replace("Ã", "A").replace("Á", "A").replace("Â", "A")
    s = s.replace("Õ", "O").replace("Ó", "O").replace("Ô", "O")
    s = s.replace("É", "E").replace("Ê", "E")
    s = s.replace("Í", "I")
    s = s.replace("Ú", "U")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_section(text: str, start_labels: list[str], end_labels: list[str]) -> str:
    """
    Extrai um bloco de texto entre um start_label e o próximo end_label.
    Trabalha por linhas e é tolerante a variações do OCR.
    """
    lines = text.splitlines()
    start_idx = None

    start_labels_n = [_norm_key(x) for x in start_labels]
    end_labels_n = [_norm_key(x) for x in end_labels]

    for i, ln in enumerate(lines):
        k = _norm_key(ln)
        if any(lbl in k for lbl in start_labels_n):
            start_idx = i
            break

    if start_idx is None:
        return ""

    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        k = _norm_key(lines[j])
        if any(lbl in k for lbl in end_labels_n):
            end_idx = j
            break

    block = "\n".join(lines[start_idx:end_idx]).strip()
    return block


# -------------------------
# Label/value extraction (inside a section)
# -------------------------
def _label_regex(label: str) -> str:
    lab = re.escape(label.strip())
    lab = lab.replace(r"\ ", r"\s*")
    return rf"(?i)\b{lab}\b\s*[:\-]?\s*"


def extract_label_value(label: str, text: str, *, max_lines: int = 3) -> str | None:
    """
    Extrai valor para um rótulo (label) dentro de um bloco/section.
    Suporta:
      - "LABEL: valor"
      - "LABEL\nvalor"
      - "LABEL - valor"
    """
    lines = [ln.strip() for ln in text.splitlines()]
    if not lines:
        return None

    lab_pat = re.compile(_label_regex(label))

    # palavras que indicam "mudança de secção"
    stop_words = {
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
        "PAGINA",
        "PÁGINA",
    }

    # se dentro do mesmo bloco aparecer outro label conhecido (linha curta), para
    def looks_like_label_line(s: str) -> bool:
        s2 = s.strip()
        if not s2:
            return False
        if len(s2) > 32:
            return False
        # "Marca", "Modelo", "Local", "Temperatura", etc.
        return bool(re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÁÀÂÃÉÊÍÓÔÕÚÇ0-9 ()/%\.\-]{0,28}\s*[:\-]?$", s2))

    for i, ln in enumerate(lines):
        m = lab_pat.search(ln)
        if not m:
            continue

        # 1) valor na mesma linha (pode vir seguido de outros labels)
        after = ln[m.end():].strip()
        if after:
            return clean_spaces(after)

        # 2) valor nas linhas seguintes
        out = []
        for j in range(i + 1, min(i + 1 + max_lines, len(lines))):
            cur = lines[j].strip()
            if not cur:
                continue

            cur_up = re.sub(r"[:\-]\s*$", "", cur).strip().upper()
            if cur_up in stop_words:
                break
            if looks_like_label_line(cur):
                break

            out.append(cur)

        return clean_spaces(" | ".join(out)) if out else None

    return None


def extract_inline_value_between_labels(line: str, label: str, next_labels: list[str]) -> str | None:
    """
    Para casos tipo:
      "Marca WIKA Intervalo de indicação -1 a 3 bar"
    Extrai "WIKA" (corta no próximo label).
    """
    # montar lookahead para "próximo label"
    next_pat = "|".join([re.escape(x) for x in next_labels])
    # label + valor até próximo label ou fim
    pat = rf"(?i)\b{re.escape(label)}\b\s*[:\-]?\s*(.+?)(?=\s+\b(?:{next_pat})\b|$)"
    return extract_first(pat, line, flags=re.IGNORECASE)


def extract_label_value_smart(label: str, section_text: str, next_labels: list[str]) -> str | None:
    """
    Primeiro tenta extração normal (linha/linhas seguintes).
    Se falhar, tenta a extração inline cortando no próximo label.
    """
    v = extract_label_value(label, section_text)
    if v:
        # se o OCR colou outros labels na mesma "value", tenta limpar
        # Ex: "WIKA Intervalo de indicação -1 a 3 bar" -> "WIKA"
        v2 = extract_inline_value_between_labels(v, label, next_labels)
        if v2:
            return clean_spaces(v2)
        return clean_spaces(v)

    # tentar procurar inline em qualquer linha
    for ln in section_text.splitlines():
        v_inline = extract_inline_value_between_labels(ln, label, next_labels)
        if v_inline:
            return clean_spaces(v_inline)

    return None


# -------------------------
# Header parsing (GENÉRICO, por secções)
# -------------------------
def parse_header_fields(text: str, source_name: str | None = None) -> dict:
    # certificado (genérico)
    cert = extract_first(
        r"(?i)\bCertificado\s*(?:n[º°o\*]?\s*[:\-]?\s*)\s*([A-Z]{1,6}\s*\d{6,}[0-9/.\-]*)\b",
        text,
    )
    if cert:
        cert = re.sub(r"\s+", "", cert)

    issue = extract_first(
        r"(?i)\bDATA\s+DE\s+EMISS[ÃA]O\s*[:\-]?\s*(20\d{2}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b",
        text,
    )
    calib = extract_first(
        r"(?i)\bDATA\s+CALIBRAC[AÃ]O\s*[:\-]?\s*(20\d{2}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b",
        text,
    )
    if not issue:
        issue = extract_first(r"\b(20\d{2}-\d{2}-\d{2})\b", text)

    # secções
    cliente_sec = extract_section(
        text,
        start_labels=["CLIENTE"],
        end_labels=["EQUIPAMENTO CALIBRADO", "CONDICOES DO TRABALHO REALIZADO", "DESCRICAO", "RESULTADOS"],
    )
    equip_sec = extract_section(
        text,
        start_labels=["EQUIPAMENTO CALIBRADO"],
        end_labels=["CONDICOES DO TRABALHO REALIZADO", "DESCRICAO", "RESULTADOS", "RASTREABILIDADE"],
    )
    cond_sec = extract_section(
        text,
        start_labels=["CONDICOES DO TRABALHO REALIZADO", "CONDIÇÕES DO TRABALHO REALIZADO"],
        end_labels=["DESCRICAO", "RESULTADOS", "RASTREABILIDADE", "INCERTEZA"],
    )
    descr_sec = extract_section(
        text,
        start_labels=["DESCRICAO", "DESCRIÇÃO"],
        end_labels=["RASTREABILIDADE", "INCERTEZA", "RESULTADOS"],
    )

    # cliente (somente dentro da secção CLIENTE)
    customer_name = extract_label_value("Nome", cliente_sec) or extract_label_value("Cliente", cliente_sec)
    customer_address = extract_label_value("Morada", cliente_sec) or extract_label_value("Endereço", cliente_sec) or extract_label_value("Endereco", cliente_sec)

    # fallback leve: nome do cliente pelo nome do ficheiro
    if not customer_name and source_name:
        m = re.search(r"\-\s*([A-Za-z0-9 .,&\-]+)$", source_name)
        if m:
            customer_name = clean_spaces(m.group(1))

    # equipamento (somente dentro da secção EQUIPAMENTO CALIBRADO)
    # lista de "próximos labels" para cortar inline
    equip_next = [
        "Modelo", "Nº Série", "N° Série", "No Série", "Número de Série", "Numero de Serie",
        "Intervalo", "Intervalo de indicação", "Intervalo de indicacao",
        "Alcance", "Resolução", "Resolucao", "Resolução estimada", "Resolucao estimada",
        "Indicação", "Indicacao", "Classe", "Ref Interna", "Ref. Interna", "Ref",
        "Estado do equipamento",
    ]

    designation = (
        extract_label_value_smart("Designação", equip_sec, equip_next)
        or extract_label_value_smart("Designacao", equip_sec, equip_next)
        or extract_label_value_smart("Equipamento", equip_sec, equip_next)
        or extract_label_value_smart("Instrumento", equip_sec, equip_next)
    )

    brand = extract_label_value_smart("Marca", equip_sec, equip_next)
    model = extract_label_value_smart("Modelo", equip_sec, equip_next)

    serial = (
        extract_label_value_smart("Nº Série", equip_sec, equip_next)
        or extract_label_value_smart("N° Série", equip_sec, equip_next)
        or extract_label_value_smart("No Série", equip_sec, equip_next)
        or extract_label_value_smart("Número de Série", equip_sec, equip_next)
        or extract_label_value_smart("Numero de Serie", equip_sec, equip_next)
        or extract_label_value_smart("Serial", equip_sec, equip_next)
    )

    meas_range = (
        extract_label_value_smart("Alcance", equip_sec, equip_next)
        or extract_label_value_smart("Alcance de medição", equip_sec, equip_next)
        or extract_label_value_smart("Alcance de medicao", equip_sec, equip_next)
        or extract_label_value_smart("Intervalo de indicação", equip_sec, equip_next)
        or extract_label_value_smart("Intervalo de indicacao", equip_sec, equip_next)
        or extract_label_value_smart("Intervalo de medição", equip_sec, equip_next)
        or extract_label_value_smart("Intervalo de medicao", equip_sec, equip_next)
    )

    resolution = (
        extract_label_value_smart("Resolução", equip_sec, equip_next)
        or extract_label_value_smart("Resolucao", equip_sec, equip_next)
        or extract_label_value_smart("Resolução estimada", equip_sec, equip_next)
        or extract_label_value_smart("Resolucao estimada", equip_sec, equip_next)
    )

    indication = extract_label_value_smart("Indicação", equip_sec, equip_next) or extract_label_value_smart("Indicacao", equip_sec, equip_next)

    # condições (somente dentro da secção CONDIÇÕES)
    # aqui NÃO agrupamos labels: cada campo é extraído pelo seu label
    cond_next = ["Temperatura", "Humidade", "Umidade", "Anexo", "Anexo Técnico", "Anexo Técnico de Acreditação", "DESCRIÇÃO", "DESCRICAO"]
    location = extract_label_value_smart("Local", cond_sec, cond_next)

    # alguns OCRs metem: "Local Porto Temperatura (20 ± 2)°C" tudo na mesma linha
    if not location:
        for ln in cond_sec.splitlines():
            v = extract_inline_value_between_labels(ln, "Local", ["Temperatura", "Humidade", "Umidade"])
            if v:
                location = clean_spaces(v)
                break

    temperature = extract_label_value("Temperatura", cond_sec)
    humidity = extract_label_value("Humidade", cond_sec) or extract_label_value("Umidade", cond_sec)

    # norma / procedimento (preferir "DESCRIÇÃO" se existir)
    standard = (
        extract_first(r"(?i)\b(NP\s*EN\s*\d{2,6}[-–]?\d*\s*(?::\s*\d{4})?)\b", descr_sec)
        or extract_first(r"(?i)\b(ISO\s*\d{3,6}[-–]?\d*\s*(?::\s*\d{4})?)\b", descr_sec)
        or extract_first(r"(?i)\b(EN\s*\d{3,6}[-–]?\d*\s*(?::\s*\d{4})?)\b", descr_sec)
    )

    return {
        "certificate_number": clean_spaces(cert),
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
            "standard_or_procedure": clean_spaces(standard),
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

    def collect_after(hint: str, max_rows=60):
        out = []
        idx = None
        for i, ln in enumerate(lines):
            if hint.lower() in ln.lower():
                idx = i
                break
        if idx is None:
            return out

        for ln in lines[idx: idx + 800]:
            nums = re.findall(r"[-+]?\d+\.\d+|[-+]?\d+", ln)
            if len(nums) >= 5:
                out.append(ln)
                if len(out) >= max_rows:
                    break
        return out

    return {
        "rows_near_results": collect_after("RESULTADOS", max_rows=80),
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