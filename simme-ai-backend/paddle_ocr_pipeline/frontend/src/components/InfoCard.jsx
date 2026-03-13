function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

export default function InfoCard({ title, data }) {
  if (!data) return null;

  return (
    <div className="info-card">
      <h3>{title}</h3>
      <div className="info-card-body">
        {Object.entries(data).map(([key, value]) => (
          <div className="info-row" key={key}>
            <span className="info-label">{key}</span>
            <span className="info-value">{formatValue(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}