# Analise comparativa dos metodos

Gerado em: 2026-05-28T17:18:32
Conjunto: `thesis_test_set_5docs`

## Resumo por metodo
| method_key | n_runs | avg_elapsed_seconds | avg_completeness_score | avg_schema_completeness_score | avg_table_extraction_score | avg_detected_tables | total_llm_conflicts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid_fast | 5 | 45.35 | 0.6797 | 0.46 | 0.6667 | 2 | 0 |
| ocr_llm | 5 | 306.3 | 1 | 0.91 | 0.6 | 3.4 | 31 |
| paddle_current | 5 | 42.46 | 0.9057 | 0.39 | 0.6 | 2.2 | 0 |
| paddleocr_vl | 5 | 0.5882 | 0.9635 | 0.65 | 0.4 | 2 | 0 |
| paddleocr_vl_llm | 5 | 321.7 | 1 | 0.89 | 0.4 | 3.2 | 46 |
| pdf_table | 5 | 0.8686 | 0 | 0.41 | 0 | 1.4 | 0 |

## Resumo por documento
| source_pdf | n_runs | best_schema_completeness_score | best_table_extraction_score | methods_run |
| --- | --- | --- | --- | --- |
| CITC_021_CORK SUPPLY PORTUGAL.pdf | 6 | 1 | 1 | ['hybrid_fast', 'ocr_llm', 'paddle_current', 'paddleocr_vl', 'paddleocr_vl_llm', 'pdf_table'] |
| Dinamómetro EX.001 RED LION.pdf | 6 | 1 | 0.5 | ['hybrid_fast', 'ocr_llm', 'paddle_current', 'paddleocr_vl', 'paddleocr_vl_llm', 'pdf_table'] |
| Extralab2G_025_GRUPO SOLAR DE SAMANIEGO SL.pdf | 6 | 1 | 1 | ['hybrid_fast', 'ocr_llm', 'paddle_current', 'paddleocr_vl', 'paddleocr_vl_llm', 'pdf_table'] |
| Medcork_116_HEREDEROS DE TORRENT MIRANDA S.L..pdf | 6 | 1 | 1 | ['hybrid_fast', 'ocr_llm', 'paddle_current', 'paddleocr_vl', 'paddleocr_vl_llm', 'pdf_table'] |
| Paquimetro MITUTOYO ns B22034284 - SYMINGTON.pdf | 6 | 0.75 | 0.5 | ['hybrid_fast', 'ocr_llm', 'paddle_current', 'paddleocr_vl', 'paddleocr_vl_llm', 'pdf_table'] |

## Execucoes em falta
_Sem dados._

## Notas para interpretacao
- `completeness_score` mede apenas campos considerados aplicaveis pelo parser.
- `schema_completeness_score` mede o preenchimento face ao schema fixo de 20 campos.
- `table_extraction_score` so e comparavel quando existe `instrument_type` com tabelas esperadas.
- `detected_tables` e `row_counts` ajudam a analisar tabelas extraidas mas ainda sem expectativa formal.
- `llm_conflicts` deve ser lido como sinal de risco: sugestoes do LLM que divergiram de valores OCR/VL ja preenchidos.

## Proximas analises qualitativas sugeridas
- Confirmar manualmente os campos onde o LLM gerou conflitos.
- Verificar se tabelas detectadas mas nao esperadas devem originar novas classes de tabela.
- Separar falhas de leitura OCR/VL de falhas de parsing/normalizacao.