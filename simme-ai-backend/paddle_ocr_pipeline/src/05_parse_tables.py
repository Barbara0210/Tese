import json
import re
from pathlib import Path
from datetime import datetime

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
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s or None


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
    return re.findall(r"[-+]?\d+(?:[.,]\d+)?", line)


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


def collect_all_results_lines(section_json: dict) -> list[str]:
    page_sections = section_json.get("page_sections", {})
    out = []
    for page_name in sorted(page_sections.keys()):
        page = page_sections[page_name]
        if page.get("results"):
            out.extend(clean_result_lines(page["results"]))
    return out


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

    if "PAQUIMETRO" in n:
        return "caliper"
    if "MANOMETRO" in n:
        return "pressure_gauge"
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


# -------------------------
# Dispatcher
# -------------------------
def parse_tables(section_json: dict) -> dict:
    instrument_type = detect_instrument_type(section_json)

    if instrument_type == "caliper":
        return {
            "instrument_type": instrument_type,
            "tables": parse_caliper_tables(section_json),
        }

    if instrument_type == "pressure_gauge":
        return {
            "instrument_type": instrument_type,
            "tables": parse_pressure_gauge_tables(section_json),
        }

    return {
        "instrument_type": instrument_type,
        "tables": {},
    }


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
        payload = {
            "source_file": data.get("source_file"),
            "extracted_at": datetime.now().isoformat(timespec="seconds"),
            "instrument_type": parsed["instrument_type"],
            "tables": parsed["tables"],
        }

        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print("saved:", out)


if __name__ == "__main__":
    main()