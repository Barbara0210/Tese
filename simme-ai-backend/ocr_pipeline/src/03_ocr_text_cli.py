import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
IN_DIR = BASE / "data" / "preprocessed"
OUT_DIR = BASE / "data" / "ocr_text"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "glm-ocr"

def ocr_page(img_path: Path) -> str:
    cmd = ["ollama", "run", MODEL, "Text Recognition:", str(img_path)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"OCR falhou ({img_path}):\nSTDERR:\n{p.stderr}\nSTDOUT:\n{p.stdout}")
    return p.stdout.strip()

def main():
    doc_folders = [p for p in IN_DIR.iterdir() if p.is_dir()]
    if not doc_folders:
        print(f"Sem imagens preprocessed em: {IN_DIR} (corre 02_preprocess_pages.py)")
        return

    for doc in doc_folders:
        doc_id = doc.name
        out_txt = OUT_DIR / f"{doc_id}.txt"
        parts = []
        for img in sorted(doc.glob("page_*.jpg")):
            print("OCR:", doc_id, img.name)
            parts.append(f"\n\n=== {img.name} ===\n")
            parts.append(ocr_page(img))
        out_txt.write_text("\n".join(parts), encoding="utf-8")
        print("saved:", out_txt)

if __name__ == "__main__":
    main()
