import json
from pathlib import Path
import random
import shutil


BASE = Path(__file__).resolve().parents[1]
IMAGES_DIR = BASE / "data" / "images"
YOLO_DIR = BASE / "data" / "yolo" / "regions"
CURATED_PAGES_PATH = YOLO_DIR / "curated_pages.json"

TRAIN_IMAGES = YOLO_DIR / "images" / "train"
VAL_IMAGES = YOLO_DIR / "images" / "val"
TRAIN_LABELS = YOLO_DIR / "labels" / "train"
VAL_LABELS = YOLO_DIR / "labels" / "val"


def ensure_dirs():
    for folder in [TRAIN_IMAGES, VAL_IMAGES, TRAIN_LABELS, VAL_LABELS]:
        folder.mkdir(parents=True, exist_ok=True)


def clear_dir(folder: Path):
    for item in folder.iterdir():
        if item.is_file():
            item.unlink()


def load_curated_pages():
    if not CURATED_PAGES_PATH.exists():
        return {}, set()

    payload = json.loads(CURATED_PAGES_PATH.read_text(encoding="utf-8"))
    keep_pages = payload.get("keep_pages", {})
    val_pages = set(payload.get("val_pages", []))
    return keep_pages, val_pages


def extract_page_number(image_path: Path):
    stem = image_path.stem
    if not stem.startswith("page_"):
        return None
    try:
        return int(stem.split("_", 1)[1])
    except (IndexError, ValueError):
        return None


def copy_pages_to_dataset(train_ratio: float = 0.8, seed: int = 42):
    ensure_dirs()
    clear_dir(TRAIN_IMAGES)
    clear_dir(VAL_IMAGES)
    clear_dir(TRAIN_LABELS)
    clear_dir(VAL_LABELS)

    split_train_dir = IMAGES_DIR / "train"
    split_val_dir = IMAGES_DIR / "val"
    if split_train_dir.exists() and split_val_dir.exists():
        train_images = []
        for doc_dir in sorted(split_train_dir.iterdir()):
            if not doc_dir.is_dir():
                continue
            train_images.extend(sorted(doc_dir.glob("page_*.png")))

        val_images = []
        for doc_dir in sorted(split_val_dir.iterdir()):
            if not doc_dir.is_dir():
                continue
            val_images.extend(sorted(doc_dir.glob("page_*.png")))

        if not train_images and not val_images:
            print(f"Sem imagens em: {IMAGES_DIR}")
            return

        for image_path in train_images:
            target_name = f"{image_path.parent.name}__{image_path.name}"
            shutil.copy2(image_path, TRAIN_IMAGES / target_name)

        for image_path in val_images:
            target_name = f"{image_path.parent.name}__{image_path.name}"
            shutil.copy2(image_path, VAL_IMAGES / target_name)

        print("train images:", len(train_images))
        print("val images:", len(val_images))
        print("split source:", IMAGES_DIR)
        print("dataset folder:", YOLO_DIR)
        return

    curated_keep_pages, curated_val_pages = load_curated_pages()

    images = []
    for doc_dir in sorted(IMAGES_DIR.iterdir()):
        if not doc_dir.is_dir():
            continue
        for image_path in sorted(doc_dir.glob("page_*.png")):
            allowed_pages = curated_keep_pages.get(doc_dir.name)
            page_number = extract_page_number(image_path)
            if allowed_pages is not None and page_number not in allowed_pages:
                continue
            images.append(image_path)

    if not images:
        print(f"Sem imagens em: {IMAGES_DIR}")
        return

    selected_names = {f"{image_path.parent.name}__{image_path.name}" for image_path in images}
    val_images = [
        image_path
        for image_path in images
        if f"{image_path.parent.name}__{image_path.name}" in curated_val_pages
    ]
    train_images = [image_path for image_path in images if image_path not in val_images]

    if not val_images:
        rng = random.Random(seed)
        rng.shuffle(images)
        split_index = int(len(images) * train_ratio)
        train_images = images[:split_index]
        val_images = images[split_index:]
    else:
        missing_val_pages = curated_val_pages - selected_names
        if missing_val_pages:
            print("warning, val pages not found:")
            for item in sorted(missing_val_pages):
                print(" -", item)

    for image_path in train_images:
        target_name = f"{image_path.parent.name}__{image_path.name}"
        shutil.copy2(image_path, TRAIN_IMAGES / target_name)

    for image_path in val_images:
        target_name = f"{image_path.parent.name}__{image_path.name}"
        shutil.copy2(image_path, VAL_IMAGES / target_name)

    print("train images:", len(train_images))
    print("val images:", len(val_images))
    print("curated pages file:", CURATED_PAGES_PATH)
    print("dataset folder:", YOLO_DIR)


if __name__ == "__main__":
    copy_pages_to_dataset()
