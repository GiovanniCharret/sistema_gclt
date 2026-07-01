"""Envio de e-mail via SMTP (`smtplib`) — Bloco B1: e-mail de credenciais (§9).

Por que existe: o sistema envia e-mails transacionais; esta sub-fase (B1) implementa
o de **credenciais / senha temporária** ao próprio usuário (na criação pelo admin e,
adiante, no reset). O envio é 100% configurável via `.env` (host, porta, TLS, remetente)
e tem um modo **dry-run** para desenvolvimento/testes (não abre conexão real). Os
e-mails de planilha validada e alerta crítico entram no Bloco E, reusando `enviar`.

Design testável: a montagem da mensagem (`montar_email_credenciais`) é separada do
transporte (`enviar`), para testar conteúdo sem SMTP e transporte com SMTP mockado.
"""

# `smtplib` faz a conexão/entrega SMTP.
import smtplib
# `EmailMessage` monta a mensagem (cabeçalhos + corpo) de forma segura.
from email.message import EmailMessage

# Configuração (SMTP, remetente, dry-run) — default do processo se nenhuma for passada.
from backend.config import obter_config

# Assunto padrão do e-mail de credenciais (§9).
_ASSUNTO_CREDENCIAIS = "Acesso ao sistema — senha temporária"


def montar_email_credenciais(email, senha_temporaria, config=None):
    """Monta a mensagem de credenciais (senha temporária) ao usuário.

    Por que existe: separar a construção do conteúdo do transporte facilita testar o
    corpo/cabeçalhos sem tocar em SMTP.

    Entrada: `email` (destinatário), `senha_temporaria` (str), `config` (opcional).
    Fase 1: resolve a config (para o remetente).
    Fase 2: cria o EmailMessage e preenche From/To/Subject.
    Fase 3: escreve o corpo em PT com a senha e a instrução de troca no 1º acesso.
    Saída: o `EmailMessage` pronto para envio.
    """
    # Fase 1: config efetiva (remetente vem dela).
    cfg = config if config is not None else obter_config()
    # Fase 2: monta a mensagem e os cabeçalhos.
    msg = EmailMessage()
    msg["From"] = cfg.smtp_from                 # remetente configurado
    msg["To"] = email                           # usuário destinatário
    msg["Subject"] = _ASSUNTO_CREDENCIAIS       # assunto padrão
    # Fase 3: corpo objetivo, com a senha e a orientação de troca.
    msg.set_content(
        "Olá,\n\n"
        "Seu acesso ao sistema foi criado.\n"
        f"Senha temporária: {senha_temporaria}\n\n"
        "Por segurança, você deverá trocar esta senha no 1º acesso.\n\n"
        "Se não reconhece este acesso, ignore este e-mail."
    )
    # Saída: mensagem pronta.
    return msg


def enviar(msg, config=None):
    """Entrega uma mensagem via SMTP, respeitando o modo dry-run.

    Por que existe: único ponto de transporte (reusado por todos os tipos de e-mail);
    o dry-run permite rodar em dev/testes sem servidor real.

    Entrada: `msg` (EmailMessage) e `config` (opcional).
    Fase 1: resolve a config.
    Fase 2: em dry-run (ou sem host), NÃO abre conexão e retorna False (não enviado).
    Fase 3: senão, conecta, opcionalmente faz STARTTLS/login e envia a mensagem.
    Saída: True se enviou de verdade; False se foi dry-run.
    """
    # Fase 1: config efetiva.
    cfg = config if config is not None else obter_config()
    # Fase 2: dry-run ou sem host configurado ⇒ não envia (dev/testes).
    if cfg.smtp_dryrun or not cfg.smtp_host:
        # Não abre SMTP; sinaliza que nada foi entregue de fato.
        return False
    # Fase 3: conecta ao SMTP (context manager garante o quit).
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as sessao:
        # STARTTLS quando configurado (criptografa a sessão).
        if cfg.smtp_tls:
            sessao.starttls()
        # Login quando há credenciais.
        if cfg.smtp_user:
            sessao.login(cfg.smtp_user, cfg.smtp_pass)
        # Entrega a mensagem.
        sessao.send_message(msg)
    # Saída: enviado com sucesso.
    return True


def enviar_credenciais(email, senha_temporaria, config=None):
    """Monta e envia o e-mail de credenciais (senha temporária) ao usuário.

    Entrada: `email`, `senha_temporaria`, `config` (opcional).
    Fase 1: monta a mensagem de credenciais.
    Fase 2: entrega via `enviar` (respeita dry-run).
    Saída: o retorno de `enviar` (True enviado / False dry-run).
    """
    # Fase 1: mensagem de credenciais.
    msg = montar_email_credenciais(email, senha_temporaria, config)
    # Fase 2/Saída: transporte.
    return enviar(msg, config)
