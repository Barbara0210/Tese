from pathlib import Path
import cv2
import numpy as np

BASE = Path(__file__).resolve().parents[1]
IN_DIR = BASE / "data" / "images"
OUT_DIR = BASE / "data" / "images_clean"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def preprocess_for_watermark(img_bgr):
    # 1) grayscale
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 2) reduzir ruído (sem desfocar demasiado o texto)
    g = cv2.fastNlMeansDenoising(g, None, h=12, templateWindowSize=7, searchWindowSize=21)

    # 3) estimar fundo (morphological opening com kernel grande)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (45, 45))
    bg = cv2.morphologyEx(g, cv2.MORPH_OPEN, kernel)

    # 4) remover fundo
    fg = cv2.subtract(g, bg)

    # 5) aumentar contraste local
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    fg = clahe.apply(fg)

    # 6) sharpen leve
    sharp = cv2.GaussianBlur(fg, (0, 0), 1.0)
    fg = cv2.addWeighted(fg, 1.5, sharp, -0.5, 0)

    return fg  # grayscale

def main():
    docs = [p for p in IN_DIR.iterdir() if p.is_dir()]
    if not docs:
        print(f"Sem imagens em: {IN_DIR} (corre 01_pdf_to_images.py primeiro)")
        return

    for doc in sorted(docs):
        out_doc = OUT_DIR / doc.name
        out_doc.mkdir(parents=True, exist_ok=True)

        for img_path in sorted(doc.glob("page_*.png")):
            img = cv2.imread(str(img_path))
            if img is None:
                print("WARN: não consegui ler:", img_path)
                continue

            proc = preprocess_for_watermark(img)

            out_path = out_doc / img_path.name
            cv2.imwrite(str(out_path), proc)
            print("saved:", out_path)

if __name__ == "__main__":
    main()