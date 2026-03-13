from fastapi import APIRouter, HTTPException

from backend.services.pipeline_service import process_file

router = APIRouter()


@router.post("/process/{file_id}")
def process_uploaded_file(file_id: str):
    try:
        result = process_file(file_id)
        return {
            "message": "Processamento concluído com sucesso.",
            "file_id": file_id,
            "result": result
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))