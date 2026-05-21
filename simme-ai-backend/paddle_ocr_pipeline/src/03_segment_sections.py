import json
import re
from pathlib import Path
from datetime import datetime
from pt_text import repair_nested_text, repair_portuguese_text

BASE = Path(__file__).resolve().parents[1]

IN_DIR = BASE / "data" / "ocr_text"
OUT_DIR = BASE / "data" / "sections"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------
# Normalizacao
# -------------------------
def normalize_line(line: str) -> str:
    s = line.upper()

    replacements = {
        "Ã‡": "C",
        "Ãƒ": "A",
        "Ã": "A",
        "Ã‚": "A",
        "Ã•": "O",
        "Ã“": "O",
        "Ã”": "O",
        "Ã‰": "E",
        "ÃŠ": "E",
        "Ã": "I",
        "Ãš": "U",
        "Ã–": "O",
        "Ã„": "A",
        "Ãœ": "U",
    }

    for k, v in replacements.items():
        s = s.replace(k, v)

    s = re.sub(r"\s+", " ", s).strip()
    return s


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def load_region_ocr_blocks(txt_path: Path) -> dict[str, list[dict]] | None:
    region_json_path = txt_path.with_name(f"{txt_path.stem}_regions.json")
    if not region_json_path.exists():
        return None

    try:
        data = read_json(region_json_path)
    except Exception:
        return None

    return data.get("pages") or None


# -------------------------
# Utils
# -------------------------
def lines_of(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.splitlines()]


def parse_region_blocks(text: str) -> list[dict]:
    parts = re.split(r"\n\[region:([^\]]+)\]\n", text)
    if len(parts) < 3:
        return []

    blocks = []
    for i in range(1, len(parts), 2):
        label = parts[i].strip()
        block_text = parts[i + 1].strip()
        if not block_text:
            continue
        blocks.append({"label": label, "text": block_text})

    return blocks


def join_clean(lines: list[str]) -> str:
    out = []
    for ln in lines:
        s = repair_portuguese_text(ln.strip())
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


def append_unique_text(bucket: list[str], text: str) -> None:
    cleaned = remove_footer_noise(text)
    if not cleaned:
        return

    cleaned_norm = normalize_line(cleaned)
    if not cleaned_norm:
        return

    for idx, existing in enumerate(bucket):
        existing_norm = normalize_line(existing)
        if cleaned_norm == existing_norm:
            return
        if cleaned_norm in existing_norm:
            return
        if existing_norm in cleaned_norm:
            bucket[idx] = cleaned
            return

    bucket.append(cleaned)


def bucket_to_text(bucket: list[str]) -> str:
    return "\n".join(bucket).strip()


def sort_region_entries(entries: list[dict]) -> list[dict]:
    def score(item: dict):
        bbox = item.get("bbox") or {}
        x1 = bbox.get("x1", 0)
        y1 = bbox.get("y1", 0)
        x2 = bbox.get("x2", 0)
        y2 = bbox.get("y2", 0)
        area = max(0, x2 - x1) * max(0, y2 - y1)
        confidence = item.get("confidence") or 0.0
        return (y1, x1, -confidence, -area)

    return sorted(entries, key=score)


def looks_like_customer_block(norm: str) -> bool:
    if norm.startswith("CLIENTE"):
        return True
    return "NOME" in norm and "MORADA" in norm


# -------------------------
# Regioes -> secoes
# -------------------------
def segment_first_page_region_entries(entries: list[dict]) -> dict:
    sections = {
        "header_meta": [],
        "customer": [],
        "equipment": [],
        "equipment_state": [],
        "work_conditions": [],
        "description": [],
        "traceability": [],
        "uncertainty": [],
        "calibration_meta": [],
    }

    for entry in sort_region_entries(entries):
        label = entry.get("label") or ""
        block_text = (entry.get("text") or "").strip()
        if not block_text:
            continue
        block_text = repair_portuguese_text(block_text)

        norm = normalize_line(block_text)

        if "RASTREABILIDADE" in norm:
            append_unique_text(sections["traceability"], block_text)
            continue

        if "INCERTEZA" in norm:
            append_unique_text(sections["uncertainty"], block_text)
            continue

        if "ESTADO DO EQUIPAMENTO" in norm:
            append_unique_text(sections["equipment_state"], block_text)
            continue

        if "DATA CALIBRACAO" in norm:
            append_unique_text(sections["calibration_meta"], block_text)
            if label == "metadata_block":
                append_unique_text(sections["header_meta"], block_text)
            continue

        if looks_like_customer_block(norm):
            append_unique_text(sections["customer"], block_text)
            continue

        if (
            "EQUIPAMENTO CALIBRADO" in norm or
            "DESIGNAGAO" in norm or
            "DESIGNACAO" in norm or
            "MARCA" in norm or
            "MODELO" in norm or
            "SERIE" in norm
        ):
            append_unique_text(sections["equipment"], block_text)
            continue

        if (
            "CONDICOES DO TRABALHO" in norm or
            ("CONDI" in norm and "TRABALHO" in norm) or
            "INSTALAC" in norm
        ):
            append_unique_text(sections["work_conditions"], block_text)
            continue

        if "DESCRICAO" in norm or "DOCUMENTOS NORMATIVOS" in norm:
            append_unique_text(sections["description"], block_text)
            continue

        if "CERTIFICADO" in norm or "DATA DE EMISSAO" in norm or label == "metadata_block":
            append_unique_text(sections["header_meta"], block_text)
            continue

        if label == "reference_block":
            append_unique_text(sections["description"], block_text)
            continue
        if label == "customer_block":
            append_unique_text(sections["customer"], block_text)
            continue
        if label == "equipment_block":
            append_unique_text(sections["equipment"], block_text)
            continue
        if label == "equipment_state_block":
            append_unique_text(sections["equipment_state"], block_text)
            continue
        if label in {"work_conditions_block", "calibration_date_block"}:
            if "LOCAL" in norm or "TRABALHO" in norm or "INSTALAC" in norm:
                append_unique_text(sections["work_conditions"], block_text)
            elif "DATA CALIBRACAO" in norm:
                append_unique_text(sections["calibration_meta"], block_text)
            else:
                append_unique_text(sections["header_meta"], block_text)

    return {key: bucket_to_text(value) for key, value in sections.items()}


def segment_results_page_region_entries(entries: list[dict]) -> dict:
    sections = {
        "results": [],
        "environmental_conditions": [],
        "observations": [],
    }

    for entry in sort_region_entries(entries):
        label = entry.get("label") or ""
        block_text = (entry.get("text") or "").strip()
        if not block_text:
            continue
        block_text = repair_portuguese_text(block_text)

        norm = normalize_line(block_text)

        if label == "results_table" or "RESULTADOS" in norm:
            append_unique_text(sections["results"], block_text)
            continue

        if "CONDICOES AMBIENTAIS" in norm or "PRESSAO ATMOSFERICA" in norm or "DENSIDADE DO AR" in norm:
            append_unique_text(sections["environmental_conditions"], block_text)
            continue

        if "OBSERVACOES" in norm:
            append_unique_text(sections["observations"], block_text)
            continue

    return {key: bucket_to_text(value) for key, value in sections.items()}


def segment_first_page_regions(text: str) -> dict:
    return segment_first_page_region_entries(parse_region_blocks(text))


def segment_results_page_regions(text: str) -> dict:
    return segment_results_page_region_entries(parse_region_blocks(text))


# -------------------------
# Segmentacao pagina 1 fallback
# -------------------------
def segment_first_page(text: str) -> dict:
    if "[region:" in text:
        return segment_first_page_regions(text)

    lines = lines_of(text)

    section_order = [
        ("customer", ["CLIENTE"], ["EQUIPAMENTO CALIBRADO"]),
        ("equipment", ["EQUIPAMENTO CALIBRADO"], ["CONDICOES DO TRABALHO REALIZADO", "CONDIÃ‡Ã•ES DO TRABALHO REALIZADO", "CONDICÃ–ES DO TRABALHO REALIZADO"]),
        ("work_conditions", ["CONDICOES DO TRABALHO REALIZADO", "CONDIÃ‡Ã•ES DO TRABALHO REALIZADO", "CONDICÃ–ES DO TRABALHO REALIZADO"], ["DESCRICAO", "DESCRIÃ‡ÃƒO"]),
        ("description", ["DESCRICAO", "DESCRIÃ‡ÃƒO"], ["RASTREABILIDADE", "INCERTEZA"]),
        ("traceability", ["RASTREABILIDADE"], ["INCERTEZA", "DATA CALIBRACAO", "DATA CALIBRAÃ‡ÃƒO"]),
        ("uncertainty", ["INCERTEZA"], ["DATA CALIBRACAO", "DATA CALIBRAÃ‡ÃƒO", "RESULTADOS"]),
        ("calibration_meta", ["DATA CALIBRACAO", "DATA CALIBRAÃ‡ÃƒO"], []),
    ]

    sections = {
        "header_meta": "",
        "customer": "",
        "equipment": "",
        "equipment_state": "",
        "work_conditions": "",
        "description": "",
        "traceability": "",
        "uncertainty": "",
        "calibration_meta": "",
    }

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
# Segmentacao paginas de resultados fallback
# -------------------------
def segment_results_page(text: str) -> dict:
    if "[region:" in text:
        return segment_results_page_regions(text)

    lines = lines_of(text)

    sections = {
        "results": "",
        "environmental_conditions": "",
        "observations": "",
    }

    idx_results = find_first_line_index(lines, ["RESULTADOS"])
    idx_env = find_first_line_index(lines, ["CONDICOES AMBIENTAIS", "CONDIÃ‡Ã•ES AMBIENTAIS"])
    idx_obs = find_first_line_index(lines, ["OBSERVACOES", "OBSERVAÃ‡Ã•ES"])

    if idx_results is None:
        idx_results = 0

    results_start = idx_results + 1
    results_end_candidates = [x for x in [idx_env, idx_obs] if x is not None]
    results_end = min(results_end_candidates) if results_end_candidates else len(lines)
    sections["results"] = remove_footer_noise(join_clean(lines[results_start:results_end]))

    if idx_env is not None:
        env_start = idx_env + 1
        env_end = idx_obs if idx_obs is not None and idx_obs > idx_env else len(lines)
        sections["environmental_conditions"] = remove_footer_noise(join_clean(lines[env_start:env_end]))

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
    region_pages = load_region_ocr_blocks(txt_path) or {}

    page_keys = sorted(pages.keys())

    page_sections = {}
    page_region_blocks = {}

    for page_key in page_keys:
        page_text = pages[page_key]
        page_entries = region_pages.get(page_key, [])
        page_region_blocks[page_key] = repair_nested_text(page_entries)

        if page_key == "page_01.png":
            if page_entries:
                page_sections[page_key] = segment_first_page_region_entries(page_entries)
            else:
                page_sections[page_key] = segment_first_page(page_text)
        else:
            if page_entries:
                page_sections[page_key] = segment_results_page_region_entries(page_entries)
            else:
                page_sections[page_key] = segment_results_page(page_text)

    return repair_nested_text({
        "source_file": txt_path.name,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "page_sections": page_sections,
        "page_region_blocks": page_region_blocks,
    })


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
