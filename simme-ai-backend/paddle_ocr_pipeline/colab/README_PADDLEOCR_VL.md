# PaddleOCR-VL no Colab

Este teste serve para validar, de forma controlada, se o `PaddleOCR-VL-0.9B`
consegue interpretar melhor páginas de certificados do que os métodos já
existentes no projeto.

## Objetivo desta fase

Nesta fase não vamos integrar já o modelo no backend principal.

Primeiro queremos confirmar três pontos:

1. O modelo consegue ler páginas reais dos teus certificados.
2. O output bruto faz sentido para campos e tabelas.
3. Vale a pena avançar para integração como novo método experimental.

## Pasta recomendada no Google Drive

Cria esta estrutura no teu Drive:

```text
MyDrive/
  paddleocr_vl_poc/
    input/
    output/
```

Dentro de `input/`, coloca uma ou mais pastas de páginas PNG já geradas pelo
projeto, por exemplo:

```text
input/
  CITC_021_CORK SUPPLY PORTUGAL/
    page_01.png
    page_02.png
  Medcork_116_HEREDEROS DE TORRENT MIRANDA S.L/
    page_01.png
    page_02.png
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

Recomendação inicial:

- `CITC_021_CORK SUPPLY PORTUGAL`
- `Manómetro analógico_CorkSupply Itália_038`
- `Paquimetro MITUTOYO ns B22034284 - SYMINGTON`
- `Medcork_116_HEREDEROS DE TORRENT MIRANDA S.L`

## Ordem certa de trabalho

1. Testar 1 ou 2 páginas no Colab.
2. Inspecionar o output bruto do `PaddleOCR-VL`.
3. Só depois decidir como mapear esse output para o JSON do backend.

## Ficheiro para colar no Colab

Usa o conteúdo de:

```text
colab/paddleocr_vl_poc_colab.txt
```

Esse ficheiro está pensado para:

- montar o Drive
- instalar o necessário
- percorrer uma pasta de páginas PNG
- correr `paddleocr doc_parser`
- guardar outputs por página em `output/`

## Nota importante

Segundo a documentação oficial, o melhor é usar o pipeline completo do
`PaddleOCR-VL` e não apenas o componente VLM isolado via `transformers`, porque
o modelo sozinho não equivale ao parsing documental completo.

## Próximo passo depois desta prova de conceito

Se o output parecer promissor, o próximo passo será:

1. criar um script em `src/` para chamar o modelo
2. converter os resultados para o schema do teu backend
3. registar um novo método experimental no sistema
