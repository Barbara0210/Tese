from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parents[1]
INP = BASE / "data" / "images" / "pt_Folha de Verificação Medcork - Amorim De Sousa" / "page_01.png"
OUT = BASE / "data" / "images" / "pt_Folha de Verificação Medcork - Amorim De Sousa" / "page_01_1700.jpg"

MAX_SIDE = 1700  # <= 1800 é o objetivo

img = Image.open(INP).convert("RGB")
w, h = img.size

scale = min(1.0, MAX_SIDE / max(w, h))
if scale < 1.0:
    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

img.save(OUT, "JPEG", quality=92)
print("saved:", OUT)
print("size:", img.size)