import json
from datetime import datetime
from pathlib import Path

from PIL import Image


BASE = Path(__file__).resolve().parents[1]

IMAGES_DIR = BASE / "data" / "images"
REGIONS_DIR = BASE / "data" / "regions"
REGIONS_DIR.mkdir(parents=True, exist_ok=True)

YOLO_WEIGHTS = BASE / "data" / "models" / "yolo_regions.pt"


def _load_yolo_model():
    if not YOLO_WEIGHTS.exists():
        return None, "weights_not_found"

    try:
        from ultralytics import YOLO
    except Exception:
        return None, "ultralytics_not_available"

    try:
        return YOLO(str(YOLO_WEIGHTS)), "ok"
    except Exception as exc:
        return None, f"model_load_error:{type(exc).__name__}"


def _fallback_regions(image_path: Path) -> list[dict]:
    with Image.open(image_path) as image:
        width, height = image.size

    return [
        {
            "label": "full_page",
            "confidence": None,
            "bbox": {
                "x1": 0,
                "y1": 0,
                "x2": width,
                "y2": height,
            },
            "source": "fallback_full_page",
        }
    ]


def _predict_regions(model, image_path: Path) -> list[dict]:
    if model is None:
        return _fallback_regions(image_path)

    try:
        results = model.predict(
            source=str(image_path),
            conf=0.20,
            verbose=False,
        )
    except Exception:
        return _fallback_regions(image_path)

    regions = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        names = getattr(result, "names", {})
        if boxes is None:
            continue

        for box in boxes:
            xyxy = box.xyxy[0].tolist()
            cls = int(box.cls[0].item()) if box.cls is not None else -1
            conf = float(box.conf[0].item()) if box.conf is not None else None
            regions.append(
                {
                    "label": names.get(cls, f"class_{cls}"),
                    "confidence": conf,
                    "bbox": {
                        "x1": int(xyxy[0]),
                        "y1": int(xyxy[1]),
                        "x2": int(xyxy[2]),
                        "y2": int(xyxy[3]),
                    },
                    "source": "yolo",
                }
            )

    return regions or _fallback_regions(image_path)


def main():
    model, model_status = _load_yolo_model()
    docs = [path for path in IMAGES_DIR.iterdir() if path.is_dir()]
    if not docs:
        print(f"Sem imagens em: {IMAGES_DIR} (corre 01_pdf_to_images.py)")
        return

    for doc_dir in sorted(docs):
        page_regions = {}

        for image_path in sorted(doc_dir.glob("page_*.png")):
            page_regions[image_path.name] = _predict_regions(model, image_path)

        payload = {
            "source_file": f"{doc_dir.name}.pdf",
            "extracted_at": datetime.now().isoformat(timespec="seconds"),
            "detector": {
                "type": "yolo",
                "weights_path": str(YOLO_WEIGHTS),
                "status": model_status,
            },
            "pages": page_regions,
        }

        out_path = REGIONS_DIR / f"{doc_dir.name}_regions.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("saved:", out_path)


if __name__ == "__main__":
    main()
