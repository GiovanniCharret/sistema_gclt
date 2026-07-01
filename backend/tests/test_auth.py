"""Testes de autenticação — hashing e store de usuários (`backend/auth.py`) — Bloco B1.

Por que existe: a §5.2 da spec define login/senha reais com **hash pbkdf2 + salt por
usuário** e um store em arquivo (`usuarios.json`, tratado como segredo). Estes testes
cobrem o hashing (verifica/rejeita, salt aleatório), a senha temporária e o CRUD mínimo
do store (criar com flag de troca, obter case-insensitive, desativar). O store usa
`tmp_path` — nunca o `usuarios.json` real.
"""

# `json` inspeciona o arquivo persistido pelo store.
import json
# `patch` espiona o envio de e-mail no teste da CLI (sem enviar de verdade).
from unittest.mock import patch

# Funções sob teste do módulo de autenticação.
from backend.auth import (
    gerar_hash,
    verificar_senha,
    gerar_senha_temporaria,
    criar_usuario,
    obter_usuario,
    desativar_usuario,
    gerar_token,
    verificar_token,
    autenticar,
    trocar_senha,
    resetar_senha,
    LimitadorReset,
)
# Config injetável (para forçar TTL do token nos testes).
from backend.config import Config
# Entrypoint testável da CLI de provisionamento (`admin_usuarios`).
from backend.admin_usuarios import executar


def test_hash_verifica_senha_correta():
    """`verificar_senha` aceita a senha certa.

    Fase 1: gera hash+salt de uma senha.
    Fase 2: verifica a mesma senha → True.
    """
    # Fase 1: deriva hash e salt.
    hash_hex, salt = gerar_hash("segredo123")
    # Fase 2: a senha original confere.
    assert verificar_senha("segredo123", hash_hex, salt) is True


def test_hash_rejeita_senha_errada():
    """`verificar_senha` rejeita senha diferente.

    Fase 1: gera hash de uma senha.
    Fase 2: verifica outra senha → False.
    """
    # Fase 1: hash da senha real.
    hash_hex, salt = gerar_hash("segredo123")
    # Fase 2: senha errada não confere.
    assert verificar_senha("errada", hash_hex, salt) is False


def test_hash_usa_salt_aleatorio_por_chamada():
    """Dois hashes da MESMA senha diferem (salt aleatório por usuário).

    Fase 1: gera dois hashes da mesma senha.
    Fase 2: salts e hashes devem diferir (senão o salt não é aleatório).
    """
    # Fase 1: dois hashes independentes da mesma senha.
    h1, s1 = gerar_hash("mesmasenha")
    h2, s2 = gerar_hash("mesmasenha")
    # Fase 2: salt aleatório ⇒ salts e hashes distintos.
    assert s1 != s2
    assert h1 != h2


def test_senha_temporaria_e_string_nao_trivial():
    """A senha temporária é uma string com tamanho razoável.

    Fase 1: gera uma senha temporária.
    Fase 2: é `str` e não é curta demais.
    """
    # Fase 1: gera a senha.
    senha = gerar_senha_temporaria()
    # Fase 2: string com pelo menos 8 caracteres.
    assert isinstance(senha, str)
    assert len(senha) >= 8


def test_criar_usuario_grava_hash_e_flag_de_troca(tmp_path):
    """`criar_usuario` persiste o usuário com senha em hash e `precisa_trocar_senha`.

    Entrada: um caminho de store temporário e um e-mail com caixa mista.
    Fase 1: cria o usuário (senha temporária gerada internamente).
    Fase 2: o e-mail é normalizado (minúsculas); flags corretas; senha em hash
            (não em texto) e verificável.
    Fase 3: o arquivo `usuarios.json` foi realmente gravado com o usuário.
    Saída: asserções.
    """
    # Store temporário (nunca o real).
    caminho = tmp_path / "usuarios.json"
    # Fase 1: cria o usuário; devolve o registro e a senha temporária em texto.
    registro, senha = criar_usuario("Fulano@Equatorialenergia.com.br", caminho=caminho)
    # Fase 2: e-mail normalizado para minúsculas.
    assert registro["email"] == "fulano@equatorialenergia.com.br"
    # Precisa trocar no 1º acesso e está ativo.
    assert registro["precisa_trocar_senha"] is True
    assert registro["ativo"] is True
    # A senha é guardada em hash, não em texto.
    assert registro["senha_hash"] != senha
    # E o hash confere com a senha temporária devolvida.
    assert verificar_senha(senha, registro["senha_hash"], registro["salt"]) is True
    # Fase 3: persistido no arquivo, sob a chave do e-mail normalizado.
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert "fulano@equatorialenergia.com.br" in dados


def test_obter_usuario_case_insensitive(tmp_path):
    """`obter_usuario` acha o usuário ignorando a caixa; None se não existe.

    Fase 1: cria "a@b.com".
    Fase 2: busca com caixa diferente → acha.
    Fase 3: busca inexistente → None.
    """
    # Store temporário.
    caminho = tmp_path / "usuarios.json"
    # Fase 1: cria o usuário.
    criar_usuario("a@b.com", caminho=caminho)
    # Fase 2: busca case-insensitive encontra o registro.
    encontrado = obter_usuario("A@B.COM", caminho=caminho)
    assert encontrado is not None
    assert encontrado["email"] == "a@b.com"
    # Fase 3: e-mail inexistente devolve None.
    assert obter_usuario("nao@existe.com", caminho=caminho) is None


def test_desativar_usuario(tmp_path):
    """`desativar_usuario` marca `ativo=False`.

    Fase 1: cria e desativa.
    Fase 2: o registro fica inativo.
    """
    # Store temporário.
    caminho = tmp_path / "usuarios.json"
    # Fase 1: cria e depois desativa.
    criar_usuario("a@b.com", caminho=caminho)
    desativar_usuario("a@b.com", caminho=caminho)
    # Fase 2: usuário agora inativo.
    assert obter_usuario("a@b.com", caminho=caminho)["ativo"] is False


def test_cli_add_cria_usuario_e_envia_credenciais(tmp_path):
    """`admin_usuarios add <email>` cria o usuário e dispara o e-mail de credenciais.

    Entrada: store temporário; e-mail novo; envio de e-mail espionado (mock).
    Fase 1: executa a CLI `add` com o SMTP-layer mockado.
    Fase 2: o usuário foi criado com `precisa_trocar_senha=True`.
    Fase 3: `enviar_credenciais` foi chamado com (e-mail, senha) e a senha confere
            com o hash gravado (ou seja, é a senha temporária real do usuário).
    Fase 4: a CLI retornou código 0 (sucesso).
    Saída: asserções.
    """
    # Store temporário.
    caminho = tmp_path / "usuarios.json"
    # Fase 1: espiona o envio de credenciais e roda a CLI.
    with patch("backend.admin_usuarios.enviar_credenciais") as mock_env:
        codigo = executar(["add", "Novo@Equatorialenergia.com.br"], caminho=caminho)
    # Fase 2: usuário criado com a flag de troca.
    usuario = obter_usuario("novo@equatorialenergia.com.br", caminho=caminho)
    assert usuario is not None
    assert usuario["precisa_trocar_senha"] is True
    # Fase 3: e-mail de credenciais disparado com a senha temporária correta.
    assert mock_env.called is True
    email_arg, senha_arg = mock_env.call_args.args[0], mock_env.call_args.args[1]
    assert email_arg == "novo@equatorialenergia.com.br"
    assert verificar_senha(senha_arg, usuario["senha_hash"], usuario["salt"]) is True
    # Fase 4: código de saída 0.
    assert codigo == 0


def test_cli_disable_desativa_usuario(tmp_path):
    """`admin_usuarios disable <email>` desativa um usuário existente.

    Entrada: store temporário com um usuário.
    Fase 1: cria o usuário e roda a CLI `disable`.
    Fase 2: o usuário fica inativo e a CLI retorna 0.
    Saída: asserções.
    """
    # Store temporário com um usuário.
    caminho = tmp_path / "usuarios.json"
    criar_usuario("a@b.com", caminho=caminho)
    # Fase 1: executa o disable.
    codigo = executar(["disable", "a@b.com"], caminho=caminho)
    # Fase 2: inativo e sucesso.
    assert obter_usuario("a@b.com", caminho=caminho)["ativo"] is False
    assert codigo == 0


def test_token_roundtrip_devolve_email():
    """Um token gerado é validado e devolve o e-mail (subject).

    Fase 1: gera token para um e-mail.
    Fase 2: verifica o token → devolve o mesmo e-mail.
    """
    # Config de teste com segredo próprio.
    cfg = Config(secret_key="chave-de-teste-longa-com-mais-de-32-bytes-ok", token_ttl=3600)
    # Fase 1: gera o token.
    token = gerar_token("fulano@equatorialenergia.com.br", config=cfg)
    # Fase 2: verificar devolve o e-mail assinado.
    assert verificar_token(token, config=cfg) == "fulano@equatorialenergia.com.br"


def test_token_expirado_e_invalido():
    """Token expirado (ttl negativo) → verificação devolve None.

    Fase 1: gera token já expirado (ttl = -1s).
    Fase 2: verificar → None.
    """
    # Config com TTL negativo ⇒ token nasce expirado.
    cfg = Config(secret_key="chave-de-teste-longa-com-mais-de-32-bytes-ok", token_ttl=-1)
    # Fase 1: token expirado.
    token = gerar_token("x@y.com", config=cfg)
    # Fase 2: expirado não valida.
    assert verificar_token(token, config=cfg) is None


def test_token_assinatura_invalida_e_rejeitado():
    """Token assinado com outro segredo → None (assinatura inválida).

    Fase 1: gera com um segredo.
    Fase 2: valida com outro segredo → None.
    """
    # Gera com um segredo, valida com outro.
    token = gerar_token("x@y.com", config=Config(secret_key="chave-A-longa-com-mais-de-32-bytes-aqui-ok", token_ttl=3600))
    # Assinatura não confere ⇒ None.
    assert verificar_token(token, config=Config(secret_key="chave-B-longa-com-mais-de-32-bytes-aqui-ok", token_ttl=3600)) is None


def test_autenticar_senha_correta_emite_token(tmp_path):
    """`autenticar` com senha certa (sem flag de troca) emite token.

    Entrada: store temporário com usuário SEM flag de troca.
    Fase 1: cria o usuário e zera `precisa_trocar_senha` (simula pós-troca).
    Fase 2: autentica com a senha correta.
    Fase 3: resultado autenticado, com token válido.
    Saída: asserções.
    """
    caminho = tmp_path / "usuarios.json"
    cfg = Config(secret_key="chave-de-teste-longa-com-mais-de-32-bytes-ok", token_ttl=3600)
    # Fase 1: cria com senha conhecida e remove a flag de troca.
    registro, _ = criar_usuario("a@b.com", senha="MinhaSenha1", caminho=caminho)
    registro["precisa_trocar_senha"] = False
    # regrava o store com a flag desligada
    import json as _json
    caminho.write_text(_json.dumps({registro["email"]: registro}), encoding="utf-8")
    # Fase 2: autentica.
    resultado = autenticar("a@b.com", "MinhaSenha1", caminho=caminho, config=cfg)
    # Fase 3: autenticado e com token válido.
    assert resultado["autenticado"] is True
    assert verificar_token(resultado["token"], config=cfg) == "a@b.com"


def test_autenticar_flag_de_troca_nao_emite_token(tmp_path):
    """`autenticar` com senha certa mas flag ligada → precisaTrocarSenha (sem token).

    Fase 1: cria o usuário (nasce com `precisa_trocar_senha=True`).
    Fase 2: autentica com a senha temporária correta.
    Fase 3: sinaliza troca, sem token.
    """
    caminho = tmp_path / "usuarios.json"
    # Fase 1: cria com senha conhecida (flag de troca ligada por padrão).
    criar_usuario("a@b.com", senha="Temp123", caminho=caminho)
    # Fase 2: autentica com a senha temporária.
    resultado = autenticar("a@b.com", "Temp123", caminho=caminho)
    # Fase 3: precisa trocar, sem token.
    assert resultado["autenticado"] is True
    assert resultado.get("precisaTrocarSenha") is True
    assert "token" not in resultado


def test_autenticar_senha_errada_ou_inativo_falha(tmp_path):
    """`autenticar` falha com senha errada, usuário inexistente ou inativo.

    Fase 1: cria um usuário.
    Fase 2: senha errada → não autenticado.
    Fase 3: usuário inexistente → não autenticado.
    Fase 4: usuário inativo → não autenticado (mesmo com senha certa).
    """
    caminho = tmp_path / "usuarios.json"
    # Fase 1: cria o usuário.
    criar_usuario("a@b.com", senha="Certa123", caminho=caminho)
    # Fase 2: senha errada.
    assert autenticar("a@b.com", "errada", caminho=caminho)["autenticado"] is False
    # Fase 3: inexistente.
    assert autenticar("nao@existe.com", "x", caminho=caminho)["autenticado"] is False
    # Fase 4: inativo não entra nem com a senha certa.
    desativar_usuario("a@b.com", caminho=caminho)
    assert autenticar("a@b.com", "Certa123", caminho=caminho)["autenticado"] is False


def test_trocar_senha_1o_acesso_zera_flag_e_emite_token(tmp_path):
    """`trocar_senha` grava a nova senha, zera a flag e emite token.

    Entrada: store temp com usuário recém-criado (flag de troca ligada).
    Fase 1: cria com senha temporária conhecida.
    Fase 2: troca para uma nova senha.
    Fase 3: ok + token válido; flag desligada; nova senha confere e a antiga não.
    Saída: asserções.
    """
    caminho = tmp_path / "usuarios.json"
    cfg = Config(secret_key="chave-de-teste-longa-com-mais-de-32-bytes-ok", token_ttl=3600)
    # Fase 1: usuário com senha temporária conhecida.
    criar_usuario("a@b.com", senha="Temp123", caminho=caminho)
    # Fase 2: troca de senha.
    resultado = trocar_senha("a@b.com", "Temp123", "NovaSenha456", caminho=caminho, config=cfg)
    # Fase 3: sucesso + token válido.
    assert resultado["ok"] is True
    assert verificar_token(resultado["token"], config=cfg) == "a@b.com"
    # Flag zerada e senhas atualizadas.
    usuario = obter_usuario("a@b.com", caminho=caminho)
    assert usuario["precisa_trocar_senha"] is False
    assert verificar_senha("NovaSenha456", usuario["senha_hash"], usuario["salt"]) is True
    assert verificar_senha("Temp123", usuario["senha_hash"], usuario["salt"]) is False


def test_trocar_senha_atual_errada_falha_e_nao_altera(tmp_path):
    """`trocar_senha` com senha atual errada falha e não muda nada.

    Fase 1: cria o usuário.
    Fase 2: tenta trocar com senha atual errada → ok False.
    Fase 3: a senha original continua válida e a flag intacta.
    """
    caminho = tmp_path / "usuarios.json"
    # Fase 1: cria o usuário.
    criar_usuario("a@b.com", senha="Temp123", caminho=caminho)
    # Fase 2: senha atual incorreta.
    resultado = trocar_senha("a@b.com", "errada", "NovaSenha456", caminho=caminho)
    assert resultado["ok"] is False
    # Fase 3: nada mudou (senha original ainda confere).
    usuario = obter_usuario("a@b.com", caminho=caminho)
    assert verificar_senha("Temp123", usuario["senha_hash"], usuario["salt"]) is True


def test_resetar_senha_gera_nova_e_liga_flag(tmp_path):
    """`resetar_senha` gera nova senha temporária, liga a flag e devolve (email, senha).

    Entrada: store temp com um usuário.
    Fase 1: cria o usuário.
    Fase 2: reseta a senha.
    Fase 3: devolve o e-mail canônico + a nova senha; flag religada; nova confere e a
            antiga não.
    Saída: asserções.
    """
    caminho = tmp_path / "usuarios.json"
    # Fase 1: usuário com senha conhecida.
    criar_usuario("a@b.com", senha="Antiga1", caminho=caminho)
    # Fase 2: reset self-service.
    resultado = resetar_senha("a@b.com", caminho=caminho)
    # Fase 3: (email, nova) e efeitos no store.
    email_canonico, nova = resultado
    assert email_canonico == "a@b.com"
    usuario = obter_usuario("a@b.com", caminho=caminho)
    assert usuario["precisa_trocar_senha"] is True
    assert verificar_senha(nova, usuario["senha_hash"], usuario["salt"]) is True
    assert verificar_senha("Antiga1", usuario["senha_hash"], usuario["salt"]) is False


def test_resetar_senha_inexistente_devolve_none(tmp_path):
    """`resetar_senha` de e-mail inexistente devolve None (resposta genérica na rota)."""
    caminho = tmp_path / "usuarios.json"
    # Nenhum usuário criado → None.
    assert resetar_senha("nao@existe.com", caminho=caminho) is None


def test_limitador_reset_bloqueia_apos_maximo_e_reabre_apos_janela():
    """`LimitadorReset` libera até o máximo por janela, bloqueia o excedente e reabre depois.

    Entrada: limitador (máx 2 por 100s) e um relógio injetado (`agora`).
    Fase 1: 2 permitidos dentro da janela.
    Fase 2: o 3º dentro da janela é bloqueado.
    Fase 3: após a janela, libera de novo.
    Fase 4: outro e-mail é independente.
    Saída: asserções.
    """
    # Limitador determinístico (tempo injetado).
    lim = LimitadorReset(maximo=2, janela_s=100)
    # Fase 1: dois primeiros liberados.
    assert lim.permitido("a@b.com", agora=1000) is True
    assert lim.permitido("a@b.com", agora=1001) is True
    # Fase 2: terceiro dentro da janela bloqueado.
    assert lim.permitido("a@b.com", agora=1002) is False
    # Fase 3: passada a janela, libera novamente.
    assert lim.permitido("a@b.com", agora=1200) is True
    # Fase 4: e-mail diferente não é afetado.
    assert lim.permitido("c@d.com", agora=1002) is True
