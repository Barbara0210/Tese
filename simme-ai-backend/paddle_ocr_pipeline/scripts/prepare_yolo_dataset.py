from pathlib import Path
import random
import shutil


BASE = Path(__file__).resolve().parents[1]
IMAGES_DIR = BASE / "data" / "images"
YOLO_DIR = BASE / "data" / "yolo" / "regions"

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


def copy_pages_to_dataset(train_ratio: float = 0.8, seed: int = 42):
    ensure_dirs()
    clear_dir(TRAIN_IMAGES)
    clear_dir(VAL_IMAGES)

    images = []
    for doc_dir in sorted(IMAGES_DIR.iterdir()):
        if not doc_dir.is_dir():
            continue
        for image_path in sorted(doc_dir.glob("page_*.png")):
            images.append(image_path)

    if not images:
        print(f"Sem imagens em: {IMAGES_DIR}")
        return

    rng = random.Random(seed)
    rng.shuffle(images)

    split_index = int(len(images) * train_ratio)
    train_images = images[:split_index]
    val_images = images[split_index:]

    for image_path in train_images:
        target_name = f"{image_path.parent.name}__{image_path.name}"
        shutil.copy2(image_path, TRAIN_IMAGES / target_name)

    for image_path in val_images:
        target_name = f"{image_path.parent.name}__{image_path.name}"
        shutil.copy2(image_path, VAL_IMAGES / target_name)

    print("train images:", len(train_images))
    print("val images:", len(val_images))
    print("dataset folder:", YOLO_DIR)


if __name__ == "__main__":
    copy_pages_to_dataset()
