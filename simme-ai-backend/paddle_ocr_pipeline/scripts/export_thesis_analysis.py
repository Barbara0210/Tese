"""
Export thesis-ready comparison artifacts from archived method runs.

The backend already archives every execution under backend/archives and refreshes
method_runs_summary.json. This script turns those artifacts into compact files
for the dissertation:

    data/analysis/<run_id>/summary.json
    data/analysis/<run_id>/runs.csv
    data/analysis/<run_id>/fields.csv
    data/analysis/<run_id>/tables.csv
    data/analysis/<run_id>/report.md

It is intentionally read-only over archives: it does not rerun OCR or LLMs.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
ARCHIVES_DIR = BACKEND_DIR / "archives"
RUNS_SUMMARY_PATH = BACKEND_DIR / "method_runs_summary.json"
DEFAULT_MANIFEST = BASE_DIR / "config" / "thesis_test_set_5docs.json"
ANALYSIS_DIR = BASE_DIR / "data" / "analysis"

DEFAULT_METHODS = [
    "paddle_current",
    "pdf_table",
    "hybrid_fast",
    "ocr_llm",
    "paddleocr_vl",
    "paddleocr_vl_llm",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "").strip("_")
    return value or "analysis"


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return read_json(path)


def load_run_entries() -> list[dict]:
    if RUNS_SUMMARY_PATH.exists():
        return read_json(RUNS_SUMMARY_PATH).get("entries", [])

    entries = []
    for result_path in sorted(ARCHIVES_DIR.glob("*/result.json")):
        try:
            result = read_json(result_path)
        except Exception:
            continue

        document_metrics = (result.get("metrics") or {}).get("document") or {}
        field_metrics = document_metrics.get("fields") or {}
        table_metrics = document_metrics.get("tables") or {}
        method = result.get("method") or {}
        entries.append(
            {
                "file_id": result.get("file_id"),
                "source_pdf": result.get("source_pdf"),
                "method_key": method.get("key"),
                "method_label": method.get("label"),
                "method_category": method.get("category"),
                "elapsed_seconds": (result.get("processing_summary") or {}).get("elapsed_seconds"),
                "instrument_type": document_metrics.get("instrument_type"),
                "filled_fields": field_metrics.get("filled_fields"),
                "total_fields": field_metrics.get("total_fields"),
                "completeness_score": field_metrics.get("completeness_score"),
                "schema_filled_fields": field_metrics.get("schema_filled_fields"),
                "schema_total_fields": field_metrics.get("schema_total_fields"),
                "schema_completeness_score": field_metrics.get("schema_completeness_score"),
                "found_tables": table_metrics.get("found_tables"),
                "expected_tables": table_metrics.get("expected_tables"),
                "detected_tables": table_metrics.get("detected_tables"),
                "table_extraction_score": table_metrics.get("table_extraction_score"),
                "archive_run_dir": str(result_path.parent),
                "recorded_at": datetime.fromtimestamp(result_path.stat().st_mtime).isoformat(timespec="seconds"),
            }
        )
    return entries


def latest_entries(entries: list[dict]) -> dict[tuple[str, str], dict]:
    latest = {}
    for entry in entries:
        source_pdf = entry.get("source_pdf")
        method_key = entry.get("method_key")
        if not source_pdf or not method_key:
            continue
        key = (source_pdf, method_key)
        current = latest.get(key)
        if current is None or (entry.get("recorded_at") or "") >= (current.get("recorded_at") or ""):
            latest[key] = entry
    return latest


def load_result(entry: dict | None) -> dict | None:
    if not entry:
        return None
    archive = entry.get("archive_run_dir")
    if not archive:
        return None
    result_path = Path(archive) / "result.json"
    if not result_path.exists():
        return None
    try:
        return read_json(result_path)
    except Exception:
        return None


def pick_metric(entry: dict, *keys: str) -> Any:
    for key in keys:
        if entry.get(key) is not None:
            return entry.get(key)
    return None


def average(values: list[float]) -> float | None:
    values = [value for value in values if isinstance(value, (int, float))]
    return round(mean(values), 4) if values else None


def build_run_row(document: dict, method_key: str, entry: dict | None, result: dict | None) -> dict:
    metrics = ((result or {}).get("metrics") or {}).get("document") or {}
    fields = metrics.get("fields") or {}
    tables = metrics.get("tables") or {}

    llm_audit = (
        (((result or {}).get("raw") or {}).get("parsed") or {})
        .get("raw_blocks", {})
        .get("ollama_llm", {})
    )
    conflicts = llm_audit.get("conflicts") or []

    if not entry:
        return {
            "source_pdf": document["source_pdf"],
            "method_key": method_key,
            "status": "missing",
            "notes": "No archived run found for this document/method.",
        }

    return {
        "source_pdf": document["source_pdf"],
        "method_key": method_key,
        "status": "ok",
        "file_id": entry.get("file_id"),
        "method_label": entry.get("method_label"),
        "elapsed_seconds": entry.get("elapsed_seconds"),
        "instrument_type": pick_metric(entry, "instrument_type"),
        "filled_fields": pick_metric(entry, "filled_fields"),
        "total_fields": pick_metric(entry, "total_fields"),
        "completeness_score": pick_metric(entry, "completeness_score"),
        "schema_filled_fields": pick_metric(entry, "schema_filled_fields"),
        "schema_total_fields": pick_metric(entry, "schema_total_fields"),
        "schema_completeness_score": pick_metric(entry, "schema_completeness_score"),
        "found_tables": pick_metric(entry, "found_tables"),
        "expected_tables": pick_metric(entry, "expected_tables"),
        "detected_tables": pick_metric(entry, "detected_tables") or tables.get("detected_tables"),
        "table_extraction_score": pick_metric(entry, "table_extraction_score"),
        "row_counts": tables.get("row_counts", {}),
        "llm_conflicts": len(conflicts),
        "archive_run_dir": entry.get("archive_run_dir"),
        "recorded_at": entry.get("recorded_at"),
    }


def build_field_rows(document: dict, method_key: str, result: dict | None) -> list[dict]:
    if not result:
        return []
    fields = ((((result.get("metrics") or {}).get("document") or {}).get("fields")) or {})
    presence = fields.get("presence") or {}
    applicable = fields.get("applicable_presence") or {}
    rows = []
    for field_name in sorted(set(presence) | set(applicable)):
        rows.append(
            {
                "source_pdf": document["source_pdf"],
                "method_key": method_key,
                "field": field_name,
                "present": presence.get(field_name),
                "applicable": applicable.get(field_name),
            }
        )
    return rows


def build_table_rows(document: dict, method_key: str, result: dict | None) -> list[dict]:
    if not result:
        return []
    tables = ((((result.get("metrics") or {}).get("document") or {}).get("tables")) or {})
    presence = tables.get("presence") or {}
    row_counts = tables.get("row_counts") or {}
    rows = []
    for table_name in sorted(set(presence) | set(row_counts)):
        rows.append(
            {
                "source_pdf": document["source_pdf"],
                "method_key": method_key,
                "table": table_name,
                "present": presence.get(table_name),
                "row_count": row_counts.get(table_name),
            }
        )
    return rows


def aggregate_rows(run_rows: list[dict]) -> dict:
    ok_rows = [row for row in run_rows if row.get("status") == "ok"]
    by_method = defaultdict(list)
    by_document = defaultdict(list)
    for row in ok_rows:
        by_method[row["method_key"]].append(row)
        by_document[row["source_pdf"]].append(row)

    method_summary = []
    for method_key, rows in sorted(by_method.items()):
        method_summary.append(
            {
                "method_key": method_key,
                "n_runs": len(rows),
                "avg_elapsed_seconds": average([row.get("elapsed_seconds") for row in rows]),
                "avg_completeness_score": average([row.get("completeness_score") for row in rows]),
                "avg_schema_completeness_score": average([row.get("schema_completeness_score") for row in rows]),
                "avg_table_extraction_score": average([row.get("table_extraction_score") for row in rows]),
                "avg_detected_tables": average([row.get("detected_tables") for row in rows]),
                "total_llm_conflicts": sum(row.get("llm_conflicts") or 0 for row in rows),
            }
        )

    document_summary = []
    for source_pdf, rows in sorted(by_document.items()):
        best_schema = max(
            (row.get("schema_completeness_score") for row in rows if row.get("schema_completeness_score") is not None),
            default=None,
        )
        best_tables = max(
            (row.get("table_extraction_score") for row in rows if row.get("table_extraction_score") is not None),
            default=None,
        )
        document_summary.append(
            {
                "source_pdf": source_pdf,
                "n_runs": len(rows),
                "best_schema_completeness_score": best_schema,
                "best_table_extraction_score": best_tables,
                "methods_run": [row["method_key"] for row in sorted(rows, key=lambda item: item["method_key"])],
            }
        )

    missing = [row for row in run_rows if row.get("status") != "ok"]
    return {
        "method_summary": method_summary,
        "document_summary": document_summary,
        "missing_runs": missing,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    columns = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: safe_cell(row.get(key)) for key in columns})


def markdown_table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "_Sem dados._"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, float):
                value = f"{value:.4g}"
            values.append(str(value if value is not None else ""))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_report(path: Path, manifest: dict, aggregate: dict, run_rows: list[dict]) -> None:
    missing = aggregate["missing_runs"]
    content = [
        "# Analise comparativa dos metodos",
        "",
        f"Gerado em: {datetime.now().isoformat(timespec='seconds')}",
        f"Conjunto: `{manifest.get('name', 'sem_nome')}`",
        "",
        "## Resumo por metodo",
        markdown_table(
            aggregate["method_summary"],
            [
                "method_key",
                "n_runs",
                "avg_elapsed_seconds",
                "avg_completeness_score",
                "avg_schema_completeness_score",
                "avg_table_extraction_score",
                "avg_detected_tables",
                "total_llm_conflicts",
            ],
        ),
        "",
        "## Resumo por documento",
        markdown_table(
            aggregate["document_summary"],
            [
                "source_pdf",
                "n_runs",
                "best_schema_completeness_score",
                "best_table_extraction_score",
                "methods_run",
            ],
        ),
        "",
        "## Execucoes em falta",
        markdown_table(missing, ["source_pdf", "method_key", "status", "notes"]),
        "",
        "## Notas para interpretacao",
        "- `completeness_score` mede apenas campos considerados aplicaveis pelo parser.",
        "- `schema_completeness_score` mede o preenchimento face ao schema fixo de 20 campos.",
        "- `table_extraction_score` so e comparavel quando existe `instrument_type` com tabelas esperadas.",
        "- `detected_tables` e `row_counts` ajudam a analisar tabelas extraidas mas ainda sem expectativa formal.",
        "- `llm_conflicts` deve ser lido como sinal de risco: sugestoes do LLM que divergiram de valores OCR/VL ja preenchidos.",
        "",
        "## Proximas analises qualitativas sugeridas",
        "- Confirmar manualmente os campos onde o LLM gerou conflitos.",
        "- Verificar se tabelas detectadas mas nao esperadas devem originar novas classes de tabela.",
        "- Separar falhas de leitura OCR/VL de falhas de parsing/normalizacao.",
    ]
    path.write_text("\n".join(content), encoding="utf-8")


def export_analysis(manifest_path: Path, methods: list[str] | None, out_dir: Path | None) -> Path:
    manifest = load_manifest(manifest_path)
    documents = manifest.get("documents", [])
    methods = methods or manifest.get("methods") or DEFAULT_METHODS

    latest = latest_entries(load_run_entries())
    run_rows = []
    field_rows = []
    table_rows = []

    for document in documents:
        for method_key in methods:
            entry = latest.get((document["source_pdf"], method_key))
            result = load_result(entry)
            run_rows.append(build_run_row(document, method_key, entry, result))
            field_rows.extend(build_field_rows(document, method_key, result))
            table_rows.extend(build_table_rows(document, method_key, result))

    aggregate = aggregate_rows(run_rows)
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}__{slug(manifest.get('name', 'analysis'))}"
    out_dir = out_dir or ANALYSIS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "manifest": manifest,
        "methods": methods,
        "aggregate": aggregate,
        "runs": run_rows,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_dir / "runs.csv", run_rows)
    write_csv(out_dir / "fields.csv", field_rows)
    write_csv(out_dir / "tables.csv", table_rows)
    write_report(out_dir / "report.md", manifest, aggregate, run_rows)
    return out_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export thesis comparison artifacts from archived method runs.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--methods", nargs="*", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = export_analysis(args.manifest, args.methods, args.out_dir)
    print(f"saved analysis: {out_dir}")


if __name__ == "__main__":
    main()
