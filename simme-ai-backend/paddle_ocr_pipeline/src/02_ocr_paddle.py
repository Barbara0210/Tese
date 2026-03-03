from pathlib import Path
from paddleocr import PaddleOCR

BASE = Path(__file__).resolve().parents[1]
IMG_DIR = BASE / "data" / "images"
OUT_DIR = BASE / "data" / "ocr_text"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Fase 0: baseline. Se "pt" falhar, muda para "en" (lê PT na mesma muitas vezes).
ocr = PaddleOCR(lang="pt", use_angle_cls=True)

def ocr_page(img_path: Path) -> str:
    res = ocr.ocr(str(img_path), cls=True)
    if not res:
        return ""

    lines = []
    for item in res[0]:
        try:
            txt = item[1][0]
            if txt:
                lines.append(txt)
        except Exception:
            pass
    return "\n".join(lines)

def main():
    docs = [p for p in IMG_DIR.iterdir() if p.is_dir()]
    if not docs:
        print(f"Sem imagens em: {IMG_DIR} (corre 01_pdf_to_images.py)")
        return

    for doc in sorted(docs):
        out_txt = OUT_DIR / f"{doc.name}.txt"
        parts = []

        for img in sorted(doc.glob("page_*.png")):
            print("OCR:", doc.name, img.name)
            text = ocr_page(img)

            parts.append(f"\n\n=== {img.name} ===\n")
            parts.append(text)

        out_txt.write_text("\n".join(parts), encoding="utf-8")
        print("saved:", out_txt)

if __name__ == "__main__":
    main()