import { useEffect, useState } from "react";
import api from "./api/client";
import ResultViewer from "./components/ResultViewer";
import StatusBox from "./components/StatusBox";
import UploadForm from "./components/UploadForm";
import { repairText } from "./utils/text";
import "./App.css";

const NAV_ITEMS = ["Painel", "Campos", "Secções", "Tabelas", "JSON"];

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

  const activeMethod = methods.find((method) => method.key === selectedMethod);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">S</div>
          <div>
            <strong>SIMME AI</strong>
            <span>Inteligência Documental</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item, index) => (
            <button
              type="button"
              key={item}
              className={`sidebar-nav-item ${index === 0 ? "active" : ""}`}
            >
              <span className="sidebar-nav-dot" />
              <span>{item}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-panel">
          <span className="sidebar-panel-label">Método ativo</span>
          <strong>{repairText(activeMethod?.label || selectedMethod || "—")}</strong>
          <p>{repairText(activeMethod?.description || "Escolhe um método para iniciar a análise.")}</p>
        </div>
      </aside>

      <main className="workspace">
        <header className="workspace-header">
          <div>
            <div className="workspace-kicker">Painel de Certificados de Calibração</div>
            <h1>Extração Inteligente de Certificados</h1>
            <p>
              Visualiza os campos detetados, compara completudes e inspeciona secções OCR
              numa interface orientada à análise documental.
            </p>
          </div>
        </header>

        <section className="control-panel">
          <div className="control-panel-copy">
            <h2>Painel de Processamento</h2>
            <p>
              Carrega um PDF, seleciona o pipeline e acompanha a execução com métricas e
              resultados estruturados.
            </p>
          </div>
          <UploadForm
            methods={methods}
            selectedMethod={selectedMethod}
            onMethodChange={setSelectedMethod}
            onResult={setResult}
            onStatus={setStatus}
          />
        </section>

        <StatusBox status={status} />
        <ResultViewer data={result} />
      </main>
    </div>
  );
}
