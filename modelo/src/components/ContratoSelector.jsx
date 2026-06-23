import { contratosDaUf } from "../seedData";

// Passo 2 (sublista) — escolha do contrato (chave principal de cada registro).
// Lista apenas contratos da UF cujo `vigente` é diferente de "Encerrado".
// Cartões em grade, espelhando o painel de UFs.
export default function ContratoSelector({ uf, onSelect, onBack }) {
  const lista = contratosDaUf(uf.sigla);

  return (
    <div className="auth-shell">
      <div className="auth-card wide">
        <p className="eyebrow">Passo 2 · Selecione o contrato</p>
        <h1 className="auth-title">Contrato — {uf.sigla} · {uf.nome}</h1>
        <div className="contrato-grid">
          {lista.map((c) => (
            <button key={c.numero} type="button" className="contrato-tile" onClick={() => onSelect(c)}>
              <span className="contrato-numero">{c.numero}</span>
              <span className="contrato-meta">{c.tipo_contrato}, {c.tranche}</span>
              <span className="contrato-sigla">{c.sigla} · {c.uf}</span>
              <span className="contrato-ucs">{c.ucs.toLocaleString("pt-BR")} UCs cadastradas</span>
              <span className={`contrato-vig ${c.vigente === "Encerramento" ? "encerramento" : "andamento"}`}>
                {c.vigente}
              </span>
            </button>
          ))}
        </div>
        <div className="btn-row">
          <button className="btn-back" onClick={onBack}>← Trocar UF</button>
        </div>
      </div>
    </div>
  );
}
