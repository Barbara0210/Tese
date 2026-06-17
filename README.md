# SIMME AI - Extração Inteligente de Certificados de Calibração

Protótipo experimental desenvolvido no âmbito de uma dissertação de mestrado para extração automática de informação a partir de certificados de calibração heterogéneos.

O projeto compara diferentes estratégias de extração documental, desde OCR clássico e extração direta de tabelas em PDF até abordagens híbridas com deteção visual de regiões, PaddleOCR-VL e normalização semântica com LLM local via Ollama.

## Objetivo

O objetivo principal é avaliar que métodos são mais adequados para extrair dados metrológicos relevantes de certificados de calibração, com vista a uma futura integração no contexto do sistema SIMME.

A solução permite:

- carregar certificados PDF;
- selecionar diferentes pipelines de extração;
- extrair campos documentais, tabelas e métricas;
- visualizar resultados no frontend;
- arquivar automaticamente cada execução;
- comparar métodos com métricas automáticas e avaliação manual por gold set.

## Métodos Implementados

| Método | Descrição |
| --- | --- |
| `paddle_current` | Baseline com PDF convertido em imagem, OCR de página completa com PaddleOCR, segmentação e parsers heurísticos. |
| `pdf_table` | Extração direta de tabelas do PDF com `pdfplumber`. |
| `hybrid_fast` | Deteção de regiões documentais com YOLO seguida de OCR localizado com PaddleOCR. |
| `ocr_llm` | OCR clássico com PaddleOCR seguido de normalização semântica por LLM local via Ollama. |
| `paddleocr_vl` | Importação dos resultados multimodais produzidos pelo PaddleOCR-VL no Google Colab. |
| `paddleocr_vl_llm` | PaddleOCR-VL combinado com normalização semântica por LLM local e validação por evidência. |

## Arquitetura Geral

Fluxo simplificado:

```text
PDF -> Backend FastAPI -> Pipeline selecionado -> JSON estruturado -> Frontend React
```

Componentes principais:

- `backend/`: API FastAPI, gestão de uploads, execução dos pipelines e arquivo de resultados.
- `frontend/`: interface React/Vite para upload, seleção de método e visualização de resultados.
- `src/`: scripts de processamento documental.
- `data/`: diretórios de trabalho para PDFs, imagens, OCR, tabelas, métricas e resultados intermédios.
- `scripts/`: scripts auxiliares para preparação, análise e avaliação.
- `colab/`: scripts e documentação para execução do PaddleOCR-VL no Google Colab.
- `docs/`: documentação técnica do workflow experimental.

## Estrutura Relevante

```text
simme-ai-backend/
  paddle_ocr_pipeline/
    backend/
      app.py
      routes/
      services/
      archives/
    frontend/
      src/
      package.json
    src/
      01_pdf_to_images.py
      02_ocr_paddle.py
      03_segment_sections.py
      04_parse_fields.py
      05_parse_tables.py
      06_metrics_phase1.py
      10_extract_tables_pdfplumber.py
      11_detect_regions_yolo.py
      12_ocr_regions_paddle.py
      13_merge_regions_to_text.py
      15_import_paddleocr_vl.py
      16_normalize_with_ollama.py
    scripts/
      export_thesis_analysis.py
      evaluate_gold_set.py
    colab/
    docs/
    requirements.txt
```

## Requisitos

Ambiente utilizado durante o desenvolvimento:

- Windows 10/11
- Miniconda
- Python 3.10
- Node.js
- Ollama, para os métodos com LLM
- Google Colab, para execução do PaddleOCR-VL

Principais dependências Python:

- `paddleocr==2.7.0.3`
- `paddlepaddle==2.6.2`
- `pdfplumber==0.11.5`
- `ultralytics==8.3.146`
- `fastapi==0.115.0`
- `uvicorn==0.30.6`

Principais dependências frontend:

- React
- Vite
- Axios

## Instalação do Backend

Abrir Anaconda Prompt ou CMD:

```cmd
cd C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline
conda activate paddle_tese
pip install -r requirements.txt
```

Se o comando `conda` não estiver disponível no CMD, usar o Anaconda Prompt ou ativar diretamente o ambiente:

```cmd
C:\Users\barbaramartins\AppData\Local\miniconda3\Scripts\activate.bat paddle_tese
```

## Execução do Backend

```cmd
cd C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline
conda activate paddle_tese
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Verificar se a API está ativa:

```text
http://127.0.0.1:8000/health
```

Documentação interativa:

```text
http://127.0.0.1:8000/docs
```

## Instalação e Execução do Frontend

Num segundo terminal:

```cmd
cd C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline\frontend
npm install
npm run dev
```

Abrir o endereço apresentado pelo Vite, normalmente:

```text
http://localhost:5173
```

## Configuração do Ollama

O Ollama é necessário para os métodos:

- `ocr_llm`
- `paddleocr_vl_llm`

Instalar o modelo usado no projeto:

```cmd
ollama pull qwen3:4b
```

Confirmar modelos disponíveis:

```cmd
ollama list
```

Configuração recomendada antes de iniciar o backend:

```cmd
set OLLAMA_OCR_LLM_MODEL=qwen3:4b
set OLLAMA_TIMEOUT_SECONDS=600
set OLLAMA_CONTEXT_CHAR_LIMIT=12000
```

Se estiver a usar PowerShell:

```powershell
$env:OLLAMA_OCR_LLM_MODEL = "qwen3:4b"
$env:OLLAMA_TIMEOUT_SECONDS = "600"
$env:OLLAMA_CONTEXT_CHAR_LIMIT = "12000"
```

## PaddleOCR-VL no Google Colab

Os métodos `paddleocr_vl` e `paddleocr_vl_llm` exigem um ficheiro `run_summary.json` gerado previamente no Google Colab.

Fluxo resumido:

1. Converter os PDFs em imagens organizadas por documento.
2. Executar PaddleOCR-VL no Colab com GPU ativa.
3. Gerar um `run_summary.json` por documento.
4. No frontend, submeter o PDF e o respetivo `run_summary.json`.
5. O backend importa esse resumo através do script `15_import_paddleocr_vl.py`.

Documentação relacionada:

```text
simme-ai-backend/paddle_ocr_pipeline/colab/
```

## Execução dos Métodos

No frontend:

1. Carregar o PDF.
2. Selecionar o método.
3. Se for PaddleOCR-VL, carregar também o `run_summary.json`.
4. Clicar em `Enviar e Processar`.
5. Consultar campos, tabelas, métricas e JSON bruto.

Métodos que precisam apenas do PDF:

```text
paddle_current
pdf_table
hybrid_fast
ocr_llm
```

Métodos que precisam do PDF e do `run_summary.json`:

```text
paddleocr_vl
paddleocr_vl_llm
```

## Arquivo de Execuções

Cada execução é arquivada automaticamente em:

```text
simme-ai-backend/paddle_ocr_pipeline/backend/archives/
```

Cada pasta de arquivo pode conter:

- PDF submetido;
- `result.json`;
- campos extraídos;
- tabelas extraídas;
- métricas;
- logs;
- artefactos intermédios;
- outputs LLM, quando aplicável.

## Avaliação e Relatórios

Depois de executar os métodos, é possível exportar a análise comparativa:

```cmd
cd C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline
conda activate paddle_tese
python scripts\export_thesis_analysis.py
```

Avaliação com gold set manual:

```cmd
python scripts\evaluate_gold_set.py
```

Os resultados são guardados em:

```text
data/analysis/
data/evaluation/
```

## Gold Set

Foi criado um gold set manual para cinco certificados representativos. Este conjunto permite distinguir:

- campos apenas preenchidos;
- campos efetivamente corretos;
- precisão quando o método preenche;
- correção de tabelas;
- acerto do tipo de instrumento.

Ficheiro principal:

```text
data/gold/thesis_test_set_5docs_gold.json
```

## YOLO e Label Studio

O método `hybrid_fast` usa um modelo YOLO treinado para detetar regiões documentais, como:

- `metadata_block`
- `customer_block`
- `equipment_block`
- `results_table`
- `standard_equipment_block`
- `calibration_date_block`

O dataset foi anotado manualmente no Label Studio e treinado com Ultralytics YOLO no Google Colab.

Configuração de treino utilizada:

```python
from ultralytics import YOLO

model = YOLO("yolo11n.pt")
results = model.train(
    data="/content/yolo_regions/dataset.yaml",
    epochs=20,
    imgsz=1280,
    batch=4,
    project="/content/drive/MyDrive/yolo_runs",
    name="regions_v2_test"
)
```

## Notas Sobre Dados Sensíveis

Este projeto trabalha com certificados reais de calibração. Antes de tornar o repositório público ou partilhá-lo externamente, confirmar se existem dados sensíveis em:

```text
data/
backend/archives/
uploads/
prints/
exports/
```

Recomenda-se não versionar certificados reais, outputs com dados de clientes ou arquivos completos de execução quando estes contêm informação confidencial.

## Comandos Rápidos

Backend:

```cmd
cd C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline
conda activate paddle_tese
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```cmd
cd C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline\frontend
npm run dev
```

Ollama:

```cmd
ollama list
ollama pull qwen3:4b
```

Exportar análise:

```cmd
cd C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline
conda activate paddle_tese
python scripts\export_thesis_analysis.py
python scripts\evaluate_gold_set.py
```

## Estado do Projeto

Protótipo experimental para dissertação. O foco principal é comparação metodológica, rastreabilidade dos resultados e análise da viabilidade de integração futura com o SIMME.

## Licença

Projeto académico. Definir a licença antes de publicação externa.

