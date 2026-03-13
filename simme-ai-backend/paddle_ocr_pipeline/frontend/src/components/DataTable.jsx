export default function DataTable({ title, rows }) {
  if (!rows || !Array.isArray(rows) || rows.length === 0) return null;

  const columns = Object.keys(rows[0]);

  return (
    <div className="table-card">
      <h3>{title}</h3>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
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