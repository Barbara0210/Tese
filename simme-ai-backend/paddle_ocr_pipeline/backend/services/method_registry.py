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
    "ocr_llm": {
        "key": "ocr_llm",
        "label": "OCR + LLM",
        "short_label": "OCR + LLM",
        "description": "Pipeline híbrido com PaddleOCR e LLM para interpretação semântica e estruturação.",
        "implemented": True,
        "category": "multimodal",
    },
    "paddleocr_vl": {
        "key": "paddleocr_vl",
        "label": "PaddleOCR-VL",
        "short_label": "PaddleOCR-VL",
        "description": "Importa os resultados multimodais do PaddleOCR-VL gerados no Colab e converte-os para o esquema de campos, tabelas e metricas do projeto.",
        "implemented": True,
        "category": "multimodal",
    },
}


def list_methods():
    return list(METHODS.values())


def get_method(method_key: str):
    return METHODS.get(method_key)
