import { useState } from "react";
import api from "../api/client";

export default function UploadForm({ onResult, onStatus }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();

    if (!file) {
      onStatus("Seleciona um ficheiro PDF primeiro.");
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

      onStatus("Ficheiro enviado. A processar pipeline...");

      await api.post(`/process/${fileId}`);

      onStatus("Pipeline concluído. A obter resultado...");

      const resultResponse = await api.get(`/result/${fileId}`);

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