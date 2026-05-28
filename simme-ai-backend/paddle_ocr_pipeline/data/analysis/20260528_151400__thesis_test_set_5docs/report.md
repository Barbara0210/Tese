# Analise comparativa dos metodos

Gerado em: 2026-05-28T15:14:00
Conjunto: `thesis_test_set_5docs`

## Resumo por metodo
| method_key | n_runs | avg_elapsed_seconds | avg_completeness_score | avg_schema_completeness_score | avg_table_extraction_score | avg_detected_tables | total_llm_conflicts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid_fast | 3 | 91.54 | 0.419 | 0.4 | 0.6667 |  | 0 |
| paddle_current | 4 | 38.17 | 0.7477 | 0.4167 | 0.25 |  | 0 |
| paddleocr_vl | 3 | 2.945 | 1 | 0.7333 | 0.5 |  | 0 |
| paddleocr_vl_llm | 1 | 247.4 | 1 | 1 | 0 | 4 | 0 |
| pdf_table | 2 | 1.081 | 0.2727 |  | 0 |  | 0 |

## Resumo por documento
| source_pdf | n_runs | best_schema_completeness_score | best_table_extraction_score | methods_run |
| --- | --- | --- | --- | --- |
| CITC_021_CORK SUPPLY PORTUGAL.pdf | 4 | 1 | 1 | ['hybrid_fast', 'paddle_current', 'paddleocr_vl', 'paddleocr_vl_llm'] |
| Dinamómetro EX.001 RED LION.pdf | 2 | 0.9 | 0.5 | ['paddle_current', 'paddleocr_vl'] |
| Extralab2G_025_GRUPO SOLAR DE SAMANIEGO SL.pdf | 1 | 0.75 | 0 | ['paddleocr_vl'] |
| Medcork_116_HEREDEROS DE TORRENT MIRANDA S.L..pdf | 3 | 0.6 | 1 | ['hybrid_fast', 'paddle_current', 'pdf_table'] |
| Paquimetro MITUTOYO ns B22034284 - SYMINGTON.pdf | 3 |  | 0 | ['hybrid_fast', 'paddle_current', 'pdf_table'] |

## Execucoes em falta
| source_pdf | method_key | status | notes |
| --- | --- | --- | --- |
| CITC_021_CORK SUPPLY PORTUGAL.pdf | pdf_table | missing | No archived run found for this document/method. |
| CITC_021_CORK SUPPLY PORTUGAL.pdf | ocr_llm | missing | No archived run found for this document/method. |
| Dinamómetro EX.001 RED LION.pdf | pdf_table | missing | No archived run found for this document/method. |
| Dinamómetro EX.001 RED LION.pdf | hybrid_fast | missing | No archived run found for this document/method. |
| Dinamómetro EX.001 RED LION.pdf | ocr_llm | missing | No archived run found for this document/method. |
| Dinamómetro EX.001 RED LION.pdf | paddleocr_vl_llm | missing | No archived run found for this document/method. |
| Extralab2G_025_GRUPO SOLAR DE SAMANIEGO SL.pdf | paddle_current | missing | No archived run found for this document/method. |
| Extralab2G_025_GRUPO SOLAR DE SAMANIEGO SL.pdf | pdf_table | missing | No archived run found for this document/method. |
| Extralab2G_025_GRUPO SOLAR DE SAMANIEGO SL.pdf | hybrid_fast | missing | No archived run found for this document/method. |
| Extralab2G_025_GRUPO SOLAR DE SAMANIEGO SL.pdf | ocr_llm | missing | No archived run found for this document/method. |
| Extralab2G_025_GRUPO SOLAR DE SAMANIEGO SL.pdf | paddleocr_vl_llm | missing | No archived run found for this document/method. |
| Medcork_116_HEREDEROS DE TORRENT MIRANDA S.L..pdf | ocr_llm | missing | No archived run found for this document/method. |
| Medcork_116_HEREDEROS DE TORRENT MIRANDA S.L..pdf | paddleocr_vl | missing | No archived run found for this document/method. |
| Medcork_116_HEREDEROS DE TORRENT MIRANDA S.L..pdf | paddleocr_vl_llm | missing | No archived run found for this document/method. |
| Paquimetro MITUTOYO ns B22034284 - SYMINGTON.pdf | ocr_llm | missing | No archived run found for this document/method. |
| Paquimetro MITUTOYO ns B22034284 - SYMINGTON.pdf | paddleocr_vl | missing | No archived run found for this document/method. |
| Paquimetro MITUTOYO ns B22034284 - SYMINGTON.pdf | paddleocr_vl_llm | missing | No archived run found for this document/method. |

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