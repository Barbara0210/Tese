from fastapi import APIRouter, HTTPException

from backend.services.pipeline_service import get_result

router = APIRouter()


@router.get("/result/{file_id}")
def read_result(file_id: str):
    result = get_result(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Resultado não encontrado.")
    return result