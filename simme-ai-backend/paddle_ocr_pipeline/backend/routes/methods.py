from fastapi import APIRouter

from backend.services.method_registry import list_methods

router = APIRouter()


@router.get("/methods")
def read_methods():
    return {"methods": list_methods()}
