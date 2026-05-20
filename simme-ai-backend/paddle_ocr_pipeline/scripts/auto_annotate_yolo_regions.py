import json
import re
from pathlib import Path

from PIL import Image


BASE = Path(__file__).resolve().parents[1]
RAW_PDFS_DIR = BASE / "data" / "raw_pdfs"
IMAGES_DIR = BASE / "data" / "images"
YOLO_DIR = BASE / "data" / "yolo" / "regions"
TRAIN_IMAGES = YOLO_DIR / "images" / "train"
VAL_IMAGES = YOLO_DIR / "images" / "val"
TRAIN_LABELS = YOLO_DIR / "labels" / "train"
VAL_LABELS = YOLO_DIR / "labels" / "val"

CLASS_MAP = {
    "metadata_block": 0,
    "customer_block": 1,
    "equipment_block": 2,
    "work_conditions_block": 3,
    "reference_block": 4,
    "results_table": 5,
}


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.upper()
    replacements = {
        "Ç": "C",
        "Ã": "A",
        "Á": "A",
        "Â": "A",
        "À": "A",
        "Õ": "O",
        "Ó": "O",
        "Ô": "O",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ú": "U",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def has_any_pattern(text: str, patterns):
    normalized = normalize_text(text)
    return any(normalize_text(pattern) in normalized for pattern in patterns)


def collect_lines_with_bounds(page):
    words = page.extract_words(use_text_flow=True, keep_blank_chars=False)
    if not words:
        return []

    lines = {}
    for word in words:
        key = round(word["top"], 1)
        lines.setdefault(key, []).append(word)

    output = []
    for _, line_words in sorted(lines.items(), key=lambda item: item[0]):
        line_words = sorted(line_words, key=lambda item: item["x0"])
        text = " ".join(word["text"] for word in line_words).strip()
        output.append(
            {
                "text": text,
                "normalized": normalize_text(text),
                "x0": min(word["x0"] for word in line_words),
                "x1": max(word["x1"] for word in line_words),
                "top": min(word["top"] for word in line_words),
                "bottom": max(word["bottom"] for word in line_words),
            }
        )
    return output


def find_line_index(lines, patterns):
    normalized_patterns = [normalize_text(pattern) for pattern in patterns]
    for idx, line in enumerate(lines):
        if any(pattern in line["normalized"] for pattern in normalized_patterns):
            return idx
    return None


def make_bbox(x0, top, x1, bottom, page_width, page_height, margin=12):
    x0 = max(0, x0 - margin)
    top = max(0, top - margin)
    x1 = min(page_width, x1 + margin)
    bottom = min(page_height, bottom + margin)
    if x1 <= x0 or bottom <= top:
        return None
    return (x0, top, x1, bottom)


def full_width_bbox(top, bottom, page_width, page_height, margin=12, side_ratio=0.04):
    x0 = page_width * side_ratio
    x1 = page_width * (1 - side_ratio)
    return make_bbox(x0, top, x1, bottom, page_width, page_height, margin=margin)


def lines_bbox(lines, start_idx, end_idx, page_width, page_height):
    selected = lines[start_idx:end_idx]
    if not selected:
        return None
    x0 = min(line["x0"] for line in selected)
    x1 = max(line["x1"] for line in selected)
    top = min(line["top"] for line in selected)
    bottom = max(line["bottom"] for line in selected)
    return make_bbox(x0, top, x1, bottom, page_width, page_height)


def section_bbox(lines, start_idx, end_idx, page_width, page_height):
    selected = lines[start_idx:end_idx]
    if not selected:
        return None
    top = min(line["top"] for line in selected)
    bottom = max(line["bottom"] for line in selected)
    return full_width_bbox(top, bottom, page_width, page_height, margin=18)


def classify_heading(lines, idx):
    text = lines[idx]["normalized"]
    window_text = " ".join(line["normalized"] for line in lines[idx : idx + 8])

    if has_any_pattern(text, ["CLIENTE", "CUSTOMER", "CLIENTE / CUSTOMER"]):
        return "customer_block"

    if has_any_pattern(
        text,
        [
            "EQUIPAMENTO CALIBRADO",
            "CALIBRATED EQUIPMENT",
            "EQUIPMENT",
            "PRINCIPAL EQUIPAMENTO UTILIZADO",
        ],
    ):
        return "equipment_block"

    if has_any_pattern(text, ["DESCRICAO", "DESCRIPTION", "TEST DESCRIPTION"]):
        if has_any_pattern(
            window_text,
            [
                "EQUIPAMENTO",
                "DESIGNACAO",
                "MARCA",
                "MODELO",
                "SERIE",
                "SERIAL",
                "INDICACAO",
                "RESOLUCAO",
                "INTERVALO DE MEDICAO",
            ],
        ):
            return "equipment_block"
        return "reference_block"

    if has_any_pattern(text, ["OPERACOES EFECTUADAS", "OPERACOES EFETUADAS", "OPERATIONS PERFORMED"]):
        if has_any_pattern(window_text, ["TEMPERATURA", "HUMIDADE", "HUMIDITY", "AMBIENTE", "AMBIENT"]):
            return "work_conditions_block"
        return "reference_block"

    if has_any_pattern(
        text,
        [
            "CONDICOES DO TRABALHO",
            "WORK CONDITIONS",
            "LOCAL / PLACE",
            "LOCAL",
            "PLACE",
        ],
    ):
        return "work_conditions_block"

    if has_any_pattern(
        text,
        [
            "CALIBRATION ACCORDING TO NORMATIVE",
            "CALIBRACAO SEGUNDO",
            "DOCUMENTOS NORMATIVOS",
            "NORMATIVE DOCUMENTS",
        ],
    ):
        return "reference_block"

    return None


def find_section_headings(lines):
    headings = []
    seen_labels = set()
    for idx, line in enumerate(lines):
        label = classify_heading(lines, idx)
        if label and label not in seen_labels:
            headings.append((label, idx))
            seen_labels.add(label)
    return sorted(headings, key=lambda item: item[1])


def page1_annotations(page):
    page_width = page.width
    page_height = page.height
    lines = collect_lines_with_bounds(page)
    annotations = []

    if not lines:
        return annotations

    headings = find_section_headings(lines)
    if not headings:
        return annotations

    first_heading_idx = headings[0][1]
    annotations.append(("metadata_block", section_bbox(lines, 0, first_heading_idx, page_width, page_height)))

    for position, (label_name, start_idx) in enumerate(headings):
        end_idx = headings[position + 1][1] if position + 1 < len(headings) else len(lines)
        bbox = section_bbox(lines, start_idx, end_idx, page_width, page_height)
        if bbox is not None:
            annotations.append((label_name, bbox))

    return [(label, bbox) for label, bbox in annotations if bbox is not None]


def is_table_like_line(line):
    text = line["normalized"]
    number_matches = re.findall(r"[-+]?\d+(?:[.,]\d+)?", text)
    if len(number_matches) >= 3:
        return True
    if has_any_pattern(
        text,
        [
            "STANDARD",
            "PADRAO",
            "EQUIPMENT AVERAGE",
            "ERROR",
            "ERRO",
            "UNCERTAINTY",
            "INCERTEZA",
            "READING",
            "LEITURA",
            "MM",
            "G",
            "%",
            "Q",
            "B",
            "A",
            "F 0",
        ],
    ):
        return True
    return False


def merge_bboxes(bboxes, page_width, page_height, gap=28):
    if not bboxes:
        return []

    sorted_boxes = sorted(bboxes, key=lambda item: (item[1], item[0]))
    merged = [list(sorted_boxes[0])]

    for x0, top, x1, bottom in sorted_boxes[1:]:
        current = merged[-1]
        overlaps_horizontally = not (x1 < current[0] - gap or x0 > current[2] + gap)
        close_vertically = top <= current[3] + gap
        if overlaps_horizontally and close_vertically:
            current[0] = min(current[0], x0)
            current[1] = min(current[1], top)
            current[2] = max(current[2], x1)
            current[3] = max(current[3], bottom)
        else:
            merged.append([x0, top, x1, bottom])

    return [make_bbox(x0, top, x1, bottom, page_width, page_height) for x0, top, x1, bottom in merged]


def results_annotations(page):
    page_width = page.width
    page_height = page.height
    annotations = []

    try:
        tables = page.find_tables(
            table_settings={
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "intersection_tolerance": 8,
                "snap_tolerance": 3,
                "join_tolerance": 3,
            }
        )
    except Exception:
        tables = []

    if not tables:
        try:
            tables = page.find_tables(
                table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "min_words_vertical": 2,
                    "min_words_horizontal": 1,
                    "snap_tolerance": 3,
                }
            )
        except Exception:
            tables = []

    table_boxes = []
    min_area_ratio = 0.01
    page_area = page_width * page_height

    for table in tables:
        bbox = table.bbox
        if not bbox:
            continue
        x0, top, x1, bottom = bbox
        normalized_bbox = make_bbox(x0, top, x1, bottom, page_width, page_height)
        if normalized_bbox is None:
            continue
        box_area = (normalized_bbox[2] - normalized_bbox[0]) * (normalized_bbox[3] - normalized_bbox[1])
        if page_area and (box_area / page_area) >= min_area_ratio:
            table_boxes.append(normalized_bbox)

    if table_boxes:
        for bbox in merge_bboxes(table_boxes, page_width, page_height):
            if bbox is not None:
                annotations.append(("results_table", bbox))
        return annotations

    lines = collect_lines_with_bounds(page)
    if not lines:
        return annotations

    start_idx = None
    end_idx = len(lines)
    for idx, line in enumerate(lines):
        if has_any_pattern(line["normalized"], ["RESULTS", "RESULTADOS"]):
            start_idx = idx
            break
        if is_table_like_line(line):
            start_idx = idx
            break

    if start_idx is None:
        return annotations

    for idx in range(start_idx + 1, len(lines)):
        text = lines[idx]["normalized"]
        if has_any_pattern(
            text,
            [
                "ENVIRONMENTAL CONDITIONS",
                "OBSERVATIONS",
                "OBSERVACOES",
                "OBSERVAÇÕES",
                "EQUIPAMENTO UTILIZADO",
                "QUIPAMENTO UTILIZADO",
                "TRACEABILITY",
                "RASTREABILIDADE",
            ],
        ):
            end_idx = idx
            break

    selected_indices = [idx for idx in range(start_idx, end_idx) if is_table_like_line(lines[idx])]
    if len(selected_indices) < 3:
        return annotations

    bbox = section_bbox(lines, selected_indices[0], selected_indices[-1] + 1, page_width, page_height)
    if bbox is not None:
        annotations.append(("results_table", bbox))

    return annotations


def to_yolo_line(class_id, bbox, image_width, image_height):
    x0, top, x1, bottom = bbox
    x_center = ((x0 + x1) / 2) / image_width
    y_center = ((top + bottom) / 2) / image_height
    width = (x1 - x0) / image_width
    height = (bottom - top) / image_height
    return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"


def build_pdf_index():
    index = {}
    for pdf_path in RAW_PDFS_DIR.glob("*.pdf"):
        index[pdf_path.stem] = pdf_path
    return index


def annotate_dataset_folder(images_dir: Path, labels_dir: Path):
    pdf_index = build_pdf_index()
    if not images_dir.exists():
        return

    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber é necessário para gerar anotações automáticas.") from exc

    for image_path in sorted(images_dir.glob("*.png")):
        stem = image_path.stem
        if "__page_" not in stem:
            continue

        doc_name, page_name = stem.split("__page_", 1)
        page_number = int(page_name)
        pdf_path = pdf_index.get(doc_name)
        if pdf_path is None:
            print("skip, pdf not found for", image_path.name)
            continue

        with Image.open(image_path) as image:
            image_width, image_height = image.size

        with pdfplumber.open(pdf_path) as pdf:
            if page_number - 1 >= len(pdf.pages):
                continue
            page = pdf.pages[page_number - 1]
            if page_number == 1:
                annotations = page1_annotations(page)
            else:
                annotations = results_annotations(page)

        label_lines = []
        for label_name, bbox in annotations:
            class_id = CLASS_MAP[label_name]
            label_lines.append(to_yolo_line(class_id, bbox, image_width, image_height))

        label_path = labels_dir / f"{image_path.stem}.txt"
        label_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.write_text("\n".join(label_lines) + ("\n" if label_lines else ""), encoding="utf-8")
        print("saved:", label_path)


def main():
    annotate_dataset_folder(TRAIN_IMAGES, TRAIN_LABELS)
    annotate_dataset_folder(VAL_IMAGES, VAL_LABELS)


if __name__ == "__main__":
    main()
