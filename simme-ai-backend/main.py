import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import easyocr
import re
from typing import List, Dict

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
def extract_fields_from_lines(lines: List[Dict]) -> Dict:
    """
    Recebe a lista de linhas do OCR e tenta extrair campos importantes
    usando regex e heurísticas simples.
    """
    full_text = " ".join(line["text"] for line in lines)

    fields: Dict[str, str] = {}

    # 1) Número do certificado (ex: M0517/14)
    match_cert = re.search(r"\b([A-Z]?\d{3,5}/\d{2})\b", full_text)
    if match_cert:
        fields["certificate_number"] = match_cert.group(1)

    # 2) Data (AAAA-MM-DD)
    match_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", full_text)
    if match_date:
        fields["date"] = match_date.group(1)

    # 3) Cliente (linha onde aparece PRECERAM ou semelhante)
    for line in lines:
        if "PRECERAM" in line["text"].upper():
            fields["client_name"] = line["text"]
            break

    # 4) Tipo de equipamento (Balança)
    for line in lines:
        if "BALANÇA" in line["text"].upper():
            fields["equipment_type"] = "Balança"
            break

    # 5) Modelo – lidar com "Modelo" mal lido (ex: "Mcdelo 150")
    for line in lines:
        text_upper = line["text"].upper()
        if "MODELO" in text_upper or "MCDelo".upper() in text_upper or "MCDOLO" in text_upper or "MCD" in text_upper:
            # tentar apanhar um número no fim da linha
            m_num = re.search(r"(\d+)", line["text"])
            if m_num:
                fields["model"] = m_num.group(1)
            else:
                fields["model"] = line["text"]
            break

    # 6) Nº de série – linha "No serie" + linha seguinte com o valor
    for idx, line in enumerate(lines):
        if "NO SERIE" in line["text"].upper() or "Nº SERIE" in line["text"].upper():
            # tentar apanhar número na mesma linha
            m_same = re.search(r"(?:SERIE)\s*[:\-]?\s*([A-Za-z0-9<>]+)", line["text"], re.IGNORECASE)
            if m_same:
                fields["serial_number"] = m_same.group(1)
            # senão, usar a próxima linha como nº de série (como no teu exemplo)
            elif idx + 1 < len(lines):
                possible_sn = lines[idx + 1]["text"]
                # retirar lixo tipo "<"
                possible_sn = re.sub(r"[^A-Za-z0-9]", "", possible_sn)
                fields["serial_number"] = possible_sn
            break

    return fields


app = FastAPI(
    title="SIMME AI Backend",
    description="API para extração automática de dados de certificados de calibração",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar OCR (português + inglês, sem GPU)
ocr = easyocr.Reader(['pt', 'en'], gpu=False)


@app.get("/")
def read_root():
    return {"message": "SIMME AI Backend a funcionar 🚀"}


@app.post("/upload")
async def upload_certificate(file: UploadFile = File(...)):
    # Por agora vamos suportar apenas imagens (png/jpg/jpeg)
    if file.content_type not in ["image/png", "image/jpeg", "image/jpg"]:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de ficheiro não suportado para já: {file.content_type}. "
                   f"Envia uma imagem (PNG ou JPG) para testar o OCR."
        )

    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    # Guardar a imagem em disco
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Correr OCR com EasyOCR
    try:
        result = ocr.readtext(file_path, detail=1)  # detail=1 devolve bbox, texto, confiança
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao executar OCR: {str(e)}")

    # Transformar o resultado numa lista de linhas com texto + confiança
    lines = []
    for bbox, text, conf in result:
        lines.append({
            "text": text,
            "confidence": float(conf),
        })

    extracted_fields = extract_fields_from_lines(lines)

    return {
        "filename": file.filename,
        "saved_as": unique_name,
        "lines": lines,
        "extracted_fields": extracted_fields,
    }
