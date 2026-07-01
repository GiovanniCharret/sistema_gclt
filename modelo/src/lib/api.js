// Camada de acesso à API do backend (FastAPI em /api). Centraliza a URL-base,
// o cabeçalho de autenticação (Bearer) e o tratamento de resposta JSON.
//
// URL-base: em produção o front e o backend ficam atrás do mesmo Nginx, então "/api".
// Em desenvolvimento o Vite (5175) e o uvicorn (8000) são origens diferentes — por isso
// o default aponta para o backend local. Pode ser sobrescrito por VITE_API_BASE.
const API_BASE =
  import.meta.env.VITE_API_BASE ??
  (import.meta.env.DEV ? "http://127.0.0.1:8000/api" : "/api");

// POST JSON genérico. Não lança em 401/4xx — devolve {ok, status, dados} para o
// chamador decidir a mensagem. Só relança em falha de rede (fetch rejeitado).
async function postJson(caminho, corpo, token) {
  const resposta = await fetch(`${API_BASE}${caminho}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // Inclui o token só quando há um (rotas protegidas — Blocos C/E).
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(corpo),
  });
  // Tenta ler o corpo JSON; tolera resposta sem corpo.
  let dados = null;
  try {
    dados = await resposta.json();
  } catch {
    dados = null;
  }
  return { ok: resposta.ok, status: resposta.status, dados };
}

// GET JSON com token (rotas protegidas). Não lança em 4xx — devolve {ok,status,dados}.
async function getJson(caminho, token) {
  const resposta = await fetch(`${API_BASE}${caminho}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  let dados = null;
  try {
    dados = await resposta.json();
  } catch {
    dados = null;
  }
  return { ok: resposta.ok, status: resposta.status, dados };
}

// POST /api/login — { token } | { precisaTrocarSenha: true } | 401.
export function login(email, senha) {
  return postJson("/login", { email, senha });
}

// GET /api/contexto — { email, grupo, ufs, contratos } (rota protegida).
export function contexto(token) {
  return getJson("/contexto", token);
}

// POST /api/validar — envia o arquivo real (multipart) + contrato/uf; devolve o painel.
// Não define Content-Type: o browser monta o boundary do multipart automaticamente.
export async function validar(token, arquivo, contrato, uf) {
  const form = new FormData();
  form.append("arquivo", arquivo);
  form.append("contrato", contrato);
  form.append("uf", uf);
  const resposta = await fetch(`${API_BASE}/validar`, {
    method: "POST",
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: form,
  });
  let dados = null;
  try {
    dados = await resposta.json();
  } catch {
    dados = null;
  }
  return { ok: resposta.ok, status: resposta.status, dados };
}

// GET /api/modelo — baixa o modelo oficial (rota protegida). Como precisa do token no
// header, busca o Blob e dispara o download por âncora (âncora simples não manda header).
export async function baixarModelo(token) {
  const resposta = await fetch(`${API_BASE}/modelo`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!resposta.ok) throw new Error(`falha ao baixar modelo (${resposta.status})`);
  const blob = await resposta.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.xlsx";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  // Adia a limpeza (revogar o ObjectURL na hora pode cancelar o download).
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 0);
}

// POST /api/trocar-senha — { token } | 400/401.
export function trocarSenha(email, senhaAtual, novaSenha) {
  return postJson("/trocar-senha", { email, senhaAtual, novaSenha });
}

// POST /api/esqueci-senha — sempre { ok: true } (resposta genérica).
export function esqueciSenha(email) {
  return postJson("/esqueci-senha", { email });
}

// Exposto para depuração/uso futuro (ex.: montar URLs de download).
export { API_BASE };
