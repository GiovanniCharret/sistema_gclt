"""Testes e2e das rotas da API (via TestClient).

Por que existe: a §13 da spec e o CLAUDE.md exigem testes e2e cobrindo os
caminhos importantes. Cobre o health-check (A1–A3) e o login (B2), este último com
o store de usuários apontado para um `tmp_path` via override de dependência.
"""

# `json` grava o store de usuários temporário dos testes de login.
import json
# `types` monta uma referência fake (SimpleNamespace) nos testes de validar.
import types
# `patch` espiona o envio de e-mail / injeta fakes.
from unittest.mock import patch

# `pytest` para a fixture de store temporário.
import pytest
# `HTTPException` é levantada pelo guard de token (testado diretamente).
from fastapi import HTTPException

# App, dependência do caminho do store e guard de token (para os testes).
from backend.app import app, caminho_usuarios, usuario_do_token
# Criação de usuário, verificação de token e geração de token nos testes.
from backend.auth import criar_usuario, verificar_token, gerar_token, obter_usuario
# Gerador de .xlsx-fixture para os testes de validar.
from backend.tests.fixtures import gerar_xlsx


@pytest.fixture
def store_usuarios(tmp_path):
    """Aponta o store de usuários da API para um arquivo temporário.

    Entrada: `tmp_path`.
    Fase 1: define o caminho temporário e sobrescreve a dependência `caminho_usuarios`.
    Fase 2: entrega o caminho ao teste.
    Fase 3: limpa o override ao final (não vaza para outros testes).
    Saída: o Path do store temporário.
    """
    # Fase 1: caminho temp + override da dependência da API.
    caminho = tmp_path / "usuarios.json"
    app.dependency_overrides[caminho_usuarios] = lambda: str(caminho)
    # Fase 2: disponibiliza ao teste.
    yield caminho
    # Fase 3: remove o override (isolamento entre testes).
    app.dependency_overrides.pop(caminho_usuarios, None)


def _criar_usuario_sem_flag(caminho, email, senha):
    """Cria um usuário já 'pós-troca' (sem `precisa_trocar_senha`) no store.

    Entrada: `caminho` (store), `email`, `senha`.
    Fase 1: cria o usuário (nasce com flag de troca).
    Fase 2: zera a flag e regrava o store.
    Saída: nenhuma (efeito no arquivo).
    """
    # Fase 1: cria com a senha conhecida.
    registro, _ = criar_usuario(email, senha=senha, caminho=caminho)
    # Fase 2: desliga a flag de troca e persiste.
    registro["precisa_trocar_senha"] = False
    caminho.write_text(json.dumps({registro["email"]: registro}), encoding="utf-8")


def test_health_retorna_200_e_status_ok(client):
    """Garante que `GET /api/health` responde 200 com `{"status": "ok"}`.

    Entrada: a fixture `client` (TestClient do app).
    Fase 1: faz `GET /api/health`.
    Fase 2: confere o código HTTP (200) — prova que a rota existe e o app subiu.
    Fase 3: confere o corpo JSON (`status == "ok"`) — prova o contrato mínimo
            do health esperado pela A1.
    Saída: asserções; o teste passa se todas forem verdadeiras.
    """
    # Fase 1: dispara a requisição ao endpoint de saúde.
    resposta = client.get("/api/health")
    # Fase 2: o health-check deve sempre responder 200 quando o serviço está de pé.
    assert resposta.status_code == 200
    # Fase 3: o corpo mínimo acordado para a A1 é {"status": "ok"}.
    assert resposta.json()["status"] == "ok"


def test_health_expoe_contagem_da_referencia(client):
    """Garante que `GET /api/health` expõe as contagens da referência (A2).

    Entrada: a fixture `client` (TestClient) — o app carrega o `entrada/` real.
    Fase 1: faz `GET /api/health`.
    Fase 2: lê o bloco `referencia` do corpo.
    Fase 3: confere que as 4 contagens existem e são positivas (o `entrada/`
            real tem dezenas de milhares de pares (odi, uc) e mapeamentos odi→loc).
    Saída: asserções.
    """
    # Fase 1: consulta o health.
    corpo = client.get("/api/health").json()
    # Fase 2: o bloco de contagens da referência deve estar presente.
    referencia = corpo["referencia"]
    # Fase 3: as 4 contagens devem ser positivas com os dados reais de `entrada/`.
    assert referencia["totalChavesUc"] > 0
    assert referencia["totalOdiRef"] > 0
    assert referencia["contratosComChavesUc"] > 0
    assert referencia["contratosComOdiRef"] > 0


def test_health_lista_integridade_22_sem_referencia(client):
    """Garante que `GET /api/health` expõe a integridade com os 22 sem UC (A3).

    Entrada: a fixture `client` (TestClient) — app com `entrada/` e `base_contratos.json` reais.
    Fase 1: faz `GET /api/health` e lê o bloco `integridade`.
    Fase 2: confere 19 com referência, 22 sem referência e 0 órfãos (estado atual da base).
    Fase 3: confere que os 3 LPT pendentes estão entre os sem-referência.
    Saída: asserções.
    """
    # Fase 1: lê a integridade do health.
    integridade = client.get("/api/health").json()["integridade"]
    # Fase 2: classificação esperada hoje (19 com UC; 22 sem — 19 MLA + 3 LPT; 0 órfãos).
    assert integridade["contratosComReferencia"] == 19
    assert len(integridade["contratosSemReferencia"]) == 22
    assert integridade["orfaos"] == []
    # Fase 3: os 3 contratos LPT ainda pendentes devem estar na lista de sem-referência.
    for contrato in ["ECO 034/2026", "ECO 039/2025", "ECO 042/2025"]:
        assert contrato in integridade["contratosSemReferencia"]


def test_login_senha_correta_retorna_token(client, store_usuarios):
    """`POST /api/login` com senha certa (sem flag) → 200 + token válido.

    Entrada: store temp com usuário pós-troca; TestClient.
    Fase 1: cria o usuário no store.
    Fase 2: faz login com a senha correta.
    Fase 3: 200 + token que valida para o e-mail.
    Saída: asserções.
    """
    # Fase 1: usuário sem flag de troca.
    _criar_usuario_sem_flag(store_usuarios, "op@equatorialenergia.com.br", "Senha123")
    # Fase 2: login com credenciais corretas.
    resposta = client.post("/api/login",
                           json={"email": "op@equatorialenergia.com.br", "senha": "Senha123"})
    # Fase 3: sucesso com token válido.
    assert resposta.status_code == 200
    token = resposta.json()["token"]
    assert verificar_token(token) == "op@equatorialenergia.com.br"


def test_login_dominio_nao_registrado_retorna_403(client, store_usuarios):
    """`POST /api/login` com domínio fora do mapa de acesso → 403 (não autentica).

    Não precisa nem existir usuário: o domínio não mapeia a nenhum grupo, então não há
    o que acessar — informa e para (§5.1). Fase 1: login com domínio desconhecido.
    Fase 2: 403 com mensagem sobre domínio não registrado.
    """
    # Fase 1/2: domínio desconhecido → 403.
    resposta = client.post("/api/login",
                           json={"email": "alguem@desconhecido.com", "senha": "qualquer"})
    assert resposta.status_code == 403
    assert "registrad" in resposta.json()["detail"].lower()


def test_login_senha_errada_retorna_401(client, store_usuarios):
    """`POST /api/login` com senha errada → 401.

    Fase 1: cria o usuário.
    Fase 2: login com senha errada → 401.
    """
    # Fase 1: usuário no store.
    _criar_usuario_sem_flag(store_usuarios, "op@equatorialenergia.com.br", "Senha123")
    # Fase 2: senha incorreta.
    resposta = client.post("/api/login",
                           json={"email": "op@equatorialenergia.com.br", "senha": "errada"})
    # 401 esperado.
    assert resposta.status_code == 401


def test_login_precisa_trocar_senha_sem_token(client, store_usuarios):
    """`POST /api/login` no 1º acesso (flag ligada) → 200 + precisaTrocarSenha, sem token.

    Fase 1: cria o usuário (flag de troca ligada por padrão).
    Fase 2: login com a senha temporária.
    Fase 3: 200, precisaTrocarSenha=true e sem token.
    """
    # Fase 1: usuário recém-criado (precisa_trocar_senha=True).
    criar_usuario("novo@equatorialenergia.com.br", senha="Temp123", caminho=store_usuarios)
    # Fase 2: login com a senha temporária.
    resposta = client.post("/api/login",
                           json={"email": "novo@equatorialenergia.com.br", "senha": "Temp123"})
    # Fase 3: sinaliza troca, sem token.
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo.get("precisaTrocarSenha") is True
    assert "token" not in corpo


def test_trocar_senha_no_1o_acesso_e_depois_loga(client, store_usuarios):
    """`POST /api/trocar-senha` troca no 1º acesso; depois o login entra direto.

    Fase 1: cria usuário (flag de troca ligada) com senha temporária.
    Fase 2: troca a senha → 200 + token.
    Fase 3: login com a nova senha → 200 + token, SEM precisaTrocarSenha.
    """
    # Fase 1: usuário recém-criado.
    criar_usuario("op@equatorialenergia.com.br", senha="Temp123", caminho=store_usuarios)
    # Fase 2: troca de senha no 1º acesso.
    troca = client.post("/api/trocar-senha", json={
        "email": "op@equatorialenergia.com.br",
        "senhaAtual": "Temp123",
        "novaSenha": "NovaSenha456",
    })
    assert troca.status_code == 200
    assert "token" in troca.json()
    # Fase 3: agora loga direto com a nova senha (sem precisar trocar).
    login = client.post("/api/login", json={
        "email": "op@equatorialenergia.com.br", "senha": "NovaSenha456",
    })
    assert login.status_code == 200
    assert "token" in login.json()
    assert "precisaTrocarSenha" not in login.json()


def test_trocar_senha_atual_errada_retorna_401(client, store_usuarios):
    """`POST /api/trocar-senha` com senha atual errada → 401.

    Fase 1: cria o usuário.
    Fase 2: troca com senha atual errada → 401.
    """
    # Fase 1: usuário no store.
    criar_usuario("op@equatorialenergia.com.br", senha="Temp123", caminho=store_usuarios)
    # Fase 2: senha atual incorreta.
    resposta = client.post("/api/trocar-senha", json={
        "email": "op@equatorialenergia.com.br",
        "senhaAtual": "errada",
        "novaSenha": "NovaSenha456",
    })
    assert resposta.status_code == 401


# --- Guard de token (B4) — testado diretamente na dependência ---

def test_guard_sem_token_401():
    """`usuario_do_token` sem header Authorization → 401."""
    # Sem token → HTTPException 401.
    with pytest.raises(HTTPException) as erro:
        usuario_do_token(authorization=None)
    assert erro.value.status_code == 401


def test_guard_token_invalido_401():
    """`usuario_do_token` com token inválido → 401."""
    # Token lixo → 401.
    with pytest.raises(HTTPException) as erro:
        usuario_do_token(authorization="Bearer lixo-invalido")
    assert erro.value.status_code == 401


def test_guard_token_valido_retorna_email():
    """`usuario_do_token` com Bearer válido → devolve o e-mail do token."""
    # Token válido (config do processo) → e-mail.
    token = gerar_token("op@equatorialenergia.com.br")
    assert usuario_do_token(authorization=f"Bearer {token}") == "op@equatorialenergia.com.br"


# --- Esqueci minha senha (B4) ---

def test_esqueci_senha_envia_nova_credencial(client, store_usuarios):
    """`POST /api/esqueci-senha` gera nova senha temporária e a envia ao usuário.

    Fase 1: cria o usuário; espiona o envio de e-mail.
    Fase 2: chama esqueci-senha → 200 genérico `{ok: true}`.
    Fase 3: e-mail de credenciais disparado ao usuário; flag religada.
    """
    # Fase 1: usuário no store + spy do envio.
    criar_usuario("op@equatorialenergia.com.br", senha="Antiga1", caminho=store_usuarios)
    with patch("backend.app.enviar_credenciais") as mock_env:
        # Fase 2: dispara o reset.
        resposta = client.post("/api/esqueci-senha",
                               json={"email": "op@equatorialenergia.com.br"})
    # Resposta genérica de sucesso.
    assert resposta.status_code == 200
    assert resposta.json() == {"ok": True}
    # Fase 3: e-mail enviado ao usuário e flag de troca religada.
    assert mock_env.called is True
    assert mock_env.call_args.args[0] == "op@equatorialenergia.com.br"
    assert obter_usuario("op@equatorialenergia.com.br",
                         caminho=store_usuarios)["precisa_trocar_senha"] is True


def test_esqueci_senha_email_inexistente_resposta_generica(client, store_usuarios):
    """`POST /api/esqueci-senha` de e-mail inexistente → 200 genérico, sem enviar e-mail.

    Fase 1: store vazio; espiona o envio.
    Fase 2: chama esqueci-senha para e-mail que não existe.
    Fase 3: 200 `{ok: true}` (não revela) e nenhum e-mail enviado.
    """
    # Fase 1/2: reset de e-mail inexistente, com spy.
    with patch("backend.app.enviar_credenciais") as mock_env:
        resposta = client.post("/api/esqueci-senha",
                               json={"email": "nao@existe.com"})
    # Fase 3: resposta genérica idêntica e nada enviado.
    assert resposta.status_code == 200
    assert resposta.json() == {"ok": True}
    assert mock_env.called is False


# --- Contexto de login (C1) — rota protegida ---

def test_contexto_sem_token_retorna_401(client):
    """`GET /api/contexto` sem token → 401 (rota protegida pelo guard)."""
    # Sem Authorization → 401.
    assert client.get("/api/contexto").status_code == 401


def test_contexto_equatorial_ve_18_contratos(client):
    """`GET /api/contexto` com token equatorial → grupo EQUATORIAL e 18 contratos.

    Fase 1: gera token para um e-mail do domínio equatorial.
    Fase 2: chama a rota com o Bearer.
    Fase 3: grupo correto, 18 contratos (todos EQUATORIAL) e UFs com nome resolvido.
    """
    # Fase 1: token do usuário equatorial.
    token = gerar_token("op@equatorialenergia.com.br")
    # Fase 2: consulta o contexto autenticado.
    resposta = client.get("/api/contexto", headers={"Authorization": f"Bearer {token}"})
    assert resposta.status_code == 200
    corpo = resposta.json()
    # Fase 3: grupo, contratos e UFs coerentes com a base real.
    assert corpo["grupo"] == "EQUATORIAL"
    assert len(corpo["contratos"]) == 18
    assert all(c["sigla"] == "EQUATORIAL" for c in corpo["contratos"])
    assert all("nome" in u and "contratos" in u for u in corpo["ufs"])


def test_contexto_enbpar_ve_41_contratos(client):
    """`GET /api/contexto` com token enbpar (curinga) → todos os 41 contratos."""
    # Token enbpar → vê tudo.
    token = gerar_token("chefe@enbpar.gov.br")
    resposta = client.get("/api/contexto", headers={"Authorization": f"Bearer {token}"})
    assert resposta.status_code == 200
    assert len(resposta.json()["contratos"]) == 41


# --- Validar (E2) e Modelo (E3) — rotas protegidas ---

# Domínios pequenos para a validação nos testes de /api/validar.
_DOM_VAL = {
    "TIPO_ATENDIMENTO": ["Extensão de Rede"],
    "UF": ["AM"],
    "SIM_NAO": ["Sim", "Não"],
    "TIPO_COMUNIDADE": ["1 - Comunidade indígena"],
    "ENQUADRAMENTO_BENEFICIARIO": ["0 - Não é prioridade"],
}

# Uma linha 100% válida (para o caminho limpo).
_LINHA_LIMPA = {
    "Número ODI": "O1", "Número da Unidade Consumidora": "U1",
    "Código IBGE do Município": "1302603", "Município": "MANACAPURU", "UF": "AM",
    "Latitude": "-3.30", "Longitude": "-60.0", "Data de Energização da UC": "14/02/2026",
    "Tipo de Atendimento": "Extensão de Rede", "Tipo de Comunidade": "1 - Comunidade indígena",
    "Enquadramento do beneficiário": "0 - Não é prioridade",
    "0 - Não é prioridade": "Não", "I - Baixa renda": "Sim",
}


def _referencia_fake():
    """Referência fake: 'CTR TESTE' tem UC; 'CTR SEMREF' não tem (para o 409)."""
    return types.SimpleNamespace(
        chaves_uc={"CTR TESTE": {("O1", "U1")}},
        odi_ref={"CTR TESTE": {"O1": ("AM", "MANACAPURU")}},
        recarregar_se_preciso=lambda: None,
    )


def _base_fake():
    """Base fake: dois contratos EQUATORIAL selecionáveis (um com, outro sem referência)."""
    contratos = [
        {"numero": "CTR TESTE", "sigla": "EQUATORIAL", "uf": "AM",
         "tipo_contrato": "LPT", "tranche": "1ª", "vigente": "Andamento"},
        {"numero": "CTR SEMREF", "sigla": "EQUATORIAL", "uf": "AM",
         "tipo_contrato": "LPT", "tranche": "1ª", "vigente": "Andamento"},
    ]
    return {"contratos": contratos, "selecionaveis": {"CTR TESTE", "CTR SEMREF"},
            "todos": {"CTR TESTE", "CTR SEMREF"}}


@pytest.fixture
def validar_env():
    """Injeta referência/base/domínios fake e espiona os envios de e-mail."""
    with patch("backend.app.obter_referencia", _referencia_fake), \
         patch("backend.app.obter_base_contratos", _base_fake), \
         patch("backend.app.obter_dominios", lambda: _DOM_VAL), \
         patch("backend.app.enviar_planilha_validada") as env_planilha, \
         patch("backend.app.enviar_alerta_critico") as env_alerta:
        env_planilha.return_value = True
        yield {"planilha": env_planilha, "alerta": env_alerta}


def _headers(email="op@equatorialenergia.com.br"):
    """Cabeçalho Authorization com um token válido para o e-mail dado."""
    return {"Authorization": f"Bearer {gerar_token(email)}"}


def test_validar_sem_token_retorna_401(client):
    """`POST /api/validar` sem token → 401."""
    r = client.post("/api/validar", files={"arquivo": ("a.xlsx", b"x")},
                    data={"contrato": "CTR TESTE", "uf": "AM"})
    assert r.status_code == 401


def test_validar_planilha_limpa_envia_email(client, validar_env):
    """Planilha limpa → 200, ok=true, e-mail da planilha disparado."""
    conteudo = gerar_xlsx([_LINHA_LIMPA])
    r = client.post("/api/validar", headers=_headers(),
                    files={"arquivo": ("Anexo.xlsx", conteudo)},
                    data={"contrato": "CTR TESTE", "uf": "AM"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["ok"] is True and corpo["totalErros"] == 0
    assert corpo["enviado"] is True
    assert validar_env["planilha"].called is True


def test_validar_planilha_suja_nao_envia(client, validar_env):
    """Planilha com erro → 200, ok=false, e-mail NÃO enviado."""
    suja = {**_LINHA_LIMPA, "UF": "XX"}  # UF fora do domínio
    conteudo = gerar_xlsx([suja])
    r = client.post("/api/validar", headers=_headers(),
                    files={"arquivo": ("Anexo.xlsx", conteudo)},
                    data={"contrato": "CTR TESTE", "uf": "AM"})
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert validar_env["planilha"].called is False


def test_validar_contrato_fora_do_grupo_403(client, validar_env):
    """Contrato de outro grupo (token ENERGISA, contrato EQUATORIAL) → 403."""
    conteudo = gerar_xlsx([_LINHA_LIMPA])
    r = client.post("/api/validar", headers=_headers("op@energisa.com.br"),
                    files={"arquivo": ("Anexo.xlsx", conteudo)},
                    data={"contrato": "CTR TESTE", "uf": "AM"})
    assert r.status_code == 403


def test_validar_contrato_sem_referencia_409_e_alerta(client, validar_env):
    """Contrato sem referência → 409 e alerta crítico ao admin."""
    conteudo = gerar_xlsx([_LINHA_LIMPA])
    r = client.post("/api/validar", headers=_headers(),
                    files={"arquivo": ("Anexo.xlsx", conteudo)},
                    data={"contrato": "CTR SEMREF", "uf": "AM"})
    assert r.status_code == 409
    assert validar_env["alerta"].called is True


def test_validar_arquivo_invalido_400(client, validar_env):
    """Arquivo que não é .xlsx → 400."""
    r = client.post("/api/validar", headers=_headers(),
                    files={"arquivo": ("a.xlsx", b"isto nao e xlsx")},
                    data={"contrato": "CTR TESTE", "uf": "AM"})
    assert r.status_code == 400


def test_modelo_sem_token_retorna_401(client):
    """`GET /api/modelo` sem token → 401."""
    assert client.get("/api/modelo").status_code == 401


def test_modelo_baixa_o_arquivo(client):
    """`GET /api/modelo` com token → 200 + Content-Disposition + bytes."""
    r = client.get("/api/modelo", headers=_headers())
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "").lower()
    assert len(r.content) > 0
