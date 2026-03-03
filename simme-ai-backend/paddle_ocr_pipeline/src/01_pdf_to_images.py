from pathlib import Path
from pdf2image import convert_from_path

BASE = Path(__file__).resolve().parents[1]
PDF_DIR = BASE / "data" / "raw_pdfs"
OUT_DIR = BASE / "data" / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DPI = 300

def main():
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"Sem PDFs em: {PDF_DIR}")
        return

    for pdf in pdfs:
        doc_dir = OUT_DIR / pdf.stem
        doc_dir.mkdir(parents=True, exist_ok=True)

        pages = convert_from_path(str(pdf), dpi=DPI)
        for i, page in enumerate(pages, start=1):
            out_path = doc_dir / f"page_{i:02d}.png"
            page.save(out_path, "PNG")
            print("saved:", out_path)

if __name__ == "__main__":
    main()