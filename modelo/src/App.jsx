import { useEffect, useRef, useState } from "react";

import AuthScreen from "./components/AuthScreen";
import MenuPrincipal from "./components/MenuPrincipal";
import UfSelector from "./components/UfSelector";
import ContratoSelector from "./components/ContratoSelector";
import VersaoPlanilha from "./components/VersaoPlanilha";
import UploadAnexoV from "./components/UploadAnexoV";
import PainelInconsistencias from "./components/PainelInconsistencias";
import SucessoEnvio from "./components/SucessoEnvio";
import { descreverContrato } from "./seedData";

// Orquestrador do mock. Telas: login → menu → UF → contrato → versão → shell
// (upload → painel → sucesso). Tudo em estado local; validação roteirada.
export default function App() {
  const [user, setUser] = useState(null);          // null = não autenticado
  const [moduloOk, setModuloOk] = useState(false); // menu principal escolhido
  const [uf, setUf] = useState(null);              // UF selecionada
  const [contrato, setContrato] = useState(null);  // contrato (chave principal)
  const [versaoOk, setVersaoOk] = useState(false); // passo 3 — versão conferida
  const [view, setView] = useState("upload");      // upload | painel | sucesso
  const [attempt, setAttempt] = useState(1);       // 1 = mostra erros · 2 = limpa
  const [toast, setToast] = useState("");
  const toastTimer = useRef(null);

  function showToast(msg) {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 2600);
  }
  useEffect(() => () => clearTimeout(toastTimer.current), []);

  function handleLogout() {
    setUser(null);
    setModuloOk(false);
    setUf(null);
    setContrato(null);
    setVersaoOk(false);
    setView("upload");
    setAttempt(1);
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
    setAttempt(1);
  }

  // Fim da validação roteirada: 1ª tentativa → painel; 2ª (corrigida) → sucesso.
  function handleValidated() {
    setView(attempt === 1 ? "painel" : "sucesso");
  }

  // ── Telas de entrada ──────────────────────────────────────────────
  if (!user) return <AuthScreen onEnter={setUser} />;
  if (!moduloOk) return <MenuPrincipal onClassificacao={() => setModuloOk(true)} />;
  if (!uf) return <UfSelector onSelect={selectUf} />;
  if (!contrato) return <ContratoSelector uf={uf} onSelect={selectContrato} onBack={() => setUf(null)} />;
  if (!versaoOk) return <VersaoPlanilha onAvancar={() => setVersaoOk(true)} onBack={() => setContrato(null)} />;

  // ── Shell logado ──────────────────────────────────────────────────
  const contratoLabel = descreverContrato(contrato);

  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="topbar-brand">Classificação de Beneficiários</span>
        <nav className="topbar-nav">
          <button
            className={`topbar-link${view === "upload" ? " is-active" : ""}`}
            onClick={() => { setAttempt(1); setView("upload"); }}
          >
            Envio da Planilha
          </button>
          <button className="topbar-link" onClick={() => { setContrato(null); setUf(null); }}>Trocar Contrato</button>
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
            secondAttempt={attempt === 2}
            onComplete={handleValidated}
          />
        )}
        {view === "painel" && (
          <PainelInconsistencias
            uf={uf}
            contrato={contrato}
            onCorrigir={() => { setAttempt(2); setView("upload"); }}
            onToast={showToast}
          />
        )}
        {view === "sucesso" && (
          <SucessoEnvio
            uf={uf}
            contrato={contrato}
            onNova={() => { setAttempt(1); setView("upload"); }}
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
