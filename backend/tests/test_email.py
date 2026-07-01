"""Testes de envio de e-mail (`backend/email_envio.py`) — Bloco B1 (e-mail de credenciais).

Por que existe: a §9 da spec define o e-mail de **credenciais / senha temporária** ao
próprio usuário (na criação e no reset). Nesta sub-fase (B1) cobrimos: a montagem da
mensagem (destinatário, assunto, corpo com a senha) e o transporte com **SMTP mockado**
mais o modo **dry-run** (dev, sem servidor real). Os demais e-mails (planilha validada,
alerta crítico) entram no Bloco E.
"""

# `unittest.mock.patch` substitui `smtplib.SMTP` para não enviar de verdade.
from unittest.mock import patch

# Config injetável (evita depender de `.env` real nos testes).
from backend.config import Config
# Funções sob teste.
from backend.email_envio import montar_email_credenciais, enviar, enviar_credenciais


def _config_smtp_real():
    """Config apontando para um SMTP fictício, com dry-run DESLIGADO.

    Entrada: nenhuma.
    Fase 1: monta uma Config com host fictício e `smtp_dryrun=False`.
    Saída: a Config (o SMTP em si é mockado no teste).
    """
    # Fase 1/Saída: força envio "real" (mockado) com remetente conhecido.
    return Config(smtp_host="smtp.teste", smtp_port=587, smtp_from="nao-responder@teste",
                  smtp_tls=False, smtp_dryrun=False)


def test_montar_email_credenciais_tem_destino_assunto_e_senha():
    """A mensagem de credenciais leva destinatário, assunto e a senha no corpo.

    Entrada: e-mail do usuário e uma senha temporária.
    Fase 1: monta a mensagem com uma Config de teste.
    Fase 2: confere From/To/Subject e que o corpo contém a senha e a instrução de troca.
    Saída: asserções.
    """
    # Fase 1: monta o EmailMessage.
    msg = montar_email_credenciais("usuario@equatorialenergia.com.br", "SENHA-TMP-123",
                                   config=_config_smtp_real())
    # Fase 2: remetente/destinatário/assunto corretos.
    assert msg["To"] == "usuario@equatorialenergia.com.br"
    assert msg["From"] == "nao-responder@teste"
    assert "senha temporária" in msg["Subject"].lower()
    # Corpo contém a senha e orienta a troca no 1º acesso.
    corpo = msg.get_content()
    assert "SENHA-TMP-123" in corpo
    assert ("trocar" in corpo.lower()) or ("1º acesso" in corpo.lower())


def test_enviar_dry_run_nao_abre_smtp():
    """Em dry-run, `enviar` NÃO abre conexão SMTP e sinaliza que não enviou.

    Entrada: uma Config com `smtp_dryrun=True`.
    Fase 1: monta uma mensagem qualquer.
    Fase 2: chama `enviar` com o SMTP mockado.
    Fase 3: o SMTP não é instanciado e o retorno é False (não enviado de verdade).
    Saída: asserções.
    """
    # Config em dry-run (padrão de dev).
    cfg = Config(smtp_dryrun=True, smtp_from="x@y")
    # Fase 1: mensagem mínima.
    msg = montar_email_credenciais("a@b.com", "TMP", config=cfg)
    # Fase 2: patch do SMTP para provar que não é chamado.
    with patch("backend.email_envio.smtplib.SMTP") as mock_smtp:
        enviado = enviar(msg, config=cfg)
    # Fase 3: nada de SMTP; retorno False.
    assert mock_smtp.called is False
    assert enviado is False


def test_enviar_credenciais_dispara_smtp_mock():
    """`enviar_credenciais` (fora do dry-run) manda a mensagem via SMTP (mockado).

    Entrada: e-mail do usuário + senha; Config com dry-run desligado.
    Fase 1: patch de `smtplib.SMTP`.
    Fase 2: chama `enviar_credenciais`.
    Fase 3: o SMTP foi usado, `send_message` recebeu a mensagem ao usuário (com a
            senha no corpo), e o retorno é True.
    Saída: asserções.
    """
    # Fase 1: intercepta o SMTP.
    with patch("backend.email_envio.smtplib.SMTP") as mock_smtp:
        # Sessão SMTP retornada pelo context manager `with ... as s`.
        sessao = mock_smtp.return_value.__enter__.return_value
        # Fase 2: envia as credenciais.
        enviado = enviar_credenciais("op@energisa.com.br", "TMP-XYZ",
                                     config=_config_smtp_real())
    # Fase 3: SMTP instanciado e mensagem enviada.
    assert mock_smtp.called is True
    assert sessao.send_message.called is True
    # A mensagem enviada é para o usuário e contém a senha.
    msg_enviada = sessao.send_message.call_args.args[0]
    assert msg_enviada["To"] == "op@energisa.com.br"
    assert "TMP-XYZ" in msg_enviada.get_content()
    # Retorno indica envio bem-sucedido.
    assert enviado is True
