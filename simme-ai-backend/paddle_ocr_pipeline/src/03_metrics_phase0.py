import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TXT_DIR = BASE / "data" / "ocr_text"
OUT = BASE / "data" / "reports" / "metrics_phase0.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

def main():
    txts = sorted(TXT_DIR.glob("*.txt"))
    if not txts:
        print(f"Sem OCR txt em: {TXT_DIR}")
        return

    docs = []
    for t in txts:
        content = t.read_text(encoding="utf-8", errors="ignore")
        blocks = content.split("=== ")
        page_blocks = [b for b in blocks if b.strip().startswith("page_")]

        counts = []
        empty_pages = 0
        for pb in page_blocks:
            parts = pb.split("===\n", 1)
            body = parts[1] if len(parts) == 2 else ""
            n = len(body.strip())
            counts.append(n)
            if n < 30:
                empty_pages += 1

        docs.append({
            "doc_id": t.stem,
            "n_pages": len(page_blocks),
            "total_chars": sum(counts),
            "avg_chars_per_page": (sum(counts) / len(counts)) if counts else 0,
            "empty_pages_lt30chars": empty_pages,
        })

    report = {"phase": 0, "n_documents": len(docs), "documents": docs}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved:", OUT)

if __name__ == "__main__":
    main()