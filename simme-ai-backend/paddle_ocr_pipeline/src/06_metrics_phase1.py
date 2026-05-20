import json
from pathlib import Path
from statistics import mean
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]

PARSED_DIR = BASE / "data" / "parsed"
TABLES_DIR = BASE / "data" / "tables"
OUT_DIR = BASE / "data" / "metrics"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------
# Helpers
# -------------------------
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


# -------------------------
# Field definitions
# -------------------------
FIELD_MAP = {
    "header.issue_date": ("header", "issue_date"),
    "header.certificate_number": ("header", "certificate_number"),
    "header.lab_name": ("header", "lab_name"),
    "header.lab_unit": ("header", "lab_unit"),

    "customer.name": ("customer", "name"),
    "customer.address": ("customer", "address"),

    "equipment.designation": ("equipment", "designation"),
    "equipment.brand": ("equipment", "brand"),
    "equipment.model": ("equipment", "model"),
    "equipment.serial_number": ("equipment", "serial_number"),
    "equipment.range": ("equipment", "range"),
    "equipment.resolution": ("equipment", "resolution"),
    "equipment.estimated_resolution": ("equipment", "estimated_resolution"),
    "equipment.indication": ("equipment", "indication"),
    "equipment.internal_ref": ("equipment", "internal_ref"),
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
    }
}


# -------------------------
# Field metrics
# -------------------------
def evaluate_fields(parsed_doc: dict) -> dict:
    field_presence = {}
    filled_count = 0

    for field_name, (section, key) in FIELD_MAP.items():
        value = parsed_doc.get(section, {}).get(key)
        present = is_filled(value)
        field_presence[field_name] = present
        if present:
            filled_count += 1

    total_fields = len(FIELD_MAP)
    completeness_score = round(filled_count / total_fields, 4) if total_fields else 0.0

    return {
        "field_presence": field_presence,
        "filled_fields": filled_count,
        "total_fields": total_fields,
        "completeness_score": completeness_score,
    }


# -------------------------
# Table metrics
# -------------------------
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
            if isinstance(value.get("rows"), list):
                row_count = len(value["rows"])
            else:
                row_count = 1 if present else 0
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


# -------------------------
# Match parsed + tables docs
# -------------------------
def build_doc_index(files):
    idx = {}
    for fp in files:
        data = read_json(fp)
        source = data.get("source_file")
        if source:
            idx[source] = {
                "path": fp,
                "data": data,
            }
    return idx


# -------------------------
# Main
# -------------------------
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
    field_coverage_counter = {k: 0 for k in FIELD_MAP.keys()}
    table_coverage_counter = {}
    completeness_scores = []
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

        # atualizar cobertura de campos
        for field_name, present in field_metrics["field_presence"].items():
            if present:
                field_coverage_counter[field_name] += 1

        # atualizar cobertura de tabelas
        for table_name, present in table_metrics["table_presence"].items():
            table_coverage_counter.setdefault(table_name, 0)
            if present:
                table_coverage_counter[table_name] += 1

        completeness_scores.append(field_metrics["completeness_score"])
        table_scores.append(table_metrics["table_extraction_score"])

        documents.append({
            "source_file": source_file,
            "instrument_type": table_metrics["instrument_type"],
            "fields": {
                "filled_fields": field_metrics["filled_fields"],
                "total_fields": field_metrics["total_fields"],
                "completeness_score": field_metrics["completeness_score"],
                "presence": field_metrics["field_presence"],
            },
            "tables": {
                "found_tables": table_metrics["found_tables"],
                "expected_tables": table_metrics["expected_tables"],
                "table_extraction_score": table_metrics["table_extraction_score"],
                "presence": table_metrics["table_presence"],
                "row_counts": table_metrics["table_row_counts"],
            }
        })

    n_docs = len(documents)

    field_coverage = {
        k: round(v / n_docs, 4) if n_docs else 0.0
        for k, v in field_coverage_counter.items()
    }

    table_coverage = {
        k: round(v / n_docs, 4) if n_docs else 0.0
        for k, v in table_coverage_counter.items()
    }

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_documents": n_docs,
        "global_metrics": {
            "avg_field_completeness": safe_mean(completeness_scores),
            "avg_table_extraction": safe_mean(table_scores),
            "field_coverage": field_coverage,
            "table_coverage": table_coverage,
        },
        "documents": documents
    }

    out_path = OUT_DIR / "metrics_phase1.json"
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("saved:", out_path)


if __name__ == "__main__":
    main()
