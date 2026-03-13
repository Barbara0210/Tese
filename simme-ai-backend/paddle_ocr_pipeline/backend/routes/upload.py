from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, UploadFile, HTTPException

BASE = Path(__file__).resolve().parents[1]
UPLOADS_DIR = BASE / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Ficheiro inválido.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Só são aceites ficheiros PDF.")

    file_id = uuid4().hex
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    stored_name = f"{file_id}__{safe_name}"
    out_path = UPLOADS_DIR / stored_name

    content = await file.read()
    out_path.write_bytes(content)

    return {
        "message": "Upload concluído com sucesso.",
        "file_id": file_id,
        "original_filename": file.filename,
        "stored_filename": stored_name,
        "stored_path": str(out_path)
    }