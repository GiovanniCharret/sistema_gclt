import { useState } from "react";
import * as api from "../lib/api";

// Tela de troca de senha no 1º acesso (POST /api/trocar-senha). Reusa o design system
// da entrada (auth-shell/auth-card/field/btn-primary) — sem inventar visual novo.
//
// A "senha atual" é a temporária que o usuário ACABOU de usar no login (chega por prop),
// então não a pedimos de novo — evita erro de digitação/autofill e agiliza o 1º acesso.
export default function TrocarSenha({ email, senhaAtual, onTrocada, onVoltar }) {
  const [nova, setNova] = useState("");
  const [confirma, setConfirma] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    // Validações locais antes de chamar o backend.
    if (nova.length < 6) {
      setErro("A nova senha deve ter ao menos 6 caracteres.");
      return;
    }
    if (nova !== confirma) {
      setErro("A confirmação não coincide com a nova senha.");
      return;
    }
    setCarregando(true);
    try {
      const { ok, status, dados } = await api.trocarSenha(email, senhaAtual, nova);
      if (status === 401) {
        // Só ocorre se a senha carregada do login não bater (sessão inconsistente).
        setErro("Sua sessão expirou. Volte ao login e entre novamente.");
        return;
      }
      if (!ok) {
        setErro("Não foi possível trocar a senha. Tente novamente.");
        return;
      }
      // Troca concluída: backend devolve o token de sessão → entra.
      onTrocada(email, dados.token);
    } catch {
      setErro("Não foi possível conectar ao servidor.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <p className="eyebrow">Primeiro acesso</p>
        <h1 className="auth-title">Definir nova senha</h1>
        <p className="auth-subtitle">
          Crie uma nova senha para <strong>{email}</strong> antes de continuar.
        </p>
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="field">
            <label className="field-label">Nova senha</label>
            <input
              type="password"
              autoComplete="new-password"
              value={nova}
              onChange={(e) => setNova(e.target.value)}
              placeholder="ao menos 6 caracteres"
            />
          </div>
          <div className="field">
            <label className="field-label">Confirmar nova senha</label>
            <input
              type="password"
              autoComplete="new-password"
              value={confirma}
              onChange={(e) => setConfirma(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          {erro && <p className="auth-error">{erro}</p>}
          <button className="btn-primary full" type="submit" disabled={carregando}>
            {carregando ? "Salvando…" : "Salvar e entrar"}
          </button>
        </form>
        <div className="auth-links">
          <button type="button" className="auth-link" onClick={onVoltar}>
            Voltar ao login
          </button>
        </div>
      </div>
    </div>
  );
}
