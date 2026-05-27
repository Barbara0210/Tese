# PaddleOCR-VL no Colab

Este fluxo usa o `PaddleOCR-VL-1.5-0.9B` no Google Colab para extrair páginas
PNG dos certificados e depois importa o `run_summary.json` para o backend como
um método experimental chamado `paddleocr_vl`.

## Quando usar

Usa este método quando quiseres testar a abordagem multimodal gratuita sem
instalar o PaddleOCR-VL localmente. O modelo corre no Colab com GPU e o projeto
local apenas converte o resultado para os mesmos artefactos dos outros métodos:

- `data/parsed/<documento>.json`
- `data/tables/<documento>_tables.json`
- `data/sections/<documento>_sections.json`
- `data/metrics/phase1_metrics.json`

## Pasta recomendada no Google Drive

Cria esta estrutura no Drive:

```text
MyDrive/
  paddleocr_vl_poc/
    input/
    output/
```

Dentro de `input/`, coloca as pastas de páginas PNG já geradas pelo projeto:

```text
input/
  CITC_021_CORK SUPPLY PORTUGAL/
    page_01.png
    page_02.png
    page_03.png
    page_04.png
```

## Como preparar as páginas localmente

1. Coloca os PDFs de teste em:

```text
C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline\data\raw_pdfs
```

2. Gera as páginas:

```powershell
python .\src\01_pdf_to_images.py
```

3. Copia para o Google Drive apenas as pastas que queres testar primeiro.

## Colab

Usa o conteúdo de:

```text
colab/paddleocr_vl_poc_colab.txt
```

Antes de correr, ativa GPU no Colab:

```text
Runtime > Change runtime type > T4 GPU
```

O ficheiro faz:

- montagem do Drive
- instalação controlada das dependências
- execução de `paddleocr doc_parser` para todas as pastas dentro de `input/`
- gravação de `output/<DOC_NAME>/run_summary.json` para cada documento
- gravação de `output/all_run_summaries.json` com o resumo global

Por defeito usa `RUN_BY_DOCUMENT = True`, ou seja, tenta chamar o
`paddleocr doc_parser` uma vez por pasta/documento. Isto evita carregar o modelo
uma vez por página e tende a ser bastante mais rápido. Se o CLI não aceitar a
pasta no ambiente do Colab, o script faz fallback automático para o modo antigo,
página a página.

Nota: o `paddleocr doc_parser` escreve o resultado útil no `stderr`, por isso o
`run_summary.json` guarda `stdout` e `stderr`.

## Importar para o projeto

Depois de o Colab terminar, podes usar o frontend diretamente:

```text
1. Upload do PDF correspondente.
2. Escolher o método PaddleOCR-VL.
3. Upload do ficheiro output/<DOC_NAME>/run_summary.json.
4. Enviar e Processar.
```

O backend copia automaticamente esse JSON para:

```text
C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline\data\paddleocr_vl\<DOC_NAME>\run_summary.json
```

O backend vai correr:

```text
src/15_import_paddleocr_vl.py
src/06_metrics_phase1.py
```

## Observações atuais

No certificado `CITC_021_CORK SUPPLY PORTUGAL`, o método já conseguiu extrair as
4 páginas e recuperar tabelas que o OCR clássico tinha dificuldade em ler. Ainda
há pequenos erros de OCR e algumas tabelas precisam de normalização, por isso o
script de importação conserva também as células originais em `raw_cells`.
