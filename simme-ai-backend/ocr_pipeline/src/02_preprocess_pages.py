from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parents[1]
IMG_DIR = BASE / "data" / "images"
OUT_DIR = BASE / "data" / "preprocessed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_SIDE = 2400 
JPEG_QUALITY = 92

def preprocess_image(inp: Path, outp: Path):
    img = Image.open(inp).convert("RGB")
    w, h = img.size

    scale = min(1.0, MAX_SIDE / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    outp.parent.mkdir(parents=True, exist_ok=True)
    img.save(outp, "PNG")
    return img.size

def main():
    doc_folders = [p for p in IMG_DIR.iterdir() if p.is_dir()]
    if not doc_folders:
        print(f"Sem imagens em: {IMG_DIR} (corre 01_pdf_to_images.py)")
        return

    for doc in doc_folders:
        for png in sorted(doc.glob("page_*.png")):
            rel = png.relative_to(IMG_DIR)
            outp = OUT_DIR / rel.with_suffix(".png")
            size = preprocess_image(png, outp)
            print("preprocessed:", outp, "size:", size)

if __name__ == "__main__":
    main()
