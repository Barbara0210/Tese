# Interpretação atualizada dos métodos nos 5 certificados

Análise baseada nos artefactos exportados em `2026-05-31`:

- Comparação quantitativa: `data/analysis/20260531_220436__thesis_test_set_5docs/`
- Avaliação gold corrigida: `data/evaluation/20260531_220740__thesis_gold_5docs/`

Esta leitura substitui a interpretação anterior, porque foram entretanto
introduzidas melhorias no parser, na classificação de tabelas e na avaliação
manual por gold set.

## 1. Leitura global corrigida

A conclusão principal mudou: o método `paddleocr_vl_llm` passou a ser o melhor
candidato global, desde que seja usado com validação forte contra a evidência
OCR/VL. O método `paddleocr_vl` isolado continua a ser o melhor método sem LLM
para campos documentais, mas ainda depende bastante da camada de parsing para
classificar corretamente tabelas e tipo de instrumento.

Na avaliação gold mais recente, a média por método foi:

| Método | Preenchimento no gold | Correção de campos | Precisão quando preenche | Correção de tabelas | Tipo de instrumento |
|---|---:|---:|---:|---:|---:|
| `paddleocr_vl_llm` | 1.0000 | 0.9667 | 0.9667 | 0.6667 | 0.6000 |
| `paddleocr_vl` | 0.9533 | 0.9367 | 0.9800 | 0.4667 | 0.4000 |
| `ocr_llm` | 0.9444 | 0.7376 | 0.7904 | 0.3333 | 0.6000 |
| `hybrid_fast` | 0.6119 | 0.6008 | 0.9846 | 0.5167 | 0.8000 |
| `paddle_current` | 0.5500 | 0.5500 | 1.0000 | 0.3333 | 0.6000 |
| `pdf_table` | 0.4981 | 0.4848 | 0.5846 | 0.0000 | 0.0000 |

Isto mostra três coisas importantes:

- O LLM só é vantajoso quando parte de uma base estrutural forte. Em cima do PaddleOCR-VL, melhora a completude e mantém boa precisão. Em cima do OCR clássico, aumenta muito o preenchimento, mas também aumenta bastante o risco de valores inventados.
- A métrica antiga de completude era insuficiente. O caso `ocr_llm` prova isto: tem completude formal muito alta, mas a correção real no gold fica bastante abaixo do `paddleocr_vl_llm`.
- O método mais fiável para uso futuro não é "LLM puro"; é uma arquitetura híbrida: PaddleOCR-VL para leitura estruturada, parsers determinísticos para tabelas e LLM local apenas como normalizador semântico controlado.

## 2. Correção ao resumo anterior

No resumo anterior, o `paddleocr_vl` aparecia como o candidato mais promissor e o
`paddleocr_vl_llm` como uma extensão ainda arriscada. A nova leitura deve ser
mais precisa:

- `paddleocr_vl_llm` deve ser apresentado como o melhor método global nos testes atuais, porque combina preenchimento total no gold com a maior correção média de campos.
- `paddleocr_vl` deve ser apresentado como o melhor método base, sem dependência de LLM, com excelente precisão quando extrai os campos.
- `ocr_llm` não deve ser defendido como solução principal. Serve como prova de conceito, mas mostra o risco de o LLM compensar falhas do OCR com valores plausíveis mas errados.
- `hybrid_fast` continua relevante metodologicamente, sobretudo porque mostra boa precisão quando encontra os campos e boa robustez em algumas tabelas, mas é limitado pela cobertura do modelo YOLO e dos parsers posteriores.
- `pdf_table` deve ser tratado como método auxiliar/baseline rápido, não como solução principal.

## 3. Análise por documento

### CITC

O certificado CITC passou a ser um caso forte para `paddleocr_vl` e
`paddleocr_vl_llm`. Ambos atingem correção de campos de `1.0000` no gold
corrigido e correção de tabelas de `1.0000`.

O erro antigo em que `PÁGINA 1 DE 4` entrava como cliente foi resolvido no parser.
O método VL consegue agora recuperar corretamente cliente, equipamento, datas,
procedimento e tabelas de força. A principal lição deste documento é que o VL
preserva melhor a estrutura documental do que o OCR de página completa.

O `ocr_llm` continua a ser o pior exemplo de risco: apesar de preencher tudo,
produziu valores inventados como cliente, morada, marca, modelo, número de série
e procedimento. Este caso é central para justificar a separação entre campo
preenchido e campo correto.

### Dinamómetro RED LION

Nos campos, `paddleocr_vl` e `paddleocr_vl_llm` são excelentes: ambos atingem
correção de campos de `1.0000`. O problema observado nos arquivos atuais está
nas tabelas, onde a avaliação ainda mostra `0.0000`.

A análise dos `raw_tables` mostrou que isto não era falha de leitura do
PaddleOCR-VL. As tabelas estavam presentes, mas o cabeçalho tinha uma primeira
célula vazia antes de `Equipamento`, por exemplo:

```text
"", "Equipamento", "Erro", "k'", "v'ef", "Incerteza Expandida"
```

O classificador antigo exigia que `Equipamento` estivesse na primeira célula e
por isso não reconhecia a tabela. Esta regra foi corrigida. Em teste local sobre
o `run_summary.json`, o parser atual passa a devolver:

```text
instrument_type = force_calibration
force_calibration_measurements = 22 linhas
```

Assim, para a tese, a interpretação correta é: o erro no Dinamómetro era uma
falha de classificação/parsing de cabeçalho, não uma limitação do PaddleOCR-VL.
Depois de rerun, este documento deverá melhorar nas métricas de tabela para
`paddleocr_vl` e `paddleocr_vl_llm`.

### Extralab2G

Este documento continua a ser o caso em que os métodos clássicos se comportam
melhor nas tabelas de força. `paddle_current`, `hybrid_fast` e `ocr_llm`
recuperam melhor as tabelas de resultados do que o `paddleocr_vl`.

No `paddleocr_vl`, os campos são muito bons, mas os `raw_tables` disponíveis no
arquivo VL não incluem as tabelas principais de resultados de força; aparecem
sobretudo blocos administrativos e a tabela de equipamento padrão. Por isso, o
problema aqui parece estar antes do parser: ou o Colab/PaddleOCR-VL não
exportou as tabelas de resultados como `table`, ou estas páginas/blocos não
foram corretamente capturados no `run_summary.json`.

Conclusão para este documento: o VL é forte para campos e equipamento padrão,
mas ainda precisa de verificação no Colab/output para garantir que todas as
páginas e tabelas de resultados estão a ser capturadas.

### MEDCORK

MEDCORK tornou-se um dos melhores casos para o método VL. `paddleocr_vl` e
`paddleocr_vl_llm` atingem:

```text
field_accuracy = 1.0000
table_accuracy = 1.0000
instrument_type = generic_block_table
```

Este resultado é importante porque MEDCORK não segue a estrutura típica dos
certificados de força. A melhoria de classificação por cabeçalhos permitiu
identificar a tabela genérica de resultados a partir de sinais como `Padrão`,
`Leitura`, `Erro` e `Incerteza`, sem depender do nome do documento.

Este documento pode ser usado na dissertação como evidência de que a abordagem
por cabeçalho é mais robusta do que a classificação por tipo documental.

### Paquímetro MITUTOYO

O Paquímetro continua a ser o documento mais delicado, mas a situação melhorou.
No arquivo mais recente, `paddleocr_vl_llm` consegue:

```text
field_fill = 1.0000
field_accuracy = 0.8333
table_accuracy = 1.0000
instrument_type = caliper
```

Ou seja, a estrutura tabular do paquímetro já foi recuperada no método VL+LLM:
`E_contact_partial`, `S_scale_change`, `L_line_contact` e `reference_equipment`.
Isto é uma melhoria muito forte em relação ao comportamento anterior.

As duas falhas restantes no arquivo atual são:

- `header.certificate_number = CAL-2023-1015`, que é uma alucinação;
- `reference.standard_or_procedure = ISO/IEC 17025:2017`, que existe como
  norma de acreditação, mas não é o procedimento de calibração do paquímetro.

Depois desta análise, a validação LLM foi reforçada para:

- rejeitar identificadores alfanuméricos que não apareçam exatamente na
  evidência OCR/VL;
- rejeitar `ISO/IEC 17025` como `reference.standard_or_procedure`, por ser
  acreditação laboratorial e não procedimento específico do instrumento.

Também foi verificado localmente que o importador `paddleocr_vl` atual, quando
aplicado ao `run_summary.json` do Paquímetro, já classifica:

```text
instrument_type = caliper
reference_equipment = 5 linhas
E_contact_partial = 6 linhas
S_scale_change = 4 linhas
L_line_contact = 1 linha
```

Portanto, as métricas arquivadas do `paddleocr_vl` simples para Paquímetro ainda
não refletem totalmente o código corrigido. Para relatório final, este método
deve ser rerun depois de reiniciar o backend.

## 4. Porque cada método falha

### `paddle_current`

O baseline é conservador: quando preenche, tende a acertar. A precisão quando
preenche é `1.0000` no gold. O problema é cobertura. Falha sobretudo em campos
administrativos e de equipamento quando a estrutura textual do OCR fica
desordenada, e perde várias tabelas completas.

Interpretação: bom baseline auditável, mas insuficiente como solução final.

### `pdf_table`

É rápido, mas estruturalmente frágil. Não consegue mapear as tabelas para o
schema metrológico e tem precisão baixa quando tenta inferir campos.

Interpretação: útil apenas como método auxiliar para PDFs digitais muito
tabulares; não deve ser defendido como solução principal.

### `hybrid_fast`

Tem alta precisão quando encontra informação (`0.9846`), mas baixa cobertura
global. Isto indica que a deteção visual ajuda a evitar ruído, mas o pipeline
ainda depende muito de as regiões certas serem detetadas e de os parsers
posteriores conseguirem interpretar cada bloco.

Interpretação: metodologicamente importante, especialmente como ponte entre OCR
clássico e visão documental, mas precisa de mais treino/anotações para competir
em campos com o VL.

### `ocr_llm`

É o método mais perigoso. O preenchimento é alto (`0.9444`), mas a correção
fica em `0.7376`. No CITC, o gap é extremo: preenche tudo, mas só acerta
`0.3077` dos campos gold.

Interpretação: demonstra bem o risco de usar LLM para "resolver" extrações
fracas. Deve ser descrito como abordagem exploratória, não como solução final.

### `paddleocr_vl`

É o melhor extrator base. Tem alta correção de campos (`0.9367`) e precisão
quando preenche (`0.9800`). As falhas principais não são de leitura, mas sim de
classificação/interpretação posterior: tipo de instrumento, tabelas específicas
e alguns casos em que o `run_summary.json` não contém as tabelas esperadas.

Interpretação: excelente fundação para a solução final.

### `paddleocr_vl_llm`

É o melhor método global nos testes atuais. Atinge maior correção de campos
(`0.9667`) e melhor correção de tabelas (`0.6667`). O LLM é útil quando trabalha
em cima de evidência VL estruturada e quando não pode sobrescrever valores já
extraídos.

Interpretação: deve ser apresentado como a evolução mais promissora, mas com
uma ressalva técnica: precisa de validação anti-alucinação e auditoria por
evidência.

## 5. Conclusão metodológica para a tese

A melhor conclusão para defender no capítulo da tese é:

> A abordagem mais robusta não corresponde a um único modelo isolado, mas a uma
> arquitetura híbrida em camadas: leitura documental multimodal com
> PaddleOCR-VL, classificação determinística de tabelas por cabeçalhos,
> normalização semântica controlada por LLM local e validação final contra
> evidência OCR/VL e gold set manual.

Isto é mais forte do que dizer simplesmente "o LLM melhora". O que os testes
mostram é que:

- o LLM melhora quando a evidência de entrada já é boa;
- o LLM degrada quando tenta compensar OCR fraco;
- a completude sozinha é enganadora;
- a avaliação gold é essencial para medir precisão real;
- a classificação de tabelas por cabeçalhos é indispensável para documentos
  heterogéneos.

## 6. Próximos passos recomendados

Antes de congelar os resultados finais para a dissertação:

1. Reiniciar o backend.
2. Rerun `paddleocr_vl` e `paddleocr_vl_llm` pelo frontend para Dinamómetro e Paquímetro.
3. Correr novamente:

```powershell
python scripts\export_thesis_analysis.py
python scripts\evaluate_gold_set.py
```

4. Confirmar se:

- Dinamómetro passa a ter `force_calibration_measurements = 22`;
- Paquímetro `paddleocr_vl` passa a ter `instrument_type = caliper`;
- Paquímetro `paddleocr_vl_llm` deixa de aceitar `CAL-2023-1015` e `ISO/IEC 17025:2017`.

Se estes pontos se confirmarem, o resultado final deve reforçar ainda mais a
posição do método `paddleocr_vl_llm` como melhor solução experimental.
