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

# `time` fornece o relógio do rate-limiter do esqueci-senha.
import time

# `FastAPI`/`Depends`/`HTTPException`/`Header`/`File`/`Form`/`UploadFile` — app, DI, erros,
# header e upload multipart (E2).
from fastapi import FastAPI, Depends, HTTPException, Header, File, Form, UploadFile
# `FileResponse` serve o modelo oficial como download (E3).
from fastapi.responses import FileResponse
# `CORSMiddleware` libera chamadas cross-origin do front em desenvolvimento.
from fastapi.middleware.cors import CORSMiddleware
# `BaseModel` valida/tipa o corpo JSON das requisições (ex.: login).
from pydantic import BaseModel

# Cache de referência de `entrada/` (A2), autoridade (A3) e normalização do nº de contrato.
from backend.referencia import obter_referencia, obter_base_contratos, _norm_contrato
# Configuração do processo (caminho do store de usuários) e auth (B2–B4).
from backend.config import obter_config
from backend.auth import autenticar, trocar_senha, resetar_senha, verificar_token, LimitadorReset
# E-mails: credenciais (B1), planilha validada e alerta crítico (E1) — mockáveis nos testes.
from backend.email_envio import enviar_credenciais, enviar_planilha_validada, enviar_alerta_critico
# Montagem do contexto, resolução do grupo e filtro de contratos por grupo (C1/E2, §5.1).
from backend.acesso import montar_contexto, grupo_do_email, contratos_visiveis
# Parsing (D1), domínios (D2) e validação (D3–D5) da planilha.
from backend.planilha import ler_preenchimento, obter_dominios, PlanilhaInvalida, _MODELO_PADRAO
from backend.validacao import validar

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


def caminho_usuarios():
    """Dependência: caminho do store de usuários (da config).

    Por que existe: isola de onde vem o `usuarios.json`, permitindo os testes
    sobrescreverem para um arquivo temporário via `app.dependency_overrides`.

    Entrada: nenhuma.
    Fase 1: lê `usuarios_path` da config do processo.
    Saída: o caminho (str) do store.
    """
    # Fase 1/Saída: caminho configurado do store de usuários.
    return obter_config().usuarios_path


class LoginIn(BaseModel):
    """Corpo do `POST /api/login`: e-mail + senha."""

    # E-mail informado no login.
    email: str
    # Senha em texto (validada contra o hash guardado).
    senha: str


@app.post("/api/login")
def login(dados: LoginIn, caminho=Depends(caminho_usuarios)):
    """Autentica o usuário; emite token ou sinaliza troca de senha (B2, §5.2/§6).

    Entrada: `dados` (email/senha) e `caminho` (store, injetado).
    Fase 1: aplica a regra de login (`autenticar`).
    Fase 2: credenciais inválidas → 401.
    Fase 3: 1º acesso (flag) → `{precisaTrocarSenha: true}` (sem token).
    Fase 4: caso normal → `{token}`.
    Saída: JSON conforme o desfecho; 401 quando inválido.
    """
    # Fase 0: domínio do e-mail precisa mapear a um grupo (§5.1); senão não há o que
    # acessar — informa e para (não faz sentido autenticar num domínio não registrado).
    if grupo_do_email(dados.email) is None:
        raise HTTPException(status_code=403, detail="Domínio de e-mail não registrado no sistema.")
    # Fase 1: decide o desfecho do login.
    resultado = autenticar(dados.email, dados.senha, caminho=caminho)
    # Fase 2: inválido → 401 (mensagem genérica, não revela o que falhou).
    if not resultado["autenticado"]:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    # Fase 3: precisa trocar senha no 1º acesso (sem token pleno).
    if resultado.get("precisaTrocarSenha"):
        return {"precisaTrocarSenha": True}
    # Fase 4/Saída: login pleno com token de sessão.
    return {"token": resultado["token"]}


class TrocarSenhaIn(BaseModel):
    """Corpo do `POST /api/trocar-senha`: e-mail + senha atual + nova senha."""

    # E-mail do usuário que está trocando a senha.
    email: str
    # Senha atual (temporária, no 1º acesso).
    senhaAtual: str
    # Nova senha desejada.
    novaSenha: str


@app.post("/api/trocar-senha")
def trocar_senha_rota(dados: TrocarSenhaIn, caminho=Depends(caminho_usuarios)):
    """Troca a senha (1º acesso) e emite token (B3, §5.2/§6).

    Entrada: `dados` (email/senhaAtual/novaSenha) e `caminho` (store, injetado).
    Fase 1: valida que a nova senha não é vazia → senão 400.
    Fase 2: aplica a troca (`trocar_senha`); senha atual inválida → 401.
    Fase 3: sucesso → `{token}`.
    Saída: JSON `{token}`; 400/401 nos erros.
    """
    # Fase 1: nova senha obrigatória (política mínima).
    if not dados.novaSenha.strip():
        raise HTTPException(status_code=400, detail="Nova senha obrigatória")
    # Fase 2: tenta trocar; falha de credencial → 401.
    resultado = trocar_senha(dados.email, dados.senhaAtual, dados.novaSenha, caminho=caminho)
    if not resultado["ok"]:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    # Fase 3/Saída: token de sessão após a troca.
    return {"token": resultado["token"]}


def usuario_do_token(authorization: str = Header(default=None)):
    """Guard de rota: extrai e valida o token `Bearer`, devolvendo o e-mail (B4).

    Por que existe: as rotas protegidas (`/api/contexto`, `/api/validar`, `/api/modelo`
    a partir dos Blocos C/E) identificam o usuário pelo token, não por parâmetro. Este
    guard reusável rejeita requisições sem token válido.

    Entrada: header `Authorization: Bearer <token>` (injetado).
    Fase 1: exige o esquema Bearer; ausente/mal-formado → 401.
    Fase 2: valida o token; inválido/expirado → 401.
    Saída: o e-mail (subject) do token.
    """
    # Fase 1: precisa do header no formato "Bearer <token>".
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente")
    # Extrai o token após "Bearer ".
    token = authorization[len("Bearer "):].strip()
    # Fase 2: valida a assinatura/expiração.
    email = verificar_token(token)
    if email is None:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    # Saída: e-mail autenticado.
    return email


# Rate-limiter do esqueci-senha (compartilhado no processo; tempo real via time.time()).
_limitador_reset = LimitadorReset()


class EsqueciSenhaIn(BaseModel):
    """Corpo do `POST /api/esqueci-senha`: apenas o e-mail."""

    # E-mail que solicitou a redefinição.
    email: str


@app.post("/api/esqueci-senha")
def esqueci_senha_rota(dados: EsqueciSenhaIn, caminho=Depends(caminho_usuarios)):
    """Reset self-service: gera nova senha temporária e a envia (B4, §5.2/§6).

    Segurança: resposta **genérica** (não revela se o e-mail existe) e **rate-limited**
    por e-mail (mitiga abuso).

    Entrada: `dados` (email) e `caminho` (store, injetado).
    Fase 1: consulta o rate-limiter (silenciosamente ignora se estourou).
    Fase 2: se permitido, tenta resetar; se o usuário existe, envia a nova senha por e-mail.
    Fase 3: responde sempre `{ok: true}` (genérico).
    Saída: JSON `{ok: true}`.
    """
    # Fase 1: respeita o rate-limit (sem revelar nada ao chamador).
    if _limitador_reset.permitido(dados.email, time.time()):
        # Fase 2: reseta (None se não existe/inativo) e, se resetou, envia o e-mail.
        resultado = resetar_senha(dados.email, caminho=caminho)
        if resultado is not None:
            email_canonico, nova_senha = resultado
            enviar_credenciais(email_canonico, nova_senha)
    # Fase 3/Saída: resposta genérica (não revela existência do e-mail).
    return {"ok": True}


@app.post("/api/validar")
async def validar_rota(
    arquivo: UploadFile = File(...),
    contrato: str = Form(...),
    uf: str = Form(...),
    email=Depends(usuario_do_token),
):
    """Valida a planilha e, se passar, envia por e-mail (E2, §5.1/§6/§8).

    Protegida: o e-mail vem do token. `multipart/form-data` com `arquivo`/`contrato`/`uf`.

    Entrada: arquivo (.xlsx), contrato, uf; email (do token).
    Fase 1: escopo — contrato precisa pertencer ao grupo do e-mail (senão 403).
    Fase 2: anomalia — contrato sem referência em `entrada/` → alerta crítico + 409 (§8).
    Fase 3: parsing — lê a aba Preenchimento (não-.xlsx/sem aba → 400).
    Fase 4: valida (regras D3/D4) e monta o painel (D5).
    Fase 5: se 0 erros, envia o `.xlsx` como veio aos destinatários (marca `enviado`).
    Saída: JSON do painel + `ok`/`enviado` (+ `erroEnvio` em falha de SMTP).
    """
    # Número do contrato normalizado (casa com as chaves da referência/base).
    contrato_norm = _norm_contrato(contrato)
    referencia = obter_referencia()
    referencia.recarregar_se_preciso()
    base = obter_base_contratos()
    # Fase 1: o contrato precisa estar entre os visíveis do grupo do e-mail.
    visiveis = {c["numero"] for c in contratos_visiveis(grupo_do_email(email), base["contratos"])}
    if contrato_norm not in visiveis:
        raise HTTPException(status_code=403, detail="Contrato fora do escopo do seu acesso.")
    # Fase 2: contrato sem referência (sem chaves_uc) = anomalia → alerta + 409 (§8).
    if contrato_norm not in referencia.chaves_uc:
        enviar_alerta_critico(contrato, uf, arquivo.filename or "(sem nome)")
        raise HTTPException(status_code=409,
                            detail="Não foi possível validar este contrato no momento.")
    # Fase 3: lê os bytes e parseia a aba Preenchimento.
    conteudo = await arquivo.read()
    try:
        linhas = ler_preenchimento(conteudo)
    except PlanilhaInvalida as erro:
        raise HTTPException(status_code=400, detail=erro.mensagem)
    # Fase 4: valida contra domínios + referência do contrato.
    resultado = validar(
        linhas,
        obter_dominios(),
        referencia.chaves_uc.get(contrato_norm, set()),
        referencia.odi_ref.get(contrato_norm, {}),
    )
    # Fase 5: sem erros → envia o arquivo como veio (respeita dry-run/falha de SMTP).
    enviado = False
    erro_envio = None
    if resultado["ok"]:
        try:
            enviado = enviar_planilha_validada(conteudo, contrato, uf)
        except Exception as erro:  # falha de SMTP não derruba a resposta
            erro_envio = str(erro)
    # Saída: painel + status de envio.
    resposta = {**resultado, "enviado": enviado}
    if erro_envio:
        resposta["erroEnvio"] = erro_envio
    return resposta


@app.get("/api/modelo")
def modelo(email=Depends(usuario_do_token)):
    """Baixa o modelo oficial do Anexo V (E3, §6). Protegida pelo token.

    Entrada: email (do token, injetado).
    Fase 1: confere que o arquivo do modelo existe (senão 404).
    Fase 2: devolve como download (Content-Disposition attachment, nome canônico).
    Saída: o arquivo .xlsx.
    """
    # Fase 1: o modelo precisa estar presente (em `manuais/`, no servidor).
    if not _MODELO_PADRAO.exists():
        raise HTTPException(status_code=404, detail="Modelo não encontrado no servidor.")
    # Fase 2/Saída: download com o nome oficial.
    return FileResponse(
        str(_MODELO_PADRAO),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.xlsx",
    )


@app.get("/api/contexto")
def contexto(email=Depends(usuario_do_token)):
    """Contexto de login: grupo do usuário + UFs/contratos visíveis (C1, §5.1/§6).

    Protegida: o e-mail vem do token (guard `usuario_do_token`), nunca de parâmetro.

    Entrada: `email` (do token, injetado).
    Fase 1: obtém referência (recarrega se `entrada/` mudou) e a autoridade de contratos.
    Fase 2: calcula a contagem de UCs por contrato (tamanho de `chaves_uc`).
    Fase 3: monta o contexto filtrado pelo grupo do e-mail.
    Saída: JSON `{email, grupo, ufs, contratos}`.
    """
    # Fase 1: caches de referência e autoridade.
    referencia = obter_referencia()
    referencia.recarregar_se_preciso()
    base = obter_base_contratos()
    # Fase 2: nº de UCs por contrato (a partir dos pares (odi, uc) da referência).
    ucs_por_contrato = {numero: len(pares) for numero, pares in referencia.chaves_uc.items()}
    # Fase 3/Saída: contexto filtrado pelo grupo do e-mail do token.
    return montar_contexto(email, base["contratos"], ucs_por_contrato)
