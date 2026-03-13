import { useState } from "react";
import UploadForm from "./components/UploadForm";
import StatusBox from "./components/StatusBox";
import ResultViewer from "./components/ResultViewer";
import "./App.css";

export default function App() {
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("Pronto.");

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>OCR de Certificados</h1>
        <p>
          Upload de PDF, processamento do pipeline e visualização dos dados extraídos.
        </p>
      </header>

      <UploadForm onResult={setResult} onStatus={setStatus} />
      <StatusBox status={status} />
      <ResultViewer data={result} />
    </div>
  );
}