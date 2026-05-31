# Workflow de avaliacao para a tese

Este workflow serve para avaliar os 5 certificados escolhidos com todos os
metodos e guardar resultados comparaveis para o capitulo da tese.

## Conjunto fixo de teste

Manifest:

```text
config/thesis_test_set_5docs.json
```

Certificados:

- `CITC_021_CORK SUPPLY PORTUGAL.pdf`
- `Dinamómetro EX.001 RED LION.pdf`
- `Extralab2G_025_GRUPO SOLAR DE SAMANIEGO SL.pdf`
- `Medcork_116_HEREDEROS DE TORRENT MIRANDA S.L..pdf`
- `Paquimetro MITUTOYO ns B22034284 - SYMINGTON.pdf`

## Metodos a testar

- `paddle_current`
- `pdf_table`
- `hybrid_fast`
- `ocr_llm`
- `paddleocr_vl`
- `paddleocr_vl_llm`

Notas:

- `paddle_current`, `pdf_table`, `hybrid_fast` e `ocr_llm` precisam apenas do PDF.
- `paddleocr_vl` e `paddleocr_vl_llm` precisam do PDF e do `run_summary.json` gerado no Colab.
- Neste momento existem `run_summary.json` locais para `CITC`, `Dinamómetro` e `Extralab`.
- Para `Medcork` e `Paquimetro`, e necessario gerar primeiro os respetivos `run_summary.json` no Colab se quisermos testar os metodos VL.

## Como executar pelo frontend

1. Arrancar o backend.
2. Arrancar o frontend.
3. Para cada PDF, correr cada metodo.
4. Para metodos `PaddleOCR-VL` e `PaddleOCR-VL + LLM`, anexar tambem o `run_summary.json`.
5. No fim de cada execucao, o backend arquiva automaticamente os artefactos em:

```text
backend/archives/<file_id>__<method>__<documento>/
```

Tambem sao atualizados:

```text
backend/method_runs_summary.json
backend/method_comparison_summary.json
```

## Exportar tabelas para analise

Depois de executares os metodos, correr:

```powershell
python scripts/export_thesis_analysis.py
```

Isto cria uma pasta em:

```text
data/analysis/<timestamp>__thesis_test_set_5docs/
```

Com os ficheiros:

- `summary.json`: resumo completo estruturado;
- `runs.csv`: uma linha por documento/metodo;
- `fields.csv`: presenca de cada campo por documento/metodo;
- `tables.csv`: presenca/linhas de cada tabela por documento/metodo;
- `report.md`: relatorio Markdown pronto para apoiar a escrita da tese.

## Como ler as metricas

- `completeness_score`: completude apenas dos campos considerados aplicaveis.
- `schema_completeness_score`: preenchimento face ao schema fixo de 20 campos.
- `table_extraction_score`: recuperacao das tabelas esperadas para o tipo de instrumento.
- `detected_tables`: grupos tabulares encontrados, mesmo que ainda nao exista expectativa formal.
- `row_counts`: numero de linhas por tabela extraida.
- `llm_conflicts`: sugestoes do LLM que divergiram de valores ja preenchidos por OCR/VL.

## Avaliar correcao com gold set manual

Para separar campos simplesmente preenchidos de campos realmente corretos, foi
criado um gold set manual compacto:

```text
data/gold/thesis_test_set_5docs_gold.json
```

Depois de todos os metodos estarem arquivados, correr:

```powershell
python scripts/evaluate_gold_set.py
```

Isto cria uma pasta em:

```text
data/evaluation/<timestamp>__thesis_gold_5docs/
```

Com os ficheiros:

- `gold_summary.json`: resumo estruturado;
- `gold_runs.csv`: uma linha por documento/metodo com preenchimento e correcao;
- `gold_fields.csv`: comparacao campo a campo;
- `gold_tables.csv`: comparacao tabela a tabela;
- `gold_report.md`: resumo Markdown para apoiar a escrita da tese.

Metricas principais:

- `field_fill_rate_on_gold`: proporcao dos campos gold em que o metodo devolveu algum valor;
- `field_accuracy`: proporcao dos campos gold em que o valor devolvido coincide com o gold;
- `field_precision_when_filled`: dos campos preenchidos, quantos estavam corretos;
- `table_accuracy`: proporcao das tabelas gold encontradas com pelo menos o numero minimo de linhas definido.

## O que observar qualitativamente

- Se o metodo leu corretamente o texto mas falhou no parser.
- Se as tabelas foram detetadas mas nao classificadas no tipo certo.
- Se o LLM preencheu campos vazios com utilidade ou sugeriu valores perigosos.
- Se o metodo e robusto a layouts densos, rodapes, imagens, formulas e tabelas longas.
- Se o tempo de execucao e aceitavel para uso pratico.
