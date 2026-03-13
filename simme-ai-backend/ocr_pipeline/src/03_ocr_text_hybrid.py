import base64
from pathlib import Path
import requests

from paddleocr import PaddleOCR

BASE = Path(__file__).resolve().parents[1]
IN_DIR = BASE / "data" / "preprocessed"
OUT_DIR = BASE / "data" / "ocr_text"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/chat"
GLM_MODEL = "glm-ocr"

# PaddleOCR (Português). Se o 'pt' der problemas, tenta 'en' como fallback.
paddle = PaddleOCR(
    lang="latin",
    use_textline_orientation=True,
    enable_mkldnn=False
)
# Heurística: se o texto for curto demais, consideramos falha
MIN_CHARS_OK = 40

def glm_ocr_text(image_path: Path) -> str:
    """
    OCR via Ollama API (base64). Mais estável do que CLI para multimodal.
    """
    b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    payload = {
        "model": GLM_MODEL,
        "messages": [{
            "role": "user",
            "content": "Extract ALL text from this image. Return plain text only.",
            "images": [b64]
        }]
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=300)
    r.raise_for_status()
    data = r.json()
    return (data.get("message", {}) or {}).get("content", "") or ""

def paddle_ocr_text(image_path: Path) -> str:
    """
    OCR via PaddleOCR (robusto a formatos diferentes).
    """
    res = paddle.ocr(str(image_path))
    if not res:
        return ""

    lines = []

    # Caso A: res = [ [ [box, (text, score)], ... ] ]
    if isinstance(res, list) and len(res) > 0 and isinstance(res[0], list):
        for item in res[0]:
            try:
                text = item[1][0]
                if text:
                    lines.append(text)
            except Exception:
                continue
        return "\n".join(lines)

    # Caso B: res = [ [box, (text, score)], ... ]
    if isinstance(res, list):
        for item in res:
            try:
                text = item[1][0]
                if text:
                    lines.append(text)
            except Exception:
                continue
        return "\n".join(lines)

    return ""

def is_bad(text: str) -> bool:
    t = (text or "").strip()
    # casos típicos de "vazio" que tu viste
    if t == "":
        return True
    if t.lower() in ["portuguese text:", "text:", "ocr:", "none"]:
        return True
    # se for muito curto, quase sempre falhou
    if len(t) < MIN_CHARS_OK:
        return True
    return False

def main():
    doc_folders = [p for p in IN_DIR.iterdir() if p.is_dir()]
    if not doc_folders:
        print(f"Sem imagens em: {IN_DIR} (corre 01 e 02)")
        return

    for doc in doc_folders:
        doc_id = doc.name
        out_txt = OUT_DIR / f"{doc_id}.txt"
        parts = []

        for img in sorted(doc.glob("page_*.png")):
            print("OCR:", doc_id, img.name)

            # 1) tenta GLM
            engine = "glm-ocr"
            try:
                text = glm_ocr_text(img)
            except Exception as e:
                text = ""
                engine = "glm-ocr_error"

            # 2) fallback Paddle se vazio/fraco
            if is_bad(text):
                engine = "paddleocr"
                try:
                    text = paddle_ocr_text(img)
                except Exception as e:
                    engine = f"paddleocr_error:{type(e).__name__}"
                    text = f"[PADDLE_OCR_ERROR] {e}"

            parts.append(f"\n\n=== {img.name} | engine={engine} ===\n")
            parts.append(text)

        out_txt.write_text("\n".join(parts), encoding="utf-8")
        print("saved:", out_txt)

if __name__ == "__main__":
    main()