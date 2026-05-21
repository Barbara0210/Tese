import json
import re
from pathlib import Path
from datetime import datetime
from pt_text import repair_nested_text, repair_portuguese_text

BASE = Path(__file__).resolve().parents[1]

IN_DIR = BASE / "data" / "sections"
OUT_DIR = BASE / "data" / "tables"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------
# Helpers
# -------------------------
def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_spaces(s: str | None) -> str | None:
    if not s:
        return None
    s = repair_portuguese_text(re.sub(r"[ \t]+", " ", s).strip())
    return s or None


def normalize_display_text(s: str | None) -> str | None:
    if not s:
        return None
    return repair_portuguese_text(s)

    replacements = {
        "Diämetro": "Diametro",
        "Diāmetro": "Diametro",
        "Diametro": "Diametro",
        "Humidade": "Humidade",
        "Padrao": "Padrao",
        "Calibracäo": "Calibracao",
        "Designagäo": "Designagao",
        "Instalacöes": "Instalacoes",
        "InvestigaciÃ³n": "Investigacion",
        "CÃ¤diz": "Cadiz",
    }

    out = s
    for old, new in replacements.items():
        out = out.replace(old, new)

    return out


def normalize(s: str | None) -> str:
    if not s:
        return ""
    s = s.upper()
    repl = {
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
        "Ö": "O",
        "Ä": "A",
        "Ü": "U",
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def to_float(x: str | None):
    if x is None:
        return None
    try:
        return float(x.replace(",", "."))
    except Exception:
        return None


def extract_numbers(line: str) -> list[str]:
    compact = re.sub(r"(?<=\d)\s+(?=\d{3}(?:[.,]\d+)?)", "", line)
    return re.findall(r"[-+]?\d+(?:[.,]\d+)?", compact)


def is_footer_noise(line: str) -> bool:
    n = normalize(line)
    bad_prefixes = [
        "RUA DOS PLATANOS",
        "RUA CIDADE DO PORTO",
        "ESTRADA DO PACO DO LUMIAR",
        "4100-414 PORTO",
        "4705-086 BRAGA",
        "1649-038 LISBOA",
        "OS RESULTADOS APRESENTADOS REFER",
        "ESTE DOCUMENTO NAO PODE SER REPRODUZIDO",
        "AUTORIZACAO POR ESCRITO DO CATIM",
        "A AUTORIZAGAO POR ESCRITO DO CATIM",
        "S ITENS CALIBRADOS OU ENSAIADOS",
        ": ITENS CALIBRADOS OU ENSAIADOS",
    ]
    return any(n.startswith(p) for p in bad_prefixes)


def clean_result_lines(text: str) -> list[str]:
    out = []
    for ln in split_lines(text):
        if is_footer_noise(ln):
            continue
        out.append(ln)
    return out


def collect_region_block_texts(section_json: dict, label: str) -> list[str]:
    page_region_blocks = section_json.get("page_region_blocks", {})
    texts = []

    for page_name in sorted(page_region_blocks.keys()):
        for block in page_region_blocks.get(page_name, []):
            if (block.get("label") or "") != label:
                continue
            text = (block.get("text") or "").strip()
            if text:
                texts.append(text)

    return texts


def collect_all_results_lines(section_json: dict) -> list[str]:
    region_texts = collect_region_block_texts(section_json, "results_table")
    if region_texts:
        out = []
        for text in region_texts:
            out.extend(clean_result_lines(text))
        return out

    page_sections = section_json.get("page_sections", {})
    out = []
    for page_name in sorted(page_sections.keys()):
        page = page_sections[page_name]
        if page.get("results"):
            out.extend(clean_result_lines(page["results"]))
    return out


def collect_results_pages(section_json: dict) -> dict[str, list[str]]:
    page_sections = section_json.get("page_sections", {})
    pages = {}
    for page_name in sorted(page_sections.keys()):
        page = page_sections[page_name]
        if page.get("results"):
            pages[page_name] = clean_result_lines(page["results"])
    return pages


def collect_environmental_conditions_lines(section_json: dict) -> list[str]:
    page_sections = section_json.get("page_sections", {})
    out = []
    for page_name in sorted(page_sections.keys()):
        page = page_sections[page_name]
        if page.get("environmental_conditions"):
            out.extend(clean_result_lines(page["environmental_conditions"]))
    return out


def detect_instrument_type(section_json: dict) -> str | None:
    page01 = section_json.get("page_sections", {}).get("page_01.png", {})
    equipment_text = page01.get("equipment", "")
    n = normalize(equipment_text)
    results_text = "\n".join(collect_all_results_lines(section_json))
    results_n = normalize(results_text)

    if "PAQUIMETRO" in n:
        return "caliper"
    if "MANOMETRO" in n:
        return "pressure_gauge"
    if (
        "MAQUINA UNIVERSAL DE ENSAIO" in n or
        ("GAMA NOMINAL" in results_n and "INCERTEZA EXPANDIDA" in results_n and "ERROS RELATIVOS" in results_n)
    ):
        return "force_calibration"
    return None


# -------------------------
# Generic numeric chunking
# -------------------------
def chunk_numeric_lines(lines: list[str], chunk_size: int) -> list[list[str]]:
    """
    Junta números linha a linha e devolve grupos de N.
    Só usa linhas que sejam 'quase puramente numéricas'.
    """
    chunks = []
    current = []

    for ln in lines:
        nums = extract_numbers(ln)
        n = normalize(ln)

        # ignorar cabeçalhos, eixos de gráfico, etc.
        if not nums:
            continue
        if any(word in n for word in [
            "ERRO", "RESULTADOS", "VALOR", "PADRAO", "PADRÃO", "LEITURA",
            "INCERTEZA", "EXPANDIDA", "MAXILAS", "PONTOS DE MEDICAO",
            "PONTOS DE MEDIGAO", "CONTACTO", "CONTATO", "EXEMPLO",
            "ZONA", "MM", "K'", "V'EF", "U MM", "PRESSAO / BAR",
            "TEMPERATURA", "HUMIDADE", "PRESSAO ATMOSFERICA", "DENSIDADE DO AR",
        ]):
            # exceção: linha totalmente numérica com mm etc não interessa
            # aqui preferimos ignorar
            pass

        # usar apenas linhas muito simples
        if len(nums) == 1 and re.fullmatch(r"\s*[-+]?\d+(?:[.,]\d+)?\s*", ln):
            current.append(nums[0])

            if len(current) == chunk_size:
                chunks.append(current[:])
                current = []

    return chunks


# -------------------------
# Caliper parsing
# -------------------------
def slice_between(lines: list[str], start_keywords: list[str], end_keywords: list[str] | None = None) -> list[str]:
    start_idx = None
    end_idx = len(lines)

    for i, ln in enumerate(lines):
        n = normalize(ln)
        if any(k in n for k in start_keywords):
            start_idx = i + 1
            break

    if start_idx is None:
        return []

    if end_keywords:
        for i in range(start_idx, len(lines)):
            n = normalize(lines[i])
            if any(k in n for k in end_keywords):
                end_idx = i
                break

    return lines[start_idx:end_idx]


def parse_caliper_E_table(lines: list[str]) -> list[dict]:
    section = slice_between(
        lines,
        start_keywords=["ERRO DE INDICAGAO COM CONTACTO PARCIAL", "ERRO DE INDICACAO COM CONTACTO PARCIAL"],
        end_keywords=["ERRO DE INDICAGAO TROCA DE ESCALA", "ERRO DE INDICACAO TROCA DE ESCALA"],
    )

    chunks = chunk_numeric_lines(section, 8)
    rows = []

    for c in chunks:
        row = {
            "standard_value_mm": to_float(c[0]),
            "zone_1_mm": to_float(c[1]),
            "zone_2_mm": to_float(c[2]),
            "zone_3_mm": to_float(c[3]),
            "error_E_mm": to_float(c[4]),
            "k": to_float(c[5]),
            "vef": to_float(c[6]),
            "U_mm": to_float(c[7]),
        }

        # filtrar lixo do gráfico/eixos
        if row["standard_value_mm"] is None:
            continue
        if row["standard_value_mm"] < 1.0:
            continue
        if row["k"] is None or row["k"] < 1.5 or row["k"] > 3.0:
            continue
        if row["U_mm"] is None or row["U_mm"] <= 0:
            continue

        rows.append(row)

    return rows


def parse_caliper_S_table(lines: list[str]) -> list[dict]:
    section = slice_between(
        lines,
        start_keywords=["ERRO DE INDICAGAO TROCA DE ESCALA", "ERRO DE INDICACAO TROCA DE ESCALA"],
        end_keywords=["CONTACTO EM LINHA"],
    )

    rows = []
    current_feature = None
    numeric_buffer = []

    for ln in section:
        n = normalize(ln)
        nums = extract_numbers(ln)

        if any(x in n for x in ["INTERIORES", "HASTE", "DEGRAU", "FACA"]):
            current_feature = clean_spaces(ln)
            numeric_buffer = []
            continue

        if len(nums) == 1 and re.fullmatch(r"\s*[-+]?\d+(?:[.,]\d+)?\s*", ln):
            numeric_buffer.append(nums[0])
            if len(numeric_buffer) == 6:
                rows.append({
                    "feature": current_feature,
                    "standard_value_mm": to_float(numeric_buffer[0]),
                    "reading_mm": to_float(numeric_buffer[1]),
                    "error_S_mm": to_float(numeric_buffer[2]),
                    "k": to_float(numeric_buffer[3]),
                    "vef": to_float(numeric_buffer[4]),
                    "U_mm": to_float(numeric_buffer[5]),
                })
                numeric_buffer = []

    return rows


def parse_caliper_L_table(lines: list[str]) -> list[dict]:
    section = slice_between(
        lines,
        start_keywords=["CONTACTO EM LINHA"],
        end_keywords=["OBSERVACOES", "OBSERVAÇÕES"],
    )

    rows = []
    current_feature = None
    numeric_buffer = []

    for ln in section:
        n = normalize(ln)
        nums = extract_numbers(ln)

        if "MAXILAS DE EXTERIORES" in n:
            current_feature = clean_spaces(ln)
            numeric_buffer = []
            continue

        if len(nums) == 1 and re.fullmatch(r"\s*[-+]?\d+(?:[.,]\d+)?\s*", ln):
            numeric_buffer.append(nums[0])
            if len(numeric_buffer) == 7:
                rows.append({
                    "feature": current_feature,
                    "standard_value_mm": to_float(numeric_buffer[0]),
                    "max_value_mm": to_float(numeric_buffer[1]),
                    "min_value_mm": to_float(numeric_buffer[2]),
                    "error_L_mm": to_float(numeric_buffer[3]),
                    "k": to_float(numeric_buffer[4]),
                    "vef": to_float(numeric_buffer[5]),
                    "U_mm": to_float(numeric_buffer[6]),
                })
                numeric_buffer = []

    return rows


def parse_caliper_tables(section_json: dict) -> dict:
    lines = collect_all_results_lines(section_json)
    return {
        "E_contact_partial": parse_caliper_E_table(lines),
        "S_scale_change": parse_caliper_S_table(lines),
        "L_line_contact": parse_caliper_L_table(lines),
    }


# -------------------------
# Pressure gauge parsing
# -------------------------
def parse_pressure_error_table(lines: list[str]) -> list[dict]:
    """
    Procura a tabela principal do manómetro.
    Cada linha útil tem 6 números:
    equipamento, erro_bar, k, vef, U_bar, erro_percent_FE
    """
    rows = []
    numeric_buffer = []

    collecting = False

    for ln in lines:
        n = normalize(ln)
        nums = extract_numbers(ln)

        # começar a recolher quando aparece cabeçalho ou logo que entremos em linhas numéricas plausíveis
        if "ERRO" in n and "EQUIPAMENTO" in n:
            collecting = True
            continue

        if "ERRO MAXIMO DE HISTERESE" in n or "ERRO MÁXIMO DE HISTERESE" in n:
            break

        if not collecting:
            # fallback: se aparecer uma linha numérica típica, começa
            if len(nums) == 1 and re.fullmatch(r"\s*[-+]?\d+(?:[.,]\d+)?\s*", ln):
                collecting = True
            else:
                continue

        if len(nums) == 1 and re.fullmatch(r"\s*[-+]?\d+(?:[.,]\d+)?\s*", ln):
            numeric_buffer.append(nums[0])

            if len(numeric_buffer) == 6:
                row = {
                    "equipment_bar": to_float(numeric_buffer[0]),
                    "error_bar": to_float(numeric_buffer[1]),
                    "k": to_float(numeric_buffer[2]),
                    "vef": to_float(numeric_buffer[3]),
                    "U_bar": to_float(numeric_buffer[4]),
                    "error_percent_FE": to_float(numeric_buffer[5]),
                }

                # filtro de plausibilidade
                if (
                    row["k"] is not None and 1.5 <= row["k"] <= 3.0 and
                    row["vef"] is not None and row["vef"] > 50 and
                    row["U_bar"] is not None and row["U_bar"] > 0
                ):
                    rows.append(row)

                numeric_buffer = []

    return rows

def parse_pressure_max_hysteresis(lines: list[str]) -> dict | None:
    text = "\n".join(lines)
    m = re.search(
        r"(?i)ERRO\s+M[AÁ]XIMO\s+DE\s+HISTERESE\s*:\s*([-+]?\d+(?:[.,]\d+)?)\s*BAR",
        text
    )
    if not m:
        return None

    return {
        "max_hysteresis_bar": to_float(m.group(1)),
        "raw_text": m.group(0),
    }


def parse_environmental_conditions(env_lines: list[str]) -> list[dict]:
    """
    Espera linhas com 4 colunas:
    temperatura, humidade, pressão atmosférica, densidade do ar

    Usa uma janela deslizante e validação de plausibilidade.
    """
    tokens = []
    for ln in env_lines:
        if len(extract_numbers(ln)) == 1 and re.fullmatch(r"\s*[-+]?\d+(?:[.,]\d+)?\s*", ln):
            tokens.append(extract_numbers(ln)[0])

    vals = [to_float(x) for x in tokens if to_float(x) is not None]

    rows = []
    i = 0
    while i <= len(vals) - 4:
        t, h, p, d = vals[i:i+4]

        plausible = (
            10 <= t <= 30 and
            20 <= h <= 80 and
            0.8 <= p <= 1.2 and
            1.0 <= d <= 1.3
        )

        if plausible:
            rows.append({
                "temperature_C": t,
                "humidity_percent_hr": h,
                "atmospheric_pressure_bar": p,
                "air_density": d,
            })
            i += 4
        else:
            i += 1

    return rows


def parse_pressure_gauge_tables(section_json: dict) -> dict:
    result_lines = collect_all_results_lines(section_json)
    env_lines = collect_environmental_conditions_lines(section_json)

    return {
        "pressure_error_table": parse_pressure_error_table(result_lines),
        "max_hysteresis": parse_pressure_max_hysteresis(result_lines),
        "environmental_conditions": parse_environmental_conditions(env_lines),
    }


def _find_first_index(lines: list[str], needles: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        n = normalize(line)
        if any(needle in n for needle in needles):
            return idx
    return None


def _slice_force_section(lines: list[str], start_needles: list[str], end_needles: list[str] | None = None) -> list[str]:
    start_idx = _find_first_index(lines, start_needles)
    if start_idx is None:
        return []

    start = start_idx + 1
    end = len(lines)
    if end_needles:
        for idx in range(start, len(lines)):
            n = normalize(lines[idx])
            if any(needle in n for needle in end_needles):
                end = idx
                break

    return lines[start:end]


def _extract_force_page_meta(lines: list[str]) -> dict:
    text = "\n".join(lines)

    def grab(pattern: str):
        match = re.search(pattern, text, re.IGNORECASE)
        return clean_spaces(match.group(1)) if match else None

    return {
        "gama_nominal": grab(r"Gama\s+Nominal\s*:\s*([^\n]+)"),
        "divisao": grab(r"Divis[aã]o\s*:\s*([^\n]+)"),
        "sentido": grab(r"Sentido\s*:\s*([^\n]+)"),
        "resolucao": grab(r"Resolu[cç][aã]o\s*:\s*([^\n]+)"),
    }


def _force_range_slug(meta: dict, fallback: str) -> str:
    raw = meta.get("gama_nominal") or fallback
    slug = normalize(raw).lower()
    slug = slug.replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_]+", "", slug)
    return slug or fallback


def parse_force_measurement_rows(lines: list[str]) -> list[dict]:
    section = _slice_force_section(
        lines,
        start_needles=["INCERTEZA EXPANDIDA"],
        end_needles=["ERROS RELATIVOS", "CLASSE"],
    )

    tokens = []
    for line in section:
        if _is_simple_numeric_line(line):
            nums = extract_numbers(line)
            if len(nums) == 1:
                value = to_float(nums[0])
                if value is not None:
                    tokens.append(value)

    rows = []
    buffer = []
    for value in tokens:
        buffer.append(value)
        if len(buffer) == 5:
            equipment, error, k, vef, uncertainty = buffer
            if equipment > 0 and 1.5 <= k <= 3.0 and vef > 5 and uncertainty > 0:
                rows.append(
                    {
                        "equipment_force_dan": equipment,
                        "error_dan": error,
                        "k": k,
                        "vef": vef,
                        "expanded_uncertainty_dan": uncertainty,
                    }
                )
            buffer = []

    return rows


def _is_close_force(value: float | None, expected: float | None) -> bool:
    if value is None or expected is None:
        return False
    tolerance = max(1.0, abs(expected) * 0.02)
    return abs(value - expected) <= tolerance


def parse_force_relative_rows(lines: list[str], expected_forces: list[float] | None = None) -> list[dict]:
    section = _slice_force_section(lines, start_needles=["ERROS RELATIVOS"], end_needles=["TEMPERATURA", "HUMIDADE"])
    if not section:
        return []

    numeric_values = []
    current_class = None
    for line in section:
        n = normalize(line)
        if "CLASSE" in n:
            current_class = clean_spaces(line)
            continue
        if _is_simple_numeric_line(line):
            nums = extract_numbers(line)
            if len(nums) == 1:
                value = to_float(nums[0])
                if value is not None:
                    numeric_values.append(value)

    rows = []
    if expected_forces:
        cursor = 0
        previous_force = None
        for expected_force in expected_forces:
            metrics = None

            while cursor < len(numeric_values):
                current = numeric_values[cursor]

                if previous_force is not None and _is_close_force(current, previous_force):
                    cursor += 1
                    continue

                if _is_close_force(current, expected_force):
                    candidate = numeric_values[cursor + 1: cursor + 5]
                    if len(candidate) >= 4:
                        metrics = candidate[:4]
                        cursor += 5
                        break

                candidate5 = numeric_values[cursor: cursor + 5]
                if (
                    len(candidate5) >= 5 and
                    all(value is not None and abs(value) <= 10 for value in candidate5[:3]) and
                    _is_close_force(candidate5[3], expected_force) and
                    candidate5[4] is not None and abs(candidate5[4]) <= 10
                ):
                    metrics = [candidate5[0], candidate5[1], candidate5[2], candidate5[4]]
                    cursor += 5
                    break

                candidate = numeric_values[cursor: cursor + 4]
                if len(candidate) >= 4 and all(value is not None and abs(value) <= 10 for value in candidate):
                    metrics = candidate[:4]
                    cursor += 4
                    break

                cursor += 1

            if metrics is None:
                continue

            q, b, a, fo = metrics
            rows.append(
                {
                    "equipment_force_dan": expected_force,
                    "q_percent": q,
                    "b_percent": b,
                    "a_percent": a,
                    "fo_percent": fo,
                    "class": current_class or "Classe",
                }
            )
            previous_force = expected_force
        return rows

    buffer = []
    for value in numeric_values:
        buffer.append(value)
        if len(buffer) == 5:
            equipment, q, b, a, fo = buffer
            rows.append(
                {
                    "equipment_force_dan": equipment,
                    "q_percent": q,
                    "b_percent": b,
                    "a_percent": a,
                    "fo_percent": fo,
                    "class": current_class or "Classe",
                }
            )
            buffer = []

    return rows


def parse_force_environmental_rows(lines: list[str]) -> list[dict]:
    rows = []
    for idx, line in enumerate(lines):
        n = normalize(line)
        if "TEMPERATURA" not in n:
            continue

        window = lines[idx + 1: idx + 8]
        values = []
        for candidate in window:
            if _is_simple_numeric_line(candidate):
                nums = extract_numbers(candidate)
                if len(nums) == 1:
                    value = to_float(nums[0])
                    if value is not None:
                        values.append(value)

        if len(values) >= 2:
            rows.append(
                {
                    "temperature_c": values[0],
                    "humidity_percent_hr": values[1],
                }
            )

    return rows


def parse_force_calibration_tables(section_json: dict) -> dict:
    results_pages = collect_results_pages(section_json)

    measurement_subtables = []
    relative_subtables = []
    environmental_rows = []
    measurement_rows_all = []
    relative_rows_all = []

    for page_name, lines in results_pages.items():
        meta = _extract_force_page_meta(lines)
        slug = _force_range_slug(meta, page_name.replace(".png", ""))

        measurement_rows = parse_force_measurement_rows(lines)
        if measurement_rows:
            measurement_rows_all.extend(measurement_rows)
            measurement_subtables.append(
                {
                    "key": f"force_calibration_measurements_{slug}",
                    "title": meta.get("gama_nominal") or page_name,
                    "table": {
                        "columns": [
                            "equipment_force_dan",
                            "error_dan",
                            "k",
                            "vef",
                            "expanded_uncertainty_dan",
                        ],
                        "page": page_name,
                        "meta": meta,
                        "rows": measurement_rows,
                    },
                }
            )

        expected_forces = [row["equipment_force_dan"] for row in measurement_rows]
        relative_rows = parse_force_relative_rows(lines, expected_forces)
        if relative_rows:
            relative_rows_all.extend(relative_rows)
            relative_subtables.append(
                {
                    "key": f"force_relative_errors_{slug}",
                    "title": meta.get("gama_nominal") or page_name,
                    "table": {
                        "columns": [
                            "equipment_force_dan",
                            "q_percent",
                            "b_percent",
                            "a_percent",
                            "fo_percent",
                            "class",
                        ],
                        "page": page_name,
                        "meta": meta,
                        "rows": relative_rows,
                    },
                }
            )

        environmental_rows.extend(parse_force_environmental_rows(lines))

    tables = {}

    if measurement_rows_all:
        tables["force_calibration_measurements"] = {
            "columns": [
                "equipment_force_dan",
                "error_dan",
                "k",
                "vef",
                "expanded_uncertainty_dan",
            ],
            "rows": measurement_rows_all,
            "subtables": measurement_subtables,
        }

    if relative_rows_all:
        tables["force_relative_errors"] = {
            "columns": [
                "equipment_force_dan",
                "q_percent",
                "b_percent",
                "a_percent",
                "fo_percent",
                "class",
            ],
            "rows": relative_rows_all,
            "subtables": relative_subtables,
        }

    if environmental_rows:
        tables["force_environmental_conditions"] = environmental_rows

    return tables


def _is_simple_numeric_line(line: str) -> bool:
    compact = re.sub(r"(?<=\d)\s+(?=\d{3}(?:[.,]\d+)?)", "", line.strip())
    return bool(re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", compact))


def _is_generic_header_line(line: str) -> bool:
    n = normalize(line)
    return any(token in n for token in ["LEITURA NO EQUIPAMENTO", "PADRAO", "ERRO", "INCERTEZA", "MEDIA"])


def _infer_section_from_header_line(line: str) -> str | None:
    n = normalize(line)
    if "PADRAO (G)" in n:
        return "Peso"
    if "PADRAO (%)" in n:
        return "Humidade"
    if "PADRAO (MM)" in n:
        return None
    return None


def _infer_unit_from_header_line(line: str) -> str | None:
    n = normalize(line)
    if "PADRAO (MM)" in n:
        return "mm"
    if "PADRAO (G)" in n:
        return "g"
    if "PADRAO (%)" in n:
        return "%"
    return None


def _is_generic_section_line(line: str) -> bool:
    n = normalize(line)
    if not n:
        return False
    if _is_generic_header_line(line):
        return False
    if "RESULTADOS" in n:
        return False
    if extract_numbers(line):
        return False
    words = n.split()
    if len(words) > 3:
        return False
    return any(token in n for token in ["COMPRIMENTO", "DIAMETRO", "PESO", "HUMIDADE", "UMIDADE", "PRESSAO", "TEMPERATURA"])


def _canonical_generic_columns(lines: list[str]) -> list[str]:
    joined = " ".join(normalize(line) for line in lines)
    if "PADRAO" in joined and "ERRO" in joined and "INCERTEZA" in joined:
        return ["standard_value", "reading_value", "error_value", "uncertainty_value"]
    return ["value_1", "value_2", "value_3", "value_4"]


def _dedupe_generic_rows(rows: list[dict]) -> list[dict]:
    deduped_by_values = {}
    for row in rows:
        signature = tuple(row.get("values", []))
        if signature not in deduped_by_values:
            deduped_by_values[signature] = row

    return list(deduped_by_values.values())


def _is_plausible_generic_row(values: list[float | None], columns: list[str]) -> bool:
    if len(values) < 4:
        return False

    if any(v is None for v in values[:4]):
        return False

    standard = values[0]
    reading = values[1]
    error = values[2]
    uncertainty = values[3]

    if reading is None or standard is None or error is None or uncertainty is None:
        return False

    if uncertainty <= 0:
        return False

    # Em certificados de calibração, o erro declarado deve ser compatível
    # com a diferença entre leitura e padrão, admitindo arredondamento.
    delta = standard - reading
    tolerance = max(0.05, uncertainty * 8)
    if min(abs(delta - error), abs(delta + error)) > tolerance:
        return False

    return True


def _split_generic_groups(lines: list[str]) -> list[dict]:
    groups = []
    current = None

    for line in lines:
        normalized = normalize(line)

        if _is_generic_header_line(line):
            inferred_unit = _infer_unit_from_header_line(line)
            if inferred_unit:
                if current and current["rows"]:
                    groups.append(current)
                current = {
                    "unit": inferred_unit,
                    "header_lines": [],
                    "rows": [],
                    "markers": [],
                }

            if current:
                current["header_lines"].append(line)
            continue

        if current is None:
            continue

        if _is_generic_section_line(line):
            current["markers"].append(
                {
                    "label": normalize_display_text(clean_spaces(line)),
                    "row_index": len(current["rows"]),
                }
            )
            continue

        if _is_simple_numeric_line(line):
            value = to_float(line)
            if value is not None:
                current.setdefault("numeric_buffer", []).append(value)
                if len(current["numeric_buffer"]) == 4:
                    current["rows"].append({
                        "values": current["numeric_buffer"][:],
                    })
                    current["numeric_buffer"] = []
            continue

        if extract_numbers(line):
            current["numeric_buffer"] = []

    if current and current["rows"]:
        groups.append(current)

    for group in groups:
        group.pop("numeric_buffer", None)

    return groups


def _find_monotonic_drop_boundaries(rows: list[dict]) -> list[int]:
    boundaries = []
    if len(rows) < 2:
        return boundaries

    previous = rows[0]["values"][0]
    for index in range(1, len(rows)):
        current = rows[index]["values"][0]
        if previous is None or current is None:
            previous = current
            continue

        if current < previous - 5:
            boundaries.append(index)
        previous = current

    return boundaries


def _assign_group_sections(group: dict) -> list[dict]:
    rows = [dict(row) for row in group.get("rows", [])]
    markers = [marker["label"] for marker in group.get("markers", []) if marker.get("label")]
    unit = group.get("unit")

    if not rows:
        return rows

    if unit == "mm":
        boundaries = _find_monotonic_drop_boundaries(rows)
        if boundaries and markers:
            segment_starts = [0] + boundaries + [len(rows)]
            segment_count = len(segment_starts) - 1
            labels = markers[:segment_count]
            if len(labels) < segment_count:
                labels.extend([labels[-1]] * (segment_count - len(labels)))

            for segment_index in range(segment_count):
                start = segment_starts[segment_index]
                end = segment_starts[segment_index + 1]
                label = labels[segment_index] if segment_index < len(labels) else None
                for row_index in range(start, end):
                    rows[row_index]["section"] = label
            return rows

    if len(markers) == 1:
        label = markers[0]
        for row in rows:
            row["section"] = label
        return rows

    if markers:
        current_label = None
        for row_index, row in enumerate(rows):
            for marker in group.get("markers", []):
                if marker["row_index"] <= row_index:
                    current_label = marker["label"]
            row["section"] = current_label

        if rows and rows[0].get("section") is None:
            first_label = markers[0]
            for row in rows:
                if row.get("section") is None:
                    row["section"] = first_label
                else:
                    break

    return rows


def _fallback_section_from_unit(unit: str | None) -> str | None:
    if unit == "g":
        return "Peso"
    if unit == "%":
        return "Humidade"
    return None


def _slugify_section_name(name: str | None) -> str:
    if not name:
        return "section"
    normalized = normalize(name).lower()
    normalized = normalized.replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
    return normalized or "section"


def parse_generic_results_table(lines: list[str]) -> dict:
    groups = _split_generic_groups(lines)
    rows = []
    active_columns = ["standard_value", "reading_value", "error_value", "uncertainty_value"]

    for group in groups:
        group_columns = _canonical_generic_columns(group.get("header_lines", []))
        if len(group_columns) >= 4:
            active_columns = group_columns[:4]

        assigned_rows = _assign_group_sections(group)
        for row in assigned_rows:
            values = row.get("values", [])
            if not _is_plausible_generic_row(values, active_columns):
                continue

            row_section = normalize_display_text(row.get("section") or _fallback_section_from_unit(group.get("unit")))
            parsed_row = {
                "section": row_section,
                "unit": group.get("unit"),
                "values": values,
            }
            for idx, value in enumerate(values):
                key = active_columns[idx] if idx < len(active_columns) else f"value_{idx + 1}"
                parsed_row[key] = value
            rows.append(parsed_row)

    deduped_rows = _dedupe_generic_rows(rows)
    section_names = []
    for row in deduped_rows:
        section = row.get("section")
        if section and section not in section_names:
            section_names.append(section)

    units = []
    for row in deduped_rows:
        unit = row.get("unit")
        if unit and unit not in units:
            units.append(unit)

    return {
        "columns": active_columns[:4],
        "sections": section_names,
        "units": units,
        "rows": deduped_rows,
    }


def parse_generic_block_tables(section_json: dict) -> dict:
    result_lines = collect_all_results_lines(section_json)
    generic_table = parse_generic_results_table(result_lines)
    rows = generic_table.get("rows", [])

    section_groups = {}
    for row in rows:
        section = row.get("section")
        if not section:
            continue
        section_groups.setdefault(section, []).append(row)

    subtables = []
    extra_tables = {}
    if section_groups:
        for section_name, section_rows in section_groups.items():
            units = []
            for row in section_rows:
                unit = row.get("unit")
                if unit and unit not in units:
                    units.append(unit)

            section_table = {
                "columns": generic_table.get("columns", []),
                "sections": [section_name],
                "units": units,
                "rows": section_rows,
            }
            subtables.append(
                {
                    "key": f"generic_results_table_{_slugify_section_name(section_name)}",
                    "title": section_name,
                    "table": section_table,
                }
            )
            extra_tables[f"generic_results_table_{_slugify_section_name(section_name)}"] = section_table

    generic_table["subtables"] = subtables

    tables = {
        "generic_results_table": generic_table,
    }
    tables.update(extra_tables)
    return tables


# -------------------------
# Dispatcher
# -------------------------
def parse_tables(section_json: dict) -> dict:
    instrument_type = detect_instrument_type(section_json)

    if instrument_type == "caliper":
        return repair_nested_text({
            "instrument_type": instrument_type,
            "tables": parse_caliper_tables(section_json),
        })

    if instrument_type == "pressure_gauge":
        return repair_nested_text({
            "instrument_type": instrument_type,
            "tables": parse_pressure_gauge_tables(section_json),
        })

    if instrument_type == "force_calibration":
        force_tables = parse_force_calibration_tables(section_json)
        return repair_nested_text({
            "instrument_type": instrument_type,
            "tables": force_tables,
        })

    generic_tables = parse_generic_block_tables(section_json)
    generic_rows = generic_tables.get("generic_results_table", {}).get("rows", [])
    if generic_rows:
        return repair_nested_text({
            "instrument_type": "generic_block_table",
            "tables": generic_tables,
        })

    return repair_nested_text({
        "instrument_type": instrument_type,
        "tables": {},
    })


# -------------------------
# Main
# -------------------------
def main():
    files = sorted(IN_DIR.glob("*_sections.json"))

    if not files:
        print(f"Sem ficheiros de secções em: {IN_DIR}")
        return

    for fp in files:
        data = read_json(fp)
        parsed = parse_tables(data)

        out = OUT_DIR / fp.name.replace("_sections.json", "_tables.json")
        payload = repair_nested_text({
            "source_file": data.get("source_file"),
            "extracted_at": datetime.now().isoformat(timespec="seconds"),
            "instrument_type": parsed["instrument_type"],
            "tables": parsed["tables"],
        })

        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print("saved:", out)


if __name__ == "__main__":
    main()
