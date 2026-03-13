import json
import shutil
import subprocess
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

BACKEND_DIR = BASE / "backend"
UPLOADS_DIR = BACKEND_DIR / "uploads"
OUTPUTS_DIR = BACKEND_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = BASE / "data"
RAW_PDFS_DIR = DATA_DIR / "raw_pdfs"
PARSED_DIR = DATA_DIR / "parsed"
TABLES_DIR = DATA_DIR / "tables"
SECTIONS_DIR = DATA_DIR / "sections"
IMAGES_DIR = DATA_DIR / "images"
OCR_TEXT_DIR = DATA_DIR / "ocr_text"
METRICS_DIR = DATA_DIR / "metrics"
EVALUATION_DIR = DATA_DIR / "evaluation"

SRC_DIR = BASE / "src"


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
        errors="replace"
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
        "stderr": result.stderr
    }


def _load_single_json(folder: Path, pattern: str):
    files = sorted(folder.glob(pattern))
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8"))


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


def process_file(file_id: str):
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

    # PIPELINE ATUAL
    pipeline_scripts = [
        "01_pdf_to_images.py",
        "02_ocr_paddle.py",
        "03_segment_sections.py",
        "04_parse_fields.py",
        "05_parse_tables.py",
        "06_metrics_phase1.py",
    ]

    for script in pipeline_scripts:
        logs.append(_run_script(script))

    parsed_data = _load_single_json(PARSED_DIR, "*.json")
    tables_data = _load_single_json(TABLES_DIR, "*_tables.json")
    sections_data = _load_single_json(SECTIONS_DIR, "*_sections.json")

    frontend_document = _build_frontend_document(parsed_data, tables_data)

    result_payload = {
        "file_id": file_id,
        "source_pdf": original_filename,
        "document": frontend_document,
        "raw": {
            "sections": sections_data,
            "parsed": parsed_data,
            "tables": tables_data,
        },
        "logs": logs,
    }

    out_fp = OUTPUTS_DIR / f"{file_id}.json"
    out_fp.write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return result_payload


def get_result(file_id: str):
    out_fp = OUTPUTS_DIR / f"{file_id}.json"
    if not out_fp.exists():
        return None
    return json.loads(out_fp.read_text(encoding="utf-8"))