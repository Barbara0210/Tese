function prettifyColumnName(name) {
  return String(name)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function DataTable({ title, rows }) {
  const tableData = Array.isArray(rows) ? { rows } : rows;
  const rowList = Array.isArray(tableData?.rows) ? tableData.rows : [];

  if (rowList.length === 0) return null;

  const columns =
    Array.isArray(tableData?.columns) && tableData.columns.length > 0
      ? tableData.columns
      : Object.keys(rowList[0]).filter((key) => key !== "values");

  return (
    <div className="table-card">
      <h3>{title}</h3>
      {(Array.isArray(tableData?.sections) || Array.isArray(tableData?.units)) && (
        <div className="table-meta">
          {Array.isArray(tableData?.sections) && tableData.sections.length > 0 && (
            <p>
              <strong>Secções:</strong> {tableData.sections.join(", ")}
            </p>
          )}
          {Array.isArray(tableData?.units) && tableData.units.length > 0 && (
            <p>
              <strong>Unidades:</strong> {tableData.units.join(", ")}
            </p>
          )}
        </div>
      )}
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>{prettifyColumnName(col)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowList.map((row, idx) => (
              <tr key={idx}>
                {columns.map((col) => (
                  <td key={col}>
                    {row[col] === null || row[col] === undefined || row[col] === ""
                      ? "—"
                      : String(row[col])}
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
