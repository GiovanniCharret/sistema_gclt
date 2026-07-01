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
from backend.email_envio import (
    montar_email_credenciais, enviar, enviar_credenciais,
    montar_email_planilha, enviar_planilha_validada,
    montar_email_alerta, enviar_alerta_critico,
)


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


# ── E1 · E-mail da planilha validada + alerta crítico ──

def _config_com_destinatarios():
    """Config de envio (dry-run off) com destinatários e e-mail de alerta."""
    return Config(smtp_host="smtp.teste", smtp_port=587, smtp_from="nao-responder@teste",
                  smtp_tls=False, smtp_dryrun=False,
                  destinatarios="dest1@mme.gov.br, dest2@enbpar.gov.br",
                  alerta_email="admin@enbpar.gov.br")


def test_montar_email_planilha_anexo_nomeado_e_intacto():
    """A planilha validada é anexada byte a byte, com o nome e destinos corretos.

    Fase 1: monta o e-mail com um conteúdo .xlsx fake e contrato com "/".
    Fase 2: To = destinatários; assunto tem o contrato/UF; anexo nomeado
            `Anexo V preenchido - {contrato com / → -}.xlsx` e conteúdo idêntico.
    """
    # Fase 1: monta a mensagem.
    conteudo = b"CONTEUDO-XLSX-BYTES"
    msg = montar_email_planilha(conteudo, "ECM 018/2025", "PA", config=_config_com_destinatarios())
    # Fase 2: destinatários no To e contrato no assunto.
    assert "dest1@mme.gov.br" in msg["To"] and "dest2@enbpar.gov.br" in msg["To"]
    assert "ECM 018/2025" in msg["Subject"]
    # Anexo: nome com "/"→"-" e bytes intactos.
    anexos = list(msg.iter_attachments())
    assert len(anexos) == 1
    assert anexos[0].get_filename() == "Anexo V preenchido - ECM 018-2025.xlsx"
    assert anexos[0].get_payload(decode=True) == conteudo


def test_enviar_planilha_validada_dispara_smtp_mock():
    """`enviar_planilha_validada` (fora do dry-run) envia via SMTP mockado."""
    # Intercepta o SMTP e envia.
    with patch("backend.email_envio.smtplib.SMTP") as mock_smtp:
        sessao = mock_smtp.return_value.__enter__.return_value
        enviado = enviar_planilha_validada(b"XLSX", "ECM 018/2025", "PA",
                                           config=_config_com_destinatarios())
    # SMTP usado e mensagem enviada.
    assert mock_smtp.called is True
    assert sessao.send_message.called is True
    assert enviado is True


def test_montar_email_alerta_critico_para_admin():
    """O alerta crítico vai ao ALERTA_EMAIL, com assunto de alerta e contrato no corpo."""
    # Monta o alerta.
    msg = montar_email_alerta("ECM 999/2030", "AM", "Anexo V - ...xlsx",
                              config=_config_com_destinatarios())
    # Destino e assunto de alerta.
    assert msg["To"] == "admin@enbpar.gov.br"
    assert "[ALERTA]" in msg["Subject"]
    assert "ECM 999/2030" in msg["Subject"] or "ECM 999/2030" in msg.get_content()
