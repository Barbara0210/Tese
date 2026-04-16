import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]

RAW_PDFS_DIR = BASE / "data" / "raw_pdfs"
PARSED_DIR = BASE / "data" / "parsed"
TABLES_DIR = BASE / "data" / "tables"

PARSED_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.upper()
    value = re.sub(r"\s+", " ", value).strip()
    return value


def clean_cell(value) -> str | None:
    if value is None:
        return None
    value = str(value).replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{2,}", "\n", value)
    value = value.strip()
    return value or None


def clean_value(value: str | None) -> str | None:
    value = clean_cell(value)
    if not value:
        return None
    if value == "---":
        return None
    return value


def extract_numbers(value: str | None) -> list[float]:
    if not value:
        return []
    matches = re.findall(r"[-+]?\d+(?:[.,]\d+)?", value)
    numbers = []
    for match in matches:
        try:
            numbers.append(float(match.replace(",", ".")))
        except ValueError:
            continue
    return numbers


def first_number_text(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
    return match.group(0) if match else None


def split_keyword_value(text: str | None, keyword: str) -> tuple[str | None, str | None]:
    cleaned = clean_value(text)
    if not cleaned:
        return None, None

    normalized = normalize_text(cleaned)
    keyword_normalized = normalize_text(keyword)
    position = normalized.find(keyword_normalized)

    if position == -1:
        return cleaned, None

    left = cleaned[:position].strip(" :-")
    right = cleaned[position:].strip(" :-")
    return clean_value(left), clean_value(right.replace(keyword, "", 1).strip(" :-"))


def append_multiline_value(current: str | None, extra: str | None) -> str | None:
    current = clean_value(current)
    extra = clean_value(extra)
    if not current:
        return extra
    if not extra:
        return current
    return f"{current} {extra}".strip()


def detect_instrument_type(full_text: str) -> str | None:
    normalized = normalize_text(full_text)

    if "PAQUIMETRO" in normalized:
        return "caliper"
    if "MANOMETRO" in normalized:
        return "pressure_gauge"
    return None


def is_probably_table(rows: list[list[str | None]]) -> bool:
    non_empty_rows = 0
    numeric_cells = 0

    for row in rows:
        row_values = [clean_cell(cell) for cell in row if clean_cell(cell)]
        if not row_values:
            continue
        non_empty_rows += 1
        numeric_cells += sum(1 for cell in row_values if extract_numbers(cell))

    return non_empty_rows >= 2 and numeric_cells >= 3


def extract_pdf_tables(pdf_path: Path):
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "A dependência 'pdfplumber' não está instalada. "
            "Instala as requirements do paddle_ocr_pipeline antes de usar o método PdfTable."
        ) from exc

    raw_tables = []
    page_texts = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_texts.append(page.extract_text() or "")
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "intersection_tolerance": 8,
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                }
            )

            if not tables:
                tables = page.extract_tables(
                    table_settings={
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                        "min_words_vertical": 2,
                        "min_words_horizontal": 1,
                        "snap_tolerance": 3,
                    }
                )

            for table_index, table in enumerate(tables, start=1):
                cleaned_rows = [
                    [clean_cell(cell) for cell in row]
                    for row in (table or [])
                ]
                cleaned_rows = [
                    row for row in cleaned_rows
                    if any(cell not in (None, "") for cell in row)
                ]

                if not cleaned_rows or not is_probably_table(cleaned_rows):
                    continue

                raw_tables.append(
                    {
                        "page": page_number,
                        "table_index": table_index,
                        "rows": cleaned_rows,
                        "normalized_text": normalize_text(
                            " ".join(cell or "" for row in cleaned_rows for cell in row)
                        ),
                    }
                )

    return raw_tables, "\n".join(page_texts)


def row_to_numbers(row: list[str | None]) -> list[float]:
    values = []
    for cell in row:
        values.extend(extract_numbers(cell))
    return values


def row_to_text(row: list[str | None]) -> str:
    return " ".join(cell for cell in row if cell).strip()


def extract_header_fields(rows: list[list[str | None]], full_text: str) -> dict:
    header = {
        "issue_date": None,
        "certificate_number": None,
        "lab_name": None,
        "lab_unit": None,
    }

    for row in rows:
        label = normalize_text(row[0] if len(row) > 0 else None)
        row_text = row_to_text(row)

        if "DATA DE EMISSAO" in label or "DATE OF ISSUE" in label:
            date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", row_text)
            cert_match = re.search(r"([A-Z]{2,}\d{8,}/\d{1,3})", normalize_text(row_text))
            if date_match:
                header["issue_date"] = date_match.group(0)
            if cert_match:
                header["certificate_number"] = cert_match.group(1)

    normalized_full_text = normalize_text(full_text)
    if "CATIM" in normalized_full_text:
        header["lab_name"] = "CATIM"

    if "LABORATORIO DE METROLOGIA - DIMENSIONAL" in normalized_full_text:
        header["lab_unit"] = "Laboratório de Metrologia - Dimensional"
    elif "LABORATORIO DE METROLOGIA - FORCA" in normalized_full_text:
        header["lab_unit"] = "Laboratório de Metrologia - Força"
    elif "LABORATORIO DE METROLOGIA - MASSA" in normalized_full_text:
        header["lab_unit"] = "Laboratório de Metrologia - Massa"

    return header


def extract_section_fields(rows: list[list[str | None]]) -> dict:
    customer = {"name": None, "address": None}
    equipment = {
        "designation": None,
        "brand": None,
        "model": None,
        "serial_number": None,
        "range": None,
        "resolution": None,
        "estimated_resolution": None,
        "indication": None,
        "internal_ref": None,
        "class": None,
        "state": None,
    }
    work_conditions = {
        "location": None,
        "temperature": None,
        "humidity": None,
        "accreditation_annex": None,
    }
    reference = {"standard_or_procedure": None}

    last_label = None
    current_section = None
    collect_reference_next = False

    for row in rows:
        first = clean_value(row[0] if len(row) > 0 else None)
        second = clean_value(row[1] if len(row) > 1 else None)
        third = clean_value(row[2] if len(row) > 2 else None)
        label = normalize_text(first)
        full_row_text = normalize_text(row_to_text(row))

        if full_row_text == "CLIENTE" or full_row_text == "CUSTOMER":
            current_section = "customer"
            last_label = None
            continue

        if full_row_text == "EQUIPAMENTO CALIBRADO" or full_row_text == "EQUIPMENT":
            current_section = "equipment"
            last_label = None
            continue

        if full_row_text == "CONDICOES DO TRABALHO RE ALIZADO" or full_row_text == "WORK CONDITIONS":
            current_section = "work_conditions"
            last_label = None
            continue

        if full_row_text == "DESCRICAO" or full_row_text == "DESCRIPTION":
            current_section = "description"
            last_label = None
            continue

        if "RASTREABILIDADE" in full_row_text or "TRACEABILITY" in full_row_text:
            current_section = "traceability"
            last_label = None
            continue

        if "INCERTEZA" in full_row_text or "UNCERTAINTY" in full_row_text:
            current_section = "uncertainty"
            last_label = None
            continue

        if "DATA CALIBRACAO" in full_row_text or "CALIBRATION DATE" in full_row_text:
            current_section = "calibration_date"
            last_label = None
            continue

        if any(
            token in full_row_text
            for token in [
                "EQUIPAMENTO CALIBRADO",
                "CONDICOES DO TRABALHO",
                "DESCRICAO",
                "RASTREABILIDADE",
                "INCERTEZA",
                "DATA CALIBRACAO",
            ]
        ):
            last_label = None

        if label in {"NOME", "NAME"}:
            customer["name"] = second
            last_label = "address" if customer["address"] else "name"
            continue

        if label in {"MORADA", "ADRESS", "ADDRESS"}:
            customer["address"] = second
            last_label = "address"
            continue

        if not first and second and last_label == "address" and current_section == "customer":
            customer["address"] = append_multiline_value(customer["address"], second)
            continue

        if (
            "DESIGNACAO" in label
            or ("DESCRIPTION" in label and current_section == "equipment")
            or "DESIGNACAO" in normalize_text(row_to_text(row))
        ):
            equipment["designation"] = second
            continue

        if label in {"MARCA", "MANUFACTURE"}:
            brand, maybe_range = split_keyword_value(second, "Alcance de medição")
            if maybe_range is None:
                brand, maybe_range = split_keyword_value(second, "Alcance de medicao")
            if maybe_range is None:
                brand, maybe_range = split_keyword_value(second, "Range")
            equipment["brand"] = brand
            equipment["range"] = third or maybe_range or clean_value(row[3] if len(row) > 3 else None)
            continue

        if label == "MODELO":
            model, maybe_resolution = split_keyword_value(second, "Resolução")
            if maybe_resolution is None:
                model, maybe_resolution = split_keyword_value(second, "Resolucao")
            equipment["model"] = model
            equipment["resolution"] = third or maybe_resolution
            continue

        if label == "MODEL":
            equipment["model"] = second
            if len(row) > 3 and clean_value(row[3]):
                equipment["resolution"] = clean_value(row[3])
            continue

        if "SERIE" in label or label == "SERIAL NUMBER":
            serial_number, maybe_indication = split_keyword_value(second, "Indicação")
            if maybe_indication is None:
                serial_number, maybe_indication = split_keyword_value(second, "Indicacao")
            if maybe_indication is None:
                serial_number, maybe_indication = split_keyword_value(second, "Indication")
            equipment["serial_number"] = serial_number
            equipment["indication"] = third or maybe_indication or clean_value(row[3] if len(row) > 3 else None)
            continue

        if (
            "REF. INTERNA" in label
            or "REF INTERNA" in label
            or "REF INTERNA(1)" in label
            or "EQUIPMENT REFERENCE" in label
        ):
            equipment["internal_ref"] = second
            continue

        if "ESTADO DO EQUIPAMENTO" in label or "VISUAL INSPECTION" in label:
            equipment["state"] = second
            continue

        if label in {"LOCAL", "LOCATION"}:
            location, maybe_temperature = split_keyword_value(second, "Temperatura")
            equipment_value = third or maybe_temperature
            if maybe_temperature is None:
                location, maybe_temperature = split_keyword_value(second, "Temperature")
                equipment_value = clean_value(row[3] if len(row) > 3 else None) or maybe_temperature
            work_conditions["location"] = location
            work_conditions["temperature"] = equipment_value
            continue

        if "ANEXO TECNICO" in label:
            annex, maybe_humidity = split_keyword_value(second, "Humidade")
            work_conditions["accreditation_annex"] = annex
            work_conditions["humidity"] = (
                third
                or clean_value(row[3] if len(row) > 3 else None)
                or maybe_humidity
            )
            continue

        if "ACCREDITATION ANNEX" in label:
            annex, maybe_humidity = split_keyword_value(second, "Humidity")
            work_conditions["accreditation_annex"] = annex
            work_conditions["humidity"] = (
                third
                or clean_value(row[3] if len(row) > 3 else None)
                or maybe_humidity
            )
            continue

        if any(token in full_row_text for token in ["ISO ", "LMD P", "LMF P", "EN ISO"]):
            reference["standard_or_procedure"] = append_multiline_value(
                reference["standard_or_procedure"],
                row_to_text(row),
            )
            collect_reference_next = False
            continue

        if (
            "CALIBRATION ACCORDING TO NORMATIVE" in full_row_text
            or "CALIBRACAO SEGUNDO OS DOCUMENTO" in full_row_text
        ):
            collect_reference_next = True
            continue

        if collect_reference_next and not first and second:
            reference["standard_or_procedure"] = append_multiline_value(
                reference["standard_or_procedure"],
                second,
            )
            continue

    return {
        "customer": customer,
        "equipment": equipment,
        "work_conditions": work_conditions,
        "reference": reference,
    }


def extract_parsed_payload(source_file: str, raw_tables: list[dict], full_text: str) -> dict:
    rows = []
    for table in raw_tables:
        if table["page"] == 1:
            rows.extend(table["rows"])

    header = extract_header_fields(rows, full_text)
    sections = extract_section_fields(rows)

    return {
        "source_file": source_file,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "header": header,
        "customer": sections["customer"],
        "equipment": sections["equipment"],
        "work_conditions": sections["work_conditions"],
        "reference": sections["reference"],
        "raw_blocks": {
            "method": "pdf_table",
            "page_1_table_rows": rows,
        },
    }


def parse_caliper_tables(raw_tables: list[dict]) -> dict:
    parsed = {
        "E_contact_partial": [],
        "S_scale_change": [],
        "L_line_contact": [],
    }

    current_feature = None

    for table in raw_tables:
        normalized_text = table["normalized_text"]

        if "CONTACTO PARCIAL" in normalized_text:
            for row in table["rows"]:
                numbers = row_to_numbers(row)
                if len(numbers) < 8:
                    continue
                parsed["E_contact_partial"].append(
                    {
                        "standard_value_mm": numbers[0],
                        "zone_1_mm": numbers[1],
                        "zone_2_mm": numbers[2],
                        "zone_3_mm": numbers[3],
                        "error_E_mm": numbers[4],
                        "k": numbers[5],
                        "vef": numbers[6],
                        "U_mm": numbers[7],
                    }
                )

        elif "TROCA DE ESCALA" in normalized_text:
            for row in table["rows"]:
                row_text = normalize_text(row_to_text(row))
                if any(token in row_text for token in ["INTERIORES", "HASTE", "DEGRAU", "FACA"]):
                    current_feature = row_to_text(row)
                    continue

                numbers = row_to_numbers(row)
                if len(numbers) < 6:
                    continue

                parsed["S_scale_change"].append(
                    {
                        "feature": current_feature,
                        "standard_value_mm": numbers[0],
                        "reading_mm": numbers[1],
                        "error_S_mm": numbers[2],
                        "k": numbers[3],
                        "vef": numbers[4],
                        "U_mm": numbers[5],
                    }
                )

        elif "CONTACTO EM LINHA" in normalized_text:
            for row in table["rows"]:
                row_text = normalize_text(row_to_text(row))
                if "MAXILAS DE EXTERIORES" in row_text:
                    current_feature = row_to_text(row)
                    continue

                numbers = row_to_numbers(row)
                if len(numbers) < 7:
                    continue

                parsed["L_line_contact"].append(
                    {
                        "feature": current_feature,
                        "standard_value_mm": numbers[0],
                        "max_value_mm": numbers[1],
                        "min_value_mm": numbers[2],
                        "error_L_mm": numbers[3],
                        "k": numbers[4],
                        "vef": numbers[5],
                        "U_mm": numbers[6],
                    }
                )

    if not any(parsed.values()):
        compact_rows = []
        for table in raw_tables:
            for row in table["rows"]:
                split_columns = []
                for cell in row:
                    cleaned = clean_value(cell)
                    if not cleaned:
                        continue
                    parts = [part.strip() for part in cleaned.split("\n") if part.strip()]
                    split_columns.append(parts)

                if len(split_columns) == 3 and all(len(parts) >= 1 for parts in split_columns):
                    row_count = min(len(parts) for parts in split_columns)
                    for idx in range(row_count):
                        compact_rows.append(
                            {
                                "standard_value_mm": extract_numbers(split_columns[0][idx])[0]
                                if extract_numbers(split_columns[0][idx]) else None,
                                "reading_mm": extract_numbers(split_columns[1][idx])[0]
                                if extract_numbers(split_columns[1][idx]) else None,
                                "error_mm": extract_numbers(split_columns[2][idx])[0]
                                if extract_numbers(split_columns[2][idx]) else None,
                            }
                        )

        compact_rows = [
            row for row in compact_rows
            if row["standard_value_mm"] is not None
            and row["reading_mm"] is not None
            and row["error_mm"] is not None
        ]

        if compact_rows:
            parsed["E_contact_partial"] = compact_rows

    return parsed


def parse_pressure_tables(raw_tables: list[dict]) -> dict:
    parsed = {
        "pressure_error_table": [],
        "max_hysteresis": None,
        "environmental_conditions": [],
    }

    for table in raw_tables:
        normalized_text = table["normalized_text"]

        if "ERRO" in normalized_text and "EQUIPAMENTO" in normalized_text:
            for row in table["rows"]:
                numbers = row_to_numbers(row)
                if len(numbers) < 6:
                    continue

                parsed["pressure_error_table"].append(
                    {
                        "equipment_bar": numbers[0],
                        "error_bar": numbers[1],
                        "k": numbers[2],
                        "vef": numbers[3],
                        "U_bar": numbers[4],
                        "error_percent_FE": numbers[5],
                    }
                )

        elif "HISTERESE" in normalized_text:
            row_text = row_to_text(table["rows"][0]) if table["rows"] else ""
            numbers = extract_numbers(row_text)
            if numbers and parsed["max_hysteresis"] is None:
                parsed["max_hysteresis"] = {
                    "max_hysteresis_bar": numbers[0],
                    "raw_text": row_text,
                }

        elif any(token in normalized_text for token in ["TEMPERATURA", "HUMIDADE", "PRESSAO ATMOSFERICA"]):
            for row in table["rows"]:
                numbers = row_to_numbers(row)
                if len(numbers) < 4:
                    continue

                parsed["environmental_conditions"].append(
                    {
                        "temperature_C": numbers[0],
                        "humidity_percent_hr": numbers[1],
                        "atmospheric_pressure_bar": numbers[2],
                        "air_density": numbers[3],
                    }
                )

    return parsed


def parse_generic_tables(raw_tables: list[dict]) -> dict:
    generic_tables = {}
    counter = 1

    for table in raw_tables:
        if table["page"] == 1:
            continue

        rows = table["rows"]
        if not rows:
            continue

        parsed_rows = []
        for row in rows:
            cleaned = [clean_value(cell) for cell in row]
            if not any(cleaned):
                continue

            parsed_row = {}
            for idx, cell in enumerate(cleaned, start=1):
                parsed_row[f"col_{idx}"] = cell

            parsed_rows.append(parsed_row)

        if parsed_rows:
            generic_tables[f"generic_table_{counter}"] = parsed_rows
            counter += 1

    return generic_tables


def build_tables_payload(source_file: str, instrument_type: str | None, raw_tables: list[dict]) -> dict:
    if instrument_type == "caliper":
        named_tables = parse_caliper_tables(raw_tables)
    elif instrument_type == "pressure_gauge":
        named_tables = parse_pressure_tables(raw_tables)
    else:
        named_tables = parse_generic_tables(raw_tables)

    serializable_raw_tables = [
        {
            "page": table["page"],
            "table_index": table["table_index"],
            "rows": table["rows"],
        }
        for table in raw_tables
    ]

    return {
        "source_file": source_file,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "instrument_type": instrument_type,
        "tables": named_tables,
        "raw_pdf_tables": serializable_raw_tables,
    }


def main():
    pdf_files = sorted(RAW_PDFS_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"Sem ficheiros PDF em: {RAW_PDFS_DIR}")
        return

    for pdf_path in pdf_files:
        raw_tables, full_text = extract_pdf_tables(pdf_path)
        source_file = f"{pdf_path.stem}.txt"
        instrument_type = detect_instrument_type(full_text)

        parsed_payload = extract_parsed_payload(source_file, raw_tables, full_text)
        tables_payload = build_tables_payload(source_file, instrument_type, raw_tables)

        parsed_out = PARSED_DIR / f"{pdf_path.stem}.json"
        tables_out = TABLES_DIR / f"{pdf_path.stem}_tables.json"

        parsed_out.write_text(
            json.dumps(parsed_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tables_out.write_text(
            json.dumps(tables_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print("saved:", parsed_out)
        print("saved:", tables_out)


if __name__ == "__main__":
    main()
