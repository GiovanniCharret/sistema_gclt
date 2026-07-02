import { PREVIEW_COLS } from "../seedData";
import { baixarRelatorioCsv } from "../lib/relatorioCsv";
import RuleGroups, { formatarLoc } from "./RuleGroups";

// Entregável central: resumo + grupos por tipo de regra (expansíveis) ao lado
// de um preview das primeiras linhas da planilha com as células sinalizadas.
// Dados vêm do /api/validar (via props). Avisos NÃO bloqueiam — só erros impedem o salvamento.
export default function PainelInconsistencias({
  uf, contrato, grupos, previewRows, totalErros, totalAvisos, linhasLidas, onCorrigir, onToast,
}) {
  const ucs = linhasLidas;
  // Erros antes de avisos (assim ODI/UC vêm sempre antes das tipologias).
  const gruposOrdenados = [...grupos].sort((a, b) => (a.sev === "err" ? 0 : 1) - (b.sev === "err" ? 0 : 1));

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
          <strong>{ucs.toLocaleString("pt-BR")} unidades consumidoras</strong>.{" "}
          <span className="assist-erro">
            Encontrei {totalErros} {totalErros === 1 ? "erro" : "erros"}. Os erros impedem o salvamento na base
          </span>{" "}
          — corrija e reenvie.
          {totalAvisos > 0 && " Recomendo ficar atento aos avisos abaixo também."}
        </div>
      </div>

      <div className="val-summary">
        <span className="val-pill err"><span className="big">{totalErros}</span> erros</span>
        <span className="val-pill warn"><span className="big">{totalAvisos}</span> avisos</span>
        <span className="val-pill">{ucs.toLocaleString("pt-BR")} UCs lidas</span>
      </div>

      <div className="av-split">
        {/* Coluna 1 — inconsistências por regra */}
        <div>
          <p className="av-col-title">Inconsistências por regra</p>
          <RuleGroups grupos={gruposOrdenados} />
        </div>

        {/* Coluna 2 — planilha enviada */}
        <div className="av-col-preview">
          <p className="av-col-title">Planilha enviada</p>
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
                              {c.key === "linha" ? formatarLoc(row[c.key]) : row[c.key]}
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
