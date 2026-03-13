import json
from pathlib import Path
from typing import Dict, Any

BASE = Path(__file__).resolve().parents[1]
PARSED_DIR = BASE / "data" / "parsed"
OUT_PATH = PARSED_DIR / "metrics_phase1.json"

REQUIRED_FIELDS = [
    ("header.certificate_number", "certificate_number"),
    ("header.issue_date", "issue_date"),
    ("laboratory.lab_name", "lab_name"),
    ("laboratory.lab_unit", "lab_unit"),
    ("client.name", "client_name"),
    ("equipment.designation", "designation"),
    ("equipment.brand", "brand"),
    ("equipment.model", "model"),
    ("equipment.serial_number", "serial_number"),
    ("equipment.range", "range"),
    ("equipment.resolution", "resolution"),
    ("standards", "standards"),
]

RESULT_KEYS = ["E_partial_contact", "S_scale_change", "L_line_contact"]

def get_nested(d: Dict[str, Any], path: str):
    cur = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur

def is_filled(val) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        return val.strip() != ""
    if isinstance(val, list):
        return len(val) > 0
    if isinstance(val, dict):
        return len(val) > 0
    return True

def main():
    files = [p for p in PARSED_DIR.glob("*.json") if p.name != OUT_PATH.name]
    if not files:
        print(f"Sem JSONs em {PARSED_DIR} (corre 04_parse_iso17025_min.py)")
        return

    per_doc = []
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        iso = doc.get("iso17025_min", {})
        missing = []
        present = []

        for path, key in REQUIRED_FIELDS:
            val = get_nested(iso, path)
            (present if is_filled(val) else missing).append(key)

        results = iso.get("results", {})
        has_any_results = any(is_filled(results.get(k, [])) for k in RESULT_KEYS)
        if not has_any_results:
            missing.append("results_tables")
        else:
            present.append("results_tables")

        completeness = len(present) / (len(REQUIRED_FIELDS) + 1)

        per_doc.append({
            "doc_id": doc.get("doc_id", f.stem),
            "present": present,
            "missing": missing,
            "completeness_score": round(completeness, 3),
            "results_rows": {k: len(results.get(k, [])) for k in RESULT_KEYS},
            "page_limit_detected": doc.get("notes", {}).get("page_limit_detected"),
            "pages_kept": doc.get("notes", {}).get("pages_kept"),
        })

    all_keys = [k for _, k in REQUIRED_FIELDS] + ["results_tables"]
    coverage = {k: 0 for k in all_keys}
    for k in all_keys:
        coverage[k] = round(sum(1 for d in per_doc if k in d["present"]) / len(per_doc), 3)

    out = {"n_documents": len(per_doc), "coverage": coverage, "documents": per_doc}
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved:", OUT_PATH)

if __name__ == "__main__":
    main()
