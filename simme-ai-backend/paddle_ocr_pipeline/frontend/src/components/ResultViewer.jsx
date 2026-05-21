import { useState } from "react";
import DataTable from "./DataTable";
import { EM_DASH, prettifyLabel, repairText } from "../utils/text";

function buildTableEntries(documentData) {
  const entries = [];

  for (const [tableName, tableValue] of Object.entries(documentData?.tables || {})) {
    if (tableValue && typeof tableValue === "object" && Array.isArray(tableValue.subtables) && tableValue.subtables.length > 0) {
      tableValue.subtables.forEach((subtable, index) => {
        entries.push([
          subtable.key || `${tableName}_${index}`,
          {
            ...subtable.table,
            __title: subtable.title || subtable.key || tableName,
          },
        ]);
      });
      continue;
    }

    if (Array.isArray(tableValue) && tableValue.length > 0) {
      entries.push([tableName, tableValue]);
      continue;
    }

    if (tableValue && typeof tableValue === "object") {
      if (Array.isArray(tableValue.rows) && tableValue.rows.length > 0) {
        entries.push([tableName, tableValue]);
        continue;
      }
      if (Object.keys(tableValue).length > 0) {
        entries.push([tableName, tableValue]);
      }
    }
  }

  return entries;
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return EM_DASH;
  return `${Math.round(Number(value) * 100)}%`;
}

function valueToDisplay(value) {
  if (value === null || value === undefined || value === "") return EM_DASH;
  if (Array.isArray(value)) return repairText(value).join(", ");
  if (typeof value === "object") return JSON.stringify(repairText(value), null, 2);
  return String(repairText(value));
}

function flattenDocument(documentData) {
  const groups = [
    ["Cabeçalho", documentData?.header],
    ["Cliente", documentData?.customer],
    ["Equipamento", documentData?.equipment],
    ["Condições de trabalho", documentData?.work_conditions],
    ["Referência", documentData?.reference],
  ];

  return groups
    .flatMap(([groupName, groupData]) =>
      Object.entries(groupData || {}).map(([fieldName, fieldValue]) => ({
        id: `${groupName}-${fieldName}`,
        groupName,
        fieldName,
        fieldValue,
      })),
    )
    .filter((item) => item.fieldName !== "tables");
}

function ScoreRing({ label, value, tone = "teal" }) {
  const numeric = typeof value === "number" ? value : 0;
  const percent = Math.max(0, Math.min(100, Math.round(numeric * 100)));
  const styles = { "--percent": `${percent}%` };

  return (
    <div className={`score-ring-card score-ring-${tone}`}>
      <div className="score-ring" style={styles}>
        <div className="score-ring-inner">
          <strong>{percent}%</strong>
          <span>{repairText(label)}</span>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, note, tone = "teal" }) {
  return (
    <div className={`stat-card stat-card-${tone}`}>
      <span className="stat-card-label">{repairText(label)}</span>
      <strong>{value ?? EM_DASH}</strong>
      {note ? <small>{repairText(note)}</small> : null}
    </div>
  );
}

function FieldList({ title, items }) {
  if (!items.length) return null;

  return (
    <section className="dashboard-card field-list-card">
      <div className="dashboard-card-header">
        <h3>{repairText(title)}</h3>
        <span className="section-badge">{items.length} campos</span>
      </div>
      <div className="field-list">
        {items.map((item) => (
          <div className="field-list-row" key={item.id}>
            <div className="field-list-meta">
              <span className="field-list-group">{repairText(item.groupName)}</span>
              <strong>{prettifyLabel(item.fieldName)}</strong>
            </div>
            <div className="field-list-value">{valueToDisplay(item.fieldValue)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ProgressBlock({ label, value, tone = "teal" }) {
  const numeric = typeof value === "number" ? value : 0;
  const width = `${Math.max(0, Math.min(100, Math.round(numeric * 100)))}%`;
  return (
    <div className="progress-block">
      <div className="progress-block-head">
        <span>{repairText(label)}</span>
        <strong>{formatNumber(numeric)}</strong>
      </div>
      <div className="progress-track">
        <div className={`progress-fill progress-fill-${tone}`} style={{ width }} />
      </div>
    </div>
  );
}

function SectionPanel({ pageName, sectionData }) {
  const entries = Object.entries(sectionData || {}).filter(([, value]) => value !== null && value !== undefined && value !== "");
  if (!entries.length) return null;

  return (
    <section className="dashboard-card section-panel">
      <div className="dashboard-card-header">
        <h3>{repairText(pageName)}</h3>
        <span className="section-badge">{entries.length} blocos</span>
      </div>
      <div className="section-panel-grid">
        {entries.map(([sectionName, sectionValue]) => (
          <div className="section-snippet" key={`${pageName}-${sectionName}`}>
            <span className="section-snippet-label">{prettifyLabel(sectionName)}</span>
            <div className="section-snippet-body">
              {String(repairText(sectionValue))
                .split("\n")
                .map((line) => line.trim())
                .filter(Boolean)
                .slice(0, 10)
                .map((line, index) => (
                  <span className="section-line" key={`${sectionName}-${index}`}>
                    {line}
                  </span>
                ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function YoloPanel({ blocksByPage }) {
  const pages = Object.entries(blocksByPage || {}).filter(([, blocks]) => Array.isArray(blocks) && blocks.length > 0);
  if (!pages.length) return null;

  return (
    <section className="dashboard-card">
      <div className="dashboard-card-header">
        <h3>Deteções YOLO</h3>
        <span className="section-badge">blocos e confiança</span>
      </div>

      <div className="yolo-page-grid">
        {pages.map(([pageName, blocks]) => (
          <div className="yolo-page-card" key={pageName}>
            <div className="yolo-page-head">
              <strong>{repairText(pageName)}</strong>
              <span>{blocks.length} blocos</span>
            </div>

            <div className="yolo-block-list">
              {blocks.map((block) => (
                <div className="yolo-block" key={`${pageName}-${block.region_index}-${block.label}`}>
                  <div className="yolo-block-head">
                    <span className="yolo-block-label">{repairText(block.label || "bloco")}</span>
                    <span className="yolo-block-confidence">
                      {typeof block.confidence === "number" ? `${Math.round(block.confidence * 100)}%` : EM_DASH}
                    </span>
                  </div>
                  <div className="yolo-block-meta">
                    <span>Região {block.region_index ?? EM_DASH}</span>
                    <span>
                      {block?.bbox?.x1 ?? 0},{block?.bbox?.y1 ?? 0} → {block?.bbox?.x2 ?? 0},{block?.bbox?.y2 ?? 0}
                    </span>
                  </div>
                  <div className="yolo-block-text">
                    {String(repairText(block.text || ""))
                      .split("\n")
                      .map((line) => line.trim())
                      .filter(Boolean)
                      .slice(0, 8)
                      .map((line, index) => (
                        <span key={`${pageName}-${block.region_index}-${index}`}>{line}</span>
                      ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function ResultViewer({ data }) {
  const [copied, setCopied] = useState(false);

  if (!data) {
    return (
      <div className="dashboard-card empty-state">
        <h3>Sem resultados ainda</h3>
        <p>Processa um certificado para visualizar campos, métricas, secções e tabelas.</p>
      </div>
    );
  }

  const documentData = repairText(data?.document || null);
  const method = repairText(data?.method || null);
  const summary = data?.processing_summary || null;
  const documentMetrics = data?.metrics?.document || null;
  const globalMetrics = data?.metrics?.global || null;
  const pageSections = repairText(data?.raw?.sections?.page_sections || null);
  const yoloBlocks = repairText(data?.raw?.sections?.page_region_blocks || null);
  const tableEntries = buildTableEntries(documentData);
  const fieldItems = flattenDocument(documentData).filter((item) => item.fieldValue !== null && item.fieldValue !== "");
  const rowCounts = Object.entries(documentMetrics?.tables?.row_counts || {});

  async function handleCopyJson() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch (error) {
      console.error(error);
    }
  }

  return (
    <div className="result-layout">
      <section className="dashboard-top-grid">
        <div className="dashboard-card dashboard-hero">
          <div className="dashboard-card-header">
            <div>
              <span className="section-eyebrow">Documento analisado</span>
              <h2>{repairText(data?.source_pdf || "Sem ficheiro")}</h2>
            </div>
            <div className="hero-actions">
              <span className="section-badge">{repairText(method?.short_label || method?.label || "Método")}</span>
              <button type="button" className="secondary-action" onClick={handleCopyJson}>
                {copied ? "JSON copiado" : "Copiar JSON"}
              </button>
            </div>
          </div>

          <div className="hero-meta-grid">
            <StatCard
              label="Tempo de execução"
              value={summary?.elapsed_seconds !== undefined ? `${summary.elapsed_seconds}s` : EM_DASH}
              note={`${summary?.scripts_executed?.length ?? 0} scripts`}
              tone="blue"
            />
            <StatCard
              label="Campos aplicáveis"
              value={`${documentMetrics?.fields?.filled_fields ?? EM_DASH}/${documentMetrics?.fields?.total_fields ?? EM_DASH}`}
              note="campos encontrados nos blocos"
              tone="teal"
            />
            <StatCard
              label="Campos estritos"
              value={`${documentMetrics?.fields?.schema_filled_fields ?? EM_DASH}/${documentMetrics?.fields?.schema_total_fields ?? EM_DASH}`}
              note="schema fixo"
              tone="amber"
            />
            <StatCard
              label="Tabelas"
              value={`${documentMetrics?.tables?.found_tables ?? 0}/${documentMetrics?.tables?.expected_tables ?? 0}`}
              note={repairText(documentMetrics?.instrument_type || "sem tipo")}
              tone="rose"
            />
          </div>
        </div>

        <ScoreRing label="Aplicável" value={documentMetrics?.fields?.completeness_score} tone="teal" />
        <ScoreRing label="Estrita" value={documentMetrics?.fields?.schema_completeness_score} tone="amber" />
        <ScoreRing label="Tabelas" value={documentMetrics?.tables?.table_extraction_score} tone="blue" />
      </section>

      <section className="analytics-grid">
        <div className="dashboard-card">
          <div className="dashboard-card-header">
            <h3>Desempenho do documento</h3>
            <span className="section-badge">Visão geral</span>
          </div>
          <div className="progress-stack">
            <ProgressBlock label="Completude aplicável" value={documentMetrics?.fields?.completeness_score} tone="teal" />
            <ProgressBlock label="Completude estrita" value={documentMetrics?.fields?.schema_completeness_score} tone="amber" />
            <ProgressBlock label="Extração tabular" value={documentMetrics?.tables?.table_extraction_score} tone="blue" />
            <ProgressBlock label="Média global aplicável" value={globalMetrics?.avg_field_completeness} tone="teal" />
            <ProgressBlock label="Média global estrita" value={globalMetrics?.avg_schema_field_completeness} tone="amber" />
          </div>
        </div>

        <div className="dashboard-card">
          <div className="dashboard-card-header">
            <h3>Leitura tabular</h3>
            <span className="section-badge">{rowCounts.length} grupos</span>
          </div>
          <div className="mini-bars">
            {rowCounts.length === 0 ? (
              <p className="muted-copy">Sem linhas tabulares contabilizadas.</p>
            ) : (
              rowCounts.map(([tableName, count]) => (
                <div className="mini-bar-row" key={tableName}>
                  <div className="mini-bar-head">
                    <span>{prettifyLabel(tableName)}</span>
                    <strong>{count}</strong>
                  </div>
                  <div className="mini-bar-track">
                    <div className="mini-bar-fill" style={{ width: `${Math.min(100, 16 + count * 3)}%` }} />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <FieldList title="Campos extraídos" items={fieldItems} />

      <YoloPanel blocksByPage={yoloBlocks} />

      {pageSections && (
        <section className="dashboard-section-grid">
          {Object.entries(pageSections).map(([pageName, sectionData]) => (
            <SectionPanel key={pageName} pageName={pageName} sectionData={sectionData} />
          ))}
        </section>
      )}

      <div className="tables-grid">
        {tableEntries.length === 0 ? (
          <div className="dashboard-card empty-state">
            <h3>Sem tabelas interpretadas</h3>
            <p>Este método não devolveu tabelas estruturadas para o documento atual.</p>
          </div>
        ) : (
          tableEntries.map(([tableName, rows]) => (
            <DataTable
              key={tableName}
              title={rows?.__title ? `Tabela ${rows.__title}` : `Tabela ${tableName}`}
              rows={rows}
            />
          ))
        )}
      </div>

      <div className="dashboard-card json-card">
        <div className="dashboard-card-header">
          <h3>JSON bruto</h3>
          <span className="section-badge">Depuração</span>
        </div>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    </div>
  );
}
