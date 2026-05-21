const EM_DASH = "\u2014";

const REPLACEMENTS = new Map([
  ["Ã¢â‚¬â€", EM_DASH],
  ["SecÃ§Ãµes", "Secções"],
  ["MÃ©todo", "Método"],
  ["DescriÃ§Ã£o", "Descrição"],
  ["Resumo da execuÃ§Ã£o", "Resumo da execução"],
  ["MÃ©tricas", "Métricas"],
  ["ExtraÃ§Ã£o", "Extração"],
  ["MÃ©dia", "Média"],
  ["CondiÃ§Ãµes", "Condições"],
  ["ReferÃªncia", "Referência"],
  ["NÃ£o", "Não"],
  ["nÃ£o", "não"],
  ["hÃ¡", "há"],
  ["InvestigaciÃ³n", "Investigación"],
  ["CÃ¤diz", "Cádiz"],
  ["Designagäo", "Designação"],
  ["Calibracäo", "Calibração"],
  ["Instalacöes", "Instalações"],
  ["CONDICöES", "CONDIÇÕES"],
  ["Diämetro", "Diâmetro"],
  ["Diametro", "Diâmetro"],
  ["Padräo", "Padrão"],
  ["N°", "Nº"],
  ["Applicable", "Aplicável"],
  ["Strict", "Estrita"],
  ["Applicable Completeness", "Completude aplicável"],
  ["Strict Completeness", "Completude estrita"],
  ["Table Extraction", "Extração tabular"],
  ["Debug", "Depuração"],
  ["Dashboard", "Painel"],
  ["Document Intelligence", "Inteligência Documental"],
  ["Calibration Certificate Dashboard", "Painel de Certificados de Calibração"],
  ["Performance do documento", "Desempenho do documento"],
  ["Campos strict", "Campos estritos"],
  ["Média global strict", "Média global estrita"],
]);

const FIXED_LABELS = {
  issue_date: "Data de emissão",
  certificate_number: "Número do certificado",
  calibration_date: "Data de calibração",
  name: "Nome",
  address: "Morada",
  designation: "Designação",
  brand: "Marca",
  model: "Modelo",
  serial_number: "Número de série",
  internal_ref: "Referência interna",
  range: "Intervalo de indicação",
  resolution: "Resolução",
  estimated_resolution: "Resolução estimada",
  class: "Classe",
  state: "Estado do equipamento",
  location: "Local",
  temperature: "Temperatura",
  humidity: "Humidade",
  accreditation_annex: "Anexo técnico de acreditação",
  standard_or_procedure: "Norma ou procedimento",
  standard_value: "Padrão",
  reading_value: "Leitura no equipamento",
  error_value: "Erro",
  uncertainty_value: "Incerteza",
  mean_value: "Média",
  page_01: "Página 1",
  page_02: "Página 2",
};

export function repairText(value) {
  if (value === null || value === undefined) return value;
  if (Array.isArray(value)) return value.map((item) => repairText(item));
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, repairText(item)]),
    );
  }
  if (typeof value !== "string") return value;

  let text = value;
  for (const [from, to] of REPLACEMENTS.entries()) {
    text = text.split(from).join(to);
  }
  return text;
}

export function prettifyLabel(label) {
  const raw = String(label);
  if (FIXED_LABELS[raw]) {
    return FIXED_LABELS[raw];
  }

  return repairText(
    raw
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase()),
  );
}

export { EM_DASH };
