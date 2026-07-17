# Deploy do Backend — Azure / Ubuntu 24 (guia para os engenheiros)

Front carrega na porta 80, mas **login dá 403** ("erro de acesso ao back").
Este guia resolve isso e valida o backend ponta a ponta.

> **Arquitetura:** SPA estático (`modelo/dist/`) + API FastAPI (`backend/`) por trás do
> **mesmo Nginx**. O front chama a API em **`/api`** (mesma origem). O Nginx precisa
> **servir o estático E fazer proxy de `/api` para o uvicorn** (127.0.0.1:8000).

---

## 0. Diagnóstico do 403 — COMECE AQUI (2 minutos)

O 403 tem **duas causas possíveis**. O **corpo da resposta** diz qual:

```bash
# Rode NO SERVIDOR. Veja o corpo do 403:
curl -i -X POST http://127.0.0.1/api/login \
  -H "Content-Type: application/json" \
  -d '{"operador":"enbpar","senha":"x"}'
```

- **Corpo = `{"detail":"Operador não registrado no sistema."}`** → é o **backend** recusando.
  O login **NÃO é por e-mail** — é por **operador**. Veja o Passo 3. (Causa nº 1, a mais comum.)
- **Página HTML "403 Forbidden / nginx"** → o **Nginx** não está roteando `/api`, ou é
  permissão de arquivo. Veja o Passo 4.
- **Não responde / conexão recusada** em `127.0.0.1:8000` → o **backend não está rodando**.
  Veja o Passo 2.

Escada de verificação (isola em qual camada está o problema):

```bash
# (a) backend direto (pula o Nginx):
curl -s http://127.0.0.1:8000/api/health        # espera 200 + JSON
# (b) através do Nginx:
curl -s http://127.0.0.1/api/health             # espera o MESMO 200 + JSON
```
Se **(a) funciona e (b) dá 403/404** → o problema é o **proxy `/api` do Nginx** (Passo 4).

---

## 1. Pré-requisitos (Ubuntu 24)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git
python3 --version        # 3.12.x (padrão no Ubuntu 24) — OK
```

O **front** (build do Vite) pode ser gerado na máquina de dev e enviado, ou na VM
(precisa Node 20.19+/22.x). Este guia foca no **backend + Nginx**, que é onde está o 403.

---

## 2. Backend: instalar e subir

Suponha o projeto em **`/opt/anexov`** (ajuste se usarem outro caminho). O uvicorn roda
**a partir da raiz do projeto** (onde ficam `backend/`, `entrada/`, `manuais/`,
`base_contratos.json`).

```bash
cd /opt/anexov

# venv na RAIZ do projeto + dependências
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# teste rápido de subida (Ctrl+C para sair)
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
# noutro terminal:  curl -s http://127.0.0.1:8000/api/health   → 200 + JSON
```

Arquivos que **precisam estar presentes** (vêm no `git`, exceto o `usuarios.json`):

| Arquivo/pasta | Origem | Observação |
|---|---|---|
| `entrada/**/*.csv` | git | base de referência (validação) |
| `base_contratos.json` | git (raiz) | autoridade de contratos |
| `manuais/…v260714.xlsx` | git | modelo oficial (aba Dominios) |
| `backend/usuarios.json` | **git** (semeado) | 6 operadores; senha inicial `Senha123`, troca no 1º acesso (Passo 3) |

### Serviço systemd (`/etc/systemd/system/anexov-api.service`)

```ini
[Unit]
Description=Anexo V - API FastAPI
After=network.target

[Service]
WorkingDirectory=/opt/anexov
ExecStart=/opt/anexov/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
sudo chown -R www-data:www-data /opt/anexov      # www-data precisa LER os arquivos
sudo systemctl daemon-reload
sudo systemctl enable --now anexov-api
sudo systemctl status anexov-api                 # deve estar "active (running)"
journalctl -u anexov-api -n 50 --no-pager        # logs se não subir
```

---

## 3. Operadores (login) — já vêm no repo

**O login é por OPERADOR, não por e-mail.** Os 6 operadores **já vêm versionados** em
`backend/usuarios.json` (não precisa provisionar):

```
equatorialenergia   energisa   neoenergia   ambarenergia   cerci   enbpar
```

- **Senha inicial de todos: `Senha123`** — o sistema **exige troca no 1º acesso**.
- `enbpar` é curinga (vê todos os contratos) — bom para testar o login primeiro.
- Digitar um operador fora dessa lista (ou um **e-mail**) → **403 "Operador não registrado"**.

Comandos úteis (opcionais):

```bash
cd /opt/anexov
# adicionar um operador novo (imprime a senha temporária):
sudo -u www-data .venv/bin/python -m backend.admin_usuarios add <operador>
# desativar:
sudo -u www-data .venv/bin/python -m backend.admin_usuarios disable <operador>
```
Esqueci a senha (self-service, sem e-mail): botão "Esqueci minha senha" → volta para
`Senha123` (troca obrigatória no próximo login).

> ⚠️ **`git pull` sobrescreve as senhas.** Como o `usuarios.json` é versionado, um
> `git pull` no servidor **reseta todos os logins para o seed (`Senha123`)**. Depois que
> os operadores trocarem a senha: **faça backup do `backend/usuarios.json` antes de puxar
> código novo** e restaure-o depois (ou re-semeie via "esqueci senha").

---

## 4. Nginx: estático + proxy de `/api` (a peça que costuma faltar)

`/etc/nginx/sites-available/anexov`:

```nginx
server {
    listen 80;
    server_name SEU_DOMINIO_OU_IP;

    root /opt/anexov/modelo/dist;
    index index.html;

    # SPA: rotas do front caem no index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API do backend — ESTA é a parte que resolve o 403 de infra.
    location /api/ {
        proxy_pass http://127.0.0.1:8000;      # ⚠️ SEM barra no final (preserva o /api/)
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50m;              # planilhas grandes (até ~50 mil linhas)
    }
}
```

> ⚠️ **Detalhe crítico:** `proxy_pass http://127.0.0.1:8000;` **sem** barra no final.
> Com barra (`.../8000/;`) o Nginx remove o prefixo `/api` e o backend recebe `/login`
> → 404. As rotas do backend são literalmente `/api/login`, `/api/health`, etc.

```bash
sudo ln -s /etc/nginx/sites-available/anexov /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default        # remove o site padrão
sudo nginx -t                                      # testa a config
sudo systemctl reload nginx
```

Se o **UFW** estiver ativo: `sudo ufw allow 'Nginx Full'`. (Na Azure, garanta que o
**NSG** libera a porta 80/443 — o front já carrega, então provavelmente já está ok.)

**Mesma origem = sem CORS.** Se por algum motivo o front for servido em outra origem/porta
que a API, adicione essa origem em `ORIGENS_DEV` no `backend/app.py`. No layout acima
(tudo atrás do mesmo Nginx) **não há CORS** e não é o problema.

---

## 5. Verificação — rodar TODA a suíte de testes do backend

A suíte prova que a **lógica do backend está correta** (auth, acesso por operador,
validação, rotas). Se ela passa e o site ainda dá 403, o problema é **infra** (Nginx/
provisionamento), não código.

```bash
cd /opt/anexov
.venv/bin/pip install -r backend/requirements.txt      # inclui pytest + httpx2
.venv/bin/python -m pytest backend/tests/ -v
# resultado esperado:  121 passed
```

> O `TestClient` do FastAPI exige **`httpx2`** (não `httpx`) no starlette 1.3+ — já está
> no `requirements.txt`. Rode **a partir da raiz** do projeto.

Cobertura da suíte (121 testes):

| Arquivo | Cobre |
|---|---|
| `test_api.py` (25) | login/troca/esqueci-senha, **403 de operador não registrado**, contexto (grupo→contratos), `/api/validar`, `/api/modelo`, guard de token |
| `test_auth.py` (21) | hash pbkdf2 + salt, token JWT, criar/desativar/autenticar, reset, rate-limit |
| `test_acesso.py` (10) | **operador → grupo econômico**, curinga ENBPAR, filtro de contratos |
| `test_validacao.py` (29) | regras de erro/aviso (obrigatórios, domínio, "0 - Não é prioridade", comunidade, caixa alta/baixa) |
| `test_planilha.py` (9) | parser `.xlsx`, normalização de ID/coordenada/**nome (acento/espaço)** |
| `test_referencia.py` (8) | carga de `entrada/`, integridade vs `base_contratos.json` |
| `test_dominios.py` (2) | aba Dominios do modelo |
| `test_email.py` (6) | os 4 e-mails (SMTP mockado) |

Smoke test **na máquina** (após subir tudo), simulando o front:

```bash
# 1) health através do Nginx:
curl -s http://127.0.0.1/api/health

# 2) login com o operador semeado (senha inicial Senha123; no 1º acesso o backend
#    responde {"precisaTrocarSenha": true} — isso é SUCESSO):
curl -i -X POST http://127.0.0.1/api/login \
  -H "Content-Type: application/json" \
  -d '{"operador":"enbpar","senha":"Senha123"}'
```
- **200** com `token` ou `precisaTrocarSenha` → backend + Nginx OK. ✔
- **401** → senha errada (operador válido).
- **403 "Operador não registrado"** → operador inválido/não provisionado (Passo 3).

---

## 6. Checklist do 403

| Sintoma | Causa | Correção |
|---|---|---|
| 403 JSON `{"detail":"Operador não registrado no sistema."}` | operador inválido (ex.: usaram **e-mail**) | logar com um dos 6 operadores (senha `Senha123`, Passo 3) |
| 403 HTML "nginx" | `location /api/` ausente ou permissão | adicionar o bloco `/api/` (Passo 4); `chown www-data` |
| 404 no `/api/...` | `proxy_pass` **com** barra no final | tirar a barra: `proxy_pass http://127.0.0.1:8000;` |
| 502 Bad Gateway | backend não está rodando | `systemctl status anexov-api`; `journalctl -u anexov-api` |
| Login funciona, mas **"Não foi possível trocar a senha"** (ou "esqueci senha" falha) | o backend **não consegue ESCREVER** `usuarios.json` (permissão) → 500 na escrita atômica | `sudo chown -R <user-do-serviço>:<grupo> .../backend` — o **diretório** `backend/` precisa ser gravável (cria `.tmp` + `rename`). Confirme: `journalctl -u anexov-api` mostra `PermissionError`/`os.replace` |
| Login retorna o HTML do site | só há `try_files`, sem proxy `/api` | adicionar o bloco `/api/` (Passo 4) |

---

## 7. Produção — segredos (opcional, mas recomendado)

O backend sobe **sem `.env`** (usa defaults de dev; login funciona). Para produção,
crie `/opt/anexov/backend/.env` e defina ao menos uma **SECRET_KEY** forte (assina os
tokens de sessão):

```bash
# gera uma chave forte:
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))" \
  | sudo tee -a /opt/anexov/backend/.env
sudo systemctl restart anexov-api
```

Outras chaves do `.env` (envio de e-mail da planilha validada): `SMTP_HOST`, `SMTP_PORT`,
`SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `DESTINATARIOS`, `ALERTA_EMAIL`. Sem SMTP, a
validação funciona normalmente; apenas o **envio** do `.xlsx` fica em dry-run.

`backend/.env` e `backend/usuarios.json` **nunca vão para o git** (segredos).
