import { useState } from "react";
import * as api from "../lib/api";

// Tela de entrada — login real contra POST /api/login. Se o backend responder
// { precisaTrocarSenha: true }, delega ao App para exibir a tela de troca (1º acesso).
export default function AuthScreen({ onAutenticado, onPrecisaTrocar }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");     // mensagem genérica do "esqueci senha"
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    setAviso("");
    setCarregando(true);
    try {
      const { ok, status, dados } = await api.login(email.trim(), senha);
      if (status === 401) {
        setErro("E-mail ou senha inválidos.");
        return;
      }
      if (!ok) {
        setErro("Não foi possível entrar. Tente novamente.");
        return;
      }
      // 1º acesso: backend pede troca de senha (sem token pleno). Passa a senha
      // recém-validada adiante para a tela de troca não pedi-la de novo.
      if (dados?.precisaTrocarSenha) {
        onPrecisaTrocar(email.trim(), senha);
        return;
      }
      // Login pleno: guarda o token e entra.
      onAutenticado(email.trim(), dados.token);
    } catch {
      setErro("Não foi possível conectar ao servidor.");
    } finally {
      setCarregando(false);
    }
  }

  async function handleEsqueci() {
    setErro("");
    setAviso("");
    const alvo = email.trim();
    if (!alvo) {
      setErro("Informe seu e-mail acima para redefinir a senha.");
      return;
    }
    try {
      // Resposta é sempre genérica (não revela se o e-mail existe).
      await api.esqueciSenha(alvo);
      setAviso("Se o e-mail estiver cadastrado, enviamos uma nova senha temporária.");
    } catch {
      setErro("Não foi possível conectar ao servidor.");
    }
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
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e-mail@agente"
            />
          </div>
          <div className="field">
            <label className="field-label">Senha</label>
            <input
              type="password"
              autoComplete="current-password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          {erro && <p className="auth-error">{erro}</p>}
          {aviso && <p className="auth-ok">{aviso}</p>}
          <button className="btn-primary full" type="submit" disabled={carregando}>
            {carregando ? "Entrando…" : "Entrar"}
          </button>
        </form>
        <div className="auth-links">
          <button type="button" className="auth-link" onClick={handleEsqueci}>
            Esqueci minha senha
          </button>
        </div>
      </div>
    </div>
  );
}
