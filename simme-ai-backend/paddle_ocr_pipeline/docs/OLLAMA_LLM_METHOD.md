# Metodo LLM local com Ollama

Este metodo usa um LLM local apenas como camada de normalizacao semantica. O PDF
continua a ser lido pelos pipelines existentes, como PaddleOCR ou PaddleOCR-VL.
O LLM recebe os campos, blocos e tabelas ja extraidos e tenta normalizar o
resultado para o schema comum do projeto, sem inventar valores.

## Instalar Ollama no Windows

1. Abrir a pagina oficial: https://ollama.com/download/windows
2. Descarregar e executar `OllamaSetup.exe`.
3. Concluir a instalacao e deixar o Ollama aberto em segundo plano.
4. Abrir o PowerShell e confirmar que o comando existe:

```powershell
ollama --version
```

5. Descarregar o modelo recomendado:

```powershell
ollama pull qwen3:8b
```

6. Testar uma resposta simples:

```powershell
ollama run qwen3:8b
```

7. Escrever uma mensagem curta, confirmar que responde e sair com:

```text
/bye
```

8. Confirmar que a API local responde:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
```

## Configuracao usada pelo projeto

Por defeito, o script usa um modelo leve para testes:

```text
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_OCR_LLM_MODEL=qwen3:4b
OLLAMA_TIMEOUT_SECONDS=600
OLLAMA_CONTEXT_CHAR_LIMIT=12000
```

Se quiseres mais qualidade e a maquina aguentar:

```powershell
$env:OLLAMA_OCR_LLM_MODEL = "qwen3:8b"
```

Se tiveres uma maquina mesmo forte:

```powershell
$env:OLLAMA_OCR_LLM_MODEL = "qwen3:14b"
```

## Metodo no frontend

Depois de instalares o Ollama e descarregares o modelo, podes escolher:

- `OCR + LLM`: corre PaddleOCR, faz parsing heuristico e normaliza com Ollama.
- `PaddleOCR-VL + LLM`: importa o `run_summary.json` do Colab e normaliza com Ollama.

Para `PaddleOCR-VL + LLM`, o upload precisa do PDF e do `run_summary.json`, tal
como o metodo `PaddleOCR-VL`.

## Principio de seguranca

O prompt obriga o modelo a:

- usar apenas a evidencia fornecida;
- devolver `null` quando nao houver suporte no texto/tabelas;
- nao confundir data de emissao com data de calibracao;
- guardar evidencias curtas no bloco `raw_blocks.ollama_llm`.

Isto torna o metodo mais auditavel e mais adequado para comparacao experimental
na tese.
