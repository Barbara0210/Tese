import { useState } from "react";
import api from "../api/client";

export default function UploadForm({
  methods,
  selectedMethod,
  onMethodChange,
  onResult,
  onStatus,
}) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();

    if (!file) {
      onStatus("Seleciona um ficheiro PDF primeiro.");
      return;
    }

    if (!selectedMethod) {
      onStatus("Seleciona um método de processamento.");
      return;
    }

    try {
      setLoading(true);
      onResult(null);
      onStatus("A enviar ficheiro...");

      const formData = new FormData();
      formData.append("file", file);

      const uploadResponse = await api.post("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const fileId = uploadResponse.data.file_id;

      onStatus(`Ficheiro enviado. A processar com o método "${selectedMethod}"...`);

      await api.post(`/process/${fileId}`, null, {
        params: { method: selectedMethod },
      });

      onStatus("Pipeline concluído. A obter resultado...");

      const resultResponse = await api.get(`/result/${fileId}`, {
        params: { method: selectedMethod },
      });

      onResult(resultResponse.data);
      onStatus("Processamento concluído com sucesso.");
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
        <span>Método</span>
        <select
          value={selectedMethod}
          onChange={(e) => onMethodChange(e.target.value)}
          disabled={loading || methods.length === 0}
        >
          {methods.map((method) => (
            <option key={method.key} value={method.key}>
              {method.label}
              {!method.implemented ? " (planeado)" : ""}
            </option>
          ))}
        </select>
      </label>

      <input
        type="file"
        accept=".pdf"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
      />
      <button type="submit" disabled={loading}>
        {loading ? "A processar..." : "Enviar e Processar"}
      </button>
    </form>
  );
}
