# Deploy — Site mock "Classificação de Beneficiários do Programa"

Guia para hospedar este projeto numa **VPS Hostinger** (Ubuntu) e publicar via
**Nginx**.

## Visão geral

- O **front** é um **SPA estático** (Vite + React) na pasta **`modelo/`**; o build gera
  **`modelo/dist/`**, que o Nginx entrega. Requisito: **Node.js 20.19+ ou 22.x** (Vite 7).
- O **backend** (planejado/aprovado — ver
  `planning/specs/2026-06-26-backend-validacao-envio-anexo-v-design.md`) é uma **API
  FastAPI** em **`backend/`**, servida por **uvicorn** atrás do mesmo Nginx em **`/api`**.
  Faz validação real da planilha contra `entrada/`, autenticação (login/senha) e envio do
  Anexo V por e-mail. Requisito: **Python 3.12+**.
- Enquanto o backend não está no ar, o front roda como mock estático (seção do backend
  abaixo só se aplica depois de implementado).

---

## Opção A — Build na própria VPS + Nginx (recomendado)

### 1. Conectar via SSH
```bash
ssh root@SEU_IP_DA_VPS
```

### 2. Atualizar o sistema e instalar Node.js 22 LTS + Git
```bash
apt update && apt upgrade -y
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs git
node -v && npm -v        # confirme: node v22.x, npm 10+
```

### 3. Clonar o repositório do GitHub
```bash
mkdir -p /var/www && cd /var/www
git clone https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git site-lpt
cd site-lpt/modelo
```

### 4. Instalar dependências e gerar o build
```bash
npm install
npm run build            # gera modelo/dist/
```

### 5. Instalar e configurar o Nginx
```bash
apt install -y nginx
```

Crie o arquivo `/etc/nginx/sites-available/site-lpt`:
```nginx
server {
    listen 80;
    server_name SEU_DOMINIO_OU_IP;

    root /var/www/site-lpt/modelo/dist;
    index index.html;

    # SPA: qualquer rota cai no index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # cache dos assets versionados pelo Vite
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

Ative o site e recarregue:
```bash
ln -s /etc/nginx/sites-available/site-lpt /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default   # remove o site padrão (opcional)
nginx -t                                  # testa a configuração
systemctl reload nginx
```

### 6. Liberar o firewall (se o UFW estiver ativo)
```bash
ufw allow 'Nginx Full'    # libera 80 e 443
```

Pronto — acesse `http://SEU_DOMINIO_OU_IP`.

### 7. HTTPS gratuito (com domínio apontado para a VPS)
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d SEU_DOMINIO
```
O Certbot configura o SSL e a renovação automática.

---

## Opção B — Build local + upload do `dist/` (sem Node na VPS)

Se preferir não instalar Node na VPS, gere o build na sua máquina e envie só a
pasta `dist/`.

Na **sua máquina** (Windows/PowerShell):
```powershell
cd modelo
npm install
npm run build
```

Envie o conteúdo de `modelo/dist/` para a VPS (ex.: via `scp`):
```bash
scp -r modelo/dist/* root@SEU_IP_DA_VPS:/var/www/site-lpt/modelo/dist/
```
Depois siga os passos **5 a 7** da Opção A (Nginx apontando para essa pasta).

---

## Opção C — Teste rápido sem Nginx (não recomendado para produção)

Servir com `serve` sob o gerenciador de processos `pm2`:
```bash
npm install -g pm2 serve
cd /var/www/site-lpt/modelo
npm install && npm run build
pm2 start "serve -s dist -l 8080" --name site-lpt
pm2 save
pm2 startup        # siga a instrução exibida para iniciar no boot
```
Acesse `http://SEU_IP_DA_VPS:8080` (libere a porta no firewall se necessário).

---

## Backend (API FastAPI) — quando implementado

> Baseado na §14 da spec. Aplica-se após os Blocos A–G estarem prontos.

### 1. Python + dependências
```bash
apt install -y python3 python3-venv python3-pip
cd /var/www/site-lpt/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configurar segredos (`.env`) e usuários
```bash
cp .env.example .env
nano .env     # SMTP_*, DESTINATARIOS, ALERTA_EMAIL, SECRET_KEY, TOKEN_TTL, mapas de acesso
python -m backend.admin_usuarios add fulano@equatorialenergia.com.br   # gera senha temporária
```
`.env` e `backend/usuarios.json` **não vão para o git** (segredos). `entrada/` fica em
`/var/www/site-lpt/entrada` (atualizado diariamente por processo externo).

### 3. Serviço uvicorn (systemd)
Crie `/etc/systemd/system/site-lpt-api.service`:
```ini
[Unit]
Description=Site LPT - API FastAPI
After=network.target

[Service]
WorkingDirectory=/var/www/site-lpt
ExecStart=/var/www/site-lpt/backend/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```
```bash
systemctl daemon-reload
systemctl enable --now site-lpt-api
```

### 4. Nginx: proxy de `/api` ao lado do estático
Dentro do `server { … }` do site (Opção A), acrescente:
```nginx
    # API do backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 50m;   # planilhas grandes (até ~50.000 linhas)
    }
```
```bash
nginx -t && systemctl reload nginx
```

### 5. Atualizar o backend
```bash
cd /var/www/site-lpt && git pull
cd backend && . .venv/bin/activate && pip install -r requirements.txt
systemctl restart site-lpt-api
```

---

## Atualizar o site depois de novas mudanças

```bash
cd /var/www/site-lpt
git pull
cd modelo
npm install        # só se houver novas dependências
npm run build
systemctl reload nginx     # (Opção A/B) — ou: pm2 restart site-lpt (Opção C)
```

---

## Observações

- **Não comite `node_modules/`, `dist/`, `.env` nem `backend/usuarios.json`** — já estão
  no `.gitignore` (artefatos regeneráveis e segredos). O resto do conteúdo é versionado.
- O front estático não tem variáveis de ambiente; o **backend** usa `.env` (SMTP,
  destinatários, `SECRET_KEY`, mapas de acesso) — ver seção do backend acima.
- **Estado atual:** a "validação" e o download do `.csv` são roteirados no navegador
  (mock). Após os Blocos A–G, a validação passa a ser **real** no backend e o Anexo V
  validado é **enviado por e-mail** automaticamente.
