# -*- coding: utf-8 -*-
"""Prova a credencial SMTP da ENBPAR antes de ela ir para produção.

Por que este arquivo existe: desde 29/09/2026, se o dry-run estiver desligado e o
e-mail não sair, `/api/validar` responde **502** — o operador deixa de receber a
mentira "Planilha enviada.", mas também fica impedido de concluir o envio. Ou
seja: virar `SMTP_DRYRUN=0` com uma credencial errada **bloqueia as sete
empresas**. Este script tira essa dúvida fora da produção, com o mesmo caminho
que o `email_envio.enviar` percorre: SMTP na 587 → STARTTLS → login → envio.

⚠️ Dois detalhes do Microsoft 365 que costumam ser a causa da falha, e que a
mensagem de erro aqui vai revelar:
  - **SMTP AUTH desativado** na caixa ou no tenant → erro 5.7.139
    ("basic authentication is disabled"); é liberação que a TI faz, não senha errada.
  - **Remetente sem permissão** → erro 5.7.60 ("cannot send as this user"): o
    `SMTP_FROM` precisa ser a própria caixa, ou ter "Send As" concedido.

⚠️ Este teste roda da SUA máquina. Ele prova a credencial, não prova que a VM da
Azure tem saída liberada na 587 — isso só o ambiente de produção responde.

Entrada: a senha da caixa, digitada no prompt (não fica no histórico).
Fase 1: pede a senha e monta uma mensagem mínima.
Fase 2: conecta, faz STARTTLS e autentica.
Fase 3: envia para o destinatário de teste e relata.
Saída: relatório no terminal; código de saída 1 se falhou.

Como rodar, da raiz deste repositório:
    uv run --no-project --python 3.12 python minhas_notas\testar_smtp_enbpar.py
"""

# `getpass` lê a senha sem ecoar; `smtplib` é o mesmo cliente que o backend usa.
import getpass
import smtplib
import sys
# `EmailMessage` monta a mensagem do mesmo jeito que o `email_envio`.
from email.message import EmailMessage

# --- dados informados pela TI em 29/09/2026 (não são segredo) ---
# Servidor do Microsoft 365.
HOST = "smtp.office365.com"
# Porta de submissão, com STARTTLS.
PORTA = 587
# Caixa de serviço que autentica.
USUARIO = "smtp@enbpar.gov.br"
# Remetente: no 365, o mais seguro é ser a própria caixa que autenticou.
REMETENTE = "smtp@enbpar.gov.br"


def main():
    """Conecta, autentica e envia uma mensagem de teste.

    Por que uma função só: o roteiro é linear e cada passo depende do anterior;
    separar em funções que apenas repassam a conexão não tornaria nada testável.

    Entrada: senha (prompt) e destinatário (prompt).
    Fase 1: coleta e monta a mensagem.
    Fase 2: conecta, STARTTLS, login.
    Fase 3: envia e relata.
    Saída: None (imprime; sai com 1 em falha).
    """

    # Fase 1: destinatário do teste — use o seu próprio endereço.
    destino = input("Enviar o teste para qual endereço? ").strip()
    # Senha da caixa de serviço; não aparece na tela nem no histórico.
    senha = getpass.getpass("Senha de %s (nao aparece na tela): " % USUARIO)

    # Mensagem mínima, só para provar o caminho.
    msg = EmailMessage()
    msg["Subject"] = "Teste de SMTP — sistema GCLT"
    msg["From"] = REMETENTE
    msg["To"] = destino
    msg.set_content(
        "Mensagem de teste do sistema GCLT.\n\n"
        "Se você recebeu isto, o relay da ENBPAR aceita a caixa de serviço e o\n"
        "envio da planilha validada pode ser ligado em producao (SMTP_DRYRUN=0)."
    )

    # Fase 2/3: conectar, cifrar, autenticar e entregar.
    print("\nConectando em %s:%s ..." % (HOST, PORTA))
    try:
        # `with` garante o QUIT mesmo se algo estourar no meio.
        with smtplib.SMTP(HOST, PORTA, timeout=30) as sessao:
            # STARTTLS: obrigatório no 365; sem isso o login é recusado.
            sessao.starttls()
            print("  STARTTLS ok — autenticando ...")
            # O login é o passo que revela SMTP AUTH desativado (5.7.139).
            sessao.login(USUARIO, senha)
            print("  login ok — enviando ...")
            # Envio: aqui aparece a falta de permissão de remetente (5.7.60).
            sessao.send_message(msg)
    # Erro de autenticação: credencial ou política do tenant.
    except smtplib.SMTPAuthenticationError as erro:
        print("\n[FALHOU NO LOGIN] %s" % erro)
        print("  5.7.139 => SMTP AUTH desativado para a caixa/tenant: e liberacao da TI.")
        print("  5.7.3 ou 535 genérico => usuario ou senha incorretos.")
        sys.exit(1)
    # Qualquer outra falha do protocolo ou da rede.
    except Exception as erro:
        print("\n[FALHOU] %s: %s" % (type(erro).__name__, erro))
        print("  5.7.60 => a caixa nao pode enviar como '%s' (permissao Send As)." % REMETENTE)
        print("  timeout/conexao recusada => saida na porta %s bloqueada nesta rede." % PORTA)
        sys.exit(1)

    # Saída: sucesso, com o que isso prova e o que ainda não prova.
    print("\nENVIADO. Confira a caixa de %s." % destino)
    print("Isto prova a credencial e a politica do 365.")
    print("Ainda NAO prova que a VM da Azure tem saida liberada na 587 —")
    print("isso so o primeiro envio em producao responde.")


# Executa só quando chamado como script.
if __name__ == "__main__":
    main()
