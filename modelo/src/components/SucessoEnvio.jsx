import RuleGroups from "./RuleGroups";
import { baixarRelatorioCsv } from "../lib/relatorioCsv";

// Estado final: planilha sem erros bloqueantes → validada e enviada. Mesmo aceita,
// mostra os AVISOS (não bloqueiam) para o operador conferir, com exportação em .csv.
export default function SucessoEnvio({ uf, contrato, linhasLidas, totalAvisos, grupos, onNova, onToast }) {
  const avisos = (grupos || []).filter((g) => g.sev === "warn");

  return (
    <section className="card success-card">
      <div className="success-icon">✓</div>
      <h2 className="success-title">Planilha validada e salva na base</h2>
      <p className="success-sub">
        Nenhuma inconsistência bloqueante. As unidades consumidoras foram registradas sob o
        contrato e estão disponíveis para o Painel de Monitoramento do MME.
      </p>
      <div className="success-meta">
        <span className="mi"><b>{(linhasLidas ?? 0).toLocaleString("pt-BR")}</b> UCs classificadas</span>
        <span className="mi">Contrato <b>{contrato.numero}</b></span>
        <span className="mi">{contrato.tipo_contrato} · {contrato.tranche}</span>
        <span className="mi">UF <b>{uf.sigla}</b></span>
        <span className="mi">Competência <b>06/2026</b></span>
      </div>

      {avisos.length > 0 && (
        <div className="success-avisos">
          <p className="av-col-title">
            Avisos - não bloquearam o envio
          </p>
          <p className="success-avisos-hint">
            Futuramente esses itens vão bloquear o envio. Fique atento.
          </p>
          <RuleGroups grupos={avisos} />
        </div>
      )}

      <div className="panel-actions success-actions">
        {avisos.length > 0 && (
          <button
            className="btn-ghost"
            onClick={() => { baixarRelatorioCsv(contrato, uf, avisos); onToast?.("Relatório de avisos (.csv) gerado"); }}
          >
            Baixar relatório (.csv)
          </button>
        )}
        <button className="btn-primary" onClick={onNova}>Iniciar nova validação</button>
      </div>
    </section>
  );
}
