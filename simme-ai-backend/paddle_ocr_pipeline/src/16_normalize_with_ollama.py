"""
Normalize parsed certificate data with a local Ollama LLM.

This script is intentionally a post-processing step. It does not read the PDF
again and it does not replace OCR/PaddleOCR-VL. Instead, it receives the
structured artifacts already produced by previous pipeline steps and asks a
local LLM to map them into the project schema with evidence.

Expected previous artifacts:
    data/parsed/<doc>.json
    data/tables/<doc>_tables.json

Outputs are written back to the same files, with an audit copy in:
    data/llm/<doc>_ollama_normalization.json
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
PARSED_DIR = DATA_DIR / "parsed"
TABLES_DIR = DATA_DIR / "tables"
LLM_DIR = DATA_DIR / "llm"

LLM_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_OCR_LLM_MODEL", "qwen3:4b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))
CONTEXT_CHAR_LIMIT = int(os.getenv("OLLAMA_CONTEXT_CHAR_LIMIT", "12000"))


FIELD_SECTIONS = {
    "header": [
        "issue_date",
        "certificate_number",
        "calibration_date",
        "lab_name",
        "lab_unit",
        "page_count",
    ],
    "customer": ["name", "address"],
    "equipment": [
        "designation",
        "brand",
        "model",
        "serial_number",
        "internal_ref",
        "internal_reference",
        "range",
        "resolution",
        "estimated_resolution",
        "indication",
        "class",
        "state",
    ],
    "work_conditions": [
        "location",
        "temperature",
        "humidity",
        "temperature_c",
        "humidity_percent",
        "accreditation_annex",
    ],
    "reference": ["standard_or_procedure"],
}


OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "instrument_type": {
            "type": ["string", "null"],
            "description": "Use null when the instrument type is not clear.",
        },
        "header": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "issue_date": {"type": ["string", "null"]},
                "certificate_number": {"type": ["string", "null"]},
                "calibration_date": {"type": ["string", "null"]},
                "lab_name": {"type": ["string", "null"]},
                "lab_unit": {"type": ["string", "null"]},
            },
            "required": [
                "issue_date",
                "certificate_number",
                "calibration_date",
                "lab_name",
                "lab_unit",
            ],
        },
        "customer": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": ["string", "null"]},
                "address": {"type": ["string", "null"]},
            },
            "required": ["name", "address"],
        },
        "equipment": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "designation": {"type": ["string", "null"]},
                "brand": {"type": ["string", "null"]},
                "model": {"type": ["string", "null"]},
                "serial_number": {"type": ["string", "null"]},
                "internal_ref": {"type": ["string", "null"]},
                "range": {"type": ["string", "null"]},
                "resolution": {"type": ["string", "null"]},
                "estimated_resolution": {"type": ["string", "null"]},
                "indication": {"type": ["string", "null"]},
                "class": {"type": ["string", "null"]},
                "state": {"type": ["string", "null"]},
            },
            "required": [
                "designation",
                "brand",
                "model",
                "serial_number",
                "internal_ref",
                "range",
                "resolution",
                "estimated_resolution",
                "indication",
                "class",
                "state",
            ],
        },
        "work_conditions": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "location": {"type": ["string", "null"]},
                "temperature": {"type": ["string", "null"]},
                "humidity": {"type": ["string", "null"]},
                "accreditation_annex": {"type": ["string", "null"]},
            },
            "required": [
                "location",
                "temperature",
                "humidity",
                "accreditation_annex",
            ],
        },
        "reference": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "standard_or_procedure": {"type": ["string", "null"]},
            },
            "required": ["standard_or_procedure"],
        },
        "tables": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "reference_equipment": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "force_calibration_measurements": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "force_relative_errors": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "pressure_error_table": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "environmental_conditions": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "generic_tables": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
            },
        },
        "evidence": {
            "type": "object",
            "additionalProperties": {"type": ["string", "null"]},
            "description": "Short source text supporting each filled field.",
        },
        "notes": {"type": ["string", "null"]},
    },
    "required": [
        "instrument_type",
        "header",
        "customer",
        "equipment",
        "work_conditions",
        "reference",
        "tables",
        "evidence",
        "notes",
    ],
}


SYSTEM_PROMPT = """You normalize calibration certificate extraction results.

Rules:
- Use only the evidence provided in the input JSON.
- Do not invent values.
- If a value is not supported by the input, return null.
- Keep technical units and certificate numbers exactly as observed when possible.
- Do not confuse issue date with calibration date.
- Return only JSON matching the provided schema.
- Prefer explicit fields already extracted by OCR/PaddleOCR-VL, but fix misplaced
  fields when the evidence clearly supports the correction.
"""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def slug_from_source(source_file: str | None) -> str:
    stem = Path(source_file or "document").stem
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("_") or "document"


def table_file_for(parsed_path: Path, parsed_doc: dict) -> Path | None:
    source_slug = slug_from_source(parsed_doc.get("source_file"))
    candidates = [
        TABLES_DIR / f"{parsed_path.stem}_tables.json",
        TABLES_DIR / f"{source_slug}_tables.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    source_file = parsed_doc.get("source_file")
    for path in sorted(TABLES_DIR.glob("*_tables.json")):
        try:
            data = read_json(path)
        except Exception:
            continue
        if source_file and data.get("source_file") == source_file:
            return path
    return None


def trim_string(value: str, limit: int = 1800) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit] + " ... [truncated]"


def compact_value(value: Any, depth: int = 0) -> Any:
    if isinstance(value, str):
        return trim_string(value, 1800 if depth < 3 else 700)
    if isinstance(value, list):
        return [compact_value(item, depth + 1) for item in value[:30]]
    if isinstance(value, dict):
        compacted = {}
        for key, item in value.items():
            if key in {"paddleocr_vl_pages"}:
                continue
            if key in {"html"} and isinstance(item, str):
                compacted[key] = trim_string(item, 1000)
                continue
            compacted[key] = compact_value(item, depth + 1)
        return compacted
    return value


def compact_table_value(value: Any) -> Any:
    if isinstance(value, list):
        return [compact_value(item) for item in value[:12]]
    if not isinstance(value, dict):
        return compact_value(value)

    compacted = {}
    for key, item in value.items():
        if key == "rows" and isinstance(item, list):
            compacted[key] = [compact_value(row) for row in item[:12]]
        elif key == "subtables" and isinstance(item, list):
            compacted[key] = [
                {
                    "key": subtable.get("key"),
                    "title": subtable.get("title"),
                    "table": compact_table_value(subtable.get("table")),
                }
                for subtable in item[:4]
                if isinstance(subtable, dict)
            ]
        else:
            compacted[key] = compact_value(item)
    return compacted


def compact_tables(tables: Any) -> dict:
    if not isinstance(tables, dict):
        return {}

    compacted = {}
    for table_name, table_value in tables.items():
        if table_name == "paddleocr_vl_detected_tables":
            rows = table_value.get("rows", []) if isinstance(table_value, dict) else []
            compacted[table_name] = {
                "columns": ["table_id", "page", "row_index", "cells"],
                "rows": [compact_value(row) for row in rows[:8]],
                "note": "Only the first rows are sent to the LLM to keep the prompt small.",
            }
        else:
            compacted[table_name] = compact_table_value(table_value)
    return compacted


def build_context(parsed_doc: dict, tables_doc: dict | None) -> dict:
    raw_blocks = parsed_doc.get("raw_blocks") or {}
    tables_doc = tables_doc or {}

    context = {
        "source_file": parsed_doc.get("source_file"),
        "current_extraction": {
            "header": parsed_doc.get("header", {}),
            "customer": parsed_doc.get("customer", {}),
            "equipment": parsed_doc.get("equipment", {}),
            "work_conditions": parsed_doc.get("work_conditions", {}),
            "reference": parsed_doc.get("reference", {}),
            "calibration": parsed_doc.get("calibration", {}),
        },
        "raw_text_blocks": {
            key: raw_blocks.get(key)
            for key in [
                "header_meta",
                "calibration_meta",
                "customer",
                "equipment",
                "equipment_state",
                "work_conditions",
                "description",
            ]
            if raw_blocks.get(key)
        },
    "current_tables": compact_tables(tables_doc.get("tables", {})),
        "raw_tables": tables_doc.get("raw_tables", []),
    }

    compacted = compact_value(context)
    encoded = json.dumps(compacted, ensure_ascii=False, indent=2)
    if len(encoded) <= CONTEXT_CHAR_LIMIT:
        return compacted

    compacted.pop("raw_tables", None)
    encoded = json.dumps(compacted, ensure_ascii=False, indent=2)
    if len(encoded) <= CONTEXT_CHAR_LIMIT:
        return compacted

    compacted["current_tables"] = compact_value(
        {
            key: value
            for key, value in (tables_doc.get("tables") or {}).items()
            if key != "paddleocr_vl_detected_tables"
        }
    )
    return compacted


def call_ollama(context: dict) -> dict:
    prompt = (
        "Normalize the following calibration certificate extraction into the target schema.\n"
        "Return null for unsupported values and include short evidence snippets.\n\n"
        f"Input JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": OUTPUT_SCHEMA,
        "options": {
            "temperature": 0,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Could not connect to Ollama. Start Ollama and pull the model first "
            f"(for example: ollama pull {OLLAMA_MODEL}). Details: {exc}"
        ) from exc

    raw_response = response_data.get("response")
    if not raw_response:
        raise RuntimeError(f"Unexpected Ollama response: {response_data}")

    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ollama did not return valid JSON: {raw_response[:2000]}") from exc


def default_llm_payload() -> dict:
    return {
        "instrument_type": None,
        "header": {
            "issue_date": None,
            "certificate_number": None,
            "calibration_date": None,
            "lab_name": None,
            "lab_unit": None,
        },
        "customer": {"name": None, "address": None},
        "equipment": {
            "designation": None,
            "brand": None,
            "model": None,
            "serial_number": None,
            "internal_ref": None,
            "range": None,
            "resolution": None,
            "estimated_resolution": None,
            "indication": None,
            "class": None,
            "state": None,
        },
        "work_conditions": {
            "location": None,
            "temperature": None,
            "humidity": None,
            "accreditation_annex": None,
        },
        "reference": {"standard_or_procedure": None},
        "tables": {},
        "evidence": {},
        "notes": None,
    }


def deep_fill_defaults(value: Any, default: Any) -> Any:
    if isinstance(default, dict):
        value = value if isinstance(value, dict) else {}
        merged = {}
        for key, default_item in default.items():
            merged[key] = deep_fill_defaults(value.get(key), default_item)
        for key, item in value.items():
            if key not in merged:
                merged[key] = item
        return merged
    return value if value is not None else default


def normalize_llm_payload(value: dict) -> dict:
    return deep_fill_defaults(value if isinstance(value, dict) else {}, default_llm_payload())


def merge_section(parsed_doc: dict, llm_doc: dict, section: str) -> None:
    parsed_doc.setdefault(section, {})
    for key in FIELD_SECTIONS.get(section, []):
        value = (llm_doc.get(section) or {}).get(key)
        existing = parsed_doc[section].get(key)
        if not is_filled(existing) and is_filled(value):
            parsed_doc[section][key] = value


def merge_tables(tables_doc: dict, llm_doc: dict) -> None:
    tables_doc.setdefault("tables", {})
    llm_tables = llm_doc.get("tables") or {}

    for table_name, table_value in llm_tables.items():
        if not is_filled(tables_doc["tables"].get(table_name)) and is_filled(table_value):
            tables_doc["tables"][table_name] = table_value

    if not is_filled(tables_doc.get("instrument_type")) and is_filled(llm_doc.get("instrument_type")):
        tables_doc["instrument_type"] = llm_doc.get("instrument_type")


def collect_conflicts(parsed_doc: dict, llm_doc: dict) -> list[dict]:
    conflicts = []
    for section, keys in FIELD_SECTIONS.items():
        existing_section = parsed_doc.get(section) or {}
        llm_section = llm_doc.get(section) or {}
        for key in keys:
            existing = existing_section.get(key)
            suggested = llm_section.get(key)
            if (
                is_filled(existing)
                and is_filled(suggested)
                and normalize_scalar(existing) != normalize_scalar(suggested)
            ):
                conflicts.append(
                    {
                        "field": f"{section}.{key}",
                        "kept": existing,
                        "llm_suggestion": suggested,
                    }
                )
    return conflicts


def normalize_document(parsed_path: Path) -> None:
    parsed_doc = read_json(parsed_path)
    table_path = table_file_for(parsed_path, parsed_doc)
    tables_doc = read_json(table_path) if table_path else {
        "source_file": parsed_doc.get("source_file"),
        "method": parsed_doc.get("method"),
        "instrument_type": None,
        "tables": {},
    }

    context = build_context(parsed_doc, tables_doc)
    llm_doc = normalize_llm_payload(call_ollama(context))

    updated_parsed = deepcopy(parsed_doc)
    updated_tables = deepcopy(tables_doc)

    for section in ["header", "customer", "equipment", "work_conditions", "reference"]:
        merge_section(updated_parsed, llm_doc, section)

    updated_parsed["method"] = f"{parsed_doc.get('method', 'unknown')}+ollama_llm"
    existing_instrument_type = updated_tables.get("instrument_type") or parsed_doc.get("instrument_type")
    if not is_filled(existing_instrument_type) and is_filled(llm_doc.get("instrument_type")):
        updated_parsed["instrument_type"] = llm_doc.get("instrument_type")

    updated_parsed.setdefault("raw_blocks", {})
    updated_parsed["raw_blocks"]["ollama_llm"] = {
        "model": OLLAMA_MODEL,
        "normalized_at": datetime.now(timezone.utc).isoformat(),
        "evidence": llm_doc.get("evidence") or {},
        "notes": llm_doc.get("notes"),
        "policy": "LLM suggestions only fill empty fields; existing OCR/VL values are not overwritten.",
        "conflicts": collect_conflicts(parsed_doc, llm_doc),
        "suggested_fields": {
            "instrument_type": llm_doc.get("instrument_type"),
            "header": llm_doc.get("header"),
            "customer": llm_doc.get("customer"),
            "equipment": llm_doc.get("equipment"),
            "work_conditions": llm_doc.get("work_conditions"),
            "reference": llm_doc.get("reference"),
        },
    }

    merge_tables(updated_tables, llm_doc)
    updated_tables["method"] = f"{tables_doc.get('method', 'unknown')}+ollama_llm"

    if table_path is None:
        table_path = TABLES_DIR / f"{parsed_path.stem}_tables.json"

    audit_path = LLM_DIR / f"{parsed_path.stem}_ollama_normalization.json"
    write_json(audit_path, {
        "source_file": parsed_doc.get("source_file"),
        "model": OLLAMA_MODEL,
        "ollama_url": OLLAMA_URL,
        "normalized_at": datetime.now(timezone.utc).isoformat(),
        "llm_output": llm_doc,
        "context": context,
    })
    write_json(parsed_path, updated_parsed)
    write_json(table_path, updated_tables)

    print("saved:", parsed_path)
    print("saved:", table_path)
    print("saved:", audit_path)


def main() -> None:
    parsed_files = sorted(PARSED_DIR.glob("*.json"))
    if not parsed_files:
        print(f"No parsed files found in: {PARSED_DIR}")
        return

    for parsed_path in parsed_files:
        print(f"Ollama LLM normalization: {parsed_path.name} using {OLLAMA_MODEL}")
        normalize_document(parsed_path)


if __name__ == "__main__":
    main()
