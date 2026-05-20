import InfoCard from "./InfoCard";
import DataTable from "./DataTable";

function MetricPill({ label, value }) {
  return (
    <div className="metric-pill">
      <span className="metric-pill-label">{label}</span>
      <strong>{value ?? "â€”"}</strong>
    </div>
  );
}

function buildTableEntries(documentData) {
  return Object.entries(documentData?.tables || {}).filter(([, tableValue]) => {
    if (Array.isArray(tableValue)) return tableValue.length > 0;
    if (tableValue && typeof tableValue === "object") {
      if (Array.isArray(tableValue.rows)) return tableValue.rows.length > 0;
      return Object.keys(tableValue).length > 0;
    }
    return Boolean(tableValue);
  });
}

export default function ResultViewer({ data }) {
  if (!data) {
    return (
      <div className="result-box">
        <p>Ainda nÃ£o hÃ¡ resultados.</p>
      </div>
    );
  }

  const documentData = data?.document || null;
  const method = data?.method || null;
  const summary = data?.processing_summary || null;
  const documentMetrics = data?.metrics?.document || null;
  const globalMetrics = data?.metrics?.global || null;
  const rawBlocks = data?.raw?.parsed?.raw_blocks || null;
  const pageSections = data?.raw?.sections?.page_sections || null;
  const tableEntries = buildTableEntries(documentData);

  return (
    <div className="result-layout">
      <div className="cards-grid">
        <div className="info-card">
          <h3>MÃ©todo</h3>
          <div className="info-card-body">
            <div className="info-row">
              <span className="info-label">Nome</span>
              <span className="info-value">{method?.label || "â€”"}</span>
            </div>
            <div className="info-row">
              <span className="info-label">DescriÃ§Ã£o</span>
              <span className="info-value info-value-multiline">{method?.description || "â€”"}</span>
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
          <h3>Resumo da execuÃ§Ã£o</h3>
          <div className="metrics-grid">
            <MetricPill
              label="Tempo"
              value={
                summary?.elapsed_seconds !== undefined
                  ? `${summary.elapsed_seconds}s`
                  : "â€”"
              }
            />
            <MetricPill label="Scripts" value={summary?.scripts_executed?.length ?? "â€”"} />
            <MetricPill label="Campos preenchidos" value={documentMetrics?.fields?.filled_fields ?? "â€”"} />
            <MetricPill label="Tabelas encontradas" value={documentMetrics?.tables?.found_tables ?? "â€”"} />
          </div>
        </div>
      </div>

      {(documentMetrics || globalMetrics) && (
        <div className="info-card">
          <h3>MÃ©tricas</h3>
          <div className="metrics-grid">
            <MetricPill
              label="Completude do documento"
              value={documentMetrics?.fields?.completeness_score ?? "â€”"}
            />
            <MetricPill
              label="ExtraÃ§Ã£o de tabelas"
              value={documentMetrics?.tables?.table_extraction_score ?? "â€”"}
            />
            <MetricPill
              label="Linhas de tabela"
              value={Object.values(documentMetrics?.tables?.row_counts || {}).join(", ") || "â€”"}
            />
            <MetricPill
              label="Tipo de instrumento"
              value={documentMetrics?.instrument_type ?? "â€”"}
            />
            <MetricPill
              label="MÃ©dia global campos"
              value={globalMetrics?.avg_field_completeness ?? "â€”"}
            />
            <MetricPill
              label="MÃ©dia global tabelas"
              value={globalMetrics?.avg_table_extraction ?? "â€”"}
            />
          </div>
        </div>
      )}

      <div className="cards-grid">
        <InfoCard title="Header" data={documentData?.header} />
        <InfoCard title="Cliente" data={documentData?.customer} />
        <InfoCard title="Equipamento" data={documentData?.equipment} />
        <InfoCard title="CondiÃ§Ãµes de trabalho" data={documentData?.work_conditions} />
        <InfoCard title="ReferÃªncia" data={documentData?.reference} />
      </div>

      {rawBlocks && (
        <div className="cards-grid">
          <InfoCard title="Blocos OCR" data={rawBlocks} />
        </div>
      )}

      {pageSections && (
        <div className="cards-grid">
          {Object.entries(pageSections).map(([pageName, sectionData]) => (
            <InfoCard key={pageName} title={`SecÃ§Ãµes ${pageName}`} data={sectionData} />
          ))}
        </div>
      )}

      <div className="tables-grid">
        {tableEntries.length === 0 ? (
          <div className="result-box">
            <p>Sem tabelas interpretadas para este mÃ©todo.</p>
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
