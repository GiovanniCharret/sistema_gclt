"""Configuração do backend lida do `.env` (pydantic-settings) — Bloco B1+.

Por que existe: SMTP, remetente e modo dry-run (e, adiante, chaves de token e listas
de destinatários) não devem ser hardcoded — vêm do ambiente/`.env` (§9, §12). Esta
classe centraliza a leitura tipada, com **defaults seguros para desenvolvimento/testes**
(dry-run ligado, nada é enviado de verdade) para a suíte não depender de um `.env` real.

Cada campo mapeia para uma variável de ambiente de mesmo nome em maiúsculas
(ex.: `smtp_host` ← `SMTP_HOST`), documentada em `backend/.env.example`.
"""

# Base tipada que lê variáveis de ambiente e arquivos `.env`.
# `io`/`json`/`pathlib`: leitura do JSON de parametros (ver o fim do arquivo).
import io
import json
import pathlib

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Configurações do backend (SMTP e envio); ampliada nas próximas sub-fases."""

    # Diz ao pydantic-settings para ler `backend/.env` (se existir) e ignorar chaves
    # extras (ex.: SECRET_KEY, que só será usada na B2) sem quebrar.
    model_config = SettingsConfigDict(
        env_file="backend/.env",      # arquivo lido em dev (fora do git)
        env_file_encoding="utf-8",    # encoding do .env
        extra="ignore",               # ignora variáveis ainda não modeladas
    )

    # --- Token de sessão / store de usuários (§5.2, Bloco B) ---
    # Chave secreta para assinar o token JWT (troque em produção via .env).
    # ≥32 bytes: abaixo disso o PyJWT alerta (RFC 7518) e a chave fica fraca.
    secret_key: str = "dev-inseguro-troque-em-producao-com-uma-chave-longa"
    # Tempo de vida do token de sessão, em segundos (28800 = 8h).
    token_ttl: int = 28800
    # Caminho do store de usuários (segredo; default ao lado do backend).
    usuarios_path: str = "backend/parametros/usuarios.json"

    # --- SMTP / envio de e-mail (§9) ---
    # Host do servidor SMTP (vazio = sem servidor ⇒ dry-run efetivo).
    smtp_host: str = ""
    # Porta SMTP (587 = STARTTLS por padrão).
    smtp_port: int = 587
    # Credenciais de autenticação no SMTP (vazias = sem login).
    smtp_user: str = ""
    smtp_pass: str = ""
    # Remetente exibido nos e-mails.
    smtp_from: str = "nao-responder@exemplo.com.br"
    # Usar STARTTLS ao conectar.
    smtp_tls: bool = True
    # Dry-run: não envia de verdade (padrão em dev/testes), só registraria o envio.
    smtp_dryrun: bool = True
    # Lista única e global de destinatários da planilha validada (separados por vírgula).
    destinatarios: str = ""
    # E-mail do administrador que recebe os alertas críticos (§8).
    alerta_email: str = ""

    # --- ODI+UC "dado novo" como aviso (criada em 2026-09-16; REGRA desde 2026-09-22) ---
    # Nasceu como workaround: o SQL do sistema legado que alimenta `entrada/` parou, e UCs
    # recém-energizadas ("dado novo") não chegavam à base — a regra "ODI + UC não consta
    # na referência" travaria o envio. Com True, esse dado novo vira AVISO — mas só pela
    # regra ESTRITA de `regras_cruzamento`: a base do contrato não pode estar vazia e
    # TODAS as UCs já cadastradas precisam estar na planilha. Nenhuma outra regra muda.
    # REGRA (padrão): True. SEGUNDO CAMINHO: False — todo ODI+UC fora da base volta a ser
    # erro, como antes de 2026-09-16; só por decisão explícita. É lida uma vez por
    # processo (singleton): mudar exige reiniciar o backend. Pode ser sobrescrita pela
    # variável de ambiente ODI_UC_NOVO_COMO_AVISO (ex.: no `backend/.env`).
    odi_uc_novo_como_aviso: bool = True


# Singleton de configuração (carregado uma vez por processo).
_config_singleton = None


def obter_config():
    """Devolve a configuração única do processo (cache).

    Entrada: nenhuma.
    Fase 1: instancia a Config na 1ª chamada (lê env/.env); depois reaproveita.
    Saída: a instância de `Config`.
    """
    # Permite reatribuir a variável de módulo.
    global _config_singleton
    # Fase 1: cria sob demanda e memoiza.
    if _config_singleton is None:
        _config_singleton = Config()
    # Saída: config compartilhada.
    return _config_singleton


# ---------------------------------------------------------------------------
# Parametros de e-mail: o JSON e a fonte primaria; o `.env` e so a reserva.
#
# ** OS DADOS PRIMARIOS DE E-MAIL VIVEM EM `backend/parametros/email.json` **,
# e nao mais no `.env` (decisao de 29/09/2026). O motivo e operacional: servidor,
# porta, remetente e a lista de destinatarios sao DADOS DE NEGOCIO, mudam com
# frequencia e nao sao segredo — mas, morando no `.env`, trocar um destinatario
# exigia abrir o mesmo arquivo que guarda `SMTP_PASS` e `SECRET_KEY`, e fazer um
# deploy. No `.env` fica estritamente o que nao pode vazar.
#
# As chaves antigas do `.env` seguem sendo lidas como RESERVA, para a transicao
# nao quebrar nada e para os testes que nao tem o JSON continuarem validos.
# ---------------------------------------------------------------------------

# Caminho do JSON, relativo a raiz do repositorio (e de la que o processo roda).
CAMINHO_PARAMETROS_EMAIL = "backend/parametros/email.json"

# Cache por mtime: editar o arquivo vale na requisicao seguinte, sem reiniciar o
# processo — mesma ideia que o `referencia.py` usa com o `entrada/`.
_cache_parametros_email = {"mtime": None, "dados": {}}


class ParametrosEmail:
    """Visao unica dos parametros de e-mail, com o JSON por cima do `.env`.

    Por que uma classe em vez de um dicionario: o `email_envio.py` ja le
    `cfg.smtp_host`, `cfg.destinatarios` e companhia. Expondo os MESMOS nomes de
    atributo, trocar a fonte de dados nao derrama mudanca por aquele modulo — e um
    teste que injeta uma config falsa continua funcionando igual.

    Entrada: `config` (a `Config` do `.env`) e `dados` (o dicionario do JSON).
    Fase 1: comeca com tudo o que veio do `.env`.
    Fase 2: sobrescreve com o que o JSON trouxer — chave ausente mantem o `.env`.
    Fase 3: anota a origem, para o `/api/health` poder dizer de onde veio.
    Saida: objeto com os atributos que o `email_envio` espera.
    """

    def __init__(self, config, dados):
        # Fase 1: bloco `smtp` do JSON (ausente => tudo vem do `.env`).
        smtp = dados.get("smtp") or {}
        # Servidor: sem ele, `enviar` devolve False sem nem abrir conexao.
        self.smtp_host = smtp.get("host", config.smtp_host)
        # Porta de submissao (587 com STARTTLS, no caso do Microsoft 365).
        self.smtp_port = int(smtp.get("porta", config.smtp_port))
        # STARTTLS ligado/desligado.
        self.smtp_tls = bool(smtp.get("tls", config.smtp_tls))
        # Usuario que autentica no servidor.
        self.smtp_user = smtp.get("usuario", config.smtp_user)
        # Remetente exibido; no 365 costuma ter de ser a propria caixa que autentica.
        self.smtp_from = smtp.get("remetente", config.smtp_from)
        # ** A SENHA NAO VEM DO JSON, nunca **: e segredo, e fica so no `.env`.
        self.smtp_pass = config.smtp_pass
        # Dry-run: True = nao envia nada (dev/teste); em producao e defeito.
        self.smtp_dryrun = bool(smtp.get("dryrun", config.smtp_dryrun))
        # Fase 2: destinatarios — o JSON traz lista; o `.env` trazia string com virgulas.
        lista = dados.get("destinatarios")
        # Normaliza para a MESMA string que o `_destinatarios` ja sabe dividir.
        self.destinatarios = (",".join(str(d).strip() for d in lista if str(d).strip())
                              if isinstance(lista, list) else config.destinatarios)
        # Endereco que recebe o alerta critico (contrato sem referencia).
        self.alerta_email = dados.get("alerta", config.alerta_email)
        # Fase 3/Saida: origem, so para diagnostico pelo navegador.
        self.origem = "json" if dados else "env"


def ler_parametros_email(caminho=None):
    """Le o JSON de parametros, recarregando quando o arquivo muda.

    Por que separada: isola o I/O e o cache, para `obter_parametros_email` ser so a
    mescla — e para o teste poder apontar para um arquivo temporario.

    ** Falha fechada e silenciosa **: arquivo ausente ou ilegivel devolve `{}`, e a
    configuracao inteira cai para o `.env`. E deliberado — um JSON quebrado nao pode
    derrubar o envio nem a subida do processo.

    Entrada: `caminho` (str/Path; None usa o padrao do repositorio).
    Fase 1: sem arquivo, devolve vazio.
    Fase 2: rele so se o mtime mudou desde a ultima leitura.
    Saida: dicionario do JSON (possivelmente vazio).
    """
    # Fase 1: resolve o caminho e desiste se nao houver arquivo.
    alvo = pathlib.Path(caminho or CAMINHO_PARAMETROS_EMAIL)
    if not alvo.is_file():
        return {}
    # Fase 2: mtime como carimbo; igual ao anterior, devolve o que esta em memoria.
    try:
        marca = (str(alvo), alvo.stat().st_mtime)
    except OSError:
        return {}
    if _cache_parametros_email["mtime"] == marca:
        return _cache_parametros_email["dados"]
    # Releitura: JSON invalido nao pode estourar na cara de quem so queria enviar.
    try:
        with io.open(alvo, encoding="utf-8") as arq:
            dados = json.load(arq)
    except (ValueError, OSError):
        return {}
    # Guarda o resultado com o carimbo novo.
    _cache_parametros_email["mtime"] = marca
    _cache_parametros_email["dados"] = dados if isinstance(dados, dict) else {}
    # Saida: o dicionario lido.
    return _cache_parametros_email["dados"]


def obter_parametros_email(config=None, caminho=None):
    """Devolve os parametros de e-mail em vigor (JSON por cima do `.env`).

    Por que existe: e o ponto unico onde as duas fontes se encontram, para o
    `email_envio.py` e o `/api/health` enxergarem exatamente a mesma coisa.

    ** Config passada explicitamente vence, e o JSON e ignorado **: e assim que os
    testes injetam uma configuracao falsa sem que um arquivo no disco interfira.

    Entrada: `config` (opcional) e `caminho` (opcional, para teste).
    Fase 1: injecao explicita curto-circuita tudo.
    Fase 2: mescla o JSON sobre a config do processo.
    Saida: `ParametrosEmail`, ou a propria `config` recebida.
    """
    # Fase 1: quem passou config quer aquela config, e nada mais.
    if config is not None:
        return config
    # Fase 2/Saida: `.env` do processo com o JSON por cima.
    return ParametrosEmail(obter_config(), ler_parametros_email(caminho))
