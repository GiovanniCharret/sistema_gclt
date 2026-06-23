import { useState } from "react";

// Tela de entrada genérica (mock). Qualquer "Entrar" autentica — sem backend.
export default function AuthScreen({ onEnter }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    onEnter(email.trim() || "operador@enbpar.gov.br");
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <p className="eyebrow">ENBPar - Diretoria de Gestão de Programas - GCLT</p>
        <h1 className="auth-title">Entrar</h1>
        <p className="auth-subtitle">Sistema Gerenciador do Programa Luz para Todos</p>
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="field">
            <label className="field-label">E-mail</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e-mail@agente"
            />
          </div>
          <div className="field">
            <label className="field-label">Senha</label>
            <input
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          <button className="btn-primary full" type="submit">Entrar</button>
        </form>
        <div className="auth-links">
          <button type="button" className="auth-link">Esqueci minha senha</button>
        </div>
      </div>
    </div>
  );
}
