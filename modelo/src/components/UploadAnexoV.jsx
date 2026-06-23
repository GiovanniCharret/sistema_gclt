import { useRef, useState } from "react";

// Envio da planilha (.xlsx). Sem leitura real: a "validação" é roteirada —
// roda uma barra de progresso em 3 fases e chama onComplete().
const PHASES = ["① Leitura", "② Validação", "③ Conferência"];

export default function UploadAnexoV({ uf, contrato, secondAttempt, onComplete }) {
  const [file, setFile] = useState(null);
  const [drag, setDrag] = useState(false);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState(-1); // -1 idle, 0..2 ativo
  const [label, setLabel] = useState("");
  const timers = useRef([]);

  const fileName = `Anexo V - Painel de Monitoramento - MME-CC_${uf.sigla}.xlsx`;

  function pickFile() {
    if (running) return;
    setFile(fileName);
  }
  function clearFile() {
    if (running) return;
    setFile(null);
  }

  function onDrop(e) {
    e.preventDefault();
    setDrag(false);
    if (!running) setFile(fileName); // roteirado — ignora o arquivo real
  }

  function runValidation() {
    if (!file || running) return;
    setRunning(true);
    setProgress(0);
    timers.current.forEach(clearTimeout);
    timers.current = [];

    const step = (ms, fn) => timers.current.push(setTimeout(fn, ms));

    setPhase(0);
    setLabel("Lendo a aba “Preenchimento”… (1.240 linhas)");
    setProgress(30);

    step(700, () => { setPhase(1); setLabel("Aplicando regras de validação…"); setProgress(66); });
    step(1400, () => { setPhase(2); setLabel("Conferindo resultados…"); setProgress(100); });
    step(2050, () => { setRunning(false); onComplete(); });
  }

  return (
    <>
      {secondAttempt && (
        <div className="banner-fix">
          ⚠ Reenvie a planilha corrigida. Os erros precisam ser resolvidos para o salvamento na base.
        </div>
      )}
      <section className="card">
        <div className="card-header">
          <div>
            <p className="section-kicker">Envio · {contrato.numero}</p>
            <h2 className="card-title">Planilha Anexo V — Painel de Monitoramento dos Beneficiários do Programa</h2>
          </div>
          <span className="section-badge">.xlsx somente</span>
        </div>

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
              <div className="fp-name">{file}</div>
              <div className="fp-size">1.240 linhas · 52 colunas · 184 KB</div>
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

        <div className="upload-actions">
          <button className="btn-primary" disabled={!file || running} onClick={runValidation}>
            {running ? "Validando…" : (secondAttempt ? "Reenviar planilha corrigida" : "Validar e enviar")}
          </button>
        </div>
      </section>
    </>
  );
}
