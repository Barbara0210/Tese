import json
import re
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]

IN_DIR = BASE / "data" / "ocr_text"
OUT_DIR = BASE / "data" / "sections"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------
# Normalização
# -------------------------
def normalize_line(line: str) -> str:
    s = line.upper()

    replacements = {
        "Ç": "C",
        "Ã": "A",
        "Á": "A",
        "Â": "A",
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

    for k, v in replacements.items():
        s = s.replace(k, v)

    s = re.sub(r"\s+", " ", s).strip()
    return s


# -------------------------
# Split pages
# -------------------------
def split_pages(raw: str) -> dict:
    parts = re.split(r"\n===\s*(page_\d+\.png)\s*===\n", raw)

    if len(parts) < 3:
        return {"__all__": raw}

    pages = {}
    for i in range(1, len(parts), 2):
        key = parts[i].strip()
        content = parts[i + 1]
        pages[key] = content.strip()

    return pages


# -------------------------
# Utils
# -------------------------
def lines_of(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.splitlines()]


def join_clean(lines: list[str]) -> str:
    out = []
    for ln in lines:
        s = ln.strip()
        if s:
            out.append(s)
    return "\n".join(out).strip()


def find_first_line_index(lines: list[str], candidates: list[str]) -> int | None:
    norms = [normalize_line(x) for x in candidates]

    for i, ln in enumerate(lines):
        n = normalize_line(ln)
        for c in norms:
            if c and c in n:
                return i
    return None


def find_next_line_index(lines: list[str], start_idx: int, candidates: list[str]) -> int | None:
    norms = [normalize_line(x) for x in candidates]

    for i in range(start_idx, len(lines)):
        n = normalize_line(lines[i])
        for c in norms:
            if c and c in n:
                return i
    return None


def slice_between(lines: list[str], start_candidates: list[str], end_candidates: list[str], include_start: bool = False) -> str:
    start_idx = find_first_line_index(lines, start_candidates)
    if start_idx is None:
        return ""

    content_start = start_idx if include_start else start_idx + 1
    end_idx = find_next_line_index(lines, content_start, end_candidates)

    if end_idx is None:
        end_idx = len(lines)

    return join_clean(lines[content_start:end_idx])


def remove_footer_noise(text: str) -> str:
    """
    Remove linhas muito repetitivas de moradas/rodapés e frases legais comuns.
    Não agressivo.
    """
    bad_patterns = [
        r"^RUA DOS PLATANOS",
        r"^RUA CIDADE DO PORTO",
        r"^ESTRADA DO PACO DO LUMIAR",
        r"^4100-414 PORTO",
        r"^4705-086 BRAGA",
        r"^1649-038 LISBOA",
        r"^OS RESULTADOS APRESENTADOS REFER",
        r"^ESTE DOCUMENTO NAO PODE SER REPRODUZIDO",
        r"^AUTORIZACAO POR ESCRITO DO CATIM",
        r"^: ITENS CALIBRADOS OU ENSAIADOS",
        r"^S ITENS CALIBRADOS OU ENSAIADOS",
    ]

    out = []
    for ln in lines_of(text):
        n = normalize_line(ln)
        if any(re.search(p, n) for p in bad_patterns):
            continue
        out.append(ln)

    return join_clean(out)


# -------------------------
# Segmentação página 1
# -------------------------
def segment_first_page(text: str) -> dict:
    lines = lines_of(text)

    # ordem esperada na página 1
    section_order = [
        ("customer", ["CLIENTE"], ["EQUIPAMENTO CALIBRADO"]),
        ("equipment", ["EQUIPAMENTO CALIBRADO"], ["CONDICOES DO TRABALHO REALIZADO", "CONDIÇÕES DO TRABALHO REALIZADO", "CONDICÖES DO TRABALHO REALIZADO"]),
        ("work_conditions", ["CONDICOES DO TRABALHO REALIZADO", "CONDIÇÕES DO TRABALHO REALIZADO", "CONDICÖES DO TRABALHO REALIZADO"], ["DESCRICAO", "DESCRIÇÃO"]),
        ("description", ["DESCRICAO", "DESCRIÇÃO"], ["RASTREABILIDADE", "INCERTEZA"]),
        ("traceability", ["RASTREABILIDADE"], ["INCERTEZA", "DATA CALIBRACAO", "DATA CALIBRAÇÃO"]),
        ("uncertainty", ["INCERTEZA"], ["DATA CALIBRACAO", "DATA CALIBRAÇÃO", "RESULTADOS"]),
        ("calibration_meta", ["DATA CALIBRACAO", "DATA CALIBRAÇÃO"], []),
    ]

    sections = {
        "header_meta": "",
        "customer": "",
        "equipment": "",
        "work_conditions": "",
        "description": "",
        "traceability": "",
        "uncertainty": "",
        "calibration_meta": "",
    }

    # header_meta = tudo antes de CLIENTE
    idx_customer = find_first_line_index(lines, ["CLIENTE"])
    if idx_customer is None:
        sections["header_meta"] = join_clean(lines)
        return sections

    sections["header_meta"] = join_clean(lines[:idx_customer])

    for sec_name, start_labels, end_labels in section_order:
        if end_labels:
            block = slice_between(lines, start_labels, end_labels, include_start=False)
        else:
            start_idx = find_first_line_index(lines, start_labels)
            if start_idx is None:
                block = ""
            else:
                block = join_clean(lines[start_idx + 1:])

        sections[sec_name] = remove_footer_noise(block)

    return sections


# -------------------------
# Segmentação páginas de resultados
# -------------------------
def segment_results_page(text: str) -> dict:
    lines = lines_of(text)

    sections = {
        "results": "",
        "environmental_conditions": "",
        "observations": "",
    }

    idx_results = find_first_line_index(lines, ["RESULTADOS"])
    idx_env = find_first_line_index(lines, ["CONDICOES AMBIENTAIS", "CONDIÇÕES AMBIENTAIS"])
    idx_obs = find_first_line_index(lines, ["OBSERVACOES", "OBSERVAÇÕES"])

    # se não houver RESULTADOS, assume a página inteira como resultados/continuação
    if idx_results is None:
        idx_results = 0

    # bloco results
    results_start = idx_results + 1
    results_end_candidates = [x for x in [idx_env, idx_obs] if x is not None]
    results_end = min(results_end_candidates) if results_end_candidates else len(lines)
    sections["results"] = remove_footer_noise(join_clean(lines[results_start:results_end]))

    # bloco environmental_conditions
    if idx_env is not None:
        env_start = idx_env + 1
        env_end = idx_obs if idx_obs is not None and idx_obs > idx_env else len(lines)
        sections["environmental_conditions"] = remove_footer_noise(join_clean(lines[env_start:env_end]))

    # bloco observations
    if idx_obs is not None:
        obs_start = idx_obs + 1
        sections["observations"] = remove_footer_noise(join_clean(lines[obs_start:]))

    return sections


# -------------------------
# Estrutura final por documento
# -------------------------
def process_document(txt_path: Path) -> dict:
    raw = txt_path.read_text(encoding="utf-8", errors="ignore")
    pages = split_pages(raw)

    page_keys = sorted(pages.keys())

    page_sections = {}

    for page_key in page_keys:
        page_text = pages[page_key]

        # primeira página
        if page_key == "page_01.png":
            page_sections[page_key] = segment_first_page(page_text)
        else:
            page_sections[page_key] = segment_results_page(page_text)

    return {
        "source_file": txt_path.name,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "page_sections": page_sections,
    }


# -------------------------
# Main
# -------------------------
def main():
    txt_files = sorted(IN_DIR.glob("*.txt"))

    if not txt_files:
        print("Sem OCR txt")
        return

    for txt in txt_files:
        data = process_document(txt)

        out = OUT_DIR / (txt.stem + "_sections.json")
        out.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        print("saved:", out)


if __name__ == "__main__":
    main()