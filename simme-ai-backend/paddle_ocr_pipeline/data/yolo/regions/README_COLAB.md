# YOLO Regions Training

Este dataset serve para treinar o detector do pipeline `hybrid_fast`.

## Objetivo

O YOLO deve detetar regiões do certificado, não texto OCR.

Classes sugeridas:

- `metadata_block`
- `customer_block`
- `equipment_block`
- `work_conditions_block`
- `reference_block`
- `results_table`

## Estrutura esperada

```text
yolo_regions/
  images/
    train/
    val/
  labels/
    train/
    val/
  dataset.yaml
```

## Formato das labels

Um ficheiro `.txt` por imagem, com uma linha por caixa:

```text
class_id x_center y_center width height
```

Todos os valores geométricos são normalizados entre `0` e `1`.

Exemplo:

```text
5 0.512500 0.731250 0.845000 0.180000
1 0.500000 0.215000 0.910000 0.120000
```

## Fluxo recomendado

1. Exportar páginas dos PDFs como imagens.
2. Anotar as imagens numa ferramenta compatível com YOLO.
3. Dividir em `train` e `val`.
4. Treinar no Google Colab.
5. Descarregar o melhor peso e colocar em:

```text
paddle_ocr_pipeline/data/models/yolo_regions.pt
```

## Anotação mínima para começar

Se quiseres iterar mais rápido, começa só com:

- `customer_block`
- `equipment_block`
- `results_table`

Depois adicionas as outras classes.
