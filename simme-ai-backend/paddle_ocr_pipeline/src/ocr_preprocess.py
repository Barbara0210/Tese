from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter, ImageOps


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """
    Remove parte do ruído de fundo/light watermark e reforça o texto.
    Mantém a imagem em tons de cinzento para não destruir linhas/tabelas.
    """
    gray = ImageOps.grayscale(image)

    # Estima o fundo com blur largo e "achata" a iluminação/watermark.
    background = gray.filter(ImageFilter.GaussianBlur(radius=14))

    gray_arr = np.asarray(gray, dtype=np.float32)
    bg_arr = np.asarray(background, dtype=np.float32)
    bg_arr = np.maximum(bg_arr, 1.0)

    flattened = (gray_arr / bg_arr) * 245.0
    flattened = np.clip(flattened, 0, 255).astype(np.uint8)

    cleaned = Image.fromarray(flattened, mode="L")
    cleaned = ImageOps.autocontrast(cleaned, cutoff=1)
    cleaned = cleaned.point(lambda px: 255 if px > 180 else int(px * 0.45))
    cleaned = cleaned.filter(ImageFilter.MedianFilter(size=3))
    return cleaned
