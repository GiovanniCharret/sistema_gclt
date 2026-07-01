// Estado final: planilha sem erros bloqueantes → validada e enviada por e-mail.
export default function SucessoEnvio({ uf, contrato, linhasLidas, onNova }) {
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
        <span className="mi">Lote <b>#A1B2C3</b></span>
      </div>
      <button className="btn-primary" onClick={onNova}>Iniciar nova validação</button>
    </section>
  );
}
