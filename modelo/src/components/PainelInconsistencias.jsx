import { useState } from "react";
import { PREVIEW_COLS } from "../seedData";
import { baixarRelatorioCsv } from "../lib/relatorioCsv";

// Entregável central: resumo + grupos por tipo de regra (expansíveis) ao lado
// de um preview das primeiras linhas da planilha com as células sinalizadas.
// Dados vêm do /api/validar (via props). Avisos NÃO bloqueiam — só erros impedem o salvamento.
export default function PainelInconsistencias({
  uf, contrato, grupos, previewRows, totalErros, totalAvisos, linhasLidas, onCorrigir, onToast,
}) {
  const ucs = linhasLidas;
  // primeiro grupo aberto por padrão
  const [open, setOpen] = useState(() => ({ 0: true }));
  const toggle = (i) => setOpen((o) => ({ ...o, [i]: !o[i] }));

  return (
    <section className="card">
      <div className="card-header">
        <div>
          <p className="section-kicker">Validação</p>
          <h2 className="card-title">Inconsistências encontradas</h2>
        </div>
        <span className="section-badge">{contrato.numero} · {uf.sigla}</span>
      </div>

      <div className="assist">
        <div className="assist-avatar">🤖</div>
        <div className="assist-body">
          Recebi a planilha do contrato <strong>{contrato.numero}</strong> ({contrato.sigla} · {uf.sigla}). Li{" "}
          <strong>{ucs.toLocaleString("pt-BR")} unidades consumidoras</strong>. Encontrei{" "}
          <strong>{totalErros} erros</strong> e <strong>{totalAvisos} avisos</strong>.
          Os <strong>erros impedem o salvamento</strong> na base — corrija e reenvie.
          Os avisos não bloqueiam, mas recomendo revisar.
        </div>
      </div>

      <div className="val-summary">
        <span className="val-pill err"><span className="big">{totalErros}</span> erros</span>
        <span className="val-pill warn"><span className="big">{totalAvisos}</span> avisos</span>
        <span className="val-pill">{ucs.toLocaleString("pt-BR")} UCs lidas</span>
        <span className="val-pill">{grupos.length} regras acionadas</span>
      </div>

      <div className="av-split">
        {/* Coluna 1 — inconsistências por regra */}
        <div>
          <p className="av-col-title">Inconsistências por regra</p>
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
                    <span className="issue-loc">{r.loc}</span>
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
        </div>

        {/* Coluna 2 — preview da planilha */}
        <div>
          <p className="av-col-title">Prévia da planilha (primeiras linhas)</p>
          <div className="av-preview-wrap">
            <div className="av-preview-scroll">
              <table className="av-preview">
                <thead>
                  <tr>{PREVIEW_COLS.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
                </thead>
                <tbody>
                  {previewRows.map((row) => (
                    <tr key={row.linha}>
                      {PREVIEW_COLS.map((c) => {
                        const flag = row.flags[c.key];
                        const cls = c.key === "linha" || c.key === "odi" || c.key === "uc" || c.key === "ibge" ? "num" : "";
                        return (
                          <td key={c.key} className={cls}>
                            <span className={flag === "err" ? "cell-err" : flag === "warn" ? "cell-warn" : ""}>
                              {row[c.key]}
                            </span>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="av-preview-foot">
              Células destacadas = inconsistências nesta amostra. Vermelho = erro · laranja = aviso.
            </div>
          </div>
        </div>
      </div>

      <div className="panel-actions">
        <button className="btn-primary" onClick={onCorrigir}>Corrigir e reenviar</button>
        <button
          className="btn-ghost"
          onClick={() => { baixarRelatorioCsv(contrato, uf, grupos); onToast("Relatório de inconsistências (.csv) gerado"); }}
        >
          Baixar relatório (.csv)
        </button>
      </div>
    </section>
  );
}
