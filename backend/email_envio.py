"""Envio de e-mail via SMTP (`smtplib`) — Bloco B1: e-mail de credenciais (§9).

Por que existe: o sistema envia e-mails transacionais; esta sub-fase (B1) implementa
o de **credenciais / senha temporária** ao próprio usuário (na criação pelo admin e,
adiante, no reset). O envio é 100% configurável via `.env` (host, porta, TLS, remetente)
e tem um modo **dry-run** para desenvolvimento/testes (não abre conexão real). Os
e-mails de planilha validada e alerta crítico entram no Bloco E, reusando `enviar`.

Design testável: a montagem da mensagem (`montar_email_credenciais`) é separada do
transporte (`enviar`), para testar conteúdo sem SMTP e transporte com SMTP mockado.
"""

# `datetime` compõe a data do assunto do e-mail da planilha.
import datetime
# `smtplib` faz a conexão/entrega SMTP.
import smtplib
# `EmailMessage` monta a mensagem (cabeçalhos + corpo) de forma segura.
from email.message import EmailMessage

# Configuração (SMTP, remetente, dry-run) — default do processo se nenhuma for passada.
from backend.config import obter_config

# Assunto padrão do e-mail de credenciais (§9).
_ASSUNTO_CREDENCIAIS = "Acesso ao sistema — senha temporária"
# Subtype MIME do .xlsx (planilha do Office Open XML).
_XLSX_SUBTYPE = "vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _destinatarios(cfg):
    """Lista de destinatários a partir da string `DESTINATARIOS` (separada por vírgula)."""
    # Divide por vírgula, tira espaços e descarta vazios.
    return [d.strip() for d in cfg.destinatarios.split(",") if d.strip()]


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


def montar_email_planilha(arquivo, contrato, uf, config=None):
    """Monta o e-mail com a planilha validada anexada **byte a byte** (E1, §9).

    Por que existe: quando a validação passa (0 erros), o backend envia o próprio `.xlsx`
    recebido — sem reescrever — aos destinatários configurados.

    Entrada: `arquivo` (bytes do .xlsx como veio), `contrato` (número), `uf` (sigla),
             `config` (opcional).
    Fase 1: resolve a config e a data de hoje.
    Fase 2: monta From/To (destinatários)/Subject e um corpo curto.
    Fase 3: anexa o arquivo com o nome `Anexo V preenchido - {contrato}.xlsx` (`/`→`-`).
    Saída: o `EmailMessage`.
    """
    # Fase 1: config + data de hoje (DD/MM/AAAA) para o assunto.
    cfg = config if config is not None else obter_config()
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    # Fase 2: cabeçalhos e corpo.
    msg = EmailMessage()
    msg["From"] = cfg.smtp_from
    msg["To"] = ", ".join(_destinatarios(cfg))              # lista única global
    msg["Subject"] = f"Anexo V validado — {contrato} ({uf}) — {hoje}"
    msg.set_content(
        f"Segue em anexo o Anexo V validado do contrato {contrato} ({uf}).\n\n"
        "Enviado automaticamente pelo sistema após a validação sem erros."
    )
    # Fase 3: anexo com nome de arquivo válido (`/` do número vira `-`).
    nome_anexo = f"Anexo V preenchido - {contrato.replace('/', '-')}.xlsx"
    msg.add_attachment(arquivo, maintype="application", subtype=_XLSX_SUBTYPE, filename=nome_anexo)
    # Saída: mensagem pronta.
    return msg


def enviar_planilha_validada(arquivo, contrato, uf, config=None):
    """Monta e envia o e-mail da planilha validada (respeita dry-run).

    Saída: True se enviou; False em dry-run.
    """
    # Monta e transporta.
    cfg = config if config is not None else obter_config()
    return enviar(montar_email_planilha(arquivo, contrato, uf, cfg), cfg)


def montar_email_alerta(contrato, uf, nome_arquivo, config=None):
    """Monta o e-mail de **alerta crítico** ao admin (contrato sem referência, §8).

    Entrada: `contrato`, `uf`, `nome_arquivo` (arquivo enviado), `config` (opcional).
    Fase 1: resolve a config.
    Fase 2: monta a mensagem ao `ALERTA_EMAIL` com contexto técnico.
    Saída: o `EmailMessage`.
    """
    # Fase 1: config efetiva.
    cfg = config if config is not None else obter_config()
    # Fase 2: mensagem de alerta.
    msg = EmailMessage()
    msg["From"] = cfg.smtp_from
    msg["To"] = cfg.alerta_email
    msg["Subject"] = f"[ALERTA] Contrato sem referência — {contrato}"
    msg.set_content(
        "Anomalia na validação do Anexo V.\n\n"
        f"Contrato sem referência em entrada/: {contrato} ({uf}).\n"
        f"Arquivo enviado: {nome_arquivo}.\n\n"
        "No fluxo normal todo contrato tem ODI+UC. Investigar a base de referência."
    )
    # Saída: mensagem pronta.
    return msg


def enviar_alerta_critico(contrato, uf, nome_arquivo, config=None):
    """Monta e envia o alerta crítico ao admin (respeita dry-run).

    Saída: True se enviou; False em dry-run.
    """
    # Monta e transporta.
    cfg = config if config is not None else obter_config()
    return enviar(montar_email_alerta(contrato, uf, nome_arquivo, cfg), cfg)
