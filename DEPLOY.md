# Deploy — Site mock "Classificação de Beneficiários do Programa"

Guia para hospedar este projeto numa **VPS Hostinger** (Ubuntu) e publicar via
**Nginx**.

## Visão geral

- O projeto é um **SPA estático** (Vite + React), **mock de apresentação** — sem
  backend, sem banco de dados.
- O código-fonte fica na pasta **`modelo/`** do repositório.
- O comando de build gera arquivos estáticos em **`modelo/dist/`**. É essa pasta
  que o servidor web entrega.
- Requisito: **Node.js 20.19+ ou 22.x** (o Vite 7 exige essas versões).

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

- **Não comite `node_modules/` nem `dist/`** — já estão no `.gitignore`. O `dist/`
  é gerado pelo build; o `node_modules/` é recriado pelo `npm install`.
- Por ser estático, não há variáveis de ambiente nem porta de backend a configurar.
- A "validação" das planilhas e o download do `.csv` são **roteirados no navegador**
  (mock); nada é enviado a um servidor.
