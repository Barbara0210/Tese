from pathlib import Path
from ollama import chat

MODEL = "glm-ocr:q8_0"

BASE = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    IMG = BASE / "data" / "images" / "pt_Folha de Verificação Medcork - Amorim De Sousa" / "page_01_rgb.jpg"
    print("Imagem:", IMG)

    r1 = chat(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": "Text Recognition:",
            "images": [str(IMG)]
        }]
    )
    print("\n=== TEXT ===\n")
    print(r1["message"]["content"])

    r2 = chat(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": "Table Recognition:",
            "images": [str(IMG)]
        }]
    )
    print("\n=== TABLE ===\n")
    print(r2["message"]["content"])