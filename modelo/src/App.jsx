import { useEffect, useRef, useState } from "react";

import AuthScreen from "./components/AuthScreen";
import TrocarSenha from "./components/TrocarSenha";
import MenuPrincipal from "./components/MenuPrincipal";
import UfSelector from "./components/UfSelector";
import ContratoSelector from "./components/ContratoSelector";
import VersaoPlanilha from "./components/VersaoPlanilha";
import UploadAnexoV from "./components/UploadAnexoV";
import PainelInconsistencias from "./components/PainelInconsistencias";
import SucessoEnvio from "./components/SucessoEnvio";
import { descreverContrato } from "./seedData";
import * as api from "./lib/api";

// Orquestrador. Telas: login → menu → UF → contrato → versão → shell
// (upload → painel → sucesso). Auth + contexto + validação são reais (backend).
export default function App() {
  const [user, setUser] = useState(null);          // null = não autenticado (e-mail quando logado)
  const [token, setToken] = useState(null);        // token de sessão (JWT) — usado nas rotas protegidas
  const [trocaPendente, setTrocaPendente] = useState(null); // { email, senha } aguardando troca no 1º acesso
  const [contexto, setContexto] = useState(null);  // { grupo, ufs, contratos } vindo de /api/contexto
  const [moduloOk, setModuloOk] = useState(false); // menu principal escolhido
  const [uf, setUf] = useState(null);              // UF selecionada
  const [contrato, setContrato] = useState(null);  // contrato (chave principal)
  const [versaoOk, setVersaoOk] = useState(false); // passo 3 — versão conferida
  const [view, setView] = useState("upload");      // upload | painel | sucesso
  const [resultado, setResultado] = useState(null);// resposta do /api/validar (painel real)
  const [toast, setToast] = useState("");
  const toastTimer = useRef(null);

  function showToast(msg) {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 2600);
  }
  useEffect(() => () => clearTimeout(toastTimer.current), []);

  // Ao autenticar (token disponível), busca o contexto do usuário (grupo → UFs/contratos).
  useEffect(() => {
    if (!token || contexto) return;
    let ativo = true;
    api
      .contexto(token)
      .then(({ ok, dados }) => {
        if (ativo) setContexto(ok && dados ? dados : { grupo: null, ufs: [], contratos: [] });
      })
      .catch(() => {
        if (ativo) setContexto({ grupo: null, ufs: [], contratos: [] });
      });
    return () => { ativo = false; };
  }, [token, contexto]);

  function handleLogout() {
    setUser(null);
    setToken(null);
    setTrocaPendente(null);
    setContexto(null);
    setModuloOk(false);
    setUf(null);
    setContrato(null);
    setVersaoOk(false);
    setView("upload");
    setResultado(null);
  }

  function selectUf(novaUf) {
    setUf(novaUf);
    setContrato(null);
    setVersaoOk(false);
  }

  function selectContrato(c) {
    setContrato(c);
    setVersaoOk(false);
    setView("upload");
    setResultado(null);
  }

  // Fim da validação real: sem erros → sucesso; com erros → painel de inconsistências.
  function onValidated(res) {
    setResultado(res);
    setView(res.ok ? "sucesso" : "painel");
  }

  // ── Telas de entrada ──────────────────────────────────────────────
  if (!user) {
    // 1º acesso: backend sinalizou troca de senha → tela de troca (sem estar logado).
    // A senha atual é a que o usuário acabou de usar no login (carregada daqui).
    if (trocaPendente) {
      return (
        <TrocarSenha
          email={trocaPendente.email}
          senhaAtual={trocaPendente.senha}
          onTrocada={(email, tok) => { setToken(tok); setTrocaPendente(null); setUser(email); }}
          onVoltar={() => setTrocaPendente(null)}
        />
      );
    }
    // Login real: onAutenticado (com token) entra; onPrecisaTrocar abre a tela de troca.
    return (
      <AuthScreen
        onAutenticado={(email, tok) => { setToken(tok); setUser(email); }}
        onPrecisaTrocar={(email, senha) => setTrocaPendente({ email, senha })}
      />
    );
  }
  if (!moduloOk) return <MenuPrincipal onClassificacao={() => setModuloOk(true)} />;
  // Aguarda o contexto (grupo → UFs/contratos) chegar do backend antes dos seletores.
  if (!contexto) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <p className="auth-subtitle">Carregando seu acesso…</p>
        </div>
      </div>
    );
  }
  if (!uf) return <UfSelector ufs={contexto.ufs} onSelect={selectUf} />;
  if (!contrato)
    return (
      <ContratoSelector
        uf={uf}
        contratos={contexto.contratos.filter((c) => c.uf === uf.sigla)}
        onSelect={selectContrato}
        onBack={() => setUf(null)}
      />
    );
  if (!versaoOk) return <VersaoPlanilha token={token} onAvancar={() => setVersaoOk(true)} onBack={() => setContrato(null)} />;

  // ── Shell logado ──────────────────────────────────────────────────
  const contratoLabel = descreverContrato(contrato);

  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="topbar-brand">Classificação de Beneficiários</span>
        <nav className="topbar-nav">
          <button
            className={`topbar-link${view === "upload" ? " is-active" : ""}`}
            onClick={() => { setResultado(null); setView("upload"); }}
          >
            Envio da Planilha
          </button>
          <button className="topbar-link" onClick={() => { setContrato(null); setUf(null); setResultado(null); setView("upload"); }}>Trocar Contrato</button>
        </nav>
        <div className="topbar-right">
          <span className="topbar-uf" title={`${uf.sigla} · ${contratoLabel}`}>{uf.sigla} · {contrato.numero}</span>
          <span className="topbar-user">{user}</span>
          <button className="topbar-logout" onClick={handleLogout}>Sair</button>
        </div>
      </header>

      <main className="main-content">
        {view === "upload" && (
          <UploadAnexoV
            uf={uf}
            contrato={contrato}
            token={token}
            onComplete={onValidated}
          />
        )}
        {view === "painel" && resultado && (
          <PainelInconsistencias
            uf={uf}
            contrato={contrato}
            grupos={resultado.grupos}
            previewRows={resultado.previewRows}
            totalErros={resultado.totalErros}
            totalAvisos={resultado.totalAvisos}
            linhasLidas={resultado.linhasLidas}
            onCorrigir={() => setView("upload")}
            onToast={showToast}
          />
        )}
        {view === "sucesso" && resultado && (
          <SucessoEnvio
            uf={uf}
            contrato={contrato}
            linhasLidas={resultado.linhasLidas}
            enviado={resultado.enviado}
            onNova={() => { setResultado(null); setView("upload"); }}
          />
        )}
      </main>

      <footer className="app-footer">
        <span>Mock · Classificação de Beneficiários do Programa</span>
        <span>Programa Luz para Todos · MME · ENBPar</span>
      </footer>

      {toast && <div className="toast is-on">{toast}</div>}
    </div>
  );
}
