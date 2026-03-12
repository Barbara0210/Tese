import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]

PARSED_DIR = BASE / "data" / "parsed"
TABLES_DIR = BASE / "data" / "tables"
GOLD_DIR = BASE / "data" / "gold"
OUT_DIR = BASE / "data" / "evaluation"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_value(v):
    if v is None:
        return None
    if isinstance(v, str):
        return " ".join(v.strip().split()).lower()
    return v


def compare_value(pred, gold) -> bool:
    return normalize_value(pred) == normalize_value(gold)


def get_nested(d: dict, *keys):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def main():
    gold_files = sorted(GOLD_DIR.glob("*_gold.json"))

    if not gold_files:
        print(f"Sem ficheiros gold em: {GOLD_DIR}")
        return

    documents = []
    total_field_checks = 0
    total_field_correct = 0

    table_checks = 0
    table_correct = 0

    field_accuracy = {}

    for gold_fp in gold_files:
        gold = read_json(gold_fp)
        source_file = gold["source_file"]

        parsed_fp = PARSED_DIR / source_file.replace(".txt", ".json")
        tables_fp = TABLES_DIR / source_file.replace(".txt", "_tables.json")

        if not parsed_fp.exists():
            print(f"Falta parsed para {source_file}")
            continue
        if not tables_fp.exists():
            print(f"Falta tables para {source_file}")
            continue

        pred_fields = read_json(parsed_fp)
        pred_tables = read_json(tables_fp)

        doc_field_checks = 0
        doc_field_correct = 0
        doc_field_results = {}

        sections_to_check = ["header", "customer", "equipment", "work_conditions", "reference"]

        for section in sections_to_check:
            gold_section = gold.get(section, {})
            for key, gold_value in gold_section.items():
                pred_value = get_nested(pred_fields, section, key)
                ok = compare_value(pred_value, gold_value)

                doc_field_results[f"{section}.{key}"] = {
                    "pred": pred_value,
                    "gold": gold_value,
                    "correct": ok
                }

                doc_field_checks += 1
                total_field_checks += 1

                field_accuracy.setdefault(f"{section}.{key}", {"correct": 0, "total": 0})
                field_accuracy[f"{section}.{key}"]["total"] += 1

                if ok:
                    doc_field_correct += 1
                    total_field_correct += 1
                    field_accuracy[f"{section}.{key}"]["correct"] += 1

        doc_table_results = {}
        instrument_type = gold.get("instrument_type")
        pred_tables_data = pred_tables.get("tables", {})

        gold_tables = gold.get("tables", {})

        for key, gold_value in gold_tables.items():
            if key == "E_contact_partial_rows":
                pred_value = len(pred_tables_data.get("E_contact_partial", []))
            elif key == "S_scale_change_rows":
                pred_value = len(pred_tables_data.get("S_scale_change", []))
            elif key == "L_line_contact_rows":
                pred_value = len(pred_tables_data.get("L_line_contact", []))
            elif key == "pressure_error_table_rows":
                pred_value = len(pred_tables_data.get("pressure_error_table", []))
            elif key == "environmental_conditions_rows":
                pred_value = len(pred_tables_data.get("environmental_conditions", []))
            elif key == "max_hysteresis_bar":
                mh = pred_tables_data.get("max_hysteresis")
                pred_value = mh.get("max_hysteresis_bar") if isinstance(mh, dict) else None
            else:
                pred_value = None

            ok = compare_value(pred_value, gold_value)

            doc_table_results[key] = {
                "pred": pred_value,
                "gold": gold_value,
                "correct": ok
            }

            table_checks += 1
            if ok:
                table_correct += 1

        documents.append({
            "source_file": source_file,
            "instrument_type": instrument_type,
            "field_accuracy": round(doc_field_correct / doc_field_checks, 4) if doc_field_checks else 0.0,
            "fields": doc_field_results,
            "tables": doc_table_results
        })

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_documents": len(documents),
        "overall_field_accuracy": round(total_field_correct / total_field_checks, 4) if total_field_checks else 0.0,
        "overall_table_accuracy": round(table_correct / table_checks, 4) if table_checks else 0.0,
        "field_accuracy_breakdown": {
            k: round(v["correct"] / v["total"], 4) if v["total"] else 0.0
            for k, v in field_accuracy.items()
        },
        "documents": documents
    }

    out_fp = OUT_DIR / "gold_evaluation_phase1.json"
    out_fp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved:", out_fp)


if __name__ == "__main__":
    main()