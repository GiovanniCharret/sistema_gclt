import { useState } from "react";

// "L47" → "Linha 47" (deixa "—" e demais como estão).
export function formatarLoc(loc) {
  const m = /^L(\d+)$/.exec(String(loc ?? ""));
  return m ? `Linha ${m[1]}` : loc;
}

// Lista de grupos de inconsistências (expansíveis por regra). Reusada no painel de
// erros e na tela de sucesso (para mostrar os avisos que não bloqueiam).
export default function RuleGroups({ grupos }) {
  // Primeiro grupo aberto por padrão.
  const [open, setOpen] = useState(() => ({ 0: true }));
  const toggle = (i) => setOpen((o) => ({ ...o, [i]: !o[i] }));

  return (
    <>
      {grupos.map((g, i) => (
        <div key={g.title} className={`rule-group${open[i] ? " is-open" : ""}`}>
          <button className="rule-head" onClick={() => toggle(i)}>
            <span className={`sev-badge ${g.sev}`}>{g.sev === "err" ? "Erro" : "Aviso"}</span>
            <span className="rule-titles">
              <span className="rule-title">{g.title}</span><br />
              <span className="rule-desc">{g.desc}</span>
            </span>
            <span className="rule-count">{g.count}</span>
            <span className="rule-chevron">▸</span>
          </button>
          <div className="rule-body">
            {g.rows.map((r, j) => (
              <div className="issue-row" key={j}>
                <span className="issue-loc">{formatarLoc(r.loc)}</span>
                <span className="issue-field">{r.field}</span>
                <span className="issue-msg">{r.problem} <span className="sug">→ {r.sug}</span></span>
              </div>
            ))}
            {g.count > g.rows.length && (
              <div className="issue-row">
                <span className="issue-loc"></span>
                <span className="issue-field"></span>
                <span className="issue-msg sug">+ {g.count - g.rows.length} outra(s) ocorrência(s)…</span>
              </div>
            )}
          </div>
        </div>
      ))}
    </>
  );
}
