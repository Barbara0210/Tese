OCR Phase 1 (ISO/IEC 17025 essentials): laboratório + equipamento + medições
==========================================================================

Objetivo
--------
Gerar, a partir de PDFs de certificados (ex.: paquímetro), um JSON por documento com:
- informação de cabeçalho (nº certificado, data, páginas)
- informação do laboratório (nome/identificação)
- identificação do equipamento (designação, marca, modelo, nº de série, alcance/resolução)
- medições (tabela de resultados quando existir)

Pré-requisitos (Windows)
------------------------
1) Ativar venv do teu backend:
   .\venv\Scripts\Activate.ps1

2) Instalar dependências python (no venv):
   pip install -r .\ocr_pipeline\requirements.txt

3) Poppler (para pdf2image):
   - Extrair para C:\poppler
   - PATH: C:\poppler\Library\bin
   Teste: pdfinfo -v

4) Ollama + modelo:
   - Instalar Ollama
   - ollama pull glm-ocr

Pasta de trabalho
-----------------
- Coloca os PDFs em: ocr_pipeline\data\pdfs\

Execução (pipeline simples)
---------------------------
1) Converter PDFs em imagens PNG:
   python .\ocr_pipeline\src\01_pdf_to_images.py

2) Preprocess (evitar crashes do glm-ocr):
   - converte para JPG RGB e limita max side (default 1700)
   python .\ocr_pipeline\src\02_preprocess_pages.py

3) OCR (Text Recognition) por página usando CLI do Ollama:
   python .\ocr_pipeline\src\03_ocr_text_cli.py

4) Parse para JSON (campos ISO 17025 essenciais + medições):
   python .\ocr_pipeline\src\04_parse_iso17025_min.py

Saídas
------
- OCR text: ocr_pipeline\data\ocr_text\<doc_id>.txt
- JSON:      ocr_pipeline\data\parsed\<doc_id>.json

Notas
-----
- Para documentos complexos (Medcork/Força), o ideal é segmentar/cropar por secções.
  Nesta Fase 1 focamos em "simples" (ex.: paquímetro) e criamos base sólida.
