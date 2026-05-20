import os
import json
from datetime import datetime
from pathlib import Path

from PIL import Image


BASE = Path(__file__).resolve().parents[1]
ULTRALYTICS_CONFIG_DIR = BASE / "data" / ".ultralytics"
ULTRALYTICS_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(ULTRALYTICS_CONFIG_DIR))

IMAGES_DIR = BASE / "data" / "images"
REGIONS_DIR = BASE / "data" / "regions"
REGIONS_DIR.mkdir(parents=True, exist_ok=True)

YOLO_WEIGHTS_CANDIDATES = [
    BASE / "data" / "models" / "yolo_regions.pt",
    BASE / "data" / "models" / "best.pt",
]

CANONICAL_CLASS_NAMES = {
    0: "metadata_block",
    1: "customer_block",
    2: "equipment_block",
    3: "equipment_state_block",
    4: "work_conditions_block",
    5: "reference_block",
    6: "results_table",
    7: "standard_equipment_block",
    8: "calibration_date_block",
}

MIN_CONFIDENCE = 0.05
OVERLAP_THRESHOLD = 0.85


def _resolve_weights_path():
    for candidate in YOLO_WEIGHTS_CANDIDATES:
        if candidate.exists():
            return candidate
    return YOLO_WEIGHTS_CANDIDATES[0]


def _load_yolo_model():
    weights_path = _resolve_weights_path()
    if not weights_path.exists():
        return None, "weights_not_found"

    try:
        from ultralytics import YOLO
    except Exception:
        return None, "ultralytics_not_available"

    try:
        return YOLO(str(weights_path)), "ok"
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


def _box_area(region: dict) -> int:
    bbox = region["bbox"]
    width = max(0, bbox["x2"] - bbox["x1"])
    height = max(0, bbox["y2"] - bbox["y1"])
    return width * height


def _overlap_ratio(region_a: dict, region_b: dict) -> float:
    a = region_a["bbox"]
    b = region_b["bbox"]

    x1 = max(a["x1"], b["x1"])
    y1 = max(a["y1"], b["y1"])
    x2 = min(a["x2"], b["x2"])
    y2 = min(a["y2"], b["y2"])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0

    min_area = min(_box_area(region_a), _box_area(region_b))
    if min_area == 0:
        return 0.0

    return inter_area / min_area


def _dedupe_regions(regions: list[dict]) -> list[dict]:
    filtered = []

    for region in sorted(
        regions,
        key=lambda item: (
            -(item.get("confidence") or 0.0),
            item["bbox"]["y1"],
            item["bbox"]["x1"],
        ),
    ):
        duplicate = False
        for kept in filtered:
            if kept["label"] != region["label"]:
                continue
            if _overlap_ratio(kept, region) >= OVERLAP_THRESHOLD:
                duplicate = True
                break

        if not duplicate:
            filtered.append(region)

    return sorted(filtered, key=lambda item: (item["bbox"]["y1"], item["bbox"]["x1"]))


def _predict_regions(model, image_path: Path) -> list[dict]:
    if model is None:
        return _fallback_regions(image_path)

    try:
        results = model.predict(
            source=str(image_path),
            # Early training runs produce low-confidence detections, so keep
            # the threshold permissive and let downstream parsing decide value.
            conf=0.01,
            verbose=False,
        )
    except Exception:
        return _fallback_regions(image_path)

    regions = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue

        for box in boxes:
            xyxy = box.xyxy[0].tolist()
            cls = int(box.cls[0].item()) if box.cls is not None else -1
            conf = float(box.conf[0].item()) if box.conf is not None else None
            if conf is not None and conf < MIN_CONFIDENCE:
                continue
            regions.append(
                {
                    "label": CANONICAL_CLASS_NAMES.get(cls, f"class_{cls}"),
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

    regions = _dedupe_regions(regions)
    return regions or _fallback_regions(image_path)


def main():
    model, model_status = _load_yolo_model()
    weights_path = _resolve_weights_path()
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
                "weights_path": str(weights_path),
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
