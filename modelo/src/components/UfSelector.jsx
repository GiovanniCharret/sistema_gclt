// Seleção da UF antes do envio (decisão: granularidade por UF).
// As UFs vêm do /api/contexto (filtradas pelo grupo do usuário) — via prop `ufs`.
// Domínios não registrados já são barrados no login, então aqui sempre há UFs.
export default function UfSelector({ ufs, onSelect }) {
  return (
    <div className="auth-shell">
      <div className="auth-card wide">
        <p className="eyebrow">Passo 2 · Selecione a UF e o contrato</p>
        <h1 className="auth-title">Unidade da Federação</h1>
        <div className="uf-grid">
          {ufs.map((uf) => (
            <button key={uf.sigla} type="button" className="uf-item" onClick={() => onSelect(uf)}>
              <span className="uf-sigla">{uf.sigla}</span>
              <span className="uf-nome">{uf.nome}</span>
              <span className="uf-meta">{uf.contratos} contrato{uf.contratos > 1 ? "s" : ""}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
