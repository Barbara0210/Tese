"""
Evaluate archived method runs against a small manual gold set.

This separates two different ideas that were previously mixed:

- filled fields: the method produced some value;
- correct fields: the produced value matches the manually checked gold value.

The script is read-only over backend archives. It uses the latest archived run
for each document/method pair in the thesis manifest.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
ARCHIVES_DIR = BASE_DIR / "backend" / "archives"
RUNS_SUMMARY_PATH = BASE_DIR / "backend" / "method_runs_summary.json"
DEFAULT_MANIFEST = BASE_DIR / "config" / "thesis_test_set_5docs.json"
DEFAULT_GOLD = BASE_DIR / "data" / "gold" / "thesis_test_set_5docs_gold.json"
OUT_ROOT = BASE_DIR / "data" / "evaluation"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("\\pm", "+/-").replace("±", "+/-")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9+\-/]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def important_tokens(value: str) -> list[str]:
    stopwords = {
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "em",
        "com",
        "para",
        "the",
        "and",
        "of",
    }
    return [token for token in re.findall(r"[a-z0-9]+", value) if len(token) > 2 and token not in stopwords]


def numeric_tokens(value: str) -> list[str]:
    return re.findall(r"\d+(?:[.,]\d+)?", value)


def numeric_values_match(predicted: str, gold: str) -> bool:
    pred_nums = [number.replace(",", ".") for number in numeric_tokens(predicted)]
    gold_nums = [number.replace(",", ".") for number in numeric_tokens(gold)]
    return bool(gold_nums) and pred_nums == gold_nums


def field_matches(predicted: Any, gold: Any) -> bool:
    if not is_filled(predicted):
        return False

    pred_norm = normalize(predicted)
    gold_norm = normalize(gold)
    if not pred_norm or not gold_norm:
        return False
    if pred_norm == gold_norm:
        return True
    if len(gold_norm) >= 8 and (gold_norm in pred_norm or pred_norm in gold_norm):
        return True
    if difflib.SequenceMatcher(None, pred_norm, gold_norm).ratio() >= 0.92:
        return True

    tokens = important_tokens(gold_norm)
    if not tokens:
        return numeric_values_match(pred_norm, gold_norm)
    if numeric_tokens(gold_norm) and not numeric_values_match(pred_norm, gold_norm):
        return False
    matched = sum(1 for token in tokens if token in pred_norm)
    return matched / len(tokens) >= 0.8


def get_nested(data: dict, dotted_key: str) -> Any:
    current: Any = data
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def table_row_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if not isinstance(value, dict):
        return 1 if value is not None else 0
    if isinstance(value.get("rows"), list):
        return len(value["rows"])
    if isinstance(value.get("subtables"), list):
        return sum(table_row_count(subtable.get("table")) for subtable in value["subtables"] if isinstance(subtable, dict))
    return 1 if value else 0


def load_run_entries() -> list[dict]:
    if RUNS_SUMMARY_PATH.exists():
        return read_json(RUNS_SUMMARY_PATH).get("entries", [])

    entries = []
    for result_path in sorted(ARCHIVES_DIR.glob("*/result.json")):
        try:
            result = read_json(result_path)
        except Exception:
            continue
        entries.append(
            {
                "source_pdf": result.get("source_pdf"),
                "method_key": (result.get("method") or {}).get("key"),
                "archive_run_dir": str(result_path.parent),
                "recorded_at": datetime.fromtimestamp(result_path.stat().st_mtime).isoformat(timespec="seconds"),
            }
        )
    return entries


def latest_entries(entries: list[dict]) -> dict[tuple[str, str], dict]:
    latest: dict[tuple[str, str], dict] = {}
    for entry in entries:
        source_pdf = entry.get("source_pdf")
        method_key = entry.get("method_key")
        if not source_pdf or not method_key:
            continue
        key = (source_pdf, method_key)
        if key not in latest or (entry.get("recorded_at") or "") >= (latest[key].get("recorded_at") or ""):
            latest[key] = entry
    return latest


def load_result(entry: dict | None) -> dict | None:
    if not entry:
        return None
    result_path = Path(entry.get("archive_run_dir", "")) / "result.json"
    if not result_path.exists():
        return None
    return read_json(result_path)


def mean_or_zero(values: list[float]) -> float:
    return round(mean(values), 4) if values else 0.0


def evaluate_run(source_pdf: str, method_key: str, gold_doc: dict, result: dict | None) -> tuple[dict, list[dict], list[dict]]:
    if not result:
        return (
            {
                "source_pdf": source_pdf,
                "method_key": method_key,
                "status": "missing",
            },
            [],
            [],
        )

    document = result.get("document") or {}
    gold_fields = gold_doc.get("fields") or {}
    field_rows = []

    filled = 0
    correct = 0
    for field_name, gold_value in sorted(gold_fields.items()):
        predicted = get_nested(document, field_name)
        present = is_filled(predicted)
        ok = field_matches(predicted, gold_value)
        if present:
            filled += 1
        if ok:
            correct += 1
        field_rows.append(
            {
                "source_pdf": source_pdf,
                "method_key": method_key,
                "field": field_name,
                "filled": present,
                "correct": ok,
                "predicted": predicted,
                "gold": gold_value,
            }
        )

    tables = document.get("tables") or {}
    gold_tables = gold_doc.get("tables") or {}
    table_rows = []
    table_correct = 0
    for table_name, expectation in sorted(gold_tables.items()):
        min_rows = int((expectation or {}).get("min_rows", 1))
        row_count = table_row_count(tables.get(table_name))
        ok = row_count >= min_rows
        if ok:
            table_correct += 1
        table_rows.append(
            {
                "source_pdf": source_pdf,
                "method_key": method_key,
                "table": table_name,
                "row_count": row_count,
                "min_rows": min_rows,
                "correct": ok,
            }
        )

    gold_instrument = gold_doc.get("instrument_type")
    pred_instrument = ((result.get("metrics") or {}).get("document") or {}).get("instrument_type")
    if not pred_instrument:
        pred_instrument = (((result.get("raw") or {}).get("tables") or {}).get("instrument_type"))

    total_fields = len(gold_fields)
    total_tables = len(gold_tables)
    run_row = {
        "source_pdf": source_pdf,
        "method_key": method_key,
        "status": "ok",
        "field_gold_total": total_fields,
        "field_filled": filled,
        "field_correct": correct,
        "field_fill_rate_on_gold": round(filled / total_fields, 4) if total_fields else 0.0,
        "field_accuracy": round(correct / total_fields, 4) if total_fields else 0.0,
        "field_precision_when_filled": round(correct / filled, 4) if filled else 0.0,
        "table_gold_total": total_tables,
        "table_correct": table_correct,
        "table_accuracy": round(table_correct / total_tables, 4) if total_tables else 0.0,
        "instrument_type_pred": pred_instrument,
        "instrument_type_gold": gold_instrument,
        "instrument_type_correct": normalize(pred_instrument) == normalize(gold_instrument),
        "elapsed_seconds": (result.get("processing_summary") or {}).get("elapsed_seconds"),
    }
    return run_row, field_rows, table_rows


def build_report(summary: dict, run_rows: list[dict]) -> str:
    lines = [
        "# Gold evaluation - thesis 5-document set",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "This report separates field presence from field correctness using the manual gold set.",
        "",
        "## Method averages",
        "",
        "| Method | Runs | Field fill | Field accuracy | Precision when filled | Table accuracy | Instrument type |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for method_key, stats in sorted(summary["methods"].items()):
        lines.append(
            "| {method} | {runs} | {fill:.4f} | {acc:.4f} | {prec:.4f} | {table:.4f} | {inst:.4f} |".format(
                method=method_key,
                runs=stats["runs"],
                fill=stats["avg_field_fill_rate_on_gold"],
                acc=stats["avg_field_accuracy"],
                prec=stats["avg_field_precision_when_filled"],
                table=stats["avg_table_accuracy"],
                inst=stats["instrument_type_accuracy"],
            )
        )

    lines.extend(["", "## Runs with largest correctness gap", ""])
    sorted_rows = sorted(
        [row for row in run_rows if row.get("status") == "ok"],
        key=lambda row: (row.get("field_fill_rate_on_gold", 0) - row.get("field_accuracy", 0)),
        reverse=True,
    )
    for row in sorted_rows[:10]:
        gap = row.get("field_fill_rate_on_gold", 0) - row.get("field_accuracy", 0)
        lines.append(
            "- `{method}` on `{doc}`: fill={fill:.4f}, correct={acc:.4f}, gap={gap:.4f}".format(
                method=row["method_key"],
                doc=row["source_pdf"],
                fill=row.get("field_fill_rate_on_gold", 0),
                acc=row.get("field_accuracy", 0),
                gap=gap,
            )
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    manifest = read_json(args.manifest)
    gold = read_json(args.gold).get("documents", {})
    methods = manifest.get("methods") or []
    latest = latest_entries(load_run_entries())

    run_rows: list[dict] = []
    field_rows: list[dict] = []
    table_rows: list[dict] = []

    for document in manifest.get("documents", []):
        source_pdf = document["source_pdf"]
        gold_doc = gold.get(source_pdf)
        if not gold_doc:
            continue
        for method_key in methods:
            result = load_result(latest.get((source_pdf, method_key)))
            run_row, doc_field_rows, doc_table_rows = evaluate_run(source_pdf, method_key, gold_doc, result)
            run_rows.append(run_row)
            field_rows.extend(doc_field_rows)
            table_rows.extend(doc_table_rows)

    method_stats: dict[str, dict] = {}
    for method_key in methods:
        rows = [row for row in run_rows if row.get("method_key") == method_key and row.get("status") == "ok"]
        method_stats[method_key] = {
            "runs": len(rows),
            "avg_field_fill_rate_on_gold": mean_or_zero([row["field_fill_rate_on_gold"] for row in rows]),
            "avg_field_accuracy": mean_or_zero([row["field_accuracy"] for row in rows]),
            "avg_field_precision_when_filled": mean_or_zero([row["field_precision_when_filled"] for row in rows]),
            "avg_table_accuracy": mean_or_zero([row["table_accuracy"] for row in rows]),
            "instrument_type_accuracy": mean_or_zero([1.0 if row["instrument_type_correct"] else 0.0 for row in rows]),
        }

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "manifest": str(args.manifest),
        "gold": str(args.gold),
        "methods": method_stats,
        "runs": run_rows,
    }

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "__thesis_gold_5docs"
    out_dir = args.out_dir or (OUT_ROOT / run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    write_json(out_dir / "gold_summary.json", summary)
    write_csv(out_dir / "gold_runs.csv", run_rows)
    write_csv(out_dir / "gold_fields.csv", field_rows)
    write_csv(out_dir / "gold_tables.csv", table_rows)
    (out_dir / "gold_report.md").write_text(build_report(summary, run_rows), encoding="utf-8")

    print("saved:", out_dir)


if __name__ == "__main__":
    main()
