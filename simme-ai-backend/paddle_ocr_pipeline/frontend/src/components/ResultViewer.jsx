import InfoCard from "./InfoCard";
import DataTable from "./DataTable";

function MetricPill({ label, value }) {
  return (
    <div className="metric-pill">
      <span className="metric-pill-label">{label}</span>
      <strong>{value ?? "—"}</strong>
    </div>
  );
}

export default function ResultViewer({ data }) {
  if (!data) {
    return (
      <div className="result-box">
        <p>Ainda não há resultados.</p>
      </div>
    );
  }

  const documentData = data?.document || null;
  const method = data?.method || null;
  const summary = data?.processing_summary || null;
  const documentMetrics = data?.metrics?.document || null;
  const globalMetrics = data?.metrics?.global || null;
  const tableEntries = Object.entries(documentData?.tables || {}).filter(([, rows]) => {
    if (Array.isArray(rows)) return rows.length > 0;
    if (rows && typeof rows === "object") return Object.keys(rows).length > 0;
    return Boolean(rows);
  });

  return (
    <div className="result-layout">
      <div className="cards-grid">
        <div className="info-card">
          <h3>Método</h3>
          <div className="info-card-body">
            <div className="info-row">
              <span className="info-label">Nome</span>
              <span className="info-value">{method?.label || "—"}</span>
            </div>
            <div className="info-row">
              <span className="info-label">Descrição</span>
              <span className="info-value">{method?.description || "—"}</span>
            </div>
            <div className="info-row">
              <span className="info-label">Estado</span>
              <span className="info-value">
                {method?.implemented ? "Implementado" : "Planeado"}
              </span>
            </div>
          </div>
        </div>

        <div className="info-card">
          <h3>Resumo da execução</h3>
          <div className="metrics-grid">
            <MetricPill
              label="Tempo"
              value={
                summary?.elapsed_seconds !== undefined
                  ? `${summary.elapsed_seconds}s`
                  : "—"
              }
            />
            <MetricPill label="Scripts" value={summary?.scripts_executed?.length ?? "—"} />
            <MetricPill label="Campos preenchidos" value={documentMetrics?.fields?.filled_fields ?? "—"} />
            <MetricPill label="Tabelas encontradas" value={documentMetrics?.tables?.found_tables ?? "—"} />
          </div>
        </div>
      </div>

      {(documentMetrics || globalMetrics) && (
        <div className="info-card">
          <h3>Métricas</h3>
          <div className="metrics-grid">
            <MetricPill
              label="Completude do documento"
              value={documentMetrics?.fields?.completeness_score ?? "—"}
            />
            <MetricPill
              label="Extração de tabelas"
              value={documentMetrics?.tables?.table_extraction_score ?? "—"}
            />
            <MetricPill
              label="Média global campos"
              value={globalMetrics?.avg_field_completeness ?? "—"}
            />
            <MetricPill
              label="Média global tabelas"
              value={globalMetrics?.avg_table_extraction ?? "—"}
            />
          </div>
        </div>
      )}

      <div className="cards-grid">
        <InfoCard title="Header" data={documentData?.header} />
        <InfoCard title="Cliente" data={documentData?.customer} />
        <InfoCard title="Equipamento" data={documentData?.equipment} />
        <InfoCard title="Condições de trabalho" data={documentData?.work_conditions} />
        <InfoCard title="Referência" data={documentData?.reference} />
      </div>

      <div className="tables-grid">
        {tableEntries.length === 0 ? (
          <div className="result-box">
            <p>Sem tabelas interpretadas para este método.</p>
          </div>
        ) : (
          tableEntries.map(([tableName, rows]) => (
            <DataTable key={tableName} title={`Tabela ${tableName}`} rows={rows} />
          ))
        )}
      </div>

      <div className="result-box">
        <h3>JSON bruto</h3>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    </div>
  );
}
