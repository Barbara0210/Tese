import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

BASE = Path(__file__).resolve().parents[1]
UPLOADS_DIR = BASE / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    paddleocr_vl_summary: UploadFile | None = File(default=None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Ficheiro invalido.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="So sao aceites ficheiros PDF.")

    file_id = uuid4().hex
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    stored_name = f"{file_id}__{safe_name}"
    out_path = UPLOADS_DIR / stored_name

    content = await file.read()
    out_path.write_bytes(content)

    summary_stored_name = None
    if paddleocr_vl_summary is not None:
        if not paddleocr_vl_summary.filename:
            raise HTTPException(status_code=400, detail="run_summary.json invalido.")

        if not paddleocr_vl_summary.filename.lower().endswith(".json"):
            raise HTTPException(status_code=400, detail="O resumo PaddleOCR-VL tem de ser um ficheiro JSON.")

        summary_content = await paddleocr_vl_summary.read()
        try:
            json.loads(summary_content.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="run_summary.json invalido ou ilegivel.") from exc

        summary_stored_name = f"{file_id}__paddleocr_vl_run_summary.json"
        (UPLOADS_DIR / summary_stored_name).write_bytes(summary_content)

    return {
        "message": "Upload concluido com sucesso.",
        "file_id": file_id,
        "original_filename": file.filename,
        "stored_filename": stored_name,
        "stored_path": str(out_path),
        "paddleocr_vl_summary_uploaded": summary_stored_name is not None,
        "paddleocr_vl_summary_filename": summary_stored_name,
    }
