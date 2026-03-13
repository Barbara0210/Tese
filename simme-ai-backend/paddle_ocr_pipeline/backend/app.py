from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.upload import router as upload_router
from backend.routes.process import router as process_router
from backend.routes.result import router as result_router

app = FastAPI(
    title="Paddle OCR Pipeline API",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="", tags=["upload"])
app.include_router(process_router, prefix="", tags=["process"])
app.include_router(result_router, prefix="", tags=["result"])


@app.get("/health")
def health():
    return {"status": "ok"}