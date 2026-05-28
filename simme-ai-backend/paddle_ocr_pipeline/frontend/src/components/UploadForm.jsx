import { useState } from "react";
import api from "../api/client";
import { repairText } from "../utils/text";

export default function UploadForm({
  methods,
  selectedMethod,
  onMethodChange,
  onResult,
  onStatus,
}) {
  const [file, setFile] = useState(null);
  const [paddleSummaryFile, setPaddleSummaryFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const needsPaddleSummary = ["paddleocr_vl", "paddleocr_vl_llm"].includes(selectedMethod);

  async function handleSubmit(event) {
    event.preventDefault();

    if (!file) {
      onStatus("Seleciona um ficheiro PDF primeiro.");
      return;
    }

    if (!selectedMethod) {
      onStatus("Seleciona um metodo de processamento.");
      return;
    }

    if (needsPaddleSummary && !paddleSummaryFile) {
      onStatus("Seleciona tambem o run_summary.json gerado no Colab para usar o PaddleOCR-VL.");
      return;
    }

    try {
      setLoading(true);
      onResult(null);
      onStatus(needsPaddleSummary ? "A enviar PDF e run_summary.json..." : "A enviar ficheiro...");

      const formData = new FormData();
      formData.append("file", file);
      if (needsPaddleSummary && paddleSummaryFile) {
        formData.append("paddleocr_vl_summary", paddleSummaryFile);
      }

      const uploadResponse = await api.post("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const fileId = uploadResponse.data.file_id;
      onStatus(`Ficheiro enviado. A processar com o metodo "${selectedMethod}"...`);

      await api.post(`/process/${fileId}`, null, {
        params: { method: selectedMethod },
      });

      onStatus("Pipeline concluido. A obter resultado...");

      const resultResponse = await api.get(`/result/${fileId}`, {
        params: { method: selectedMethod },
      });

      onResult(resultResponse.data);
      onStatus("Processamento concluido com sucesso.");
    } catch (error) {
      console.error(error);
      if (error.response?.data) {
        onStatus(`Erro: ${JSON.stringify(error.response.data)}`);
      } else {
        onStatus("Erro ao comunicar com o backend.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="upload-form">
      <label className="field-group">
        <span>Metodo</span>
        <select
          value={selectedMethod}
          onChange={(event) => onMethodChange(event.target.value)}
          disabled={loading || methods.length === 0}
        >
          {methods.map((method) => (
            <option key={method.key} value={method.key}>
              {repairText(method.label)}
              {!method.implemented ? " (planeado)" : ""}
            </option>
          ))}
        </select>
      </label>

      <label className="field-group field-group-file">
        <span>PDF</span>
        <input
          type="file"
          accept=".pdf"
          onChange={(event) => setFile(event.target.files?.[0] || null)}
        />
        <small>{file?.name || "Nenhum ficheiro selecionado"}</small>
      </label>

      {needsPaddleSummary ? (
        <label className="field-group field-group-file">
          <span>run_summary.json do Colab</span>
          <input
            type="file"
            accept=".json,application/json"
            onChange={(event) => setPaddleSummaryFile(event.target.files?.[0] || null)}
          />
          <small>{paddleSummaryFile?.name || "Obrigatorio para PaddleOCR-VL"}</small>
        </label>
      ) : null}

      <button type="submit" disabled={loading} className="primary-action">
        {loading ? "A processar..." : "Enviar e Processar"}
      </button>
    </form>
  );
}
