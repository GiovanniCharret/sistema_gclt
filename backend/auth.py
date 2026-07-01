"""Autenticação — hashing de senha e store de usuários em arquivo (Bloco B1, §5.2).

Por que existe: o sistema tem login/senha reais, mas **sem banco** — os usuários
ficam em `backend/usuarios.json` (tratado como segredo, fora do git). Este módulo
concentra o hashing seguro (pbkdf2 + salt por usuário, só stdlib) e o CRUD mínimo do
store (criar com senha temporária, obter, desativar), com **escrita atômica** para não
corromper o arquivo em gravações concorrentes (risco #6 da spec). O token de sessão e
os endpoints de login/troca/esqueci ficam nas sub-fases B2–B4.

O grupo econômico do usuário **não** é guardado aqui — é derivado do domínio do e-mail
(ver `acesso.py`, §5.1).
"""

# `datetime` calcula a expiração (exp) do token de sessão.
import datetime
# `hashlib.pbkdf2_hmac` deriva o hash da senha (stdlib, sem dependência nativa).
import hashlib
# `json` serializa/《desserializa》 o store.
import json
# `os` faz a troca atômica do arquivo (os.replace) na escrita.
import os
# `secrets` gera salt e senha temporária criptograficamente seguros; compare_digest
# evita timing attacks na comparação de hashes.
import secrets
# `Path` resolve o caminho padrão do store.
from pathlib import Path

# `jwt` (PyJWT) assina/valida o token de sessão (HS256 + SECRET_KEY).
import jwt

# Config (SECRET_KEY, TOKEN_TTL) usada por token/autenticação quando não injetada.
from backend.config import obter_config

# Nº de iterações do pbkdf2 (custo do hashing; alto o bastante para senhas humanas).
_ITERACOES = 200_000
# Store padrão: `backend/usuarios.json` (ao lado deste módulo).
_USUARIOS_PADRAO = Path(__file__).resolve().parent / "usuarios.json"


def gerar_hash(senha, salt=None):
    """Deriva o hash pbkdf2-sha256 de uma senha, com salt (novo se não informado).

    Por que existe: nunca guardar senha em texto; o salt por usuário impede que
    senhas iguais gerem hashes iguais e inviabiliza rainbow tables.

    Entrada: `senha` (str) e `salt` (hex str opcional; None gera um novo).
    Fase 1: se não veio salt, gera um aleatório (16 bytes → 32 hex).
    Fase 2: roda pbkdf2-hmac-sha256 sobre a senha e o salt.
    Saída: tupla `(hash_hex, salt_hex)`.
    """
    # Fase 1: salt aleatório se não fornecido (ao verificar, reusa o salt salvo).
    if salt is None:
        salt = secrets.token_hex(16)
    # Fase 2: deriva a chave (bytes) a partir da senha e do salt.
    derivado = hashlib.pbkdf2_hmac(
        "sha256",                 # algoritmo de hash subjacente
        senha.encode("utf-8"),    # senha em bytes
        bytes.fromhex(salt),      # salt em bytes (a partir do hex)
        _ITERACOES,               # custo (iterações)
    )
    # Saída: hash e salt em hexadecimal (fáceis de guardar em JSON).
    return derivado.hex(), salt


def verificar_senha(senha, hash_hex, salt):
    """Confere se uma senha corresponde ao hash+salt guardados.

    Entrada: `senha` (str), `hash_hex` (hash esperado), `salt` (salt guardado).
    Fase 1: re-deriva o hash da senha com o MESMO salt.
    Fase 2: compara em tempo constante (evita timing attack).
    Saída: True se confere, False caso contrário.
    """
    # Fase 1: recalcula o hash usando o salt original.
    calculado, _ = gerar_hash(senha, salt)
    # Fase 2/Saída: comparação resistente a timing.
    return secrets.compare_digest(calculado, hash_hex)


def gerar_senha_temporaria(nbytes=12):
    """Gera uma senha temporária aleatória e url-safe.

    Por que existe: o admin cria o usuário com uma senha temporária (trocada no 1º
    acesso); ela precisa ser imprevisível e digitável.

    Entrada: `nbytes` (entropia; 12 bytes ≈ 16 caracteres).
    Fase 1: gera um token url-safe.
    Saída: a senha (str).
    """
    # Fase 1/Saída: token seguro e url-safe (sem caracteres ambíguos de escape).
    return secrets.token_urlsafe(nbytes)


def _norm_email(email):
    """Normaliza o e-mail para chave do store (trim + minúsculas).

    Entrada: `email` (str).
    Fase 1: remove espaços e baixa a caixa.
    Saída: e-mail canônico.
    """
    # Fase 1/Saída: e-mail sem bordas e em minúsculas (chave estável).
    return email.strip().lower()


def carregar_usuarios(caminho=None):
    """Lê o store `usuarios.json` (dict e-mail → registro); vazio se não existe.

    Entrada: `caminho` (Path/str; None usa o padrão).
    Fase 1: resolve o caminho.
    Fase 2: se o arquivo não existe, devolve dict vazio (1ª execução).
    Fase 3: lê e desserializa o JSON.
    Saída: dict `{email: registro}`.
    """
    # Fase 1: caminho efetivo do store.
    alvo = Path(caminho) if caminho is not None else _USUARIOS_PADRAO
    # Fase 2: sem arquivo ainda ⇒ nenhum usuário.
    if not alvo.exists():
        return {}
    # Fase 3/Saída: carrega o dicionário de usuários.
    with open(alvo, encoding="utf-8") as fh:
        return json.load(fh)


def salvar_usuarios(dados, caminho=None):
    """Grava o store de forma **atômica** (arquivo temporário + rename).

    Por que existe: escrita direta pode corromper o arquivo se o processo morrer no
    meio; gravar num temporário e trocar via `os.replace` é atômico no SO (risco #6).

    Entrada: `dados` (dict e-mail → registro) e `caminho` (opcional).
    Fase 1: resolve o caminho e garante a pasta.
    Fase 2: escreve num arquivo temporário no mesmo diretório.
    Fase 3: troca o arquivo final pelo temporário atomicamente.
    Saída: nenhuma (efeito em disco).
    """
    # Fase 1: caminho final e diretório-pai garantido.
    alvo = Path(caminho) if caminho is not None else _USUARIOS_PADRAO
    alvo.parent.mkdir(parents=True, exist_ok=True)
    # Temporário no MESMO diretório (para o replace ser atômico no mesmo volume).
    temporario = alvo.with_suffix(alvo.suffix + ".tmp")
    # Fase 2: grava o JSON no temporário.
    with open(temporario, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)
    # Fase 3: substitui o arquivo final pelo temporário (atômico).
    os.replace(temporario, alvo)


def obter_usuario(email, caminho=None):
    """Devolve o registro de um usuário (case-insensitive) ou None.

    Entrada: `email` (str) e `caminho` (opcional).
    Fase 1: normaliza o e-mail e carrega o store.
    Saída: o registro (dict) ou None se não existir.
    """
    # Fase 1/Saída: busca pela chave normalizada.
    return carregar_usuarios(caminho).get(_norm_email(email))


def criar_usuario(email, senha=None, caminho=None):
    """Cria (ou substitui) um usuário com senha temporária e flag de troca.

    Por que existe: o provisionamento é feito pelo admin (CLI); o usuário nasce com
    uma senha temporária que deve ser trocada no 1º acesso.

    Entrada: `email` (str), `senha` (str opcional; None gera temporária), `caminho`.
    Fase 1: normaliza o e-mail; gera a senha temporária se não veio.
    Fase 2: deriva hash+salt e monta o registro (precisa_trocar_senha=True, ativo=True).
    Fase 3: persiste no store (escrita atômica).
    Saída: tupla `(registro, senha_em_texto)` — a senha em texto serve para o e-mail.
    """
    # Fase 1: e-mail canônico e senha temporária (se não fornecida).
    chave = _norm_email(email)
    senha_texto = senha if senha is not None else gerar_senha_temporaria()
    # Fase 2: hash+salt e montagem do registro.
    hash_hex, salt = gerar_hash(senha_texto)
    registro = {
        "email": chave,                    # e-mail normalizado (também é a chave)
        "senha_hash": hash_hex,            # hash pbkdf2 (nunca a senha em texto)
        "salt": salt,                      # salt por usuário
        "precisa_trocar_senha": True,      # troca obrigatória no 1º acesso
        "ativo": True,                     # usuário habilitado
    }
    # Fase 3: carrega o store, insere/atualiza e grava atomicamente.
    dados = carregar_usuarios(caminho)
    dados[chave] = registro
    salvar_usuarios(dados, caminho)
    # Saída: registro + senha em texto (para o e-mail de credenciais).
    return registro, senha_texto


def desativar_usuario(email, caminho=None):
    """Marca um usuário como inativo (`ativo=False`).

    Entrada: `email` (str) e `caminho` (opcional).
    Fase 1: carrega o store e localiza o usuário.
    Fase 2: se existe, zera `ativo` e regrava.
    Saída: True se desativou; False se o usuário não existe.
    """
    # Fase 1: store + chave normalizada.
    dados = carregar_usuarios(caminho)
    chave = _norm_email(email)
    # Usuário inexistente → nada a fazer.
    if chave not in dados:
        return False
    # Fase 2: desativa e persiste.
    dados[chave]["ativo"] = False
    salvar_usuarios(dados, caminho)
    # Saída: desativado com sucesso.
    return True


def gerar_token(email, config=None):
    """Emite um token de sessão assinado (JWT HS256) para um e-mail.

    Por que existe: as rotas protegidas identificam o usuário pelo token (não por
    parâmetro), evitando falsificação de identidade (§5.2/§6).

    Entrada: `email` (str) e `config` (opcional; None usa a config do processo).
    Fase 1: resolve a config (segredo + TTL).
    Fase 2: monta o payload (`sub`=email, `exp`=agora+TTL).
    Fase 3: assina com HS256 e a SECRET_KEY.
    Saída: o token (str).
    """
    # Fase 1: config efetiva.
    cfg = config if config is not None else obter_config()
    # Fase 2: expiração relativa ao instante atual (UTC).
    agora = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": email,                                                   # dono do token
        "exp": agora + datetime.timedelta(seconds=cfg.token_ttl),       # expira em TTL s
    }
    # Fase 3/Saída: assina e devolve o token.
    return jwt.encode(payload, cfg.secret_key, algorithm="HS256")


def verificar_token(token, config=None):
    """Valida um token e devolve o e-mail (subject), ou None se inválido/expirado.

    Entrada: `token` (str) e `config` (opcional).
    Fase 1: resolve a config.
    Fase 2: decodifica/valida assinatura e expiração; erro → None.
    Saída: o e-mail (`sub`) ou None.
    """
    # Fase 1: config efetiva.
    cfg = config if config is not None else obter_config()
    # Fase 2: decodifica; qualquer problema (expirado/assinatura) → None.
    try:
        payload = jwt.decode(token, cfg.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        # Token inválido, expirado ou adulterado.
        return None
    # Saída: e-mail assinado no token.
    return payload.get("sub")


def autenticar(email, senha, caminho=None, config=None):
    """Valida credenciais e decide o desfecho do login (§5.2).

    Por que existe: concentra a regra de login (existe? ativo? senha confere? precisa
    trocar?) num único lugar testável; a rota HTTP é só uma casca fina sobre isso.

    Entrada: `email`, `senha`, `caminho` (store opcional), `config` (opcional).
    Fase 1: busca o usuário; inexistente ou inativo → não autenticado.
    Fase 2: senha não confere → não autenticado.
    Fase 3: precisa trocar senha → autenticado, mas SEM token (sinaliza a troca).
    Fase 4: caso normal → autenticado com token de sessão.
    Saída: dict — `{"autenticado": False}` | `{"autenticado": True, "precisaTrocarSenha": True}`
           | `{"autenticado": True, "token": <jwt>}`.
    """
    # Fase 1: usuário deve existir e estar ativo.
    usuario = obter_usuario(email, caminho)
    if usuario is None or not usuario.get("ativo"):
        return {"autenticado": False}
    # Fase 2: a senha precisa conferir com o hash+salt guardados.
    if not verificar_senha(senha, usuario["senha_hash"], usuario["salt"]):
        return {"autenticado": False}
    # Fase 3: senha certa, mas 1º acesso ⇒ troca obrigatória (sem token pleno).
    if usuario.get("precisa_trocar_senha"):
        return {"autenticado": True, "precisaTrocarSenha": True}
    # Fase 4/Saída: login pleno com token de sessão.
    return {"autenticado": True, "token": gerar_token(usuario["email"], config)}


def trocar_senha(email, senha_atual, nova_senha, caminho=None, config=None):
    """Troca a senha do usuário (valida a atual), zera a flag e emite token (B3, §5.2).

    Por que existe: no 1º acesso o usuário troca a senha temporária; validar a senha
    atual antes de gravar a nova evita troca por terceiros.

    Entrada: `email`, `senha_atual`, `nova_senha`, `caminho` (store), `config`.
    Fase 1: busca o usuário; inexistente/inativo → falha.
    Fase 2: valida a senha atual; não confere → falha (nada é alterado).
    Fase 3: grava o novo hash+salt, zera `precisa_trocar_senha` e persiste.
    Fase 4: emite token de sessão.
    Saída: `{"ok": False}` ou `{"ok": True, "token": <jwt>}`.
    """
    # Fase 1: usuário deve existir e estar ativo.
    usuario = obter_usuario(email, caminho)
    if usuario is None or not usuario.get("ativo"):
        return {"ok": False}
    # Fase 2: a senha atual precisa conferir (senão não muda nada).
    if not verificar_senha(senha_atual, usuario["senha_hash"], usuario["salt"]):
        return {"ok": False}
    # Fase 3: deriva a nova senha e atualiza o registro no store.
    novo_hash, salt = gerar_hash(nova_senha)
    dados = carregar_usuarios(caminho)
    chave = _norm_email(email)
    dados[chave]["senha_hash"] = novo_hash          # novo hash
    dados[chave]["salt"] = salt                     # novo salt
    dados[chave]["precisa_trocar_senha"] = False    # troca concluída
    salvar_usuarios(dados, caminho)
    # Fase 4/Saída: token de sessão após a troca.
    return {"ok": True, "token": gerar_token(chave, config)}


def resetar_senha(email, caminho=None):
    """Gera uma nova senha temporária para o usuário (self-service "esqueci senha", B4).

    Por que existe: o reset é self-service (§5.2); gera nova senha temporária, religa a
    flag de troca e devolve a senha em texto para a rota enviá-la por e-mail. Não revela
    ao chamador se o e-mail existia além do retorno (a rota responde genericamente).

    Entrada: `email` (str), `caminho` (store opcional).
    Fase 1: busca o usuário; inexistente/inativo → None.
    Fase 2: gera nova senha temporária, deriva hash+salt e religa `precisa_trocar_senha`.
    Fase 3: persiste.
    Saída: tupla `(email_canonico, senha_nova)` ou None.
    """
    # Fase 1: usuário deve existir e estar ativo.
    usuario = obter_usuario(email, caminho)
    if usuario is None or not usuario.get("ativo"):
        return None
    # Fase 2: nova senha temporária + hash; religa a flag de troca.
    nova = gerar_senha_temporaria()
    novo_hash, salt = gerar_hash(nova)
    dados = carregar_usuarios(caminho)
    chave = _norm_email(email)
    dados[chave]["senha_hash"] = novo_hash          # novo hash
    dados[chave]["salt"] = salt                     # novo salt
    dados[chave]["precisa_trocar_senha"] = True     # troca obrigatória de novo
    # Fase 3: persiste atomicamente.
    salvar_usuarios(dados, caminho)
    # Saída: e-mail canônico + nova senha (para o e-mail de credenciais).
    return chave, nova


class LimitadorReset:
    """Rate-limiter em memória do "esqueci senha", por e-mail (§5.2, risco de abuso).

    Por que existe: evita que alguém dispare resets em massa para um e-mail. Guarda os
    horários dos últimos resets por e-mail e bloqueia acima de `maximo` dentro de
    `janela_s`. O tempo é **injetado** (`agora`) para permitir testes determinísticos.
    """

    def __init__(self, maximo=3, janela_s=3600):
        """Configura o limite (máx. por janela).

        Entrada: `maximo` (nº de resets permitidos) e `janela_s` (janela em segundos).
        Fase 1: guarda os parâmetros e o histórico vazio.
        Saída: instância pronta.
        """
        # Fase 1: parâmetros do limite + histórico {email: [timestamps]}.
        self._maximo = maximo
        self._janela = janela_s
        self._historico = {}

    def permitido(self, email, agora):
        """Diz se um reset é permitido agora e registra a tentativa se for.

        Entrada: `email` (str) e `agora` (timestamp float, injetado).
        Fase 1: normaliza o e-mail e descarta registros fora da janela.
        Fase 2: se já atingiu o máximo na janela, bloqueia (mantém o histórico podado).
        Fase 3: senão, registra o horário atual e permite.
        Saída: True (permitido) ou False (bloqueado).
        """
        # Fase 1: chave normalizada + registros ainda dentro da janela.
        chave = email.strip().lower()
        recentes = [t for t in self._historico.get(chave, []) if agora - t < self._janela]
        # Fase 2: atingiu o teto ⇒ bloqueia (guarda o histórico podado).
        if len(recentes) >= self._maximo:
            self._historico[chave] = recentes
            return False
        # Fase 3/Saída: registra e permite.
        recentes.append(agora)
        self._historico[chave] = recentes
        return True
