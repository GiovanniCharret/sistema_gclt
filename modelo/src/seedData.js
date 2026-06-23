// Dados do mock. Contratos vêm de base_contratos.json (real); inconsistências
// e preview são roteirados (sem leitura real de arquivo, sem backend).
import BASE from "./base_contratos.json";

const UF_NOMES = {
  AC: "Acre", AL: "Alagoas", AP: "Amapá", AM: "Amazonas", BA: "Bahia",
  CE: "Ceará", DF: "Distrito Federal", ES: "Espírito Santo", GO: "Goiás",
  MA: "Maranhão", MT: "Mato Grosso", MS: "Mato Grosso do Sul", MG: "Minas Gerais",
  PA: "Pará", PB: "Paraíba", PR: "Paraná", PE: "Pernambuco", PI: "Piauí",
  RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RS: "Rio Grande do Sul",
  RO: "Rondônia", RR: "Roraima", SC: "Santa Catarina", SP: "São Paulo",
  SE: "Sergipe", TO: "Tocantins",
};

// Quantidade de UCs cadastradas POR CONTRATO — MOCK. NÃO está em
// base_contratos.json; no sistema real virá do backend. Valor estável derivado
// do número do contrato (não muda entre renders/reloads).
function mockUcsContrato(numero) {
  let h = 0;
  for (let i = 0; i < numero.length; i += 1) h = (h * 31 + numero.charCodeAt(i)) >>> 0;
  return 300 + (h % 7700); // 300..7999
}

// Contratos selecionáveis = vigente diferente de "Encerrado".
// (Inclui "Andamento" e "Encerramento".)
export const CONTRATOS = Object.entries(BASE)
  .filter(([, c]) => c.vigente !== "Encerrado")
  .map(([numero, c]) => ({ numero, ...c, ucs: mockUcsContrato(numero) }));

// UFs que possuem ao menos um contrato selecionável.
export const UFS = (() => {
  const byUf = {};
  for (const c of CONTRATOS) (byUf[c.uf] ||= []).push(c);
  return Object.keys(byUf)
    .sort()
    .map((sigla) => ({ sigla, nome: UF_NOMES[sigla] || sigla, contratos: byUf[sigla].length }));
})();

export function contratosDaUf(sigla) {
  return CONTRATOS.filter((c) => c.uf === sigla).sort((a, b) => a.numero.localeCompare(b.numero, "pt-BR"));
}

// Texto canônico do contrato: "ECM 018/2025 - MLA, 2ª Tranche".
export function descreverContrato(c) {
  return `${c.numero} - ${c.tipo_contrato}, ${c.tranche}`;
}

// Nº de UCs "lidas" na planilha roteirada (mock) — coerente com o card de upload.
export const LINHAS_LIDAS = 1240;

// Inconsistências roteiradas, agrupadas por tipo de regra.
// sev: "err" (bloqueia o salvamento) | "warn" (não bloqueia).
export const RULE_GROUPS = [
  {
    sev: "err", title: "Campos obrigatórios vazios",
    desc: "Colunas obrigatórias na aba Preenchimento", count: 8,
    rows: [
      { loc: "L47",  field: "Latitude", problem: "célula vazia", sug: "preencher em graus decimais (ex.: -3.301800)" },
      { loc: "L102", field: "Código IBGE", problem: "célula vazia", sug: "informar o código IBGE de 7 dígitos do município" },
      { loc: "L155", field: "Número da UC", problem: "célula vazia", sug: "campo-chave; obrigatório para todas as UCs" },
      { loc: "L210", field: "Data Energização", problem: "célula vazia", sug: "data de energização da UC (DD/MM/AAAA)" },
    ],
  },
  {
    sev: "err", title: "Valor fora do domínio",
    desc: "Valor não consta na lista de domínios válidos", count: 3,
    rows: [
      { loc: "L47", field: "UF", problem: "valor “XX” não é uma UF válida", sug: "usar sigla de 2 letras (AM, PA, RR…)" },
      { loc: "L63", field: "Tipo de Atendimento", problem: "valor “Rede” inválido", sug: "usar “Extensão de Rede” ou “Sistemas de Geração…”" },
      { loc: "L91", field: "Tipo de Comunidade", problem: "valor “13” inexistente", sug: "o domínio aceita 1 a 12" },
    ],
  },
  {
    sev: "err", title: "Coordenadas inválidas",
    desc: "Latitude/Longitude fora da faixa geográfica", count: 2,
    rows: [
      { loc: "L77",  field: "Latitude", problem: "valor “91.5” fora da faixa", sug: "latitude deve estar entre -90 e 90" },
      { loc: "L120", field: "Longitude", problem: "valor “0” suspeito", sug: "confirmar a coordenada da UC" },
    ],
  },
  {
    sev: "err", title: "Chave ODI + UC duplicada",
    desc: "Mesma combinação Número ODI + Número da UC em mais de uma linha", count: 1,
    rows: [
      { loc: "L12 / L4087", field: "ODI + UC", problem: "ODI “210001” + UC “70012345” repetida", sug: "cada UC deve aparecer uma única vez" },
    ],
  },
  {
    sev: "warn", title: "“0 - Não é prioridade” + outra tipologia",
    desc: "Regra: marcar “0” só quando nenhuma outra tipologia se aplica", count: 5,
    rows: [
      { loc: "L30", field: "Tipologia", problem: "“0 - Não é prioridade” = Sim junto com “I - Baixa renda” = Sim", sug: "desmarcar “0” quando houver outra tipologia" },
      { loc: "L44", field: "Tipologia", problem: "“0 - Não é prioridade” = Sim junto com “IV.1 - Família indígena” = Sim", sug: "revisar a marcação" },
    ],
  },
  {
    sev: "warn", title: "Data de energização fora de 2026",
    desc: "A planilha deve conter apenas UCs ligadas em 2026", count: 3,
    rows: [
      { loc: "L201", field: "Data Energização", problem: "valor “12/11/2025”", sug: "remover ou enviar no painel do ano correspondente" },
    ],
  },
  {
    sev: "warn", title: "Valor de tipologia ≠ Sim/Não",
    desc: "Colunas de tipologia aceitam apenas “Sim” ou “Não”", count: 2,
    rows: [
      { loc: "L88", field: "V.1 - Escolas", problem: "valor “X” inválido", sug: "usar “Sim” ou “Não”" },
    ],
  },
];

export const TOTAL_ERROS = RULE_GROUPS.filter((g) => g.sev === "err").reduce((a, g) => a + g.count, 0);
export const TOTAL_AVISOS = RULE_GROUPS.filter((g) => g.sev === "warn").reduce((a, g) => a + g.count, 0);

// Amostra de linhas para o preview da planilha. `flags` marca células com
// problema: "err" (vermelho) ou "warn" (laranja).
export const PREVIEW_COLS = [
  { key: "linha", label: "Linha" },
  { key: "odi", label: "Nº ODI" },
  { key: "uc", label: "Nº UC" },
  { key: "municipio", label: "Município" },
  { key: "uf", label: "UF" },
  { key: "ibge", label: "Cód. IBGE" },
  { key: "latitude", label: "Latitude" },
  { key: "energizacao", label: "Energização" },
  { key: "tipoAtend", label: "Tipo de Atendimento" },
];

export const PREVIEW_ROWS = [
  { linha: "L12", odi: "210001", uc: "70012345", municipio: "MANACAPURU", uf: "AM", ibge: "1302603", latitude: "-3.3018", energizacao: "14/02/2026", tipoAtend: "Extensão de Rede", flags: { uc: "err" } },
  { linha: "L30", odi: "210002", uc: "70012890", municipio: "COARI", uf: "AM", ibge: "1301209", latitude: "-4.0851", energizacao: "20/02/2026", tipoAtend: "Extensão de Rede", flags: {} },
  { linha: "L47", odi: "210010", uc: "70013001", municipio: "TEFÉ", uf: "XX", ibge: "1304203", latitude: "(vazio)", energizacao: "25/02/2026", tipoAtend: "Extensão de Rede", flags: { uf: "err", latitude: "err" } },
  { linha: "L63", odi: "210015", uc: "70013120", municipio: "CARAUARI", uf: "AM", ibge: "1300805", latitude: "-4.8828", energizacao: "02/03/2026", tipoAtend: "Rede", flags: { tipoAtend: "err" } },
  { linha: "L77", odi: "210021", uc: "70013240", municipio: "EIRUNEPÉ", uf: "AM", ibge: "1301407", latitude: "91.5", energizacao: "08/03/2026", tipoAtend: "Extensão de Rede", flags: { latitude: "err" } },
  { linha: "L102", odi: "210033", uc: "70013355", municipio: "BORBA", uf: "AM", ibge: "(vazio)", latitude: "-4.3877", energizacao: "15/03/2026", tipoAtend: "Sist. Geração Descentralizado", flags: { ibge: "err" } },
  { linha: "L201", odi: "210050", uc: "70013470", municipio: "MAUÉS", uf: "AM", ibge: "1302504", latitude: "-3.3839", energizacao: "12/11/2025", tipoAtend: "Extensão de Rede", flags: { energizacao: "warn" } },
];
