from paddleocr import PaddleOCR
from pathlib import Path
import json

img = Path(r".\ocr_pipeline\data\preprocessed\Paquimetro MITUTOYO sn B22268348 - M.A. SILVA\page_01.png")

ocr = PaddleOCR(
    lang="latin",                 # <- muda já para latin
    use_textline_orientation=True,
    enable_mkldnn=False
)

res = ocr.ocr(str(img))
print("TYPE:", type(res))
print("LEN:", len(res) if hasattr(res, "__len__") else None)
print("RES:", res)

# tenta contar linhas
n = 0
try:
    if res and isinstance(res, list):
        # formatos comuns:
        # [ [ [box, (text, score)], ... ] ]
        if len(res) > 0 and isinstance(res[0], list):
            n = len(res[0])
        else:
            n = len(res)
except:
    pass
print("N_LINES_GUESS:", n)