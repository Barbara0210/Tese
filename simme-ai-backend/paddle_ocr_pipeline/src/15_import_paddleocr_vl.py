"""
Import PaddleOCR-VL Colab results into the project pipeline format.

Expected input:
    data/paddleocr_vl/run_summary.json
or:
    data/paddleocr_vl/<document name>/run_summary.json

The Colab command prints the useful `{'res': ...}` payload to stderr. This
script extracts `parsing_res_list`, converts HTML tables, and writes the same
artifacts used by the other methods:
    data/parsed/<doc>.json
    data/tables/<doc>_tables.json
    data/sections/<doc>_sections.json
"""

from __future__ import annotations

import ast
import html
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    from pt_text import repair_nested_text, repair_portuguese_text
except Exception:  # pragma: no cover - keeps this importer usable standalone
    def repair_portuguese_text(value: str) -> str:
        return value

    def repair_nested_text(value: Any) -> Any:
        return value


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_PDFS_DIR = DATA_DIR / "raw_pdfs"
PADDLEOCR_VL_DIR = DATA_DIR / "paddleocr_vl"
PARSED_DIR = DATA_DIR / "parsed"
TABLES_DIR = DATA_DIR / "tables"
SECTIONS_DIR = DATA_DIR / "sections"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


def normalize_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text


def normalize_label(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("º", "").replace("°", "")
    return re.sub(r"\s+", " ", text).strip().upper()


def clean_text(text: Any) -> str:
    if text is None:
        return ""
    value = html.unescape(str(text))
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return repair_portuguese_text(value.strip())


def parse_number(value: Any) -> float | None:
    text = html.unescape(str(value or "")).strip()
    if not text:
        return None
    text = text.replace("\u00a0", " ")
    text = re.sub(r"(?<=\d)\s+(?=\d{3}(?:[,.]|\b))", "", text)
    text = re.sub(r"[^0-9,.\-+]", "", text)
    if not text or text in {"-", "+", ".", ","}:
        return None
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def bracketed_literal(text: str, start: int) -> str:
    """Return a Python list/dict literal starting at `start`.

    The PaddleOCR-VL CLI emits a Python repr, not JSON. We only need the
    `parsing_res_list`, so a small bracket matcher is safer than trying to
    evaluate the whole payload containing numpy `array(...)` reprs.
    """
    if start < 0 or start >= len(text):
        raise ValueError("Invalid literal start")

    opening = text[start]
    closing = {"[": "]", "{": "}"}[opening]
    depth = 0
    quote: str | None = None
    escaped = False

    for index in range(start, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in {"'", '"'}:
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError("Could not find literal end")


def extract_parsing_blocks(stderr: str) -> list[dict[str, Any]]:
    text = strip_ansi(stderr)
    marker = "'parsing_res_list':"
    marker_index = text.find(marker)
    if marker_index < 0:
        return []

    list_start = text.find("[", marker_index)
    if list_start < 0:
        return []

    literal = bracketed_literal(text, list_start)
    blocks = ast.literal_eval(literal)
    if not isinstance(blocks, list):
        return []
    return [block for block in blocks if isinstance(block, dict)]


def extract_page_items(stderr: str, fallback_page_name: str) -> list[tuple[str, list[dict[str, Any]]]]:
    """Extract every PaddleOCR-VL page result printed in one CLI stderr.

    When Colab calls `paddleocr doc_parser` with a whole directory, the model is
    loaded once and the CLI may print multiple `{'res': ...}` payloads in the
    same stderr stream. This keeps the old one-page-per-process summary working
    while enabling the faster document-level mode.
    """
    text = strip_ansi(stderr)
    marker = "'parsing_res_list':"
    cursor = 0
    items: list[tuple[str, list[dict[str, Any]]]] = []

    while True:
        marker_index = text.find(marker, cursor)
        if marker_index < 0:
            break

        list_start = text.find("[", marker_index)
        if list_start < 0:
            break

        try:
            literal = bracketed_literal(text, list_start)
            blocks = ast.literal_eval(literal)
        except Exception:
            cursor = marker_index + len(marker)
            continue

        if not isinstance(blocks, list):
            cursor = list_start + 1
            continue

        result_start = text.rfind("{'res':", 0, marker_index)
        segment = text[result_start:marker_index] if result_start >= 0 else text[max(0, marker_index - 2000):marker_index]
        input_match = re.search(r"'input_path'\s*:\s*'([^']+)'", segment)
        if input_match:
            page_name = Path(input_match.group(1)).name
        elif not items:
            page_name = fallback_page_name
        else:
            page_name = f"{Path(fallback_page_name).stem}_{len(items) + 1}.png"

        items.append((page_name, [block for block in blocks if isinstance(block, dict)]))
        cursor = list_start + len(literal)

    if items:
        return items

    blocks = extract_parsing_blocks(stderr)
    return [(fallback_page_name, blocks)] if blocks else []


def select_run_summary() -> tuple[Path, str]:
    candidates = sorted(PADDLEOCR_VL_DIR.rglob("run_summary.json"))
    if not candidates:
        raise FileNotFoundError(
            "Nao encontrei data/paddleocr_vl/run_summary.json. "
            "Copia para essa pasta o run_summary.json gerado no Colab."
        )

    pdfs = sorted(RAW_PDFS_DIR.glob("*.pdf"))
    if pdfs:
        document_name = pdfs[0].stem
        wanted = normalize_key(document_name)
        matching = [
            path
            for path in candidates
            if wanted in normalize_key(str(path.parent)) or wanted in normalize_key(path.read_text(encoding="utf-8", errors="ignore")[:2000])
        ]
        if matching:
            return matching[0], document_name
        if len(candidates) > 1:
            raise FileNotFoundError(
                f"Existem varios run_summary.json em {PADDLEOCR_VL_DIR}, mas nenhum parece corresponder a '{document_name}'."
            )
        return candidates[0], document_name

    if len(candidates) > 1:
        raise FileNotFoundError(
            f"Existem varios run_summary.json em {PADDLEOCR_VL_DIR}. "
            "Mantem apenas um ou executa atraves do backend com o PDF carregado."
        )
    return candidates[0], candidates[0].parent.name


class HtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(clean_text(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(cell for cell in self._row):
                self.rows.append(self._row)
            self._row = None


def parse_html_table(markup: str) -> list[list[str]]:
    parser = HtmlTableParser()
    parser.feed(markup or "")
    return parser.rows


def iter_table_rows(pages: list["PageResult"]) -> list[list[str]]:
    rows: list[list[str]] = []
    for page in pages:
        for block in page.blocks:
            if block.get("block_label") == "table":
                rows.extend(parse_html_table(block_content(block)))
    return rows


def row_label(row: list[str], index: int = 0) -> str:
    if index >= len(row):
        return ""
    return normalize_label(row[index])


def row_has_label(row: list[str], labels: set[str]) -> bool:
    return row_label(row) in labels


def value_after_row_label(rows: list[list[str]], labels: set[str]) -> str | None:
    for index, row in enumerate(rows):
        if not row_has_label(row, labels):
            continue
        if len(row) > 1 and clean_text(row[1]):
            return clean_text(row[1])
        if index + 1 < len(rows) and rows[index + 1]:
            return clean_text(rows[index + 1][0])
    return None


def values_after_repeated_label(rows: list[list[str]], label: str) -> list[str]:
    wanted = normalize_label(label)
    values: list[str] = []
    for row in rows:
        for index, cell in enumerate(row[:-1]):
            if normalize_label(cell) == wanted:
                value = clean_text(row[index + 1])
                if value and value != "---":
                    values.append(value)
    return values


def join_values(values: list[str]) -> str | None:
    unique: list[str] = []
    for value in values:
        if value and value not in unique:
            unique.append(value)
    return " / ".join(unique) if unique else None


def text_from_rows(rows: list[list[str]], labels: set[str]) -> str:
    selected = []
    for row in rows:
        if row_has_label(row, labels):
            selected.append(" | ".join(cell for cell in row if cell))
    return "\n".join(selected)


def table_text_after_label(rows: list[list[str]], label: str) -> str | None:
    wanted = normalize_label(label)
    for index, row in enumerate(rows):
        if row_label(row) == wanted:
            collected = []
            for next_row in rows[index + 1:]:
                if len(next_row) == 1 and normalize_label(next_row[0]) in {
                    "RASTREABILIDADE",
                    "INCERTEZA",
                    "DATA CALIBRACAO",
                    "RESULTADOS",
                }:
                    break
                if next_row:
                    collected.append(" ".join(cell for cell in next_row if cell))
            return "\n".join(collected).strip() or None
    return None


@dataclass
class PageResult:
    page_name: str
    page_number: int | None
    blocks: list[dict[str, Any]]


def parse_page_number(page_name: str) -> int | None:
    match = re.search(r"(\d+)", page_name or "")
    return int(match.group(1)) if match else None


def load_pages(summary_path: Path) -> list[PageResult]:
    run_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(run_summary, list):
        raise ValueError("run_summary.json deve conter uma lista de paginas.")

    pages: list[PageResult] = []
    for entry in run_summary:
        if not isinstance(entry, dict):
            continue
        page_name = str(entry.get("page") or entry.get("output_dir") or "page")
        if int(entry.get("returncode", 1)) != 0:
            print(f"[WARN] A ignorar {page_name}: returncode={entry.get('returncode')}", file=sys.stderr)
            continue
        page_items = extract_page_items(str(entry.get("stderr") or ""), page_name)
        if not page_items:
            print(f"[WARN] A pagina {page_name} nao tem parsing_res_list utilizavel.", file=sys.stderr)
            continue
        for item_page_name, blocks in page_items:
            pages.append(
                PageResult(
                    page_name=item_page_name,
                    page_number=parse_page_number(item_page_name),
                    blocks=blocks,
                )
            )

    pages.sort(key=lambda page: (page.page_number is None, page.page_number or 0, page.page_name))
    if not pages:
        raise ValueError("Nao encontrei paginas validas com parsing_res_list no run_summary.json.")
    return pages


def block_content(block: dict[str, Any]) -> str:
    return clean_text(block.get("block_content", ""))


def all_block_text(pages: list[PageResult]) -> str:
    return "\n".join(block_content(block) for page in pages for block in page.blocks if block_content(block))


def find_first_text(pages: list[PageResult], pattern: str, flags: int = re.IGNORECASE) -> str:
    regex = re.compile(pattern, flags)
    for page in pages:
        for block in page.blocks:
            text = block_content(block)
            if regex.search(text):
                return text
    return ""


def value_after_colon(text: str) -> str:
    if ":" not in text:
        return ""
    return clean_text(text.split(":", 1)[1])


def extract_date(text: str) -> str | None:
    match = re.search(r"\b(20\d{2}[-/.]\d{2}[-/.]\d{2})\b", text or "")
    if match:
        return match.group(1).replace("/", "-").replace(".", "-")

    short_match = re.search(r"(?:^|[^0-9])([2-3]\d)[-/.](\d{2})[-/.](\d{2})(?:[^0-9]|$)", text or "")
    if short_match:
        year, month, day = short_match.groups()
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"20{year}-{month}-{day}"
    return None


def extract_dates(text: str) -> list[str]:
    dates: list[str] = []
    for match in re.finditer(r"\b(20\d{2})[-/.](\d{2})[-/.](\d{2})\b", text or ""):
        dates.append(f"{match.group(1)}-{match.group(2)}-{match.group(3)}")
    for match in re.finditer(r"(?:^|[^0-9])([2-3]\d)[-/.](\d{2})[-/.](\d{2})(?:[^0-9]|$)", text or ""):
        year, month, day = match.groups()
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            dates.append(f"20{year}-{month}-{day}")
    return dates


def extract_customer(page: PageResult | None) -> dict[str, Any]:
    if page is None:
        return {"name": None, "address": None}

    contents = [block_content(block) for block in page.blocks]
    start = next((idx for idx, text in enumerate(contents) if normalize_label(text).startswith("CLIENTE")), None)
    end = next((idx for idx, text in enumerate(contents) if "DESCRICAO" in normalize_label(text)), None)
    if start is None:
        return {"name": None, "address": None}
    if end is None or end <= start:
        end = min(start + 4, len(contents))

    values = [text for text in contents[start + 1 : end] if text]
    return {
        "name": values[0] if values else None,
        "address": "\n".join(values[1:]) if len(values) > 1 else None,
    }


def extract_prefixed_value(pages: list[PageResult], label: str) -> str | None:
    wanted = normalize_label(label)
    for page in pages:
        for block in page.blocks:
            text = block_content(block)
            normalized = normalize_label(text)
            if normalized.startswith(wanted):
                value = value_after_colon(text)
                return value or None
    return None


def build_parsed_document(pages: list[PageResult], document_name: str) -> dict[str, Any]:
    text = all_block_text(pages)
    page_one = next((page for page in pages if page.page_number == 1), pages[0] if pages else None)

    issue_date = extract_date(find_first_text(pages, r"\bData\s*:"))
    calibration_date = extract_date(find_first_text(pages, r"Data de calibra"))
    certificate_match = re.search(r"\bLMF[0-9A-Z/.-]+", text, re.IGNORECASE)
    standard_match = re.search(r"EN\s+ISO\s+7500-1\s*:\s*2018", text, re.IGNORECASE)

    operation_text = find_first_text(pages, r"EN\s+ISO\s+7500-1|Calibra[cç][aã]o segundo")
    visual_state = find_first_text(pages, r"equipamento encontra-se")
    annex = find_first_text(pages, r"Anexo T[eé]cnico de Acredita")
    lab_unit = find_first_text(pages, r"LABORAT[OÓ]RIO")

    customer = extract_customer(page_one)
    equipment = {
        "designation": extract_prefixed_value(pages, "Equipamento"),
        "brand": extract_prefixed_value(pages, "Marca"),
        "model": extract_prefixed_value(pages, "Modelo"),
        "serial_number": extract_prefixed_value(pages, "Número de Série") or extract_prefixed_value(pages, "Numero de Serie"),
        "internal_reference": extract_prefixed_value(pages, "Referência Interna") or extract_prefixed_value(pages, "Referencia Interna"),
        "indication": extract_prefixed_value(pages, "Indicação") or extract_prefixed_value(pages, "Indicacao"),
    }

    header_meta = "\n".join(
        value
        for value in [
            find_first_text(pages, r"Certificado de Calibra"),
            find_first_text(pages, r"\bData\s*:"),
            find_first_text(pages, r"Certificado"),
        ]
        if value
    )
    equipment_meta = "\n".join(
        value
        for value in [
            find_first_text(pages, r"Equipamento\s*:"),
            find_first_text(pages, r"Marca\s*:"),
            find_first_text(pages, r"Modelo\s*:"),
            find_first_text(pages, r"N[uú]mero de S[eé]rie\s*:|Numero de Serie\s*:"),
            find_first_text(pages, r"Indica[cç][aã]o\s*:"),
            find_first_text(pages, r"Refer[eê]ncia Interna\s*:"),
        ]
        if value
    )

    work_conditions = {
        "temperature_c": None,
        "humidity_percent": None,
        "location": "Instalacoes do cliente" if re.search(r"instala[cç][oõ]es do cliente", text, re.IGNORECASE) else None,
        "accreditation_annex": annex or None,
    }

    parsed = {
        "source_file": f"{document_name}.pdf",
        "method": "paddleocr_vl",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "header": {
            "certificate_number": certificate_match.group(0) if certificate_match else None,
            "issue_date": issue_date,
            "calibration_date": calibration_date,
            "lab_name": "CATIM" if "CATIM" in text.upper() else None,
            "lab_unit": lab_unit or None,
            "page_count": max((page.page_number or 0) for page in pages) or None,
        },
        "customer": customer,
        "equipment": equipment,
        "calibration": {
            "standard": standard_match.group(0) if standard_match else None,
            "operation_summary": operation_text or None,
            "equipment_state": visual_state or None,
        },
        "work_conditions": work_conditions,
        "raw_blocks": {
            "header_meta": header_meta,
            "calibration_meta": find_first_text(pages, r"Data de calibra") or "",
            "customer": "\n".join(value for value in customer.values() if value),
            "equipment": equipment_meta,
            "equipment_state": visual_state,
            "work_conditions": "\n".join(value for value in [annex, work_conditions["location"]] if value),
            "description": operation_text,
            "paddleocr_vl_pages": {
                page.page_name: [
                    {
                        "label": block.get("block_label"),
                        "content": block_content(block),
                        "bbox": block.get("block_bbox"),
                    }
                    for block in page.blocks
                ]
                for page in pages
            },
        },
    }
    return repair_nested_text(parsed)


def build_parsed_document_v2(pages: list[PageResult], document_name: str) -> dict[str, Any]:
    """Build parsed fields from both free text blocks and PaddleOCR-VL HTML tables."""
    text = all_block_text(pages)
    page_one = next((page for page in pages if page.page_number == 1), pages[0] if pages else None)
    rows = iter_table_rows(pages)

    issue_date = extract_date(value_after_row_label(rows, {"DATA DE EMISSAO"}) or "") or extract_date(
        find_first_text(pages, r"\bData\s*:")
    )
    calibration_source = value_after_row_label(rows, {"DATA CALIBRACAO", "DATA DE CALIBRACAO"}) or find_first_text(
        pages, r"Data de calibra"
    )
    calibration_date = extract_date(calibration_source)
    if not calibration_date and "DATA CALIBRACAO" in normalize_label(text):
        dates = extract_dates(text)
        calibration_date = dates[-1] if dates else None
    certificate_match = re.search(r"\bLMF[0-9A-Z/.-]+", text, re.IGNORECASE)
    standard_match = re.search(r"EN\s+ISO\s+7500-1\s*:\s*2018", text, re.IGNORECASE)

    operation_text = table_text_after_label(rows, "DESCRICAO") or find_first_text(
        pages, r"EN\s+ISO\s+7500-1|Calibra[cÃ§][aÃ£]o segundo"
    )
    visual_state = value_after_row_label(rows, {"ESTADO DO EQUIPAMENTO"}) or find_first_text(pages, r"equipamento encontra-se")
    annex = value_after_row_label(rows, {"ANEXO TECNICO DE ACREDITACAO"}) or find_first_text(
        pages, r"Anexo T[eÃ©]cnico de Acredita"
    )
    lab_unit = find_first_text(pages, r"LABORAT[OÃ“]RIO")

    customer = {
        "name": value_after_row_label(rows, {"NOME"}),
        "address": value_after_row_label(rows, {"MORADA"}),
    }
    if not customer["name"] and not customer["address"]:
        customer = extract_customer(page_one)

    internal_ref = join_values(values_after_repeated_label(rows, "Ref. Interna"))
    serial_number = join_values(values_after_repeated_label(rows, "Nº Série") or values_after_repeated_label(rows, "N Serie"))
    equipment = {
        "designation": value_after_row_label(rows, {"DESIGNACAO"}) or extract_prefixed_value(pages, "Equipamento"),
        "brand": join_values(values_after_repeated_label(rows, "Marca")) or extract_prefixed_value(pages, "Marca"),
        "model": join_values(values_after_repeated_label(rows, "Modelo")) or extract_prefixed_value(pages, "Modelo"),
        "serial_number": serial_number or extract_prefixed_value(pages, "Numero de Serie"),
        "internal_ref": internal_ref,
        "internal_reference": internal_ref,
        "indication": extract_prefixed_value(pages, "Indicacao"),
        "range": value_after_row_label(rows, {"GAMA NOMINAL"}),
        "resolution": (
            join_values(values_after_repeated_label(rows, "Divisao"))
            or value_after_row_label(rows, {"DIVISAO"})
            or value_after_row_label(rows, {"RESOLUCAO"})
        ),
        "state": visual_state or None,
    }

    location = value_after_row_label(rows, {"LOCAL"})
    temperature = join_values(values_after_repeated_label(rows, "Temperatura")) or value_after_row_label(rows, {"TEMPERATURA"})
    humidity = (
        join_values(values_after_repeated_label(rows, "Humidade"))
        or join_values(values_after_repeated_label(rows, "Umidade"))
        or value_after_row_label(rows, {"HUMIDADE", "UMIDADE"})
    )
    standard_or_procedure = standard_match.group(0) if standard_match else table_text_after_label(rows, "DESCRICAO")

    header_meta = "\n".join(
        value
        for value in [
            f"DATA DE EMISSAO: {issue_date}" if issue_date else "",
            find_first_text(pages, r"Certificado de Calibra"),
            f"Certificado: {certificate_match.group(0)}" if certificate_match else "",
        ]
        if value
    )
    customer_meta = "\n".join(
        value
        for value in [
            f"Nome: {customer.get('name')}" if customer.get("name") else "",
            f"Morada: {customer.get('address')}" if customer.get("address") else "",
        ]
        if value
    )
    equipment_meta = "\n".join(
        value
        for value in [
            f"Designacao: {equipment.get('designation')}" if equipment.get("designation") else "",
            f"Marca: {equipment.get('brand')}" if equipment.get("brand") else "",
            f"Modelo: {equipment.get('model')}" if equipment.get("model") else "",
            f"Serie: {equipment.get('serial_number')}" if equipment.get("serial_number") else "",
            f"Ref. Interna: {equipment.get('internal_ref')}" if equipment.get("internal_ref") else "",
            f"Resolucao: {equipment.get('resolution')}" if equipment.get("resolution") else "",
        ]
        if value
    )

    work_conditions = {
        "temperature": temperature,
        "humidity": humidity,
        "temperature_c": temperature,
        "humidity_percent": humidity,
        "location": location or ("Instalacoes do cliente" if re.search(r"instala[cÃ§][oÃµ]es do cliente", text, re.IGNORECASE) else None),
        "accreditation_annex": annex or None,
    }

    parsed = {
        "source_file": f"{document_name}.pdf",
        "method": "paddleocr_vl",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "header": {
            "certificate_number": certificate_match.group(0) if certificate_match else None,
            "issue_date": issue_date,
            "calibration_date": calibration_date,
            "lab_name": "CATIM" if "CATIM" in text.upper() else None,
            "lab_unit": lab_unit or None,
            "page_count": max((page.page_number or 0) for page in pages) or None,
        },
        "customer": customer,
        "equipment": equipment,
        "calibration": {
            "standard": standard_match.group(0) if standard_match else None,
            "operation_summary": operation_text or None,
            "equipment_state": visual_state or None,
        },
        "work_conditions": work_conditions,
        "reference": {
            "standard_or_procedure": standard_or_procedure,
        },
        "raw_blocks": {
            "header_meta": header_meta,
            "calibration_meta": f"DATA CALIBRACAO: {calibration_date}" if calibration_date else "",
            "customer": customer_meta,
            "equipment": equipment_meta,
            "equipment_state": f"Estado do equipamento: {visual_state}" if visual_state else "",
            "work_conditions": "\n".join(
                value
                for value in [
                    f"Local: {work_conditions.get('location')}" if work_conditions.get("location") else "",
                    f"Temperatura: {temperature}" if temperature else "",
                    f"Humidade: {humidity}" if humidity else "",
                    f"Anexo Tecnico de Acreditacao: {annex}" if annex else "",
                ]
                if value
            ),
            "description": operation_text,
            "paddleocr_vl_pages": {
                page.page_name: [
                    {
                        "label": block.get("block_label"),
                        "content": block_content(block),
                        "bbox": block.get("block_bbox"),
                    }
                    for block in page.blocks
                ]
                for page in pages
            },
        },
    }
    return repair_nested_text(parsed)


def page_meta(page: PageResult) -> dict[str, str | None]:
    content = "\n".join(block_content(block) for block in page.blocks)
    return {
        "page": page.page_name,
        "gama_nominal": extract_prefixed_line(content, "Gama Nominal"),
        "divisao": extract_prefixed_line(content, "Divisão") or extract_prefixed_line(content, "Divisao"),
        "sentido": extract_prefixed_line(content, "Sentido"),
        "resolucao": extract_prefixed_line(content, "Resolução") or extract_prefixed_line(content, "Resolucao"),
    }


def extract_prefixed_line(text: str, label: str) -> str | None:
    normalized_label = re.escape(label)
    match = re.search(rf"{normalized_label}\s*:\s*([^\n]+)", text or "", re.IGNORECASE)
    return clean_text(match.group(1)) if match else None


def is_measurement_table(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    header = normalize_label(" ".join(rows[0]))
    return "EQUIPAMENTO" in header and "ERRO" in header and "INCERTEZA EXPANDIDA" in header and "RELATIVOS" not in header


def is_relative_error_table(rows: list[list[str]]) -> bool:
    header = normalize_label(" ".join(" ".join(row) for row in rows[:2]))
    return "EQUIPAMENTO" in header and "RELATIVOS" in header and "CLASSE" in header


def parse_measurement_rows(rows: list[list[str]]) -> list[dict[str, Any]]:
    data_rows = rows[1:]
    force_rows = [
        row
        for row in data_rows
        if row and normalize_label(row[0]) != "DAN" and parse_number(row[0]) is not None
    ]
    if not force_rows:
        return []

    first_force_index = data_rows.index(force_rows[0])
    pre_force_rows = data_rows[:first_force_index]
    tail_sources: list[list[str]] = []
    if pre_force_rows and len(pre_force_rows[-1]) >= 5:
        tail_sources.append(pre_force_rows[-1][2:5])
    tail_sources.extend(row[2:5] for row in force_rows if len(row) >= 5)

    parsed_rows: list[dict[str, Any]] = []
    for index, row in enumerate(force_rows):
        tail = tail_sources[index] if index < len(tail_sources) and len(tail_sources[index]) >= 3 else row[2:5]
        if index == len(force_rows) - 1 and index > 0 and len(row) >= 5:
            # The VL model sometimes shifts the uncertainty triplet down by one
            # row, but the final row usually carries its own values.
            tail = row[2:5]
        parsed_rows.append(
            {
                "equipment_force_dan": parse_number(row[0]),
                "error_dan": parse_number(row[1]) if len(row) > 1 else None,
                "k": parse_number(tail[0]) if len(tail) > 0 else None,
                "vef": parse_number(tail[1]) if len(tail) > 1 else None,
                "expanded_uncertainty_dan": parse_number(tail[2]) if len(tail) > 2 else None,
                "raw_cells": row,
            }
        )
    return parsed_rows


def parse_relative_error_rows(rows: list[list[str]]) -> list[dict[str, Any]]:
    parsed_rows: list[dict[str, Any]] = []
    for row in rows[2:]:
        if not row or parse_number(row[0]) is None:
            continue
        parsed_rows.append(
            {
                "equipment_force_dan": parse_number(row[0]),
                "q_percent": parse_number(row[1]) if len(row) > 1 else None,
                "b_percent": parse_number(row[2]) if len(row) > 2 else None,
                "a_percent": parse_number(row[3]) if len(row) > 3 else None,
                "fo_percent": parse_number(row[4]) if len(row) > 4 else None,
                "class": clean_text(row[5]) if len(row) > 5 else None,
                "raw_cells": row,
            }
        )
    return parsed_rows


def page_meta(page: PageResult) -> dict[str, str | None]:
    page_rows = iter_table_rows([page])
    return {
        "page": page.page_name,
        "gama_nominal": value_after_row_label(page_rows, {"GAMA NOMINAL"}),
        "divisao": join_values(values_after_repeated_label(page_rows, "Divisao")),
        "sentido": value_after_row_label(page_rows, {"SENTIDO"}),
        "resolucao": value_after_row_label(page_rows, {"RESOLUCAO"}),
    }


def find_measurement_header_index(rows: list[list[str]]) -> int | None:
    for index, row in enumerate(rows):
        header = normalize_label(" ".join(row))
        if "EQUIPAMENTO" in header and "ERRO" in header and "INCERTEZA EXPANDIDA" in header and "RELATIVOS" not in header:
            return index
    return None


def find_relative_header_index(rows: list[list[str]]) -> int | None:
    for index, row in enumerate(rows):
        header = normalize_label(" ".join(" ".join(candidate) for candidate in rows[index:index + 2]))
        if "EQUIPAMENTO" in header and "RELATIVOS" in header and "CLASSE" in header:
            return index
    return None


def find_column(row: list[str], needle: str) -> int | None:
    wanted = normalize_label(needle)
    for index, cell in enumerate(row):
        normalized = normalize_label(cell)
        if wanted in normalized:
            return index
    return None


def get_cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index]


def is_measurement_table(rows: list[list[str]]) -> bool:
    return find_measurement_header_index(rows) is not None


def is_relative_error_table(rows: list[list[str]]) -> bool:
    return find_relative_header_index(rows) is not None


def parse_measurement_rows(rows: list[list[str]]) -> list[dict[str, Any]]:
    header_index = find_measurement_header_index(rows)
    if header_index is None:
        return []

    header = rows[header_index]
    equipment_col = find_column(header, "Equipamento")
    error_col = find_column(header, "Erro")
    k_col = find_column(header, "k")
    vef_col = find_column(header, "v")
    uncertainty_col = find_column(header, "Incerteza")

    if equipment_col is None or error_col is None:
        return []

    data_rows = rows[header_index + 1:]
    force_rows: list[list[str]] = []
    first_tail: list[str] | None = None

    for row in data_rows:
        joined = normalize_label(" ".join(row))
        if force_rows and ("ERRO /" in joined or "EQUIPAMENTO /" in joined):
            break

        force = parse_number(get_cell(row, equipment_col))
        if force is not None:
            force_rows.append(row)
            continue

        if not force_rows:
            candidate_tail = [get_cell(row, k_col), get_cell(row, vef_col), get_cell(row, uncertainty_col)]
            if any(parse_number(value) is not None for value in candidate_tail):
                first_tail = candidate_tail

    if not force_rows:
        return []

    current_tails = [
        [get_cell(row, k_col), get_cell(row, vef_col), get_cell(row, uncertainty_col)]
        for row in force_rows
    ]
    shifted = first_tail is not None and all(parse_number(value) is not None for value in first_tail)

    parsed_rows: list[dict[str, Any]] = []
    for index, row in enumerate(force_rows):
        tail = current_tails[index]
        if shifted:
            tail_sources = [first_tail or []] + current_tails
            tail = tail_sources[index] if index < len(tail_sources) else tail
            if index == len(force_rows) - 1 and index > 0:
                tail = current_tails[index]

        parsed_rows.append(
            {
                "equipment_force_dan": parse_number(get_cell(row, equipment_col)),
                "error_dan": parse_number(get_cell(row, error_col)),
                "k": parse_number(tail[0]) if len(tail) > 0 else None,
                "vef": parse_number(tail[1]) if len(tail) > 1 else None,
                "expanded_uncertainty_dan": parse_number(tail[2]) if len(tail) > 2 else None,
                "raw_cells": row,
            }
        )
    return parsed_rows


def max_row_width(rows: list[list[str]]) -> int:
    return max((len(row) for row in rows), default=0)


def is_meaningful_generic_table(rows: list[list[str]]) -> bool:
    return bool(rows) and max_row_width(rows) >= 2


def table_title(page_name: str, rows: list[list[str]]) -> str:
    for row in rows[:4]:
        title = clean_text(" ".join(cell for cell in row if cell))
        if title and len(title) <= 90:
            return f"{page_name} - {title}"
    return page_name


def raw_table_records(rows: list[list[str]]) -> tuple[list[str], list[dict[str, Any]]]:
    columns = [f"col_{index + 1}" for index in range(max_row_width(rows))]
    records = []
    for row_index, row in enumerate(rows, start=1):
        record = {"row_index": row_index}
        for index, column in enumerate(columns):
            record[column] = clean_text(row[index]) if index < len(row) else None
        records.append(record)
    return ["row_index", *columns], records


def is_reference_equipment_table(rows: list[list[str]]) -> bool:
    for row in rows[:3]:
        header = normalize_label(" ".join(row))
        if "PADRAO" in header and "CATIM" in header and "RASTREABILIDADE" in header:
            return True
    return False


def parse_reference_equipment_rows(rows: list[list[str]]) -> list[dict[str, Any]]:
    header_index = None
    for index, row in enumerate(rows[:3]):
        header = normalize_label(" ".join(row))
        if "PADRAO" in header and "CATIM" in header and "RASTREABILIDADE" in header:
            header_index = index
            break
    if header_index is None:
        return []

    parsed_rows = []
    for row in rows[header_index + 1:]:
        if len(row) < 2 or not any(clean_text(cell) for cell in row):
            continue
        parsed_rows.append(
            {
                "standard": clean_text(row[0]) if len(row) > 0 else None,
                "catim_number": clean_text(row[1]) if len(row) > 1 else None,
                "traceability_certificate_validity": clean_text(row[2]) if len(row) > 2 else None,
                "raw_cells": row,
            }
        )
    return parsed_rows


def build_tables(pages: list[PageResult], document_name: str) -> dict[str, Any]:
    measurement_subtables: list[dict[str, Any]] = []
    relative_subtables: list[dict[str, Any]] = []
    reference_subtables: list[dict[str, Any]] = []
    detected_subtables: list[dict[str, Any]] = []
    raw_tables: list[dict[str, Any]] = []
    table_counter = 0

    for page in pages:
        meta = page_meta(page)
        for block in page.blocks:
            if block.get("block_label") != "table":
                continue
            table_counter += 1
            markup = block_content(block)
            rows = parse_html_table(markup)
            raw_key = f"paddleocr_vl_table_{normalize_key(page.page_name)}_{table_counter}"
            raw_tables.append(
                {
                    "page": page.page_name,
                    "bbox": block.get("block_bbox"),
                    "html": markup,
                    "rows": rows,
                }
            )
            handled_as_structured = False
            if is_measurement_table(rows):
                parsed_rows = parse_measurement_rows(rows)
                slug = normalize_key(meta.get("gama_nominal") or page.page_name)
                measurement_subtables.append(
                    {
                        "key": f"force_calibration_measurements_{slug}",
                        "title": meta.get("gama_nominal") or page.page_name,
                        "table": {
                            "columns": [
                                "equipment_force_dan",
                                "error_dan",
                                "k",
                                "vef",
                                "expanded_uncertainty_dan",
                            ],
                            "page": page.page_name,
                            "meta": meta,
                            "rows": parsed_rows,
                        },
                    }
                )
                handled_as_structured = True
            elif is_relative_error_table(rows):
                parsed_rows = parse_relative_error_rows(rows)
                slug = normalize_key(meta.get("gama_nominal") or page.page_name)
                relative_subtables.append(
                    {
                        "key": f"force_relative_errors_{slug}",
                        "title": meta.get("gama_nominal") or page.page_name,
                        "table": {
                            "columns": [
                                "equipment_force_dan",
                                "q_percent",
                                "b_percent",
                                "a_percent",
                                "fo_percent",
                                "class",
                            ],
                            "page": page.page_name,
                            "meta": meta,
                            "rows": parsed_rows,
                        },
                    }
                )
                handled_as_structured = True

            if is_reference_equipment_table(rows):
                reference_rows = parse_reference_equipment_rows(rows)
                if reference_rows:
                    reference_subtables.append(
                        {
                            "key": f"reference_equipment_{normalize_key(page.page_name)}_{table_counter}",
                            "title": table_title(page.page_name, rows),
                            "table": {
                                "columns": [
                                    "standard",
                                    "catim_number",
                                    "traceability_certificate_validity",
                                ],
                                "page": page.page_name,
                                "meta": {"page": page.page_name},
                                "rows": reference_rows,
                            },
                        }
                    )
                    handled_as_structured = True

            if not handled_as_structured and is_meaningful_generic_table(rows):
                raw_columns, raw_rows = raw_table_records(rows)
                detected_subtables.append(
                    {
                        "key": raw_key,
                        "title": table_title(page.page_name, rows),
                        "table": {
                            "columns": raw_columns,
                            "page": page.page_name,
                            "meta": {"page": page.page_name},
                            "rows": raw_rows,
                        },
                    }
                )

    measurement_rows = [
        {**row, "table_id": table["key"], "meta": table["table"]["meta"]}
        for table in measurement_subtables
        for row in table["table"]["rows"]
    ]
    relative_rows = [
        {**row, "table_id": table["key"], "meta": table["table"]["meta"]}
        for table in relative_subtables
        for row in table["table"]["rows"]
    ]
    reference_rows = [
        {**row, "table_id": table["key"], "meta": table["table"]["meta"]}
        for table in reference_subtables
        for row in table["table"]["rows"]
    ]
    detected_rows = [
        {
            "table_id": table["key"],
            "page": table["table"].get("page"),
            "row_index": row.get("row_index"),
            "cells": " | ".join(str(value) for key, value in row.items() if key != "row_index" and value),
        }
        for table in detected_subtables
        for row in table["table"]["rows"]
    ]

    parsed_tables: dict[str, Any] = {}
    if measurement_rows:
        parsed_tables["force_calibration_measurements"] = {
            "columns": [
                "equipment_force_dan",
                "error_dan",
                "k",
                "vef",
                "expanded_uncertainty_dan",
            ],
            "rows": measurement_rows,
            "subtables": measurement_subtables,
        }
    if relative_rows:
        parsed_tables["force_relative_errors"] = {
            "columns": [
                "equipment_force_dan",
                "q_percent",
                "b_percent",
                "a_percent",
                "fo_percent",
                "class",
            ],
            "rows": relative_rows,
            "subtables": relative_subtables,
        }
    if reference_rows:
        parsed_tables["reference_equipment"] = {
            "columns": [
                "standard",
                "catim_number",
                "traceability_certificate_validity",
            ],
            "rows": reference_rows,
            "subtables": reference_subtables,
        }
    if detected_rows:
        parsed_tables["paddleocr_vl_detected_tables"] = {
            "columns": ["table_id", "page", "row_index", "cells"],
            "rows": detected_rows,
            "subtables": detected_subtables,
        }

    tables = {
        "source_file": f"{document_name}.pdf",
        "method": "paddleocr_vl",
        "instrument_type": "force_calibration" if measurement_rows or relative_rows else None,
        "tables": parsed_tables,
        "raw_tables": raw_tables,
    }
    return repair_nested_text(tables)


def build_sections(pages: list[PageResult], document_name: str, summary_path: Path) -> dict[str, Any]:
    return repair_nested_text(
        {
            "source_file": f"{document_name}.pdf",
            "method": "paddleocr_vl",
            "source_run_summary": str(summary_path),
            "sections": {
                page.page_name: [
                    {
                        "label": block.get("block_label"),
                        "content": block_content(block),
                        "bbox": block.get("block_bbox"),
                    }
                    for block in page.blocks
                ]
                for page in pages
            },
        }
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    summary_path, document_name = select_run_summary()
    pages = load_pages(summary_path)

    parsed = build_parsed_document_v2(pages, document_name)
    tables = build_tables(pages, document_name)
    sections = build_sections(pages, document_name, summary_path)

    write_json(PARSED_DIR / f"{document_name}.json", parsed)
    write_json(TABLES_DIR / f"{document_name}_tables.json", tables)
    write_json(SECTIONS_DIR / f"{document_name}_sections.json", sections)

    print(f"[OK] Importado PaddleOCR-VL: {summary_path}")
    print(f"[OK] Paginas validas: {len(pages)}")
    print(f"[OK] Parsed: {PARSED_DIR / f'{document_name}.json'}")
    print(f"[OK] Tables: {TABLES_DIR / f'{document_name}_tables.json'}")
    print(f"[OK] Sections: {SECTIONS_DIR / f'{document_name}_sections.json'}")


if __name__ == "__main__":
    main()
