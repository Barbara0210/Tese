import { EM_DASH, prettifyLabel, repairText } from "../utils/text";

function renderPrimitive(value) {
  if (value === null || value === undefined || value === "") {
    return <span className="info-empty">{EM_DASH}</span>;
  }

  const repaired = repairText(String(value));
  const lines = repaired
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length <= 1) {
    return <span className="info-inline">{repaired}</span>;
  }

  return (
    <div className="info-lines">
      {lines.map((line, index) => (
        <span key={`${line}-${index}`} className="info-line-chip">
          {line}
        </span>
      ))}
    </div>
  );
}

function renderValue(value) {
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="info-empty">{EM_DASH}</span>;
    return (
      <div className="info-tags">
        {repairText(value).map((item, index) => (
          <span key={`${item}-${index}`} className="info-tag">
            {String(item)}
          </span>
        ))}
      </div>
    );
  }

  if (value && typeof value === "object") {
    const entries = Object.entries(repairText(value));
    if (entries.length === 0) return <span className="info-empty">{EM_DASH}</span>;

    return (
      <div className="info-nested">
        {entries.map(([nestedKey, nestedValue]) => (
          <div className="info-nested-row" key={nestedKey}>
            <span className="info-nested-label">{prettifyLabel(nestedKey)}</span>
            <div className="info-nested-value">{renderPrimitive(nestedValue)}</div>
          </div>
        ))}
      </div>
    );
  }

  return renderPrimitive(value);
}

export default function InfoCard({ title, data }) {
  if (!data) return null;

  return (
    <div className="info-card">
      <h3>{repairText(title)}</h3>
      <div className="info-card-body">
        {Object.entries(data).map(([key, value]) => (
          <div className="info-row" key={key}>
            <span className="info-label">{prettifyLabel(key)}</span>
            <div className="info-value">{renderValue(value)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
