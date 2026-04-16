from pathlib import Path


COLAB_SCRIPT = r"""
!pip install -q ultralytics

from google.colab import drive
drive.mount('/content/drive')

# Ajusta este caminho para a pasta onde colocaste o dataset no Drive
DATASET_DIR = "/content/drive/MyDrive/yolo_regions"

from ultralytics import YOLO

model = YOLO("yolo11n.pt")

results = model.train(
    data=f"{DATASET_DIR}/dataset.yaml",
    epochs=100,
    imgsz=1280,
    batch=8,
    project="/content/yolo_runs",
    name="regions_yolo11n",
)

print("Best weights:", results.save_dir / "weights" / "best.pt")
"""


def main():
    target = Path(__file__).with_suffix(".txt")
    target.write_text(COLAB_SCRIPT.strip() + "\n", encoding="utf-8")
    print("saved:", target)


if __name__ == "__main__":
    main()
