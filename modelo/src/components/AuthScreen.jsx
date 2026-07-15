import { useState } from "react";
import * as api from "../lib/api";

// Tela de entrada — login real contra POST /api/login. Se o backend responder
// { precisaTrocarSenha: true }, delega ao App para exibir a tela de troca (1º acesso).
export default function AuthScreen({ onAutenticado, onPrecisaTrocar }) {
  // Fallback temporário: login por "operador" (o e-mail foi adiado para V1/V2).
  const [operador, setOperador] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");     // mensagem genérica do "esqueci senha"
  const [resetado, setResetado] = useState(false); // reset MVP feito → tela de aviso
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    setAviso("");
    setCarregando(true);
    try {
      const { ok, status, dados } = await api.login(operador.trim(), senha);
      if (status === 401) {
        setErro("Operador ou senha inválidos.");
        return;
      }
      if (status === 403) {
        // Operador não mapeado a nenhum grupo — informa e não entra.
        setErro(dados?.detail || "Operador não registrado no sistema.");
        return;
      }
      if (!ok) {
        setErro("Não foi possível entrar. Tente novamente.");
        return;
      }
      // 1º acesso: backend pede troca de senha (sem token pleno). Passa a senha
      // recém-validada adiante para a tela de troca não pedi-la de novo.
      if (dados?.precisaTrocarSenha) {
        onPrecisaTrocar(operador.trim(), senha);
        return;
      }
      // Login pleno: guarda o token e entra.
      onAutenticado(operador.trim(), dados.token);
    } catch {
      setErro("Não foi possível conectar ao servidor.");
    } finally {
      setCarregando(false);
    }
  }

  async function handleEsqueci() {
    setErro("");
    setAviso("");
    const alvo = operador.trim();
    if (!alvo) {
      setErro("Informe seu operador acima para redefinir a senha.");
      return;
    }
    try {
      // Resposta é sempre genérica (não revela se o operador existe). No MVP o backend
      // reseta para a senha padrão de inicialização, sem enviar e-mail.
      await api.esqueciSenha(alvo);
      setResetado(true);
    } catch {
      setErro("Não foi possível conectar ao servidor.");
    }
  }

  // Tela de aviso do reset (workaround MVP): mensagem crua + botão de voltar ao login.
  if (resetado) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <p className="eyebrow">ENBPar - Diretoria de Gestão de Programas - GCLT</p>
          <h1 className="auth-title">Senha resetada</h1>
          <p className="auth-subtitle">Sua senha foi resetada para o padrão de inicialização</p>
          <div className="auth-actions">
            <button
              type="button"
              className="btn-primary full"
              onClick={() => { setResetado(false); setSenha(""); }}
            >
              Voltar
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <p className="eyebrow">ENBPar - Diretoria de Gestão de Programas - GCLT</p>
        <h1 className="auth-title">Entrar</h1>
        <p className="auth-subtitle">Sistema Gerenciador do Programa Luz para Todos</p>
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="field">
            <label className="field-label">Operador</label>
            <input
              type="text"
              autoComplete="username"
              value={operador}
              onChange={(e) => setOperador(e.target.value)}
              placeholder="operador"
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
