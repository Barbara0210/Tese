# YOLO Dataset Base

## Objetivo

O modelo YOLO deste projeto nao vai ler texto. Ele so precisa de localizar regioes uteis do certificado para depois o PaddleOCR fazer OCR nessas zonas.

Classes:

- `metadata_block`: cabecalho com data, numero do certificado, pagina e, quando visivel, nome do laboratorio
- `customer_block`: bloco do cliente com nome e morada
- `equipment_block`: bloco do equipamento calibrado com designacao, marca, modelo, serie, indicacao, resolucao, alcance, etc.
- `work_conditions_block`: bloco de local, temperatura, humidade e anexo tecnico
- `reference_block`: bloco de descricao normativa, normas e procedimento
- `results_table`: tabelas de resultados de calibracao/medicao

## Paginas mantidas

Foram mantidas apenas paginas com informacao util para estas classes. Foram excluidas paginas de simbologia, cartas/notas, anexos explicativos e paginas finais sem blocos alvo.

- `CITC_021_CORK SUPPLY PORTUGAL`: paginas `1, 2`
- `CITC_023_FUNDACION INSTITUT CATALA DEL SURO ICSURO (1)`: paginas `1, 2, 3`
- `CORKINSERT_001_TREFINOS`: paginas `1, 2`
- `ExtraLab_012_BERLIN PACKAGING GREECE`: paginas `1, 2`
- `Medcork_103_BOUCHONS TRESCASES S.A 2026 (1)`: paginas `1, 2`
- `Medcork_115_Francisco Oller 2026`: paginas `1, 2`
- `Medcork_116_HEREDEROS DE TORRENT MIRANDA S.L`: paginas `1, 2`
- `Paquimetro MITUTOYO ns B22034284 - SYMINGTON`: paginas `1, 2, 3`
- `Paquimetro MITUTOYO sn B22268348 - M.A. SILVA (1)`: paginas `1, 2, 3`
- `TorsiLab_003_RELVAS II (1)`: paginas `1, 2`

## Como pensar os blocos

### Paginas 1

Normalmente desenha-se:

- uma caixa `metadata_block` no topo, apanhando a linha da data, certificado e pagina
- uma caixa `customer_block` a volta do bloco `CLIENTE`
- uma caixa `equipment_block` a volta do bloco `EQUIPAMENTO CALIBRADO` ou `DESCRICAO` quando esse bloco contem os campos do equipamento
- uma caixa `work_conditions_block` a volta do bloco `CONDICOES DO TRABALHO REALIZADO`
- uma caixa `reference_block` a volta do bloco `DESCRICAO` quando ele contem normas e procedimento

### Paginas de resultados

Normalmente desenha-se:

- uma ou mais caixas `results_table` a volta das tabelas principais

Se a pagina tiver graficos, figuras ou caixas ambientais, isso so interessa se fizer parte da area visual da tabela principal. Caso contrario, nao e preciso criar uma classe nova.

## Val atual

O conjunto de validacao foi escolhido manualmente para ter mistura de:

- paginas 1 com blocos administrativos
- paginas de resultados
- layouts diferentes

Os nomes exatos estao em `data/yolo/regions/curated_pages.json`.
