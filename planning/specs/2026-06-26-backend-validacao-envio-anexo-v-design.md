# Spec — Backend de validação e envio do Anexo V

> Data: 2026-06-26 · Status: **aprovação pendente** · Tema: backend FastAPI para o
> site "Classificação de Beneficiários do Programa".
> Documento-irmão: `planning/PLAN.md` (estado geral). Esta spec detalha **a primeira
> fase com backend real**, substituindo a validação roteirada por validação de verdade.

---

## 1. Objetivo

Transformar o mock estático em fluxo ponta a ponta **mínimo**:

1. O operador **baixa o modelo** oficial (`Anexo V - Planilha - Painel de Monitoramento
   - MME-CC_UF.xlsx`).
2. Preenche e **envia** a planilha pelo site.
3. O backend **valida de verdade** a aba `Preenchimento` contra os dados de referência
   em `entrada/` (atualizados diariamente) + regras de formato/domínio.
4. Se houver erro → devolve **painel de inconsistências real** (mesma tela aprovada).
5. Se passar (0 erros) → o backend **envia o `.xlsx` por e-mail automaticamente**, sem
   alterar o arquivo, para uma lista de destinatários configurável.

**Restrição dura:** o visual aprovado do front **não muda**. Só o comportamento é
religado à API real (upload real, dados reais no painel, envio automático).

## 2. Escopo

**Dentro:**
- API FastAPI (`backend/`): autenticação (login, trocar-senha, esqueci-senha) + validar,
  contexto, baixar modelo, health.
- **Autenticação real** (login/senha, admin provisiona, troca no 1º acesso), §5.2.
- Carga em memória dos CSVs de `entrada/`, com recarga ao detectar mudança (atualização
  diária) sem reiniciar o serviço.
- **Filtro de acesso por login** em duas camadas (e-mail → grupo → contratos/UFs), §5.1.
- Parsing real do `.xlsx` (aba `Preenchimento`, openpyxl).
- Regras de validação (cruzamento com `entrada/` + formato/domínio).
- Envio de e-mail (smtplib) com o `.xlsx` anexado **como veio**.
- E-mail de **alerta crítico** ao administrador em caso de anomalia (ver §8).
- Religação comportamental do front (sem mudança visual).
- Suíte de testes (pytest) e atualização do `DEPLOY.md`.

**Fora (YAGNI por agora):**
- Autocadastro de usuários / painel admin web (provisionamento é via CLI).
- Banco de dados (usuários ficam em `usuarios.json`) / histórico de envios / consulta da base.
- Reescrita/normalização da planilha (o anexo vai como veio).
- Destinatários por UF/contrato (lista é única e global).
- Motor de regras genérico / abstrações especulativas.

## 3. Decisões registradas (das perguntas ao usuário, 2026-06-26)

1. **Significado de "validar"**: (a) cruzar cada ODI+UC com `entrada/`; (b) conferir
   UF/município contra a referência; (c) regras internas de formato/domínio.
   Completude total do contrato **não** é exigência bloqueante (UC faltando = aviso).
2. **Stack**: Python + FastAPI + uvicorn, atrás do mesmo Nginx em `/api`.
3. **Anexo do e-mail**: o `.xlsx` enviado, **sem alteração**.
4. **SMTP**: configurável via `.env` (qualquer provedor).
5. **Destinatários**: lista única global (via `.env`).
6. **Auth da API**: **login + senha reais** (revisado 2026-06-27). Admin cria os usuários
   com **senha temporária**; troca obrigatória no 1º acesso. Usuários em **`usuarios.json`
   com hash** (pbkdf2 stdlib + salt por usuário). Token de sessão assinado nas chamadas
   protegidas. "Esqueci minha senha" → alerta ao admin (reemite temporária). O grupo
   (§5.1) continua derivado do domínio do e-mail. *(Backend deixa de ser stateless quanto
   a usuários; mantém-se sem DB — arquivo JSON.)*
7. **Validar + enviar = uma chamada só**: se passa nas validações, envia o e-mail
   automaticamente.
8. **Contrato sem referência em `entrada/`**: no mundo real **todo contrato tem ODI+UC**;
   se chegar um sem referência, **não** é erro de usuário — dispara **e-mail crítico**
   ao admin para investigação (ver §8).
9. **Local**: `backend/` na raiz, irmão de `modelo/`; config por `.env`.
10. **Git**: commitar todo o conteúdo; **fora do git só** artefatos regeneráveis
    (`node_modules/`, `dist/`, `build/`, logs) e segredos (`.env`); versiona `.env.example`.
11. **Filtro de acesso por login** (§5.1): grupos econômicos; e-mail → grupo (camada 1) →
    contratos/UFs visíveis (camada 2). `ENBPAR` vê tudo. Não é segurança (sem auth real).
12. **Coordenadas inválidas** = **aviso** (não bloqueia), não erro.
13. **Nome do anexo do e-mail**: `Anexo V preenchido - {contrato}.xlsx` (`/`→`-`).

## 4. Arquitetura

```
Navegador (modelo/dist — SPA, visual inalterado)
   │  fetch (multipart / GET)
   ▼
Nginx
   ├── /         → modelo/dist (estático)
   └── /api/*    → uvicorn (FastAPI)
                     │
   ┌─────────────────┴───────────────────────────────────────┐
   │ FastAPI (backend/)                                        │
   │  auth.py        login/senha (usuarios.json+hash), token   │
   │  referencia.py  carrega entrada/*.csv em memória,         │
   │                 recarrega no mtime change (atualização    │
   │                 diária); índices por contrato             │
   │  acesso.py      e-mail→grupo→contratos/UFs (filtro §5.1)  │
   │  planilha.py    lê o .xlsx (aba Preenchimento)            │
   │  validacao.py   regras → grupos + preview + totais        │
   │  email_envio.py smtplib: envio do anexo + alerta crítico  │
   │  app.py         rotas + orquestração                      │
   └──────────────────────────────────────────────────────────┘
```

Backend **stateless** (nenhum estado entre requisições além do cache de referência).
Sem banco. Domínios válidos lidos da aba `Dominios` do próprio modelo (fonte única).

## 5. Dados de referência (`entrada/`)

Estrutura observada (separador `;`, BOM UTF-8):
- `entrada/lpt/consolidado.csv` — `contrato;odi;uf;municipio`
- `entrada/lpt/consolidado_ucs.csv` — `contrato;odi;uc`
- `entrada/mla/consolidado.csv` — `contrato;odi;uf;municipio`
- (futuro) `entrada/mla/consolidado_ucs.csv` — esperado pela atualização diária

**Junção verificada (2026-06-26):** os números de contrato em `entrada/` casam 100% com
`base_contratos.json` (zero órfãos). A junção usa `contrato.numero`
normalizado (trim + colapso de espaços + upper).

**Índices em memória, por contrato:**
- `chaves_uc[contrato]` = `set((odi, uc))` — para existência ODI+UC, duplicidade e UCs
  faltando. Vem dos arquivos `*_ucs.csv`.
- `odi_ref[contrato]` = `dict odi -> (uf, municipio)` — para conferência UF/município.
  Vem dos arquivos `consolidado.csv`.

**Recarga:** o módulo guarda o `mtime` de cada CSV; a cada requisição (custo desprezível)
verifica mudança e recarrega só se necessário. Assim a atualização diária é refletida sem
reiniciar o uvicorn. Carga inicial no startup.

**Volume:** ~176k linhas no total — dicionários/sets em memória resolvem em milissegundos.

## 5.1 Filtro de acesso por login (grupo econômico) — duas camadas

**Decisão (2026-06-26):** o site é acessado por **grupos econômicos** de distribuidoras.
O que cada usuário vê depende do **domínio do e-mail** informado no login. **Não é
controle de segurança** (não há senha/auth real, conforme §3.6) — é um **filtro de
escopo** da seleção.

**Grupos (configuráveis, podem ser expandidos/ajustados):** `EQUATORIAL`, `ENERGISA`,
`NEOENERGISA`, `ÂMBAR`, `CERCI`, `ENBPAR`.

**Duas camadas:**
1. **Camada 1 — e-mail → grupo:** o domínio após o `@` resolve o grupo, via mapa
   configurável `dominio_email -> grupo` (ex.: `@equatorialenergia.com.br → EQUATORIAL`).
   Domínio desconhecido → sem contratos (ou grupo padrão a definir).
2. **Camada 2 — grupo → contratos/UFs visíveis:** mapa configurável `grupo -> {siglas}`
   filtra `base_contratos.json`. `ENBPAR` = **curinga** (vê todos os 41 selecionáveis).
   O filtro reduz **as duas etapas de seleção** do front (UF e contrato).

**Mapa `sigla -> grupo` proposto (confirmado em 2026-06-26; configurável):**
| sigla (distribuidora) | grupo |
|---|---|
| EQUATORIAL | EQUATORIAL |
| ENERGISA | ENERGISA |
| COELBA | NEOENERGISA |
| CERCI | CERCI |
| ÂMBAR · AMAZONAS · RORAIMA | ÂMBAR |
| *(todas)* | ENBPAR (curinga) |

**Enforcement:** o filtro vale no front (UX) **e** no backend: o `POST /api/validar`
rechecka que o `contrato` enviado pertence ao grupo do usuário autenticado (e-mail do
**token**, não de parâmetro); se não, `403`. Os mapas vivem em **config do backend**
(fonte única); o front os consome via `GET /api/contexto`.

## 5.2 Autenticação (login + senha)

**Decisão (2026-06-27):** login/senha reais; **admin provisiona**; troca no 1º acesso.

**Store — `backend/usuarios.json`** (fora do git; trate como segredo). Cada usuário:
```json
{ "email": "fulano@equatorialenergia.com.br", "senha_hash": "pbkdf2_sha256$...",
  "salt": "…", "precisa_trocar_senha": true, "ativo": true }
```
- **Hash:** `hashlib.pbkdf2_hmac("sha256", senha, salt, iterações)` (stdlib, sem dep
  nativa); salt aleatório por usuário.
- **Grupo:** derivado do domínio do e-mail (§5.1), não armazenado por usuário.

**Provisionamento — CLI** `python -m backend.admin_usuarios`: cria/desativa usuário,
gera **senha temporária** (`precisa_trocar_senha=true`) e **envia a senha por e-mail ao
próprio usuário** (decisão 2026-06-27; ver §9). Sem tela web de admin (não muda a UI).

**Fluxo:**
1. `POST /api/login {email, senha}` → valida hash. Se `precisa_trocar_senha`, responde
   `{precisaTrocarSenha: true}` (sem token de uso pleno) → front mostra a tela de troca.
   Senão, emite **token** de sessão (assinado, com expiração).
2. `POST /api/trocar-senha {email, senhaAtual, novaSenha}` → valida, grava novo hash,
   zera a flag, emite token.
3. `POST /api/esqueci-senha {email}` → **self-service**: gera nova senha temporária,
   marca `precisa_trocar_senha=true` e **envia a nova senha por e-mail ao usuário**.
   Resposta genérica (não revela se o e-mail existe). Sem dependência do admin.
4. Rotas protegidas (`/api/contexto`, `/api/validar`, `/api/modelo`) exigem
   `Authorization: Bearer {token}`; o e-mail vem do token.

> **Segurança (registrar):** enviar senha temporária em **texto** por e-mail é comum, mas
> não ideal. Mitigações: a senha **expira no 1º uso** (`precisa_trocar_senha`), troca
> obrigatória, e o reset é rate-limited por e-mail para evitar abuso. Revisar se exigirem
> link com token em vez de senha em texto (alternativa descartada agora por simplicidade).

**Token:** assinado (PyJWT ou itsdangerous) com `SECRET_KEY` do `.env` e expiração
(`TOKEN_TTL`). Não é OAuth nem refresh — sessão simples.

> **Nota de UI:** o modelo "admin + senha temporária" exige **uma tela nova** de *trocar
> senha* no 1º acesso. É inevitável ao adicionar auth; será construída **reusando o design
> system** (`auth-shell`/`auth-card`/`field`/`btn-primary`), sem alterar as telas já
> aprovadas. O login atual (e-mail+senha+"Esqueci minha senha") é religado sem mudança visual.

## 6. Contrato de API

Os formatos de resposta espelham **exatamente** o que o front já consome
(`RULE_GROUPS`, `PREVIEW_ROWS`, totais), para não mexer no visual. Rotas protegidas
exigem `Authorization: Bearer {token}` (§5.2); o e-mail do usuário vem do token.

### Autenticação (§5.2)
- `POST /api/login {email, senha}` → `{token}` ou `{precisaTrocarSenha: true}` ou `401`.
- `POST /api/trocar-senha {email, senhaAtual, novaSenha}` → `{token}` ou `400/401`.
- `POST /api/esqueci-senha {email}` → `{ok: true}` (gera nova senha temporária e **envia
  ao usuário**; resposta genérica). Rate-limited por e-mail.

### `POST /api/validar` *(protegida)*
`multipart/form-data`: `arquivo` (.xlsx), `contrato` (número), `uf` (sigla). O e-mail vem
do token. Valida; **se 0 erros, envia o e-mail antes de responder**.

Resposta `200`:
```json
{
  "ok": true,
  "enviado": true,
  "linhasLidas": 1240,
  "totalErros": 0,
  "totalAvisos": 3,
  "grupos": [
    { "sev": "err", "title": "Campos obrigatórios vazios", "desc": "...",
      "count": 8,
      "rows": [ { "loc": "L47", "field": "Latitude",
                  "problem": "célula vazia", "sug": "preencher em graus decimais" } ] }
  ],
  "previewRows": [
    { "linha": "L12", "odi": "210001", "uc": "70012345", "municipio": "MANACAPURU",
      "uf": "AM", "ibge": "1302603", "latitude": "-3.3018",
      "energizacao": "14/02/2026", "tipoAtend": "Extensão de Rede",
      "flags": { "uc": "err" } }
  ]
}
```
- `ok` = `totalErros == 0`. Quando `ok=true`, o e-mail já foi disparado.
- `enviado` = e-mail saiu com sucesso. `ok=true` + `enviado=false` → falha de SMTP
  (resposta inclui `erroEnvio`); o front avisa por toast.
- Erros de requisição: `401` (token ausente/inválido/expirado). `400` (arquivo
  ausente/não-.xlsx, aba `Preenchimento` ausente, parâmetros faltando). Contrato fora do
  grupo (§5.1) → `403`. Anomalia de referência (§8) → `409` + alerta enviado.

### `GET /api/contexto` *(protegida)*
Resolve o grupo do e-mail do **token** (camada 1) e devolve a seleção visível (camada 2).
Usado pelo front após o login para alimentar `UfSelector`/`ContratoSelector`.
```json
{
  "email": "fulano@equatorialenergia.com.br",
  "grupo": "EQUATORIAL",
  "ufs": [ { "sigla": "PA", "nome": "Pará", "contratos": 6 } ],
  "contratos": [ { "numero": "ECM 018/2025", "uf": "PA", "tipo_contrato": "MLA",
                   "tranche": "2ª Tranche", "sigla": "EQUATORIAL", "ucs": 4210 } ]
}
```
`ENBPAR` → todos os 41. Domínio desconhecido → listas vazias (front trata).

### `GET /api/modelo` *(protegida)*
Baixa `manuais/Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.xlsx`
(`Content-Disposition: attachment`, nome canônico). Liga o botão "Baixar modelo".

### `GET /api/health`
`{ "status": "ok", "referenciaCarregadaEm": "...", "contratosComReferencia": N,
   "contratosSemReferencia": [ ... ], "grupos": [ ... ] }`.

## 7. Regras de validação

Parsing: aba `Preenchimento`, cabeçalho na **linha 2**, dados a partir da **linha 3**.
Colunas mapeadas por **nome do cabeçalho** (robusto a reordenação), não por posição.
As 38 colunas de tipologia = as que vêm após `Enquadramento do benefício`. Domínios
válidos (Tipo de Atendimento, UF, Tipo de Comunidade, Enquadramento, Sim/Não) lidos da
aba `Dominios` do modelo.

`loc` no formato `L{n}` (linha real da planilha, base 1, contando o cabeçalho).

**Linha de dados (o que contar):** uma linha conta como **preenchida pelo usuário**
quando tem **ODI e/ou UC**. Linhas totalmente vazias são **ignoradas** (não entram em
`linhasLidas` nem geram erro). `linhasLidas` = nº de linhas preenchidas. **Guarda:** se
`linhasLidas == 0`, retorna **erro** "Planilha sem linhas de dados na aba Preenchimento"
e **não** envia (evita e-mail com planilha vazia). *(Ajustável: exigir ODI **e** UC
juntos para a linha contar.)*

**Erros — bloqueiam o e-mail (`sev: "err"`):**
| Regra | Detecção |
|---|---|
| Campos obrigatórios vazios | em linhas preenchidas (ODI/UC), célula vazia em ODI, UC, IBGE, Município, UF, Latitude, Longitude ou Data de Energização — inclui o próprio ODI/UC faltante |
| Planilha sem dados | `linhasLidas == 0` (nenhuma linha com ODI/UC) |
| Valor fora do domínio | Tipo de Atendimento / Tipo de Comunidade / Enquadramento / UF fora da aba `Dominios` |
| Chave ODI+UC duplicada | mesma `(odi, uc)` em >1 linha **na própria planilha** |
| ODI+UC não consta na referência | `(odi, uc)` ausente de `chaves_uc[contrato]` |
| UF/município divergente | `odi_ref[contrato][odi]` existe mas UF/município da linha diferem |

**Avisos — não bloqueiam (`sev: "warn"`):**
| Regra | Detecção |
|---|---|
| Coordenadas inválidas | Lat/Long não numéricas ou fora de faixa (lat −90..90, long −180..180) |
| UCs faltando | `(odi, uc)` em `chaves_uc[contrato]` ausente da planilha (count agregado) |
| "0 - Não é prioridade" + outra tipologia | coluna `0` = Sim junto de outra tipologia = Sim |
| Data de energização fora de 2026 | ano ≠ 2026 |
| Tipologia ≠ Sim/Não | célula de tipologia com valor fora de {Sim, Não, vazio} |

**Preview:** primeiras ~7–10 linhas mapeadas para as chaves de `PREVIEW_COLS`
(`linha, odi, uc, municipio, uf, ibge, latitude, energizacao, tipoAtend`), com `flags`
marcando `"err"`/`"warn"` por célula que falhou.

**Severidade:** só `err` bloqueia o envio. `warn` não.

## 8. Integridade de `entrada/` contra `base_contratos.json` (autoridade)

**Decisão (2026-06-26):** `base_contratos.json` é a **autoridade** sobre quais contratos
existem e quais são selecionáveis (`vigente ≠ "Encerrado"`). Os arquivos de `entrada/`
são **validados contra ele**, não o contrário.

**Verificação de integridade (no startup e a cada recarga):** o backend compara a
cobertura de `entrada/` com os contratos selecionáveis de `base_contratos.json` e
classifica cada contrato:
- contrato em `entrada/` **não** presente em `base_contratos.json` → log de alerta (dado
  órfão; hoje: zero);
- contrato selecionável em `base_contratos.json` **sem** referência (sem `chaves_uc`)
  em `entrada/` → marcado como "sem referência".

**Anomalia em requisição:** no fluxo real todo contrato selecionável tem ODI+UC. Se
chegar um `POST /api/validar` para um contrato marcado "sem referência":
- **Não** é erro de usuário e **não** roda o caminho normal.
- Backend envia **e-mail de erro crítico** ao admin (`ALERTA_EMAIL` no `.env`) com
  contrato/UF/nome do arquivo/timestamp para investigação.
- Responde `409` com mensagem genérica ("não foi possível validar este contrato no
  momento"); nenhum e-mail de planilha é enviado.

> **Risco de rollout (registrar):** os contratos selecionáveis **sem** dados de UC hoje
> são, essencialmente, os **19 contratos do Mais Luz para a Amazônia (MLA)** — os
> listados em `entrada/mla/consolidado.csv` —, **mais 3 contratos LPT** ainda pendentes
> (`ECO 034/2026`, `ECO 039/2025`, `ECO 042/2025`). Total: 22 de 41. Sob esta regra,
> selecioná-los hoje dispararia o alerta crítico. **Pré-condição de produção:** as
> atualizações diárias de `entrada/` devem cobrir ODI+UC de todos os selecionáveis (em
> especial gerar o `entrada/mla/consolidado_ucs.csv` do MLA). A verificação de integridade
> acima torna esse gap **observável** (no `/api/health` e nos logs) em vez de silencioso.

## 9. Envio de e-mail

`smtplib` + `email.message`. Configuração 100% via `.env`:
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_TLS`,
`DESTINATARIOS` (lista única separada por vírgula), `ALERTA_EMAIL` (admin).

- **Envio normal** (0 erros): anexa o `.xlsx` **byte a byte como veio** (sem reescrever),
  com o nome de anexo **`Anexo V preenchido - {contrato}.xlsx`** (o `/` do número do
  contrato vira `-` para nome de arquivo válido — ex.: `Anexo V preenchido - ECM 018-2025.xlsx`).
  Assunto: `Anexo V validado — {contrato} ({uf}) — {DD/MM/AAAA}`. Corpo curto em PT.
- **Alerta crítico** (§8): assunto `[ALERTA] Contrato sem referência — {contrato}`,
  corpo com contexto técnico, ao `ALERTA_EMAIL`.
- **Credenciais / senha temporária** (§5.2): ao **próprio usuário**, na **criação** (via
  CLI) e no **reset** ("esqueci minha senha"). Assunto `Acesso ao sistema — senha
  temporária`; corpo com a senha temporária + instrução de troca no 1º acesso.
- Falha de SMTP no envio normal → resposta `ok=true, enviado=false, erroEnvio="..."`.
- Sem SMTP configurado em ambiente de dev → modo "dry-run" (loga o que enviaria),
  controlado por `SMTP_DRYRUN=1`, para permitir testes locais sem servidor real.

## 10. Mudanças no front (comportamento — visual inalterado)

| Arquivo | Mudança |
|---|---|
| `AuthScreen.jsx` | Religa e-mail+senha ao `POST /api/login` (real). Se `precisaTrocarSenha`, mostra a tela de troca. "Esqueci minha senha" → `POST /api/esqueci-senha`. Guarda o **token**. Visual idêntico. |
| `TrocarSenha.jsx` *(novo)* | Tela de 1º acesso (senha atual + nova) → `POST /api/trocar-senha`. **Reusa** `auth-shell`/`auth-card`/`field`/`btn-primary` (sem inventar visual). |
| `UfSelector.jsx` / `ContratoSelector.jsx` | Passam a listar as **UFs/contratos filtrados** (vindos de `GET /api/contexto`, com token) em vez de `CONTRATOS`/`UFS` estáticos. JSX/classes idênticos. |
| `UploadAnexoV.jsx` | Envia o **arquivo real** + `contrato`/`uf` via `FormData` → `/api/validar` (token no header). Mantém a barra de 3 fases. Entrega o resultado ao `App`. Remove o filename sintético e o timer roteirado. |
| `App.jsx` | Guarda contexto (grupo/listas) e o resultado da validação em estado. `ok` → tela de sucesso (e-mail já saiu); senão → painel com dados reais. Remove a lógica de `attempt` (2 tentativas roteiradas). |
| `PainelInconsistencias.jsx` | Recebe `grupos`, `previewRows`, `totalErros`, `totalAvisos`, `linhasLidas` por **props** em vez de importar de `seedData`. JSX/classes **idênticos**. |
| `VersaoPlanilha.jsx` | "Baixar modelo" passa a baixar de `/api/modelo` (deixa de ser stub). |
| `seedData.js` | `RULE_GROUPS`/`PREVIEW_ROWS`/`LINHAS_LIDAS` deixam de alimentar o painel (podem virar fallback de dev ou sair). `CONTRATOS`/`UFS`/helpers permanecem. |
| `relatorioCsv.js` | Passa a gerar o relatório a partir dos `grupos` reais recebidos (mesma lógica de Blob/CSV). |

Base da URL da API por env de build do Vite (`VITE_API_BASE`, default `/api`).

## 11. Layout de arquivos (`backend/`)

```
backend/
  app.py            # FastAPI: rotas auth + validar/contexto/modelo/health
  config.py         # leitura do .env (pydantic-settings)
  auth.py           # usuarios.json, hash pbkdf2, token (login/trocar/esqueci), guard de rota
  admin_usuarios.py # CLI: cria/desativa usuário, gera senha temporária e envia por e-mail
  referencia.py     # carga/cache de entrada/, índices por contrato
  acesso.py         # mapas e-mail→grupo e grupo→siglas; filtro de contratos/UFs (§5.1)
  planilha.py       # parsing do .xlsx (aba Preenchimento)
  validacao.py      # regras → grupos + preview + totais
  email_envio.py    # smtplib: planilha validada + alerta crítico + credenciais/senha temporária
  usuarios.json     # store de usuários (FORA do git — segredo)
  requirements.txt  # fastapi, uvicorn[standard], openpyxl, python-multipart,
                    #   pydantic-settings, python-dotenv, PyJWT
  .env.example      # todas as chaves documentadas (sem segredos)
  tests/
    conftest.py
    fixtures/        # geradores de .xlsx de teste (openpyxl)
    test_auth.py       # hash, login, troca no 1º acesso, token, rota protegida → 401
    test_referencia.py
    test_acesso.py     # e-mail→grupo→contratos; ENBPAR curinga
    test_planilha.py
    test_validacao.py
    test_email.py
    test_api.py        # e2e via TestClient
```

**Estilo de código (regra do projeto):** toda função com docstring em PT explicando *por
que existe* e a lógica em fases numeradas (Entrada → Fase 1 → … → Saída); comentário em
cada linha.

## 12. Configuração e `.gitignore`

- **Decisão (2026-06-26):** commitar todo o conteúdo do projeto (inclui `entrada/`,
  `planning/`, `manuais/`, etc.). Fora do git **só** artefatos regeneráveis
  (`node_modules/`, `dist/`, `build/`, logs) e **segredos** (`.env`, `backend/.env`,
  **`backend/usuarios.json`** — contém hashes de senha).
- `.env.example` versionado com todas as chaves (SMTP, destinatários, alerta, mapas de
  acesso, `SECRET_KEY`, `TOKEN_TTL`); `.env` real fora do git.
- `entrada/` é versionado, mas atualizado diariamente por processo externo (fora do
  escopo desta spec).

## 13. Testes (pytest)

Exigidos pela seção *Tests* do CLAUDE.md. Cobrir happy path e edge cases:
- **referencia**: carga dos CSVs, índices corretos, recarga ao mudar mtime, normalização
  da chave de contrato.
- **auth**: hash pbkdf2 (verifica/rejeita); login ok/errado; `precisaTrocarSenha` no 1º
  acesso; troca de senha grava hash e zera flag; token válido/expirado; rota protegida sem
  token → `401`; CLI cria usuário com senha temporária **e dispara e-mail de credenciais
  (mock)**; `esqueci-senha` gera nova temporária e **envia ao usuário (mock)**; resposta
  genérica; rate-limit do reset.
- **acesso**: e-mail → grupo por domínio; grupo → contratos/UFs filtrados; `ENBPAR` vê
  todos; domínio desconhecido → vazio; `POST /api/validar` com contrato fora do grupo → `403`.
- **planilha**: leitura da aba `Preenchimento`, mapeamento por cabeçalho, linhas vazias,
  arquivo sem a aba, não-.xlsx.
- **validacao**: cada regra (erro e aviso) com fixtures dirigidos; planilha 100% limpa;
  duplicidade ODI+UC; divergência UF/município; UCs faltando; coordenadas/datas/tipologia
  inválidas; cálculo de totais; geração do preview com flags.
- **email**: SMTP mockado — planilha validada anexa o arquivo como veio (nome correto);
  alerta crítico no caminho de anomalia; **e-mail de credenciais/senha temporária ao
  usuário** (criação e reset); modo dry-run.
- **smoke manual (SMTP real)**: fora da suíte automatizada — checklist em `TESTES.md`
  ("Teste manual com SMTP real") executado ao fim do Bloco E (caixa de teste) e no Bloco G
  (deploy).
- **api (e2e, TestClient)**: `/api/validar` retornando painel (com erros) e sucesso
  (sem erros, e-mail mockado disparado); `/api/modelo` baixa o arquivo; `/api/health`;
  `409` + alerta no contrato sem referência; `400` nos erros de requisição.

## 14. Deploy

`DEPLOY.md` ganha:
- Serviço uvicorn (systemd) servindo `backend/app.py`.
- Bloco Nginx `location /api { proxy_pass http://127.0.0.1:8000; }` ao lado do estático.
- Passos de `.env` (SMTP/destinatários) e de onde fica `entrada/` no servidor.
- Limite de upload no Nginx (`client_max_body_size`) compatível com planilhas grandes.

## 15. Riscos e pendências

1. **Gap de dados atual** (§8): 22/41 contratos selecionáveis sem UC hoje.
   `base_contratos.json` é a autoridade; a verificação de integridade torna o gap
   observável (`/api/health` + logs). Pré-condição de produção: as atualizações diárias
   cobrirem ODI+UC de todos os selecionáveis.
2. **Formato de data e coordenadas**: **não há planilha preenchida real de exemplo**
   (confirmado 2026-06-26). O parser deve ser **defensivo**: aceitar data `DD/MM/AAAA`
   (texto) e serial do Excel; coordenadas com `,` ou `.` decimal; normalizar antes de
   validar. As abas `Dominios`/`Dicionario_Campos` do modelo são a referência de
   formato/domínio. Revalidar quando surgir um arquivo real preenchido.
3. **Mapa de acesso (e-mail→grupo, grupo→siglas)**: o mapa `sigla→grupo` foi confirmado;
   falta o mapa **`domínio_email → grupo`** (domínios reais de cada distribuidora/ENBPar) —
   preencher na config antes do deploy. Domínio desconhecido → sem contratos.
4. **Tamanho do upload** (até 50.000 linhas): validar limites de Nginx/uvicorn e tempo de
   parsing.
5. **Performance da recarga**: checagem de mtime por requisição é barata, mas a recarga em
   si (~176k linhas) bloqueia; aceitável (1×/dia). Reavaliar se virar gargalo.
6. **Auth com store em arquivo**: `usuarios.json` é simples, mas tem **concorrência**
   fraca (gravações simultâneas). Mitigação: escrita atômica (arquivo temporário + rename).
   Migrar para SQLite se o nº de usuários/escritas crescer. `SECRET_KEY` forte e fora do
   git é essencial.
7. **Nova tela de troca de senha** (§5.2): é a única adição de UI; reusa o design system.
   Confirmar copy/fluxo com os gestores (a UI aprovada não previa isso).
8. **Senha temporária em texto por e-mail** (§5.2/§9): aceitável, mitigado por expiração
   no 1º uso, troca obrigatória e rate-limit do reset. Reavaliar link-com-token se exigirem.
9. **Envio real só em smoke manual**: a suíte automatizada mocka SMTP. Há janela de
   "funciona no mock, falha no SMTP real" — coberta pelos smokes dos Blocos E e G.

## 16. Critérios de aceite

- Upload real de um `.xlsx` com inconsistências → painel mostra grupos/preview reais,
  sem e-mail enviado; visual idêntico ao aprovado.
- Upload de um `.xlsx` limpo → tela de sucesso e e-mail com o arquivo anexado (como veio)
  chega aos destinatários configurados.
- "Baixar modelo" baixa o `.xlsx` oficial de verdade.
- Admin cria usuário (CLI) → usuário **recebe a senha temporária por e-mail**; 1º login
  força troca; depois entra normalmente; rota sem token → `401`; "Esqueci minha senha"
  envia nova senha temporária ao usuário (self-service).
- Smoke manual com SMTP real (caixa de teste no Bloco E; homologação no Bloco G) confirma
  os 3 tipos de e-mail chegando de verdade.
- Login por e-mail filtra UFs/contratos pelo grupo; `ENBPAR` vê todos.
- Contrato fora do grupo do e-mail → `403`. Contrato sem referência → mensagem genérica
  ao usuário e alerta crítico ao admin.
- Atualização dos CSVs de `entrada/` é refletida sem reiniciar o serviço.
- `pytest` verde (happy + edge).

## 17. Fases de implementação (sub-fases testáveis)

Cada sub-fase é **pequena e testável por humano isoladamente** (governança do projeto).
Ordem pensada para entregar valor cedo e manter o front intacto até o fim. Marcador de
teste em *itálico*.

### Bloco A — Backend: fundação
- **A1 · Scaffold FastAPI.** App, `requirements.txt`, `.env.example`, CORS p/ dev,
  `GET /api/health` mínimo. *Teste: `uvicorn` sobe; `GET /api/health` → 200.*
- **A2 · Carga da referência.** `referencia.py` lê `entrada/**/*.csv` em memória, monta
  `chaves_uc` e `odi_ref`, recarrega por mtime. *Teste: health expõe contagem; alterar um
  CSV reflete sem reiniciar.*
- **A3 · Integridade vs `base_contratos.json`.** Classifica contratos com/sem referência;
  expõe no health. *Teste: health lista os 22 sem UC (19 MLA + 3 LPT).*
- **A4 · Acesso (mapas).** `acesso.py`: `domínio→grupo`, `grupo→siglas`, `ENBPAR` curinga,
  via config. *Teste unit: e-mail equatorial→EQUATORIAL→18 contratos; enbpar→41.*

### Bloco B — Backend: autenticação (login/senha)
- **B1 · Store + hash + CLI + e-mail de credenciais.** `auth.py` (usuarios.json, pbkdf2 +
  salt), `email_envio.py` (mensagem de senha temporária) e `admin_usuarios.py` (cria/
  desativa usuário, gera senha temporária e **envia por e-mail ao usuário**). *Teste: CLI
  cria usuário; hash verifica certo/errado; `precisa_trocar_senha=true`; e-mail de
  credenciais disparado (mock).*
- **B2 · `POST /api/login`.** Valida hash; emite token ou sinaliza troca. *Teste: senha
  certa→token; errada→401; flag ligada→`precisaTrocarSenha`.*
- **B3 · `POST /api/trocar-senha`.** Grava novo hash, zera a flag, emite token. *Teste:
  1º acesso troca e depois loga normal.*
- **B4 · Guard de rota + `POST /api/esqueci-senha` (self-service).** Middleware de token
  (401 sem token); esqueci-senha gera nova temporária e **envia ao usuário**; resposta
  genérica + rate-limit. *Teste: rota protegida sem token→401; reset envia e-mail (mock).*

### Bloco C — Backend: contexto de login
- **C1 · `GET /api/contexto` (protegida).** E-mail do token → grupo → UFs/contratos
  filtrados. *Teste: equatorial → só EQUATORIAL; enbpar → 41; domínio desconhecido → vazio.*

### Bloco D — Backend: parsing + validação
- **D1 · Parser do `.xlsx`.** `planilha.py`: aba `Preenchimento`, cabeçalho linha 2,
  mapeamento por nome, leitura defensiva de data/coordenada, definição de linha de dados
  (ODI/UC). *Teste: fixture → linhas; sem aba/não-.xlsx → 400; 0 linhas → guarda de erro.*
- **D2 · Domínios do modelo.** Lê listas válidas da aba `Dominios`. *Teste: retorna
  Tipo de Atendimento/UF/Tipo de Comunidade/Enquadramento/Sim-Não.*
- **D3 · Regras de formato/domínio.** Campos vazios=erro (em linha com ODI/UC), domínio=erro,
  duplicado ODI+UC=erro; coordenadas=**aviso**, data fora 2026=aviso, tipologia≠Sim/Não=aviso,
  "0"+outra=aviso. *Teste: fixture por regra acende o grupo certo c/ severidade.*
- **D4 · Regras de cruzamento com `entrada/`.** ODI+UC inexistente=erro, UF/município
  divergente=erro, UCs faltando=aviso. *Teste: fixtures vs referência mock.*
- **D5 · Montagem da resposta.** `grupos` + `previewRows` + totais + `ok`. *Teste:
  planilha limpa → ok=true, 0 erros; suja → grupos/totais corretos.*

### Bloco E — Backend: envio + endpoints finais
- **E1 · E-mail (`email_envio.py`).** smtplib via `.env`, dry-run, anexo
  `Anexo V preenchido - {contrato}.xlsx` (byte a byte), destinatários únicos; alerta
  crítico; credenciais/senha temporária ao usuário. *Teste: SMTP mock confirma nome do
  anexo, anexo intacto, destinos.*
- **E1-smoke · Smoke manual com SMTP real.** Configurar `.env` real e disparar para uma
  **caixa de teste** os 3 tipos: planilha validada (anexo chega), alerta crítico,
  credenciais. *Teste manual: e-mails reais chegam corretos (ver `TESTES.md`).*
- **E2 · `POST /api/validar` (orquestra, protegida).** Token→email; checa grupo (403),
  referência (409+alerta), erros→painel, ok→envia. *Teste e2e (TestClient, SMTP mock).*
- **E3 · `GET /api/modelo` (protegida).** Baixa o modelo oficial. *Teste: 200 +
  Content-Disposition + bytes do arquivo.*

### Bloco F — Front: religação (visual inalterado; +1 tela de troca de senha)
- **F1 · Camada de API.** `src/lib/api.js` (token no header) + `VITE_API_BASE`. *Teste:
  dev aponta p/ backend local.*
- **F2 · Login real + troca de senha.** `AuthScreen` → `/api/login`; nova `TrocarSenha`
  (reusa design system) no 1º acesso; "Esqueci minha senha" → `/api/esqueci-senha`.
  *Teste: 1º acesso força troca; depois entra direto.*
- **F3 · Contexto nos seletores.** `UfSelector`/`ContratoSelector` usam listas de
  `/api/contexto`. *Teste: equatorial só EQUATORIAL; enbpar tudo. Visual idêntico.*
- **F4 · Upload real.** `UploadAnexoV` envia `FormData` (arquivo+contrato+uf, token);
  mantém barra 3 fases. *Teste: upload real → resposta real.*
- **F5 · Roteamento real + painel por props.** `App` roteia painel/sucesso, remove
  `attempt`; `PainelInconsistencias` por props; `relatorioCsv` usa grupos reais; "Baixar
  modelo" → `/api/modelo`. *Teste: suja→painel; limpa→sucesso+e-mail.*

### Bloco G — Integração e deploy
- **G1 · E2E completo (local).** login→(troca)→contexto→upload→painel→corrige→sucesso→
  e-mail (dry-run). *Teste: roteiro ponta a ponta no navegador.*
- **G2 · Deploy + smoke real.** `DEPLOY.md`: uvicorn (systemd) + Nginx `/api` +
  `client_max_body_size` + `.env` + onde fica `usuarios.json`. *Teste: build + smoke no VPS,
  **com 1 envio real** (planilha validada + credenciais) para destinatário de homologação.*

> Cada sub-fase concluída é registrada em `planning/PLAN.md` com o resultado do teste.
