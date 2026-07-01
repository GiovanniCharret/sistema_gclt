"""Configuração do backend lida do `.env` (pydantic-settings) — Bloco B1+.

Por que existe: SMTP, remetente e modo dry-run (e, adiante, chaves de token e listas
de destinatários) não devem ser hardcoded — vêm do ambiente/`.env` (§9, §12). Esta
classe centraliza a leitura tipada, com **defaults seguros para desenvolvimento/testes**
(dry-run ligado, nada é enviado de verdade) para a suíte não depender de um `.env` real.

Cada campo mapeia para uma variável de ambiente de mesmo nome em maiúsculas
(ex.: `smtp_host` ← `SMTP_HOST`), documentada em `backend/.env.example`.
"""

# Base tipada que lê variáveis de ambiente e arquivos `.env`.
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
    usuarios_path: str = "backend/usuarios.json"

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
