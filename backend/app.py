"""Aplicação FastAPI do backend de validação e envio do Anexo V.

Por que existe: é o ponto de entrada ASGI do backend (o objeto `app` que o uvicorn
sobe e que o Nginx expõe em `/api`). Nesta sub-fase A1 ele contém apenas o
health-check mínimo; as rotas de auth/contexto/validação/modelo entram nos Blocos
B–E. Concentrar a criação do app e a configuração de CORS aqui dá um único lugar
para o servidor e os testes carregarem a mesma instância.

Lógica (Entrada → Saída):
  Entrada: import do módulo (pelo uvicorn ou pelo TestClient).
  Fase 1: cria a instância `app` do FastAPI (metadados da API).
  Fase 2: habilita CORS para o dev server do front (Vite, porta 5175), já que em
          desenvolvimento front e back rodam em origens diferentes; em produção
          ambos ficam atrás do mesmo Nginx e o CORS é inócuo.
  Fase 3: registra a rota `GET /api/health`.
  Saída: o objeto `app` pronto para servir requisições.
"""

# `FastAPI` é a classe que representa a aplicação/roteador ASGI.
from fastapi import FastAPI
# `CORSMiddleware` libera chamadas cross-origin do front em desenvolvimento.
from fastapi.middleware.cors import CORSMiddleware

# Cache de referência de `entrada/` (índices) — A2 — e da autoridade `base_contratos.json` — A3.
from backend.referencia import obter_referencia, obter_base_contratos

# Fase 1: instancia o app com título/versão (aparecem na doc OpenAPI em /docs).
app = FastAPI(
    # Nome exibido na documentação automática da API.
    title="Backend — Classificação de Beneficiários do Programa",
    # Versão da API; incrementar conforme o backend evolui pelos Blocos A–G.
    version="0.1.0",
)

# Origens permitidas no CORS = o dev server do Vite (localhost e 127.0.0.1:5175).
# Em produção o front é servido pelo mesmo host/porta do Nginx, então isto só
# importa em desenvolvimento (back em :8000, front em :5175).
ORIGENS_DEV = [
    # Forma com hostname `localhost`.
    "http://localhost:5175",
    # Forma com IP de loopback (alguns navegadores/configs usam esta).
    "http://127.0.0.1:5175",
]

# Fase 2: aplica o middleware de CORS com as origens de desenvolvimento.
app.add_middleware(
    # Middleware de CORS do Starlette/FastAPI.
    CORSMiddleware,
    # Lista explícita de origens confiáveis (não usar "*" junto de credenciais).
    allow_origins=ORIGENS_DEV,
    # Permite envio de cookies/headers de autenticação nas chamadas do front.
    allow_credentials=True,
    # Aceita qualquer método HTTP (GET/POST/...) — simplifica o dev.
    allow_methods=["*"],
    # Aceita qualquer header de requisição (ex.: Authorization no Bloco B).
    allow_headers=["*"],
)

# Carga inicial no startup (spec §5): referência (entrada/) e autoridade
# (base_contratos.json), para a 1ª requisição já encontrar tudo pronto.
obter_referencia()
obter_base_contratos()


# Fase 3: registra o endpoint de saúde sob o prefixo /api (espelha o Nginx).
@app.get("/api/health")
def health():
    """Health-check mínimo: confirma que o serviço está de pé.

    Por que existe: dá um endpoint barato para o systemd/uptime e o operador
    verificarem que o uvicorn subiu e responde; (A2) exibe as contagens da
    referência de `entrada/`; (A3) exibe a integridade vs `base_contratos.json`
    (contratos com/sem referência e órfãos), tornando o gap observável.

    Entrada: nenhuma.
    Fase 1: obtém o cache de referência e recarrega se algum CSV mudou (mtime),
            refletindo a atualização diária sem reiniciar o serviço.
    Fase 2: cruza com a autoridade `base_contratos.json` para classificar a integridade.
    Fase 3: monta o corpo com status + resumo numérico + integridade.
    Saída: JSON `{"status": "ok", "referencia": {...}, "integridade": {...}}` (HTTP 200).
    """
    # Fase 1: pega o singleton e atualiza os índices se `entrada/` mudou.
    referencia = obter_referencia()
    referencia.recarregar_se_preciso()
    # Fase 2: autoridade (selecionáveis + todos) para classificar a integridade.
    base = obter_base_contratos()
    integridade = referencia.integridade(base["selecionaveis"], base["todos"])
    # Fase 3/Saída: status + contagens + integridade; FastAPI serializa em JSON 200.
    return {
        "status": "ok",
        "referencia": referencia.resumo(),
        "integridade": integridade,
    }
