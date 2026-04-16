from fastapi import APIRouter, HTTPException, Query

from backend.services.pipeline_service import process_file

router = APIRouter()


@router.post("/process/{file_id}")
def process_uploaded_file(file_id: str, method: str = Query(default="paddle_current")):
    try:
        result = process_file(file_id, method)
        return {
            "message": "Processamento concluído com sucesso.",
            "file_id": file_id,
            "method": method,
            "result": result,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
