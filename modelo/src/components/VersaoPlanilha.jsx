import { useState } from "react";
import * as api from "../lib/api";

// Passo 3 — conferência da versão da planilha antes do envio.
const VERSAO_DATA = "23/06/2026";

export default function VersaoPlanilha({ token, onAvancar, onBack }) {
  const [baixado, setBaixado] = useState(false);
  const [erro, setErro] = useState("");

  async function baixar() {
    setErro("");
    try {
      await api.baixarModelo(token);
      setBaixado(true);
    } catch {
      setErro("Não foi possível baixar o modelo. Tente novamente.");
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card wide">
        <p className="eyebrow">Passo 3 · Confira a versão da sua planilha</p>
        <h1 className="auth-title">Versão da planilha</h1>
        <p className="auth-subtitle">
          Confira se sua versão de planilha está atualizada. Não é possível enviar dados com uma
          versão de planilha desatualizada.
        </p>

        <div className="versao-card">
          <p className="section-kicker">Modelo oficial</p>
          <h2 className="card-title">Versão de {VERSAO_DATA}</h2>
          <button className="btn-ghost versao-btn" onClick={baixar}>Baixar modelo</button>
          {baixado && <p className="versao-baixado">✓ Modelo baixado</p>}
          {erro && <p className="auth-error">{erro}</p>}
        </div>

        <div className="btn-row">
          <button className="btn-back" onClick={onBack}>← Trocar contrato</button>
          <button className="btn-primary" onClick={onAvancar}>Avançar para o envio</button>
        </div>
      </div>
    </div>
  );
}
