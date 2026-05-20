from pathlib import Path
from pdf2image import convert_from_path

BASE = Path(__file__).resolve().parents[1]
PDF_DIR = BASE / "data" / "raw_pdfs"
OUT_DIR = BASE / "data" / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DPI = 300


def _convert_pdf(pdf: Path, output_root: Path):
    doc_dir = output_root / pdf.stem
    doc_dir.mkdir(parents=True, exist_ok=True)

    pages = convert_from_path(str(pdf), dpi=DPI)
    for i, page in enumerate(pages, start=1):
        out_path = doc_dir / f"page_{i:02d}.png"
        page.save(out_path, "PNG")
        print("saved:", out_path)


def main():
    root_pdfs = sorted(PDF_DIR.glob("*.pdf"))
    split_dirs = [split_dir for split_dir in [PDF_DIR / "train", PDF_DIR / "val"] if split_dir.exists()]

    if not root_pdfs and not split_dirs:
        print(f"Sem PDFs em: {PDF_DIR}")
        return

    for pdf in root_pdfs:
        _convert_pdf(pdf, OUT_DIR)

    for split_dir in split_dirs:
        split_output_dir = OUT_DIR / split_dir.name
        split_output_dir.mkdir(parents=True, exist_ok=True)
        for pdf in sorted(split_dir.glob("*.pdf")):
            _convert_pdf(pdf, split_output_dir)

if __name__ == "__main__":
    main()
