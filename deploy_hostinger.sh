#!/usr/bin/env bash
#
# Deploy automatizado no VPS Hostinger (Ubuntu) — Classificação de Beneficiários.
# Sobe a fatia de autenticação: front (modelo/dist) + backend FastAPI atrás do Nginx
# em /api, com serviço systemd e (opcional) HTTPS via certbot.
#
# COMO USAR (no servidor, como root):
#   curl -fsSL https://raw.githubusercontent.com/GiovanniCharret/sistema_gclt_demo/main/deploy_hostinger.sh -o deploy.sh
#   sudo DOMINIO=seu-dominio.com.br ADMIN_EMAIL=voce@exemplo.com bash deploy.sh
#
# Requisitos: Ubuntu 22.04/24.04, acesso root, e o DNS do domínio já apontando para o IP
# do VPS (registro A). O script é idempotente — pode ser rodado de novo para atualizar.
#
set -euo pipefail

# ── Configuração (via variáveis de ambiente; ou edite os defaults abaixo) ──
DOMINIO="${DOMINIO:-}"                        # obrigatório: seu domínio/subdomínio
ADMIN_EMAIL="${ADMIN_EMAIL:-}"                # e-mail do certbot (se vazio, pula o HTTPS)
APP_DIR="${APP_DIR:-/opt/anexov}"             # onde o projeto é instalado
APP_USER="${APP_USER:-deploy}"               # usuário que roda o serviço (não-root)
REPO_URL="${REPO_URL:-https://github.com/GiovanniCharret/sistema_gclt_demo.git}"
SERVICO="anexov-api"                          # nome do serviço systemd

# ── Pré-checagens ──
[ "$(id -u)" -eq 0 ] || { echo "ERRO: rode como root (sudo)."; exit 1; }
[ -n "$DOMINIO" ] || { echo "ERRO: defina DOMINIO=seu-dominio.com.br"; exit 1; }

echo ">> [1/9] Pacotes base"
apt-get update -y
apt-get install -y git nginx curl ufw ca-certificates

echo ">> [2/9] Firewall (SSH + Nginx)"
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 'Nginx Full' >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true

echo ">> [3/9] Usuário de aplicação ($APP_USER)"
id "$APP_USER" &>/dev/null || adduser --disabled-password --gecos "" "$APP_USER"

echo ">> [4/9] Código em $APP_DIR"
mkdir -p "$APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  # Já é um clone — só atualiza (preserva backend/.env e usuarios.json, que são untracked).
  git -C "$APP_DIR" pull --ff-only
else
  # Garante a pasta vazia (resolve o caso de subpasta criada por clone sem ".") e clona.
  find "$APP_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  git clone "$REPO_URL" "$APP_DIR"
fi

echo ">> [5/9] Python: uv + venv + dependências"
export HOME=/root
command -v uv &>/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
cd "$APP_DIR"
uv venv
uv pip install -r backend/requirements.txt

echo ">> [6/9] backend/.env"
if [ ! -f backend/.env ]; then
  # Gera uma SECRET_KEY forte só na primeira vez (preserva em re-execuções).
  SECRET="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cat > backend/.env <<EOF
SECRET_KEY=$SECRET
TOKEN_TTL=28800
# E-mail em dry-run (não envia). Para enviar a senha temporária de verdade,
# preencha o SMTP abaixo e troque SMTP_DRYRUN para 0.
SMTP_DRYRUN=1
# SMTP_HOST=smtp.seu-provedor.com
# SMTP_PORT=587
# SMTP_USER=usuario
# SMTP_PASS=senha
# SMTP_FROM=nao-responder@$DOMINIO
# SMTP_TLS=1
EOF
  echo "   backend/.env criado (SECRET_KEY gerada, SMTP em dry-run)."
else
  echo "   backend/.env já existe — preservado."
fi

echo ">> [7/9] Front: Node 20 + build (modelo/dist)"
if ! command -v node &>/dev/null || [ "$(node -v | sed 's/v//' | cut -d. -f1)" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
cd "$APP_DIR/modelo"
npm install
npm run build
cd "$APP_DIR"

echo ">> [8/9] Permissões + serviço systemd ($SERVICO)"
# O serviço (e o usuarios.json que ele grava) pertence ao usuário de aplicação.
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
cat > /etc/systemd/system/$SERVICO.service <<EOF
[Unit]
Description=Anexo V API (FastAPI/uvicorn)
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now $SERVICO
sleep 2
systemctl restart $SERVICO
sleep 2
curl -s http://127.0.0.1:8000/api/health >/dev/null \
  && echo "   backend OK (/api/health respondeu)." \
  || echo "   AVISO: /api/health não respondeu — veja: journalctl -u $SERVICO -e"

echo ">> [9/9] Nginx (front + proxy /api)"
cat > /etc/nginx/sites-available/anexov <<EOF
server {
    listen 80;
    server_name $DOMINIO;
    root $APP_DIR/modelo/dist;
    index index.html;
    location / { try_files \$uri \$uri/ /index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 50m;
    }
}
EOF
ln -sf /etc/nginx/sites-available/anexov /etc/nginx/sites-enabled/anexov
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ── HTTPS (opcional, automático se ADMIN_EMAIL foi informado) ──
if [ -n "$ADMIN_EMAIL" ]; then
  echo ">> HTTPS: certbot (Let's Encrypt)"
  apt-get install -y certbot python3-certbot-nginx
  certbot --nginx -d "$DOMINIO" --non-interactive --agree-tos -m "$ADMIN_EMAIL" --redirect \
    || echo "   certbot falhou (o DNS já aponta p/ este IP?). Rode depois: certbot --nginx -d $DOMINIO"
fi

# ── Resumo + próximo passo ──
echo
echo "==================================================================="
echo " Deploy base concluído."
echo "   Serviço:  systemctl status $SERVICO"
echo "   Logs:     journalctl -u $SERVICO -f"
echo "   Health:   curl http://127.0.0.1:8000/api/health"
echo "   Site:     http://$DOMINIO  (https após o certbot)"
echo
echo " Falta criar o 1º usuário (rode a partir de $APP_DIR, como $APP_USER):"
echo "   cd $APP_DIR"
echo "   # com SMTP configurado (envia a senha por e-mail):"
echo "   sudo -u $APP_USER .venv/bin/python -m backend.admin_usuarios add fulano@distribuidora.com.br"
echo "   # em dry-run (cria com senha conhecida p/ testar login):"
echo "   sudo -u $APP_USER .venv/bin/python -c \"from backend.auth import criar_usuario; criar_usuario('fulano@distribuidora.com.br', senha='Temp123')\""
echo "==================================================================="
