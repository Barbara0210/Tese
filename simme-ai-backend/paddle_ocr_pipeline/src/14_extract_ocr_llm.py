import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]

IMG_DIR = BASE / "data" / "images"
OCR_DIR = BASE / "data" / "ocr_text"
PARSED_DIR = BASE / "data" / "parsed"
TABLES_DIR = BASE / "data" / "tables"

PARSED_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_OCR_LLM_MODEL", "gpt-4o")
CHAT_COMPLETIONS_URL = os.getenv(
    "OPENAI_CHAT_COMPLETIONS_URL",
    "https://api.openai.com/v1/chat/completions",
)


SYSTEM_PROMPT = """És um assistente especializado em extrair informação de certificados de calibração.

Regras obrigatórias:
- Devolve apenas JSON válido.
- Não inventes valores. Se o valor não estiver claro no documento, usa null.
- Não confundas data de emissão com data de calibração.
- Mantém unidades e designações técnicas tal como observadas, quando possível.
- Se não existir uma tabela, devolve uma lista vazia [] ou um objeto vazio {} conforme o caso.
- Usa apenas estes tipos de instrumento: "caliper", "pressure_gauge" ou null.
"""


USER_PROMPT = """Extrai a informação do certificado e devolve exatamente um objeto JSON com esta estrutura:

{
  "instrument_type": "caliper | pressure_gauge | null",
  "header": {
    "issue_date": null,
    "certificate_number": null,
    "lab_name": null,
    "lab_unit": null
  },
  "customer": {
    "name": null,
    "address": null
  },
  "equipment": {
    "designation": null,
    "brand": null,
    "model": null,
    "serial_number": null,
    "range": null,
    "resolution": null,
    "estimated_resolution": null,
    "indication": null,
    "internal_ref": null,
    "class": null,
    "state": null
  },
  "work_conditions": {
    "location": null,
    "temperature": null,
    "humidity": null,
    "accreditation_annex": null
  },
  "reference": {
    "standard_or_procedure": null
  },
  "calibration_date": null,
  "standard_equipment": [],
  "tables": {
    "pressure_error_table": [],
    "max_hysteresis": {},
    "environmental_conditions": [],
    "E_contact_partial": [],
    "S_scale_change": [],
    "L_line_contact": [],
    "generic_tables": []
  }
}

Notas:
- Para "pressure_error_table", usa uma lista de linhas em formato objeto.
- Para "max_hysteresis", usa um objeto simples quando existir.
- Para "environmental_conditions", usa uma lista de linhas em formato objeto.
- Para "E_contact_partial", "S_scale_change" e "L_line_contact", usa listas de linhas em formato objeto.
- Para "standard_equipment", usa uma lista de objetos simples ou strings curtas.
- Se houver tabelas úteis que não consigas mapear claramente, coloca-as em "generic_tables".
"""


def encode_image_to_data_url(image_path: Path) -> str:
    mime = "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def parse_ocr_pages(text: str) -> list[dict]:
    pages = []
    matches = list(re.finditer(r"===\s*(page_\d+\.png)\s*===", text))
    for idx, match in enumerate(matches):
        page_name = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        page_text = text[start:end].strip()
        pages.append({"page_name": page_name, "ocr_text": page_text})
    return pages


def extract_json_text(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    return content


def empty_payload() -> dict:
    return {
        "instrument_type": None,
        "header": {
            "issue_date": None,
            "certificate_number": None,
            "lab_name": None,
            "lab_unit": None,
        },
        "customer": {
            "name": None,
            "address": None,
        },
        "equipment": {
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
        },
        "work_conditions": {
            "location": None,
            "temperature": None,
            "humidity": None,
            "accreditation_annex": None,
        },
        "reference": {
            "standard_or_procedure": None,
        },
        "calibration_date": None,
        "standard_equipment": [],
        "tables": {
            "pressure_error_table": [],
            "max_hysteresis": {},
            "environmental_conditions": [],
            "E_contact_partial": [],
            "S_scale_change": [],
            "L_line_contact": [],
            "generic_tables": [],
        },
    }


def deep_merge_defaults(data: dict, defaults: dict) -> dict:
    merged = {}
    for key, default_value in defaults.items():
        current_value = data.get(key) if isinstance(data, dict) else None
        if isinstance(default_value, dict):
            merged[key] = deep_merge_defaults(current_value or {}, default_value)
        else:
            merged[key] = current_value if current_value is not None else default_value
    if isinstance(data, dict):
        for key, value in data.items():
            if key not in merged:
                merged[key] = value
    return merged


def call_llm(doc_name: str, page_payloads: list[dict]) -> dict:
    if not API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY não está definida. "
            "Define a variável de ambiente OPENAI_API_KEY antes de correr o método OCR + LLM."
        )

    content = [
        {
            "type": "text",
            "text": (
                f"{USER_PROMPT}\n\n"
                f"Documento: {doc_name}\n"
                "Vais receber imagens das páginas e o texto OCR correspondente a cada página."
            ),
        }
    ]

    for page in page_payloads:
        content.append(
            {
                "type": "text",
                "text": f"Página {page['page_name']} OCR:\n{page['ocr_text'] or '[sem texto OCR]'}",
            }
        )
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": page["image_data_url"],
                    "detail": "high",
                },
            }
        )

    payload = {
        "model": MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    }

    request = urllib.request.Request(
        CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Erro HTTP ao chamar o modelo OCR + LLM ({exc.code}).\n{error_body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Erro de rede ao chamar o modelo OCR + LLM: {exc}") from exc

    try:
        raw_content = response_data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(
            f"Resposta inesperada do modelo OCR + LLM: {json.dumps(response_data, ensure_ascii=False)[:2000]}"
        ) from exc

    parsed = json.loads(extract_json_text(raw_content))
    return deep_merge_defaults(parsed, empty_payload())


def build_page_payloads(doc_dir: Path, ocr_text_path: Path) -> list[dict]:
    full_ocr_text = ocr_text_path.read_text(encoding="utf-8")
    ocr_pages = {item["page_name"]: item["ocr_text"] for item in parse_ocr_pages(full_ocr_text)}

    payloads = []
    for image_path in sorted(doc_dir.glob("page_*.png")):
        payloads.append(
            {
                "page_name": image_path.name,
                "ocr_text": ocr_pages.get(image_path.name, ""),
                "image_data_url": encode_image_to_data_url(image_path),
            }
        )
    return payloads


def save_outputs(doc_name: str, llm_data: dict, page_payloads: list[dict]):
    source_file = f"{doc_name}.txt"
    extracted_at = datetime.now().isoformat(timespec="seconds")

    parsed_payload = {
        "source_file": source_file,
        "extracted_at": extracted_at,
        "method": "ocr_llm",
        "header": llm_data["header"],
        "customer": llm_data["customer"],
        "equipment": llm_data["equipment"],
        "work_conditions": llm_data["work_conditions"],
        "reference": llm_data["reference"],
        "calibration_date": llm_data.get("calibration_date"),
        "standard_equipment": llm_data.get("standard_equipment", []),
        "raw_blocks": {
            "llm_model": MODEL,
            "page_ocr": {
                item["page_name"]: item["ocr_text"]
                for item in page_payloads
            },
        },
    }

    tables_payload = {
        "source_file": source_file,
        "extracted_at": extracted_at,
        "instrument_type": llm_data.get("instrument_type"),
        "tables": llm_data.get("tables", {}),
    }

    parsed_path = PARSED_DIR / f"{doc_name}.json"
    tables_path = TABLES_DIR / f"{doc_name}_tables.json"

    parsed_path.write_text(json.dumps(parsed_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tables_path.write_text(json.dumps(tables_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("saved:", parsed_path)
    print("saved:", tables_path)


def main():
    docs = [p for p in IMG_DIR.iterdir() if p.is_dir()]
    if not docs:
        print(f"Sem imagens em: {IMG_DIR} (corre 01_pdf_to_images.py)")
        return

    for doc in sorted(docs):
        ocr_text_path = OCR_DIR / f"{doc.name}.txt"
        if not ocr_text_path.exists():
            raise FileNotFoundError(
                f"Ficheiro OCR não encontrado para {doc.name}: {ocr_text_path}. "
                "Corre 02_ocr_paddle.py antes do método OCR + LLM."
            )

        print("OCR + LLM:", doc.name)
        page_payloads = build_page_payloads(doc, ocr_text_path)
        llm_data = call_llm(doc.name, page_payloads)
        save_outputs(doc.name, llm_data, page_payloads)


if __name__ == "__main__":
    main()
