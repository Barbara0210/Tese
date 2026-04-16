# Hybrid Fast Next Steps

## Caminho recomendado

1. Preparar dataset de imagens localmente.
2. Anotar as regiões em formato YOLO.
3. Treinar no Google Colab.
4. Descarregar `best.pt`.
5. Guardar o ficheiro em:

```text
C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline\data\models\yolo_regions.pt
```

6. Voltar a correr o método `hybrid_fast`.

## Comandos locais úteis

Preparar imagens para anotação:

```powershell
python C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline\scripts\prepare_yolo_dataset.py
```

Gerar texto-base para o Colab:

```powershell
python C:\Projetos\Tese\simme-ai-backend\paddle_ocr_pipeline\colab\train_yolo_regions_colab.py
```

## Nota

Se ainda não houver `yolo_regions.pt`, o pipeline híbrido usa fallback `full_page`.
Isso permite testar o fluxo sem bloquear o desenvolvimento.
