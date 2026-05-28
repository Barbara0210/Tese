import os
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

# Keep Paddle/PaddleOCR compatible with newer protobuf versions on Windows.
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
# imgaug expects np.sctypes, which was removed in NumPy 2.
if not hasattr(np, "sctypes"):
    np.sctypes = {
        "int": [np.int8, np.int16, np.int32, np.int64],
        "uint": [np.uint8, np.uint16, np.uint32, np.uint64],
        "float": [np.float16, np.float32, np.float64],
        "complex": [np.complex64, np.complex128],
        "others": [np.bool_, np.object_, np.bytes_, np.str_],
    }
from paddleocr import PaddleOCR
from ocr_preprocess import preprocess_for_ocr


BASE = Path(__file__).resolve().parents[1]

IMAGES_DIR = BASE / "data" / "images"
REGIONS_DIR = BASE / "data" / "regions"
CROPS_DIR = BASE / "data" / "crops"
OCR_TEXT_DIR = BASE / "data" / "ocr_text"

CROPS_DIR.mkdir(parents=True, exist_ok=True)
OCR_TEXT_DIR.mkdir(parents=True, exist_ok=True)

ocr = PaddleOCR(lang="pt", use_angle_cls=True)


def _ocr_image(image_path: Path) -> str:
    with Image.open(image_path) as image:
        processed = preprocess_for_ocr(image)
        image_np = np.array(processed)

    result = ocr.ocr(image_np, cls=True)
    if not result:
        return ""
    if not result[0]:
        return ""

    lines = []
    for item in result[0]:
        try:
            text = item[1][0]
            if text:
                lines.append(text)
        except Exception:
            continue

    return "\n".join(lines)


def main():
    region_files = sorted(REGIONS_DIR.glob("*_regions.json"))
    if not region_files:
        print(f"Sem ficheiros de regiões em: {REGIONS_DIR} (corre 11_detect_regions_yolo.py)")
        return

    for region_file in region_files:
        data = json.loads(region_file.read_text(encoding="utf-8"))
        doc_name = region_file.name.replace("_regions.json", "")
        image_dir = IMAGES_DIR / doc_name
        crop_doc_dir = CROPS_DIR / doc_name
        crop_doc_dir.mkdir(parents=True, exist_ok=True)

        page_results = {}
        for page_name, regions in data.get("pages", {}).items():
            image_path = image_dir / page_name
            if not image_path.exists():
                continue

            page_results[page_name] = []
            with Image.open(image_path) as image:
                for idx, region in enumerate(regions, start=1):
                    bbox = region["bbox"]
                    crop = image.crop((bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]))
                    crop_name = f"{Path(page_name).stem}__region_{idx:02d}.png"
                    crop_path = crop_doc_dir / crop_name
                    crop.save(crop_path)

                    text = _ocr_image(crop_path)
                    page_results[page_name].append(
                        {
                            "region_index": idx,
                            "label": region.get("label"),
                            "confidence": region.get("confidence"),
                            "bbox": bbox,
                            "crop_path": str(crop_path),
                            "text": text,
                        }
                    )

        payload = {
            "source_file": data.get("source_file"),
            "extracted_at": datetime.now().isoformat(timespec="seconds"),
            "detector": data.get("detector", {}),
            "pages": page_results,
        }

        out_path = OCR_TEXT_DIR / f"{doc_name}_regions.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("saved:", out_path)


if __name__ == "__main__":
    main()
