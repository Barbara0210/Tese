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


# -------------------------
# Section getters
# -------------------------
def collect_all_results_text(section_json: dict) -> str:
    page_sections = section_json.get("page_sections", {})
    parts = []

    for page_name in sorted(page_sections.keys()):
        page = page_sections[page_name]
        if page.get("results"):
            parts.append(page["results"])

    return "\n".join(parts).strip()


def collect_environmental_conditions_text(section_json: dict) -> str:
    page_sections = section_json.get("page_sections", {})
    parts = []

    for page_name in sorted(page_sections.keys()):
        page = page_sections[page_name]
        if page.get("environmental_conditions"):
            parts.append(page["environmental_conditions"])

    return "\n".join(parts).strip()


# -------------------------
# Instrument type detection
# -------------------------
def detect_instrument_type(section_json: dict) -> str | None:
    page01 = section_json.get("page_sections", {}).get("page_01.png", {})
    equipment_text = page01.get("equipment", "")
    n = normalize(equipment_text)

    if "PAQUIMETRO" in n:
        return "caliper"

    if "MANOMETRO" in n or "MANOMETRO ANALOGICO" in n:
        return "pressure_gauge"

    return None


# -------------------------
# Caliper parsing
# -------------------------
def parse_caliper_E_table(results_text: str) -> list[dict]:
    """
    Espera linhas com 8 números:
    valor_padrao, zona1, zona2, zona3, erro, k, vef, U
    """
    lines = clean_result_lines(results_text)
    rows = []

    inside = False
    for ln in lines:
        n = normalize(ln)

        if "ERRO DE INDICAGAO COM CONTACTO PARCIAL" in n or "ERRO DE INDICACAO COM CONTACTO PARCIAL" in n:
            inside = True
            continue

        if inside and ("ERRO DE INDICAGAO TROCA DE ESCALA" in n or "ERRO DE INDICACAO TROCA DE ESCALA" in n):
            break

        if not inside:
            continue

        nums = extract_numbers(ln)
        if len(nums) == 8:
            row = {
                "standard_value_mm": to_float(nums[0]),
                "zone_1_mm": to_float(nums[1]),
                "zone_2_mm": to_float(nums[2]),
                "zone_3_mm": to_float(nums[3]),
                "error_E_mm": to_float(nums[4]),
                "k": to_float(nums[5]),
                "vef": to_float(nums[6]),
                "U_mm": to_float(nums[7]),
                "raw_line": ln,
            }
            rows.append(row)

    return rows


def parse_caliper_S_table(results_text: str) -> list[dict]:
    """
    Espera linhas com:
    texto opcional + 6 números
    valor_padrao, leitura, erro, k, vef, U
    """
    lines = clean_result_lines(results_text)
    rows = []

    inside = False
    current_feature = None

    for ln in lines:
        n = normalize(ln)

        if "ERRO DE INDICAGAO TROCA DE ESCALA" in n or "ERRO DE INDICACAO TROCA DE ESCALA" in n:
            inside = True
            continue

        if inside and ("CONTACTO EM LINHA" in n):
            break

        if not inside:
            continue

        nums = extract_numbers(ln)

        # linha com texto da feature
        if len(nums) < 6 and len(ln) > 0:
            if any(x in n for x in ["INTERIORES", "HASTE", "DEGRAU", "FACA", "FACA < 5 MM"]):
                current_feature = clean_spaces(ln)

        if len(nums) == 6:
            row = {
                "feature": current_feature,
                "standard_value_mm": to_float(nums[0]),
                "reading_mm": to_float(nums[1]),
                "error_S_mm": to_float(nums[2]),
                "k": to_float(nums[3]),
                "vef": to_float(nums[4]),
                "U_mm": to_float(nums[5]),
                "raw_line": ln,
            }
            rows.append(row)

    return rows


def parse_caliper_L_table(results_text: str) -> list[dict]:
    """
    Espera linhas com 6 números:
    valor_padrao, valor_max, valor_min, erro_L, k, vef/U? ou k, vef, U
    Nos teus exemplos a linha útil tem 6 números:
    10.000 10.00 10.00 0.000 2.02 150 0.011
    => isso na verdade são 7
    """
    lines = clean_result_lines(results_text)
    rows = []

    inside = False
    current_feature = None

    for ln in lines:
        n = normalize(ln)

        if "CONTACTO EM LINHA" in n:
            inside = True
            continue

        if inside and "OBSERVACOES" in n:
            break

        if not inside:
            continue

        if "MAXILAS DE EXTERIORES" in n:
            current_feature = clean_spaces(ln)
            continue

        nums = extract_numbers(ln)
        if len(nums) == 7:
            row = {
                "feature": current_feature,
                "standard_value_mm": to_float(nums[0]),
                "max_value_mm": to_float(nums[1]),
                "min_value_mm": to_float(nums[2]),
                "error_L_mm": to_float(nums[3]),
                "k": to_float(nums[4]),
                "vef": to_float(nums[5]),
                "U_mm": to_float(nums[6]),
                "raw_line": ln,
            }
            rows.append(row)

    return rows


def parse_caliper_tables(section_json: dict) -> dict:
    results_text = collect_all_results_text(section_json)

    return {
        "E_contact_partial": parse_caliper_E_table(results_text),
        "S_scale_change": parse_caliper_S_table(results_text),
        "L_line_contact": parse_caliper_L_table(results_text),
    }


# -------------------------
# Pressure gauge parsing
# -------------------------
def parse_pressure_error_table(results_text: str) -> list[dict]:
    """
    Para o manómetro, cada linha útil tem 6 números:
    equipamento, erro_bar, k, vef, U_bar, erro_percent_FE

    Ex:
    -0.80 0.018 2.01 200 0.033 0.45
    """
    lines = clean_result_lines(results_text)
    rows = []

    for ln in lines:
        nums = extract_numbers(ln)
        if len(nums) == 6:
            row = {
                "equipment_bar": to_float(nums[0]),
                "error_bar": to_float(nums[1]),
                "k": to_float(nums[2]),
                "vef": to_float(nums[3]),
                "U_bar": to_float(nums[4]),
                "error_percent_FE": to_float(nums[5]),
                "raw_line": ln,
            }
            rows.append(row)

    return rows


def parse_pressure_max_hysteresis(results_text: str) -> dict | None:
    m = re.search(
        r"(?i)Erro\s+m[aá]ximo\s+de\s+histerese\s*:\s*([-+]?\d+(?:[.,]\d+)?)\s*bar",
        results_text or ""
    )
    if not m:
        return None

    return {
        "max_hysteresis_bar": to_float(m.group(1)),
        "raw_text": m.group(0),
    }


def parse_environmental_conditions(env_text: str) -> list[dict]:
    """
    Fase 1 simples:
    no manómetro tens cabeçalho:
      Temperatura
      Humidade
      Pressão Atmosférica
      Densidade do Ar
    seguido de valores.
    Vamos montar linhas de 4 valores.
    """
    lines = clean_result_lines(env_text)
    numeric_lines = []

    for ln in lines:
        nums = extract_numbers(ln)
        if nums:
            numeric_lines.extend(nums)

    rows = []
    chunk_size = 4

    for i in range(0, len(numeric_lines), chunk_size):
        chunk = numeric_lines[i:i + chunk_size]
        if len(chunk) == 4:
            rows.append({
                "temperature_C": to_float(chunk[0]),
                "humidity_percent_hr": to_float(chunk[1]),
                "atmospheric_pressure_bar": to_float(chunk[2]),
                "air_density": to_float(chunk[3]),
            })

    return rows


def parse_pressure_gauge_tables(section_json: dict) -> dict:
    results_text = collect_all_results_text(section_json)
    env_text = collect_environmental_conditions_text(section_json)

    return {
        "pressure_error_table": parse_pressure_error_table(results_text),
        "max_hysteresis": parse_pressure_max_hysteresis(results_text),
        "environmental_conditions": parse_environmental_conditions(env_text),
    }


# -------------------------
# Generic dispatcher
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
        tables = parse_tables(data)

        out = OUT_DIR / fp.name.replace("_sections.json", "_tables.json")
        payload = {
            "source_file": data.get("source_file"),
            "extracted_at": datetime.now().isoformat(timespec="seconds"),
            "instrument_type": tables["instrument_type"],
            "tables": tables["tables"],
        }

        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print("saved:", out)


if __name__ == "__main__":
    main()