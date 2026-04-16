import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]

OCR_TEXT_DIR = BASE / "data" / "ocr_text"


def main():
    region_ocr_files = sorted(OCR_TEXT_DIR.glob("*_regions.json"))
    if not region_ocr_files:
        print(f"Sem OCR por regiões em: {OCR_TEXT_DIR} (corre 12_ocr_regions_paddle.py)")
        return

    for region_file in region_ocr_files:
        data = json.loads(region_file.read_text(encoding="utf-8"))
        doc_name = region_file.name.replace("_regions.json", "")
        merged_parts = []

        for page_name in sorted(data.get("pages", {}).keys()):
            merged_parts.append(f"\n=== {page_name} ===\n")
            for region in data["pages"][page_name]:
                label = region.get("label") or "region"
                text = (region.get("text") or "").strip()
                if not text:
                    continue
                merged_parts.append(f"\n[region:{label}]\n{text}\n")

        out_path = OCR_TEXT_DIR / f"{doc_name}.txt"
        out_path.write_text("\n".join(merged_parts), encoding="utf-8")
        print("saved:", out_path)


if __name__ == "__main__":
    main()
