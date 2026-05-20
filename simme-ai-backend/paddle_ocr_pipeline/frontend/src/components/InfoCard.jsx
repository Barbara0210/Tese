function prettifyLabel(label) {
  return String(label)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "â€”";
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(", ") : "â€”";
  }
  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
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
            <span className="info-label">{prettifyLabel(key)}</span>
            <span className="info-value info-value-multiline">{formatValue(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
