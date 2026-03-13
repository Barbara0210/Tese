Fase 1 — Step 2 (CATIM + Paquímetro): parser melhorado + métricas
===============================================================

O que melhora
-------------
1) Ignora anexos/páginas extra usando "PÁGINA X DE Y"
2) Extrai Cliente (nome + morada)
3) Extrai datas (emissão e calibração)
4) Extrai tabelas de resultados E / S / L (heurística robusta a OCR)
5) Gera métricas por documento (coverage + completeness score)

Como usar
---------
Substitui estes ficheiros na tua pasta:
- ocr_pipeline/src/04_parse_iso17025_min.py  (novo)
- adiciona ocr_pipeline/src/05_metrics_phase1.py

Depois corre:
python .\ocr_pipeline\src\04_parse_iso17025_min.py
python .\ocr_pipeline\src\05_metrics_phase1.py

Outputs
-------
- JSON por doc: ocr_pipeline/data/parsed/<doc_id>.json
- Métricas:     ocr_pipeline/data/parsed/metrics_phase1.json
