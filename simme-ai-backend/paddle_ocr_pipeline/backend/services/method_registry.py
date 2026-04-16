METHODS = {
    "paddle_current": {
        "key": "paddle_current",
        "label": "Baseline Atual",
        "short_label": "PaddleOCR atual",
        "description": "Pipeline atual baseado em PaddleOCR e parsers heurísticos.",
        "implemented": True,
        "category": "baseline",
    },
    "pdf_table": {
        "key": "pdf_table",
        "label": "PdfTable",
        "short_label": "PdfTable",
        "description": "Método baseado apenas em extração de tabelas diretamente do PDF.",
        "implemented": True,
        "category": "table_only",
    },
    "hybrid_fast": {
        "key": "hybrid_fast",
        "label": "Híbrido Rápido",
        "short_label": "YOLO + PaddleOCR",
        "description": "Método híbrido com deteção de regiões por YOLO e OCR por PaddleOCR.",
        "implemented": True,
        "category": "hybrid",
    },
    "vision_llm": {
        "key": "vision_llm",
        "label": "LLM com Visão",
        "short_label": "Vision LLM",
        "description": "Método multimodal com modelo de visão para extração semântica.",
        "implemented": False,
        "category": "multimodal",
    },
}


def list_methods():
    return list(METHODS.values())


def get_method(method_key: str):
    return METHODS.get(method_key)
