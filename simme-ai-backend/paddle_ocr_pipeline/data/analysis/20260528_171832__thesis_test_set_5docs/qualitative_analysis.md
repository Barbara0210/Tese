# Análise qualitativa dos 5 certificados

Gerado a partir das execuções arquivadas em `backend/archives` e da exportação
`20260528_171832__thesis_test_set_5docs`.

## 1. Leitura geral dos resultados

Foram avaliados 5 certificados com 6 métodos:

- `paddle_current`
- `pdf_table`
- `hybrid_fast`
- `ocr_llm`
- `paddleocr_vl`
- `paddleocr_vl_llm`

As métricas agregadas mostram um padrão claro:

| Método | Tempo médio (s) | Completude aplicável média | Completude estrita média | Score tabular médio | Conflitos LLM |
| --- | ---: | ---: | ---: | ---: | ---: |
| `pdf_table` | 0.87 | 0.00 | 0.41 | 0.00 | 0 |
| `paddleocr_vl` | 0.59* | 0.96 | 0.65 | 0.40 | 0 |
| `paddle_current` | 42.46 | 0.91 | 0.39 | 0.60 | 0 |
| `hybrid_fast` | 45.35 | 0.68 | 0.46 | 0.67 | 0 |
| `ocr_llm` | 306.30 | 1.00 | 0.91 | 0.60 | 31 |
| `paddleocr_vl_llm` | 321.70 | 1.00 | 0.89 | 0.40 | 46 |

\* No caso de `paddleocr_vl`, este tempo corresponde apenas à importação local
do `run_summary.json`; o tempo de inferência no Colab deve ser analisado à parte.

À primeira vista, os métodos com LLM apresentam as métricas de completude mais
altas. No entanto, a análise dos conflitos mostra que essas métricas podem estar
inflacionadas por sugestões sem suporte documental. O LLM é útil como camada
auxiliar, mas não deve ser tratado como fonte principal de verdade.

## 2. Análise por método

### `pdf_table`

Foi o método mais rápido, mas o menos robusto. Extraiu algumas tabelas genéricas
em documentos digitais, como `Dinamómetro`, `Extralab` e `Medcork`, mas falhou
na interpretação semântica. Por isso, o `table_extraction_score` ficou a zero em
todos os documentos.

Principais falhas:

- Não recupera bem campos fora de tabelas formais.
- Produz `generic_table_*`, mas não converte para tabelas esperadas.
- Em documentos com estrutura visual ou OCR implícito, fica quase sem saída.

Boa utilização:

- Método auxiliar para confirmar se o PDF tem tabelas digitais aproveitáveis.
- Não deve ser método principal.

### `paddle_current`

Teve bom desempenho em documentos para os quais os parsers já estavam mais
adaptados, como `Extralab`, `Medcork` e `CITC`. Conseguiu extrair tabelas de
força e tabelas genéricas em alguns casos. Contudo, a completude estrita média
foi baixa, porque muitos campos do schema fixo ficaram vazios.

Principais acertos:

- `CITC`: extraiu tabelas de força e erros relativos.
- `Extralab`: extraiu campos administrativos e tabelas de força.
- `Medcork`: extraiu tabelas genéricas agrupadas por grandeza.

Principais falhas:

- `Paquímetro`: praticamente só recuperou cabeçalho.
- Campos como cliente, equipamento, condições e referência falham em layouts
  densos ou quando o OCR mistura blocos.
- Em `Dinamómetro`, não recuperou condições de trabalho e norma no schema final.

Boa utilização:

- Baseline auditável.
- Forte quando o layout encaixa nas heurísticas existentes.

### `hybrid_fast`

O híbrido com YOLO + PaddleOCR melhorou algumas leituras face ao OCR completo,
sobretudo quando as regiões foram bem detetadas. Teve bom desempenho tabular em
`CITC`, `Extralab` e `Medcork`. No entanto, é dependente da qualidade do detetor
de regiões; quando as caixas não isolam bem os blocos, a extração fica fraca.

Principais acertos:

- `CITC`: encontrou as tabelas de medições e erros relativos.
- `Extralab`: encontrou tabelas de força.
- `Medcork`: recuperou tabelas genéricas do equipamento.

Principais falhas:

- `Paquímetro`: recuperou apenas parte das tabelas esperadas, sobretudo
  `L_line_contact`.
- `Dinamómetro`: conseguiu campos mas não consolidou tabelas de resultados.
- A qualidade textual ainda depende do PaddleOCR nos crops.

Boa utilização:

- Método intermédio e explicável.
- Útil para mostrar a importância da segmentação visual.

### `paddleocr_vl`

Foi o método multimodal mais interessante do ponto de vista técnico. Em vários
certificados, identificou blocos, tabelas HTML, páginas e coordenadas. Teve boa
completude aplicável e boa preservação de tabelas brutas. O problema principal
não foi tanto detetar informação, mas sim mapear todas as tabelas para os tipos
semânticos esperados pelo projeto.

Principais acertos:

- `CITC`: extraiu tabelas de força, erros relativos e equipamento padrão.
- `Dinamómetro`: recuperou quase todos os campos e 22 linhas de medições.
- `Extralab`: recuperou campos e equipamento padrão.
- `Medcork`: detetou 46 linhas tabulares genéricas.

Principais falhas:

- `Extralab`: não converteu as tabelas de resultados de força, embora tenha
  detetado tabelas genéricas.
- `Medcork`: detetou muitas linhas, mas não as agrupou em tabelas MEDCORK
  semanticamente úteis.
- `Paquímetro`: classificou tabelas de paquímetro como `force_calibration`,
  sinal de que o classificador tabular ainda está demasiado enviesado para força.
- Em `CITC` e `Paquímetro`, por vezes confundiu elementos de paginação com
  `customer.name`, como `PÁGINA 1 DE 4`.

Boa utilização:

- Melhor base para leitura multimodal.
- Deve ser combinado com parsers mais fortes de classificação tabular.

### `ocr_llm`

O método `ocr_llm` aumentou muito a completude estrita, mas introduziu risco
semântico. Em vários documentos, o LLM sugeriu valores sem suporte, incluindo
nomes fictícios, datas fictícias e certificados inventados. Após a correção do
pipeline, essas sugestões são guardadas como conflitos e não substituem valores
já extraídos.

Exemplos de divagação:

- `CITC`: sugeriu `FG-2023-1015` como certificado e `Precision Calibration Labs`
  como laboratório.
- `Extralab`: sugeriu `ABC Manufacturing` como cliente e `Force Gauge Model X`
  como equipamento.
- `Medcork`: sugeriu `John Doe`, `123 Main St` e números de série fictícios.

Boa utilização:

- Pode preencher campos vazios se houver evidência clara.
- Deve ser usado apenas com validação por evidência.

### `paddleocr_vl_llm`

Este método junta a melhor leitura multimodal com normalização semântica. Em
termos de completude estrita, melhorou vários documentos, mas também gerou mais
conflitos do que o `ocr_llm`. Isto aconteceu porque o PaddleOCR-VL fornece
muitas tabelas de equipamento padrão e o LLM por vezes interpretou equipamentos
padrão como equipamento calibrado.

Exemplos importantes:

- `CITC`: confundiu o número CATIM `03.50615` com número de certificado e o
  transdutor padrão com equipamento calibrado.
- `Dinamómetro`: sugeriu valores fictícios como `CAL-2023-1015`,
  `ABC Manufacturing` e `Force Gauge Model X-100`.
- `Medcork`: sugeriu novamente dados genéricos como `ABC Manufacturing` e
  `Precision Calibration Lab`.
- `Extralab`: foi o caso mais controlado; os conflitos foram pequenos, como
  variação da morada e extensão da norma.

Boa utilização:

- Promissor para normalização, mas só com guardrails.
- Não deve sobrescrever campos existentes.
- As sugestões devem ser auditadas por `raw_blocks.ollama_llm.conflicts`.

## 3. Análise por certificado

### CITC_021_CORK SUPPLY PORTUGAL

Foi um dos certificados em que as tabelas de força foram melhor recuperadas.
`paddle_current`, `hybrid_fast`, `ocr_llm`, `paddleocr_vl` e
`paddleocr_vl_llm` atingiram `table_extraction_score = 1.0`.

Melhor comportamento:

- `paddleocr_vl` recuperou 11 linhas de medições, 11 linhas de erros relativos
  e 3 linhas de equipamento padrão.
- `hybrid_fast` também recuperou as duas tabelas principais de força.

Falhas:

- `paddle_current` teve completude estrita baixa; praticamente ficou no
  cabeçalho e tabelas.
- `paddleocr_vl` confundiu `PÁGINA 1 DE 4` com cliente.
- O LLM tentou substituir dados reais por dados de equipamento padrão ou por
  valores fictícios.

Melhoria recomendada:

- Reforçar o parser de cliente para ignorar textos de paginação.
- Bloquear que equipamento padrão seja usado como equipamento calibrado.

### Dinamómetro EX.001 RED LION

O PaddleOCR-VL foi o método mais forte neste documento. Recuperou os principais
campos administrativos, cliente, equipamento, condições e 22 linhas de medições.

Melhor comportamento:

- `paddleocr_vl`: completude estrita de 0.90 e score tabular de 0.50.
- `paddleocr_vl_llm`: completude estrita de 1.00, mas com 18 conflitos LLM.
- `pdf_table`: extraiu campos relevantes, mas apenas como tabelas genéricas.

Falhas:

- Nenhum método recuperou totalmente as tabelas esperadas.
- `force_relative_errors` ficou com zero linhas.
- `hybrid_fast` e `paddle_current` não consolidaram tabelas.

Melhoria recomendada:

- Rever a expectativa tabular para dinamómetros: talvez o documento tenha
  medições em compressão/tração, mas não necessariamente a mesma tabela de erros
  relativos usada noutros certificados.
- Criar parser para múltiplos subconjuntos de equipamento: célula de carga e
  unidade de leitura.

### Extralab2G_025_GRUPO SOLAR DE SAMANIEGO SL

O baseline e o híbrido tiveram melhor desempenho tabular do que o PaddleOCR-VL.
O PaddleOCR-VL recuperou muito bem os campos, mas não converteu os resultados de
força para as tabelas esperadas.

Melhor comportamento:

- `paddle_current`, `hybrid_fast` e `ocr_llm`: `table_extraction_score = 1.0`.
- `paddleocr_vl`: boa extração de campos e equipamento padrão.
- `paddleocr_vl_llm`: poucos conflitos comparativamente aos outros documentos.

Falhas:

- `paddleocr_vl` preservou 21 linhas em `paddleocr_vl_detected_tables`, mas não
  as mapeou para resultados de força.
- `pdf_table` extraiu tabelas genéricas, mas com pouca utilidade semântica.

Melhoria recomendada:

- Combinar campos de `paddleocr_vl` com tabelas do `paddle_current` neste tipo
  de documento.
- Melhorar fallback para páginas onde o PaddleOCR-VL só devolve cabeçalho ou
  grupos tabulares administrativos.

### Medcork_116_HEREDEROS DE TORRENT MIRANDA S.L.

Este documento favorece os parsers clássicos e híbridos para tabelas MEDCORK.
`paddle_current` e `hybrid_fast` recuperaram bem as tabelas genéricas
especializadas por grandeza.

Melhor comportamento:

- `paddle_current` e `hybrid_fast`: `table_extraction_score = 1.0`.
- `paddleocr_vl`: detetou 46 linhas tabulares, o que mostra que viu a estrutura.

Falhas:

- `paddleocr_vl` não agrupou as 46 linhas em tabelas MEDCORK úteis.
- LLM gerou muitos valores fictícios nos dois métodos com LLM.
- Condições de trabalho ficaram fracas ou suspeitas em alguns métodos.

Melhoria recomendada:

- Criar classificador tabular genérico para MEDCORK com base em cabeçalhos e
  grandezas, não no nome do ficheiro.
- Validar temperatura/humidade contra padrões de unidade.

### Paquímetro MITUTOYO

Foi o certificado mais difícil. O baseline e o pdf_table praticamente falharam.
O híbrido recuperou apenas parte das tabelas esperadas. O PaddleOCR-VL leu
alguns campos do equipamento, mas classificou tabelas como se fossem de força.

Melhor comportamento:

- `ocr_llm`: recuperou vários campos do equipamento, incluindo marca, modelo e
  número de série.
- `paddleocr_vl`: recuperou equipamento, marca, modelo e série.
- `hybrid_fast`: encontrou parte das tabelas de contacto/linha.

Falhas:

- `paddleocr_vl` não recuperou corretamente o número do certificado.
- `paddleocr_vl_llm` preencheu o certificado com o número de série
  `B22034284`, o que é incorreto.
- As tabelas foram mapeadas como `force_calibration_measurements`, revelando
  enviesamento do parser para certificados de força.
- `customer.name` foi confundido com `PÁGINA 1 DE 3`.

Melhoria recomendada:

- Criar mapeamento tabular específico para paquímetros: `E_contact_partial`,
  `S_scale_change` e `L_line_contact`.
- Reforçar regex de certificado para preferir padrões como `LMD.../...` e não
  números de série.
- Bloquear textos de paginação como candidatos a cliente.

## 4. Conclusões principais

1. O melhor método isolado para leitura multimodal foi `paddleocr_vl`, mas ainda
   precisa de melhor classificação semântica das tabelas.

2. O método mais estável para tabelas conhecidas foi uma combinação entre
   `paddle_current` e `hybrid_fast`, porque os parsers existentes já reconhecem
   alguns formatos de resultados.

3. O `pdf_table` é demasiado frágil como solução principal, mas pode ser útil
   como fallback rápido para PDFs digitais.

4. Os métodos com LLM aumentam a completude, mas também aumentam o risco de
   divagação. As métricas de completude não devem ser interpretadas isoladamente
   quando há LLM.

5. A melhor arquitetura futura é uma solução híbrida por camadas:

   - usar PaddleOCR-VL para leitura multimodal e deteção de blocos;
   - usar parsers determinísticos para campos e tabelas conhecidas;
   - usar o LLM apenas para preencher vazios ou sugerir normalização;
   - exigir evidência textual para aceitar sugestões do LLM;
   - guardar conflitos para auditoria.

## 5. Melhorias prioritárias

1. Adicionar validação anti-alucinação para LLM:
   - rejeitar valores como `ABC Manufacturing`, `John Doe`, `Precision Calibration`
     e datas genéricas sem evidência;
   - aceitar sugestões apenas se o texto existir no OCR/VL original;
   - nunca usar equipamento padrão como equipamento calibrado.

2. Melhorar parser de cliente:
   - ignorar `PÁGINA X DE Y`;
   - procurar cliente após `CLIENTE`, `Nome` ou linhas imediatamente seguintes;
   - evitar que cabeçalhos e rodapés entrem como cliente.

3. Melhorar classificação de tabelas:
   - distinguir força, paquímetro, MEDCORK e equipamento padrão por cabeçalhos;
   - usar `raw_cells` e não apenas nome da tabela;
   - conservar sempre tabela genérica quando a classificação for incerta.

4. Rever métricas:
   - separar completude de validade;
   - penalizar conflitos LLM;
   - distinguir tabelas detetadas de tabelas semanticamente classificadas;
   - evitar que campos não aplicáveis prejudiquem a avaliação estrita.

5. Criar um pequeno gold set manual para estes 5 documentos:
   - número de certificado;
   - datas;
   - cliente;
   - equipamento;
   - normas;
   - tabelas principais.

Esse gold set permitiria calcular precisão/recall reais e provar, na tese, que
completude alta nem sempre significa extração correta.
