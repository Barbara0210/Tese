import { repairText } from "../utils/text";

function getTone(status) {
  const value = String(status || "").toLowerCase();
  if (value.includes("erro")) return "error";
  if (value.includes("conclu")) return "success";
  if (value.includes("process") || value.includes("enviar") || value.includes("obter")) return "active";
  return "idle";
}

export default function StatusBox({ status }) {
  const tone = getTone(status);

  return (
    <div className={`status-box status-box-${tone}`}>
      <div className="status-dot" />
      <div className="status-content">
        <span className="status-label">Estado do pipeline</span>
        <strong>{repairText(status)}</strong>
      </div>
    </div>
  );
}
