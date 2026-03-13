import InfoCard from "./InfoCard";
import DataTable from "./DataTable";

export default function ResultViewer({ data }) {
  if (!data) {
    return (
      <div className="result-box">
        <p>Ainda não há resultados.</p>
      </div>
    );
  }

const documentData = data?.document || null;

  return (
    <div className="result-layout">
      <div className="cards-grid">
        <InfoCard title="Header" data={documentData?.header} />
        <InfoCard title="Cliente" data={documentData?.customer} />
        <InfoCard title="Equipamento" data={documentData?.equipment} />
        <InfoCard title="Condições de trabalho" data={documentData?.work_conditions} />
        <InfoCard title="Referência" data={documentData?.reference} />
      </div>

      <div className="tables-grid">
        <DataTable
          title="Tabela E_contact_partial"
          rows={documentData?.tables?.E_contact_partial}
        />
        <DataTable
          title="Tabela S_scale_change"
          rows={documentData?.tables?.S_scale_change}
        />
        <DataTable
          title="Tabela L_line_contact"
          rows={documentData?.tables?.L_line_contact}
        />
        <DataTable
          title="Tabela pressure_error_table"
          rows={documentData?.tables?.pressure_error_table}
        />
        <DataTable
          title="Tabela environmental_conditions"
          rows={documentData?.tables?.environmental_conditions}
        />
      </div>

      <div className="result-box">
        <h3>JSON bruto</h3>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    </div>
  );
}