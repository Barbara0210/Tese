import { EM_DASH, prettifyLabel, repairText } from "../utils/text";

export default function DataTable({ title, rows }) {
  const tableData = Array.isArray(rows) ? { rows } : rows;
  const rowList = Array.isArray(tableData?.rows) ? tableData.rows : [];

  if (rowList.length === 0) return null;

  const columns =
    Array.isArray(tableData?.columns) && tableData.columns.length > 0
      ? tableData.columns
      : Object.keys(rowList[0]).filter((key) => key !== "values");

  const fixedSections = Array.isArray(tableData?.sections) ? repairText(tableData.sections) : [];
  const fixedUnits = Array.isArray(tableData?.units) ? repairText(tableData.units) : [];

  return (
    <div className="table-card">
      <div className="table-card-header">
        <h3>{repairText(title)}</h3>
        {(fixedSections.length > 0 || fixedUnits.length > 0) && (
          <div className="table-badges">
            {fixedSections.map((section) => (
              <span key={`section-${section}`} className="table-badge">
                {section}
              </span>
            ))}
            {fixedUnits.map((unit) => (
              <span key={`unit-${unit}`} className="table-badge table-badge-soft">
                {unit}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{prettifyLabel(column)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowList.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((column) => (
                  <td key={column}>
                    {row[column] === null || row[column] === undefined || row[column] === ""
                      ? EM_DASH
                      : String(repairText(row[column]))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
