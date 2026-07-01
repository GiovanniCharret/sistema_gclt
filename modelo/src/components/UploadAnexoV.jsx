import { useRef, useState } from "react";
import * as api from "../lib/api";

// Envio real da planilha (.xlsx) → POST /api/validar. Mantém a barra de 3 fases
// (① Leitura · ② Validação · ③ Conferência) enquanto aguarda a resposta do backend.
const PHASES = ["① Leitura", "② Validação", "③ Conferência"];

export default function UploadAnexoV({ uf, contrato, token, onComplete }) {
  const [file, setFile] = useState(null);       // File real selecionado/arrastado
  const [drag, setDrag] = useState(false);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState(-1);       // -1 idle, 0..2 ativo
  const [label, setLabel] = useState("");
  const [erro, setErro] = useState("");
  const inputRef = useRef(null);

  function escolher(f) {
    // Só aceita .xlsx (o backend também valida).
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".xlsx")) {
      setErro("Selecione um arquivo .xlsx.");
      return;
    }
    setErro("");
    setFile(f);
  }

  function pickFile() {
    if (running) return;
    inputRef.current?.click();
  }
  function clearFile() {
    if (running) return;
    setFile(null);
    setErro("");
    if (inputRef.current) inputRef.current.value = "";
  }
  function onDrop(e) {
    e.preventDefault();
    setDrag(false);
    if (!running) escolher(e.dataTransfer.files?.[0]);
  }

  async function runValidation() {
    if (!file || running) return;
    setRunning(true);
    setErro("");
    setPhase(0);
    setProgress(20);
    setLabel("Enviando e lendo a aba “Preenchimento”…");
    // Animação leve da 2ª fase enquanto o backend processa.
    const t = setTimeout(() => {
      setPhase(1);
      setProgress(65);
      setLabel("Aplicando regras de validação…");
    }, 450);

    try {
      const { status, dados } = await api.validar(token, file, contrato.numero, uf.sigla);
      clearTimeout(t);
      if (status === 200) {
        // Resposta do painel (dados.ok diz se está limpa ou com erros).
        setPhase(2);
        setProgress(100);
        setLabel("Conferindo resultados…");
        setTimeout(() => { setRunning(false); onComplete(dados); }, 350);
        return;
      }
      // Erros de requisição — mostra a mensagem e volta ao estado ocioso.
      const msg = {
        401: "Sua sessão expirou. Entre novamente.",
        403: dados?.detail || "Este contrato está fora do seu acesso.",
        409: dados?.detail || "Não foi possível validar este contrato no momento.",
        400: dados?.detail || "Arquivo inválido. Envie o .xlsx do Anexo V.",
      }[status] || "Não foi possível validar. Tente novamente.";
      setErro(msg);
      setRunning(false);
      setPhase(-1);
    } catch {
      clearTimeout(t);
      setErro("Não foi possível conectar ao servidor.");
      setRunning(false);
      setPhase(-1);
    }
  }

  return (
    <section className="card">
      <div className="card-header">
        <div>
          <p className="section-kicker">Envio · {contrato.numero}</p>
          <h2 className="card-title">Planilha Anexo V — Painel de Monitoramento dos Beneficiários do Programa</h2>
        </div>
        <span className="section-badge">.xlsx somente</span>
      </div>

      {/* input real (escondido) — acionado pela dropzone */}
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx"
        style={{ display: "none" }}
        onChange={(e) => escolher(e.target.files?.[0])}
      />

      {!file ? (
        <div
          className={`dropzone${drag ? " is-drag" : ""}`}
          onClick={pickFile}
          onDragEnter={(e) => { e.preventDefault(); setDrag(true); }}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={(e) => { e.preventDefault(); setDrag(false); }}
          onDrop={onDrop}
        >
          <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M7 16a4 4 0 0 1-.88-7.903A5 5 0 1 1 15.9 6L16 6a5 5 0 0 1 1 9.9M15 13l-3-3m0 0l-3 3m3-3v12" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <strong className="dropzone-label">Arraste a planilha (.xlsx) ou clique para selecionar</strong>
          <span className="dropzone-hint">Apenas a aba “Preenchimento” é validada · unidades consumidoras ligadas em 2026</span>
        </div>
      ) : (
        <div className="file-pill">
          <span className="fp-icon">📄</span>
          <div>
            <div className="fp-name">{file.name}</div>
            <div className="fp-size">{(file.size / 1024).toFixed(0)} KB</div>
          </div>
          {!running && <button className="fp-clear" onClick={clearFile} title="Remover">✕</button>}
        </div>
      )}

      {running && (
        <div className="progress-block">
          <div className="progress-phases">
            {PHASES.map((p, i) => (
              <span key={p} className={phase === i ? "phase-active" : (phase > i ? "phase-done" : "phase-idle")}>{p}</span>
            ))}
          </div>
          <div className="progress-track">
            <div className={`progress-fill${phase === 1 ? " is-processing" : ""}`} style={{ width: `${progress}%` }} />
          </div>
          <span className="progress-label">{label}</span>
        </div>
      )}

      {erro && <p className="auth-error">{erro}</p>}

      <div className="upload-actions">
        <button className="btn-primary" disabled={!file || running} onClick={runValidation}>
          {running ? "Validando…" : "Validar e enviar"}
        </button>
      </div>
    </section>
  );
}
