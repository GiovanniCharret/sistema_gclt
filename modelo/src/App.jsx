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

// Formata a data ISO que vem do backend (2026-10-02) no padrão brasileiro (02/10/2026).
// Por que aqui e não no backend: a rota devolve ISO porque é o formato que ordena e que
// qualquer consumidor entende; a apresentação é decisão da tela.
function formatarDataBr(iso) {
  // Sem data (arquivo antigo, sem o bloco derivado), não há o que formatar.
  if (!iso || iso.length < 10) return "";
  // Fatia em vez de `new Date`: `new Date("2026-10-02")` é interpretada como UTC e, em
  // fuso negativo, exibiria o dia anterior.
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
}

// Rodapé único do app, com a versão no canto esquerdo. Nas telas de entrada (login,
// menu, seleção de UF/contrato) vai FIXO ao pé da janela — elas centralizam o conteúdo
// em tela cheia (.auth-shell) e não têm footer no fluxo; no shell logado entra no fluxo
// normal da página, como sempre.
function Rodape({ fixo = false }) {
  // Versão e data da última atualização vêm do backend (GET /api/versao), que lê
  // `controle_versao/historico.json` do disco a cada pedido. Antes era constante no código:
  // exibia V0.0.0804 desde 04/08/2026 enquanto o histórico já ia em outubro — ou seja, o
  // rodapé mentia justamente sobre o que existia para informar.
  const [versao, setVersao] = useState(null);

  useEffect(() => {
    // `vivo` evita escrever estado depois que o componente saiu da tela (o rodapé é
    // desmontado a cada troca de passo do fluxo).
    let vivo = true;
    api
      .versao()
      .then((r) => {
        // Só aceita resposta completa: 503 (arquivo não publicado) deixa o rodapé sem
        // versão, que é melhor do que exibir um número inventado ou velho.
        if (vivo && r.ok && r.dados && r.dados.versao) setVersao(r.dados);
      })
      // Falha de rede não pode derrubar a tela por causa do rodapé.
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, []);

  // Enquanto não chega (ou se não vier), mostra só o nome do produto — sem versão falsa.
  const data = versao ? formatarDataBr(versao.data) : "";
  const etiqueta = versao
    ? `${versao.versao}${data ? ` · atualizado em ${data}` : ""} · Monitoramento dos Beneficiários do Programa`
    : "Monitoramento dos Beneficiários do Programa";

  return (
    <footer className={fixo ? "app-footer is-fixo" : "app-footer"}>
      <span>{etiqueta}</span>
      <span>Programa Luz para Todos · MME · ENBPar</span>
    </footer>
  );
}

// Orquestrador. Telas: login → menu → UF → contrato → versão → shell
// (upload → painel → sucesso). Auth + contexto + validação são reais (backend).
export default function App() {
  const [user, setUser] = useState(null);          // null = não autenticado (operador quando logado)
  const [token, setToken] = useState(null);        // token de sessão (JWT) — usado nas rotas protegidas
  const [trocaPendente, setTrocaPendente] = useState(null); // { operador, senha } aguardando troca no 1º acesso
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
          operador={trocaPendente.operador}
          senhaAtual={trocaPendente.senha}
          onTrocada={(operador, tok) => { setToken(tok); setTrocaPendente(null); setUser(operador); }}
          onVoltar={() => setTrocaPendente(null)}
        />
      );
    }
    // Login real: onAutenticado (com token) entra; onPrecisaTrocar abre a tela de troca.
    return (
      <>
        <AuthScreen
          onAutenticado={(operador, tok) => { setToken(tok); setUser(operador); }}
          onPrecisaTrocar={(operador, senha) => setTrocaPendente({ operador, senha })}
        />
        <Rodape fixo />
      </>
    );
  }
  if (!moduloOk)
    return (
      <>
        <MenuPrincipal onClassificacao={() => setModuloOk(true)} />
        <Rodape fixo />
      </>
    );
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
  if (!uf)
    return (
      <>
        <UfSelector ufs={contexto.ufs} onSelect={selectUf} />
        <Rodape fixo />
      </>
    );
  if (!contrato)
    return (
      <>
        <ContratoSelector
          uf={uf}
          contratos={contexto.contratos.filter((c) => c.uf === uf.sigla)}
          onSelect={selectContrato}
          onBack={() => setUf(null)}
        />
        <Rodape fixo />
      </>
    );
  if (!versaoOk) return <VersaoPlanilha token={token} onAvancar={() => setVersaoOk(true)} onBack={() => setContrato(null)} />;

  // ── Shell logado ──────────────────────────────────────────────────
  const contratoLabel = descreverContrato(contrato);

  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="topbar-brand">Monitoramento dos Beneficiários</span>
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
            totalAvisos={resultado.totalAvisos}
            grupos={resultado.grupos}
            onNova={() => { setResultado(null); setView("upload"); }}
            onToast={showToast}
          />
        )}
      </main>

      <Rodape />

      {toast && <div className="toast is-on">{toast}</div>}
    </div>
  );
}
