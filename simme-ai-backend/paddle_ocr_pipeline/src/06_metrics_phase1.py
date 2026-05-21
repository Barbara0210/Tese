import json
import re
from datetime import datetime
from pathlib import Path
from statistics import mean

BASE = Path(__file__).resolve().parents[1]

PARSED_DIR = BASE / "data" / "parsed"
TABLES_DIR = BASE / "data" / "tables"
OUT_DIR = BASE / "data" / "metrics"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return True


def safe_mean(values):
    return round(mean(values), 4) if values else 0.0


def normalize(text: str | None) -> str:
    if not text:
        return ""
    value = text.upper()
    replacements = {
        "Ã‡": "C",
        "Ç": "C",
        "Ã": "A",
        "Á": "A",
        "À": "A",
        "Â": "A",
        "Ä": "A",
        "É": "E",
        "Ê": "E",
        "Ë": "E",
        "Í": "I",
        "Ì": "I",
        "Î": "I",
        "Ó": "O",
        "Ò": "O",
        "Ô": "O",
        "Ö": "O",
        "Ú": "U",
        "Ù": "U",
        "Û": "U",
        "Ü": "U",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def contains_any(text: str | None, needles: list[str]) -> bool:
    haystack = normalize(text)
    return any(needle in haystack for needle in needles)


FIELD_MAP = {
    "header.issue_date": ("header", "issue_date"),
    "header.certificate_number": ("header", "certificate_number"),
    "header.calibration_date": ("header", "calibration_date"),
    "customer.name": ("customer", "name"),
    "customer.address": ("customer", "address"),
    "equipment.designation": ("equipment", "designation"),
    "equipment.brand": ("equipment", "brand"),
    "equipment.model": ("equipment", "model"),
    "equipment.serial_number": ("equipment", "serial_number"),
    "equipment.internal_ref": ("equipment", "internal_ref"),
    "equipment.range": ("equipment", "range"),
    "equipment.resolution": ("equipment", "resolution"),
    "equipment.estimated_resolution": ("equipment", "estimated_resolution"),
    "equipment.class": ("equipment", "class"),
    "equipment.state": ("equipment", "state"),
    "work_conditions.location": ("work_conditions", "location"),
    "work_conditions.temperature": ("work_conditions", "temperature"),
    "work_conditions.humidity": ("work_conditions", "humidity"),
    "work_conditions.accreditation_annex": ("work_conditions", "accreditation_annex"),
    "reference.standard_or_procedure": ("reference", "standard_or_procedure"),
}


TABLE_EXPECTATIONS = {
    "caliper": {
        "E_contact_partial": 1,
        "S_scale_change": 1,
        "L_line_contact": 1,
    },
    "pressure_gauge": {
        "pressure_error_table": 1,
        "max_hysteresis": 1,
        "environmental_conditions": 1,
    },
    "generic_block_table": {
        "generic_results_table": 1,
    },
}


def infer_applicable_fields(parsed_doc: dict) -> dict:
    raw = parsed_doc.get("raw_blocks", {}) or {}

    header_meta = raw.get("header_meta")
    calibration_meta = raw.get("calibration_meta")
    customer = raw.get("customer")
    equipment = raw.get("equipment")
    equipment_state = raw.get("equipment_state")
    work_conditions = raw.get("work_conditions")
    description = raw.get("description")

    return {
        "header.issue_date": contains_any(header_meta, ["DATA DE EMISSAO"]),
        "header.certificate_number": contains_any(header_meta, ["CERTIFICADO"]),
        "header.calibration_date": contains_any(calibration_meta, ["DATA CALIBRACAO"]),
        "customer.name": contains_any(customer, ["NOME"]),
        "customer.address": contains_any(customer, ["MORADA"]),
        "equipment.designation": contains_any(equipment, ["DESIGNAGAO", "DESIGNACAO"]),
        "equipment.brand": contains_any(equipment, ["MARCA"]),
        "equipment.model": contains_any(equipment, ["MODELO"]),
        "equipment.serial_number": contains_any(equipment, ["SERIE"]),
        "equipment.internal_ref": contains_any(equipment, ["REF. INTERNA", "REF INTERNA"]),
        "equipment.range": contains_any(
            equipment,
            ["ALCANCE", "INTERVALO DE INDICACAO", "INTERVALO DE INDICAGAO", "INTERVALO DE MEDICAO"],
        ),
        "equipment.resolution": contains_any(equipment, ["RESOLUCAO", "RESOLUGAO"]),
        "equipment.estimated_resolution": contains_any(
            equipment,
            ["RESOLUCAO ESTIMADA", "RESOLUGAO ESTIMADA"],
        ),
        "equipment.class": contains_any(equipment, ["CLASSE"]),
        "equipment.state": contains_any(equipment_state, ["ESTADO DO EQUIPAMENTO"]),
        "work_conditions.location": contains_any(work_conditions, ["LOCAL"]),
        "work_conditions.temperature": contains_any(work_conditions, ["TEMPERATURA", "C", "°C"]),
        "work_conditions.humidity": contains_any(work_conditions, ["HUMIDADE", "UMIDADE"]),
        "work_conditions.accreditation_annex": contains_any(work_conditions, ["ANEXO TECNICO", "ANEXO T"]),
        "reference.standard_or_procedure": contains_any(description, ["NORMATIV", "NP ", "EN ", "ISO ", "LMD "]),
    }


def evaluate_fields(parsed_doc: dict) -> dict:
    field_presence = {}
    strict_filled_count = 0

    for field_name, (section, key) in FIELD_MAP.items():
        value = parsed_doc.get(section, {}).get(key)
        present = is_filled(value)
        field_presence[field_name] = present
        if present:
            strict_filled_count += 1

    strict_total_fields = len(FIELD_MAP)
    strict_completeness_score = round(strict_filled_count / strict_total_fields, 4) if strict_total_fields else 0.0

    applicable_map = infer_applicable_fields(parsed_doc)
    applicable_total_fields = sum(1 for is_applicable in applicable_map.values() if is_applicable)
    applicable_filled_fields = sum(
        1
        for field_name, is_applicable in applicable_map.items()
        if is_applicable and field_presence.get(field_name)
    )
    applicable_completeness_score = (
        round(applicable_filled_fields / applicable_total_fields, 4)
        if applicable_total_fields
        else 0.0
    )

    return {
        "field_presence": field_presence,
        "applicable_presence": applicable_map,
        "filled_fields": applicable_filled_fields,
        "total_fields": applicable_total_fields,
        "completeness_score": applicable_completeness_score,
        "schema_filled_fields": strict_filled_count,
        "schema_total_fields": strict_total_fields,
        "schema_completeness_score": strict_completeness_score,
    }


def evaluate_tables(table_doc: dict) -> dict:
    instrument_type = table_doc.get("instrument_type")
    tables = table_doc.get("tables", {})

    expected = TABLE_EXPECTATIONS.get(instrument_type, {})
    table_presence = {}
    table_row_counts = {}
    found_count = 0

    for table_name in expected:
        value = tables.get(table_name)

        if isinstance(value, list):
            present = len(value) > 0
            row_count = len(value)
        elif isinstance(value, dict):
            present = len(value) > 0
            row_count = len(value.get("rows", [])) if isinstance(value.get("rows"), list) else (1 if present else 0)
        else:
            present = value is not None
            row_count = 1 if present else 0

        table_presence[table_name] = present
        table_row_counts[table_name] = row_count

        if present:
            found_count += 1

    total_expected = len(expected)
    extraction_score = round(found_count / total_expected, 4) if total_expected else 0.0

    return {
        "instrument_type": instrument_type,
        "table_presence": table_presence,
        "table_row_counts": table_row_counts,
        "found_tables": found_count,
        "expected_tables": total_expected,
        "table_extraction_score": extraction_score,
    }


def build_doc_index(files):
    index = {}
    for path in files:
        data = read_json(path)
        source_file = data.get("source_file")
        if source_file:
            index[source_file] = {"path": path, "data": data}
    return index


def main():
    parsed_files = sorted(PARSED_DIR.glob("*.json"))
    table_files = sorted(TABLES_DIR.glob("*_tables.json"))

    if not parsed_files:
        print(f"Sem ficheiros parsed em: {PARSED_DIR}")
        return

    if not table_files:
        print(f"Sem ficheiros tables em: {TABLES_DIR}")
        return

    parsed_index = build_doc_index(parsed_files)
    table_index = build_doc_index(table_files)
    all_sources = sorted(set(parsed_index.keys()) | set(table_index.keys()))

    documents = []
    field_coverage_counter = {key: 0 for key in FIELD_MAP.keys()}
    applicable_field_counter = {key: 0 for key in FIELD_MAP.keys()}
    table_coverage_counter = {}
    completeness_scores = []
    schema_completeness_scores = []
    table_scores = []

    for source_file in all_sources:
        parsed_doc = parsed_index.get(source_file, {}).get("data")
        table_doc = table_index.get(source_file, {}).get("data")

        if not parsed_doc:
            continue

        field_metrics = evaluate_fields(parsed_doc)

        if table_doc:
            table_metrics = evaluate_tables(table_doc)
        else:
            table_metrics = {
                "instrument_type": None,
                "table_presence": {},
                "table_row_counts": {},
                "found_tables": 0,
                "expected_tables": 0,
                "table_extraction_score": 0.0,
            }

        for field_name, present in field_metrics["field_presence"].items():
            if present:
                field_coverage_counter[field_name] += 1

        for field_name, present in field_metrics["applicable_presence"].items():
            if present:
                applicable_field_counter[field_name] += 1

        for table_name, present in table_metrics["table_presence"].items():
            table_coverage_counter.setdefault(table_name, 0)
            if present:
                table_coverage_counter[table_name] += 1

        completeness_scores.append(field_metrics["completeness_score"])
        schema_completeness_scores.append(field_metrics["schema_completeness_score"])
        table_scores.append(table_metrics["table_extraction_score"])

        documents.append(
            {
                "source_file": source_file,
                "instrument_type": table_metrics["instrument_type"],
                "fields": {
                    "filled_fields": field_metrics["filled_fields"],
                    "total_fields": field_metrics["total_fields"],
                    "completeness_score": field_metrics["completeness_score"],
                    "schema_filled_fields": field_metrics["schema_filled_fields"],
                    "schema_total_fields": field_metrics["schema_total_fields"],
                    "schema_completeness_score": field_metrics["schema_completeness_score"],
                    "presence": field_metrics["field_presence"],
                    "applicable_presence": field_metrics["applicable_presence"],
                },
                "tables": {
                    "found_tables": table_metrics["found_tables"],
                    "expected_tables": table_metrics["expected_tables"],
                    "table_extraction_score": table_metrics["table_extraction_score"],
                    "presence": table_metrics["table_presence"],
                    "row_counts": table_metrics["table_row_counts"],
                },
            }
        )

    n_docs = len(documents)
    field_coverage = {key: round(value / n_docs, 4) if n_docs else 0.0 for key, value in field_coverage_counter.items()}
    applicable_field_ratio = {
        key: round(value / n_docs, 4) if n_docs else 0.0 for key, value in applicable_field_counter.items()
    }
    table_coverage = {key: round(value / n_docs, 4) if n_docs else 0.0 for key, value in table_coverage_counter.items()}

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_documents": n_docs,
        "global_metrics": {
            "avg_field_completeness": safe_mean(completeness_scores),
            "avg_schema_field_completeness": safe_mean(schema_completeness_scores),
            "avg_table_extraction": safe_mean(table_scores),
            "field_coverage": field_coverage,
            "applicable_field_ratio": applicable_field_ratio,
            "table_coverage": table_coverage,
        },
        "documents": documents,
    }

    output_path = OUT_DIR / "metrics_phase1.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved:", output_path)


if __name__ == "__main__":
    main()
