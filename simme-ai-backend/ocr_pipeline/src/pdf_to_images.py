from pathlib import Path
from pdf2image import convert_from_path

BASE = Path(__file__).resolve().parents[1]
PDF_DIR = BASE / "data" / "pdfs"
IMG_DIR = BASE / "data" / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

DPI = 350

def main():
    pdfs = list(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"Sem PDFs em: {PDF_DIR}")
        return

    for pdf in pdfs:
        out_sub = IMG_DIR / pdf.stem
        out_sub.mkdir(parents=True, exist_ok=True)

        pages = convert_from_path(str(pdf), dpi=DPI)
        for i, page in enumerate(pages, start=1):
            out_path = out_sub / f"page_{i:02d}.png"
            page.save(out_path, "PNG")
            print("saved:", out_path)

if __name__ == "__main__":
    main()