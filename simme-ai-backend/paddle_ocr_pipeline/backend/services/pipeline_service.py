import json
import shutil
import subprocess
import time
from pathlib import Path

from backend.services.method_registry import get_method


BASE = Path(__file__).resolve().parents[2]

BACKEND_DIR = BASE / "backend"
UPLOADS_DIR = BACKEND_DIR / "uploads"
OUTPUTS_DIR = BACKEND_DIR / "outputs"
ARCHIVES_DIR = BACKEND_DIR / "archives"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = BASE / "data"
RAW_PDFS_DIR = DATA_DIR / "raw_pdfs"
PARSED_DIR = DATA_DIR / "parsed"
TABLES_DIR = DATA_DIR / "tables"
SECTIONS_DIR = DATA_DIR / "sections"
IMAGES_DIR = DATA_DIR / "images"
OCR_TEXT_DIR = DATA_DIR / "ocr_text"
METRICS_DIR = DATA_DIR / "metrics"
EVALUATION_DIR = DATA_DIR / "evaluation"
REGIONS_DIR = DATA_DIR / "regions"
CROPS_DIR = DATA_DIR / "crops"

SRC_DIR = BASE / "src"

PIPELINES = {
    "paddle_current": [
        "01_pdf_to_images.py",
        "02_ocr_paddle.py",
        "03_segment_sections.py",
        "04_parse_fields.py",
        "05_parse_tables.py",
        "06_metrics_phase1.py",
    ],
    "pdf_table": [
        "10_extract_tables_pdfplumber.py",
        "06_metrics_phase1.py",
    ],
    "hybrid_fast": [
        "01_pdf_to_images.py",
        "11_detect_regions_yolo.py",
        "12_ocr_regions_paddle.py",
        "13_merge_regions_to_text.py",
        "03_segment_sections.py",
        "04_parse_fields.py",
        "05_parse_tables.py",
        "06_metrics_phase1.py",
    ],
}


def _clean_data_folders():
    folders = [
        RAW_PDFS_DIR,
        IMAGES_DIR,
        OCR_TEXT_DIR,
        SECTIONS_DIR,
        PARSED_DIR,
        TABLES_DIR,
        METRICS_DIR,
        EVALUATION_DIR,
        REGIONS_DIR,
        CROPS_DIR,
    ]

    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        for item in folder.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)


def _run_script(script_name: str):
    script_path = SRC_DIR / script_name

    if not script_path.exists():
        raise FileNotFoundError(f"Script não encontrado: {script_path}")

    result = subprocess.run(
        ["python", str(script_path)],
        cwd=str(BASE),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Erro ao correr {script_name}\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    return {
        "script": script_name,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _load_single_json(folder: Path, pattern: str):
    files = sorted(folder.glob(pattern))
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8"))


def _find_document_metrics(metrics_data: dict | None, source_file: str | None):
    if not metrics_data or not source_file:
        return None

    for document in metrics_data.get("documents", []):
        if document.get("source_file") == source_file:
            return document

    return None


def _build_frontend_document(parsed_data: dict | None, tables_data: dict | None):
    parsed_data = parsed_data or {}
    tables_data = tables_data or {}

    return {
        "header": parsed_data.get("header", {}),
        "customer": parsed_data.get("customer", {}),
        "equipment": parsed_data.get("equipment", {}),
        "work_conditions": parsed_data.get("work_conditions", {}),
        "reference": parsed_data.get("reference", {}),
        "tables": tables_data.get("tables", {}),
    }


def _safe_archive_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)


def _copy_folder_contents(source_dir: Path, target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)

    for item in source_dir.iterdir():
        destination = target_dir / item.name
        if item.is_file():
            shutil.copy2(item, destination)
        elif item.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(item, destination)


def _archive_run_artifacts(
    file_id: str,
    method_key: str,
    original_filename: str,
    result_payload: dict,
):
    run_dir = ARCHIVES_DIR / f"{file_id}__{method_key}__{_safe_archive_name(Path(original_filename).stem)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "file_id": file_id,
        "method": method_key,
        "source_pdf": original_filename,
        "archived_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if matches := list(UPLOADS_DIR.glob(f"{file_id}__*.pdf")):
        shutil.copy2(matches[0], run_dir / matches[0].name)

    _copy_folder_contents(PARSED_DIR, run_dir / "parsed")
    _copy_folder_contents(TABLES_DIR, run_dir / "tables")
    _copy_folder_contents(METRICS_DIR, run_dir / "metrics")
    _copy_folder_contents(SECTIONS_DIR, run_dir / "sections")
    _copy_folder_contents(OCR_TEXT_DIR, run_dir / "ocr_text")
    _copy_folder_contents(REGIONS_DIR, run_dir / "regions")
    _copy_folder_contents(CROPS_DIR, run_dir / "crops")

    return run_dir


def process_file(file_id: str, method_key: str = "paddle_current"):
    method = get_method(method_key)
    if not method:
        raise ValueError(f"Método inválido: {method_key}")

    if not method.get("implemented"):
        raise NotImplementedError(
            f"O método '{method_key}' ainda não está implementado. "
            "Usa o baseline atual enquanto montamos os outros pipelines."
        )

    matches = list(UPLOADS_DIR.glob(f"{file_id}__*.pdf"))
    if not matches:
        raise FileNotFoundError(f"Não foi encontrado nenhum upload com file_id={file_id}")

    upload_pdf = matches[0]

    _clean_data_folders()

    RAW_PDFS_DIR.mkdir(parents=True, exist_ok=True)

    original_filename = upload_pdf.name.split("__", 1)[1]
    target_pdf = RAW_PDFS_DIR / original_filename
    shutil.copy2(upload_pdf, target_pdf)

    logs = []
    started_at = time.perf_counter()
    pipeline_scripts = PIPELINES[method_key]

    for script in pipeline_scripts:
        logs.append(_run_script(script))

    elapsed_seconds = round(time.perf_counter() - started_at, 3)

    parsed_data = _load_single_json(PARSED_DIR, "*.json")
    tables_data = _load_single_json(TABLES_DIR, "*_tables.json")
    sections_data = _load_single_json(SECTIONS_DIR, "*_sections.json")
    metrics_data = _load_single_json(METRICS_DIR, "*.json")

    frontend_document = _build_frontend_document(parsed_data, tables_data)
    source_file = parsed_data.get("source_file") if parsed_data else None

    result_payload = {
        "file_id": file_id,
        "source_pdf": original_filename,
        "method": method,
        "processing_summary": {
            "elapsed_seconds": elapsed_seconds,
            "scripts_executed": pipeline_scripts,
        },
        "metrics": {
            "document": _find_document_metrics(metrics_data, source_file),
            "global": metrics_data.get("global_metrics") if metrics_data else None,
        },
        "document": frontend_document,
        "raw": {
            "sections": sections_data,
            "parsed": parsed_data,
            "tables": tables_data,
            "metrics": metrics_data,
        },
        "logs": logs,
    }

    out_fp = OUTPUTS_DIR / f"{file_id}__{method_key}.json"
    out_fp.write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    archive_dir = _archive_run_artifacts(
        file_id=file_id,
        method_key=method_key,
        original_filename=original_filename,
        result_payload=result_payload,
    )
    result_payload["archive"] = {
        "run_dir": str(archive_dir),
    }
    (archive_dir / "result.json").write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out_fp.write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return result_payload


def get_result(file_id: str, method_key: str = "paddle_current"):
    out_fp = OUTPUTS_DIR / f"{file_id}__{method_key}.json"
    if not out_fp.exists():
        return None
    return json.loads(out_fp.read_text(encoding="utf-8"))
