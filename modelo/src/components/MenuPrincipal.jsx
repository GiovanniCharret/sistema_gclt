// Menu principal (hub) entre o login e a seleção de UF/contrato.
// Por ora um único módulo; no futuro recebe outras opções (ex.: upload de
// notas fiscais). O cartão tem uma ilustração em marca d'água para deixar a
// experiência mais leve.
export default function MenuPrincipal({ onClassificacao }) {
  return (
    <div className="auth-shell">
      <div className="auth-card wide">
        <p className="eyebrow">MME · Luz para Todos</p>
        <h1 className="auth-title">Menu principal</h1>
        <p className="auth-subtitle">Selecione um módulo para começar.</p>

        <div className="modulo-grid">
          <button type="button" className="modulo-card" onClick={onClassificacao}>
            <Ilustracao />
            <div className="modulo-card-body">
              <h2 className="modulo-card-title">Classificação de Beneficiários do Programa</h2>
              <p className="modulo-card-desc">
                Upload de Informações Sobre Unidades Consumidoras — Decreto Nº 12.964, de 8 de Maio de 2026
              </p>
              <span className="modulo-card-cta">Acessar →</span>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}

// Marca d'água: cena de eletrificação rural (sol + casa + poste com fio).
// Line-art em currentColor; opacidade controlada no CSS.
function Ilustracao() {
  return (
    <svg className="modulo-wm" viewBox="0 0 240 200" fill="none" stroke="currentColor"
      strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {/* sol */}
      <circle cx="196" cy="44" r="16" />
      <line x1="196" y1="14" x2="196" y2="4" />
      <line x1="196" y1="84" x2="196" y2="74" />
      <line x1="166" y1="44" x2="156" y2="44" />
      <line x1="236" y1="44" x2="226" y2="44" />
      <line x1="174" y1="22" x2="167" y2="15" />
      <line x1="218" y1="66" x2="225" y2="73" />
      <line x1="218" y1="22" x2="225" y2="15" />
      <line x1="174" y1="66" x2="167" y2="73" />
      {/* casa */}
      <path d="M48 100 L96 62 L144 100" />
      <path d="M58 96 L58 168 L134 168 L134 96" />
      <rect x="86" y="132" width="22" height="36" />
      <rect x="68" y="112" width="18" height="18" />
      {/* poste + fio até a casa */}
      <line x1="186" y1="92" x2="186" y2="170" />
      <line x1="172" y1="104" x2="200" y2="104" />
      <path d="M186 96 C 168 104, 150 92, 134 84" />
      {/* chão */}
      <line x1="24" y1="170" x2="216" y2="170" />
    </svg>
  );
}
