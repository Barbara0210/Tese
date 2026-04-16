import { useEffect, useState } from "react";
import api from "./api/client";
import UploadForm from "./components/UploadForm";
import StatusBox from "./components/StatusBox";
import ResultViewer from "./components/ResultViewer";
import "./App.css";

export default function App() {
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("Pronto.");
  const [methods, setMethods] = useState([]);
  const [selectedMethod, setSelectedMethod] = useState("paddle_current");

  useEffect(() => {
    async function loadMethods() {
      try {
        const response = await api.get("/methods");
        const availableMethods = response.data?.methods || [];
        setMethods(availableMethods);

        if (availableMethods.length > 0) {
          setSelectedMethod(availableMethods[0].key);
        }
      } catch (error) {
        console.error(error);
        setStatus("Não foi possível carregar a lista de métodos.");
      }
    }

    loadMethods();
  }, []);

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>OCR de Certificados</h1>
        <p>Upload de PDF, seleção do método e comparação das métricas extraídas.</p>
      </header>

      <UploadForm
        methods={methods}
        selectedMethod={selectedMethod}
        onMethodChange={setSelectedMethod}
        onResult={setResult}
        onStatus={setStatus}
      />
      <StatusBox status={status} />
      <ResultViewer data={result} />
    </div>
  );
}
