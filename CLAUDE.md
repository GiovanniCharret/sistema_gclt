# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Governance (do not remove)

- **Do not edit `planning/PROJECT_BUILDING.md`.** All phases and progress tracking
  are recorded in **`planning/PLAN.md`**.
- All documentation lives in the **`planning/`** directory; the key document is
  **`planning/PLAN.md`** — read it first for current state and dated decisions.
- **Product versioning (since 2026-07-07): V0 DELIVERED** (production live at
  `gerenciador-gclt.com`); **V1 in planning**. Version scope, known limitations and
  the V1 backlog live in **`planning/VERSOES.md`** — V1 work is tracked there
  (dated decisions still go to PLAN.md). Each closed version gets a git tag (`v0`, …).
- Deliver in **small, individually human-testable parts** (see PLAN.md "Fases").
- `planning/BEHAVIORAL_GUIDELINES.md` applies: state assumptions, prefer the minimum
  code that solves the problem, make surgical changes, no speculative abstractions.
- UI strings are **Brazilian Portuguese**. Keep them that way.

## What this repository is

A **real, deployed web app** called **"Classificação de Beneficiários do Programa"**
(a.k.a. *Anexo V — Painel de Monitoramento*). An operator uploads the monthly "Anexo V"
spreadsheet of energized consumer units (UCs) for a given **contract**; the backend
**parses and validates it for real** against domain rules + reference data, shows an
inconsistency panel if there are errors, and — when clean — **emails the validated
`.xlsx`** to a configurable recipient list.

Domain: Programa Luz para Todos / MME / ENBPar.

> **History (important — avoids confusion):** this project **began as a non-functional
> static mock** (routed/faked validation, no backend). That mock was approved to become
> a real backend on 2026-06-27 and shipped as **V0** (Blocos A–G, all done). Vestiges of
> the mock era survive and are **dead code** — see "Front architecture" below. Also: an
> **earlier, unrelated NF/GFIP mock** used to occupy `modelo/` and was deleted. Any
> reference anywhere to "Recebimento de Notas Fiscais", SSE uploads, or an
> `installMockApi.js` fetch interceptor belongs to that dead project — it does **not**
> describe this one.

## Backend — FastAPI (V0 delivered; spec in `planning/specs/2026-06-26-…-design.md`)

The backend is **real and complete** (Blocos A–G). FastAPI + uvicorn behind the same
Nginx at **`/api`** in production (`/opt/anexov`, systemd unit `anexov-api`). Modules
under `backend/`:

- **`app.py`** — the ASGI `app`; dev CORS (Vite :5175); all routes:
  `GET /api/health`, `POST /api/login`, `POST /api/trocar-senha`,
  `POST /api/esqueci-senha`, `POST /api/validar` (multipart upload → painel),
  `GET /api/modelo` (download the official model), `GET /api/contexto` (grupo → UFs/contratos).
- **`auth.py`** — real login/senha; signed token on protected routes; first-access
  password change; self-service reset. `admin_usuarios.py` is the CLI that provisions
  users (`criar_usuario`) and **emails the temporary password**. Users live in
  **`backend/usuarios.json`** (pbkdf2 hashes, **gitignored**, VPS-only — see secrets below).
- **`acesso.py`** — two-layer access filter: email domain → grupo econômico
  (EQUATORIAL, ENERGISA, NEOENERGISA, ÂMBAR, CERCI, ENBPAR) → visible UFs/contratos.
  ENBPAR sees all. `montar_contexto` builds `/api/contexto`. (ÂMBAR sigla uses U+00C2;
  the domain→grupo map may still be provisional — check the spec.)
- **`referencia.py`** — loads `entrada/**/*.csv` into memory (`chaves_uc`, `odi_ref`),
  **reloads on mtime change** (no restart). `carregar_base_contratos` reads the authority
  `base_contratos.json` (repo root) — **cached once per process, so a restart is needed
  if it changes.** `integridade()` classifies contracts com/sem referência + órfãos.
  Singletons `obter_referencia` / `obter_base_contratos`.
- **`planilha.py`** — `.xlsx` parser (`ler_preenchimento` reads the **`Preenchimento`**
  sheet, header on row 2, maps columns **by header name**, keeps only rows with ODI/UC).
  `ler_dominios`/`obter_dominios` read the model's **`Dominios`** sheet. Structural errors
  → `PlanilhaInvalida` (→ HTTP 400). Defensive `normalizar_id` / `normalizar_coordenada`
  / `normalizar_data`. `_MODELO_PADRAO` is the path to the versioned model file (see below).
- **`validacao.py`** — the validation core (see "Validation rules" below) + panel assembly.
- **`email_envio.py`** — the 4 email types (validated spreadsheet → recipients;
  critical alert → admin; credentials/temp password → user on creation and reset).
  Automated tests **mock SMTP**; real sending is a **manual smoke test** (`planning/TESTES.md`).
- **`config.py`** — process config (user store path, SMTP/secrets via `.env`).

### Validation rules (`backend/validacao.py`) — only `sev="err"` blocks the send

Per-line: empty required cells (**err**), value out of domain vs `Dominios` sheet
(**err**), invalid/out-of-range coordinates (**warn**), tipologia ≠ Sim/Não (**warn**),
and **"0 - Não é prioridade" consistency (err, 3 clauses)**: (0) column "0" is mandatory
— **blank "0" = err** (since 2026-07-14; also closes the "row with nothing marked" hole);
(1) if "0" = "Sim", all other tipologia columns must be "Não"; (2) if "0" = "Não",
at least one other tipologia must be "Sim" (clauses 1–2 err since 2026-07-09).
Cross-line: duplicate ODI+UC key (**err**),
duplicate UC regardless of ODI (**err**). Cross-check vs `entrada/`: ODI+UC not in the
contract's reference (**err**), UF/município divergent from the ODI's reference (**err**),
reference UCs missing from the sheet (**warn**). Zero data rows → "Planilha sem dados" (**err**).

> **The old "Data de energização fora de 2026" rule was removed (2026-07-09)** — any date
> is accepted; a **blank** date is still an error (it's a required field).

## Commands

**Front** commands run from `modelo/`. Requires **Node.js 20.19+ or 22.x** (Vite 7).

```bash
npm install
npm run dev      # Vite dev server on port 5175
npm run build    # produces modelo/dist/ (static SPA; this IS the deployable artifact)
npm run preview
```

The **front** has **no tests, linter, or type-checker** — don't claim front test/lint
results. `DEPLOY.md` (repo root) covers hosting `modelo/dist/` on the Nginx VPS.

**Backend** commands run from the **repo root** (`.venv` lives at root, created with `uv`):

```bash
uv venv                                    # create .venv (CPython 3.12) — first time only
uv pip install -r backend/requirements.txt
.venv\Scripts\python.exe -m pytest backend/tests/ -v            # run the suite (105 green)
.venv\Scripts\python.exe -m pytest backend/tests/test_validacao.py -v -k tipologia   # single file / -k filter
.venv\Scripts\python.exe -m uvicorn backend.app:app --port 8000 # run the API
```

The **backend HAS pytest tests** (`backend/tests/`, ~105 green; see `planning/TESTES.md`)
— run them and report real results. `TestClient` needs **`httpx2`**, not `httpx`, on
starlette 1.3+. On Windows, kill stray `python` before a uvicorn smoke test (an orphan
holding the port silently serves stale code); prefer a fresh port.

## Architecture

### Front ↔ backend (real API)

The React SPA (`modelo/src/`) talks to the backend through **`src/lib/api.js`** (the
single fetch layer: base URL `/api` in prod, `http://127.0.0.1:8000/api` in dev; Bearer
token on protected routes). There is **no fetch interceptor** and **no mock** — every
call is real.

**`src/App.jsx`** is the single stateful container and orchestrator. Gating sequence,
each guard a full-screen step until satisfied:

`AuthScreen` (real login) → *(first access →)* `TrocarSenha` → `MenuPrincipal` →
**fetch `/api/contexto`** (grupo → UFs/contratos) → `UfSelector` → `ContratoSelector`
→ `VersaoPlanilha` (Passo 3) → **logged-in shell** (`upload` → `painel` → `sucesso`).

Inside the shell: `UploadAnexoV` posts the **real file** to `/api/validar`; the response
(`{ok, grupos, previewRows, totalErros, totalAvisos, linhasLidas}`) drives `onValidated`
→ `sucesso` if `ok`, else `painel`. `PainelInconsistencias` and `SucessoEnvio` render
directly from that response (props). The **contract is the primary key** of the flow;
UF is just the grouping above it.

### Legacy mock vestiges (dead code — don't wire new work to them)

`src/seedData.js` still exports mock routed data — **`RULE_GROUPS`, `PREVIEW_ROWS`,
`TOTAL_ERROS`, `TOTAL_AVISOS`, `CONTRATOS`, `UFS`** — but **nothing imports them anymore**
(superseded by `/api/contexto` and `/api/validar` in Bloco F). Only two exports survive:
**`descreverContrato(c)`** (canonical contract label, used by `App.jsx`) and
**`PREVIEW_COLS`** (column headers, used by `PainelInconsistencias`). The footer still
reads "Mock · …" — a cosmetic leftover, not a description of behavior. Treat the dead
exports as removable, not as source of truth.

### The official model file is VERSIONED

The Anexo V model lives in **`manuais/`** (committed to the repo) with a **version-stamped
name**: `Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.vDDMMAA.xlsx` (current:
`.v260714.xlsx` = 14/07/2026). `GET /api/modelo` serves it from disk each request (no
restart to swap contents). **Per new model version, update all of:** `_MODELO_PADRAO`
(`backend/planilha.py`), the `a.download` filename (`modelo/src/lib/api.js`), `VERSAO_DATA`
(`VersaoPlanilha.jsx` + `relatorioCsv.js`), and the download test (`backend/tests/test_api.py`
asserts the version string). Then **commit the `.xlsx`** — `manuais/` is tracked, so the VPS
`git pull` carries the new model (**no scp needed**). See the latest model-swap decision in PLAN.md.

### Real client-side download (`src/lib/relatorioCsv.js`)

The panel's "Baixar relatório (.csv)" generates and downloads a file in the browser
(Blob + anchor): UTF-8 BOM, `;` separator (Excel pt-BR), quotes only when a field
contains `;`/`"`, ObjectURL revocation deferred via `setTimeout(0)` (revoking immediately
cancels the download). `modelo_relatorio_inconsistencias.csv` at the repo root is the
reference for what that download should produce.

## Conventions when editing

- **`descreverContrato(c)`** in `seedData.js` is the canonical contract label
  (`"ECM 018/2025 - MLA, 2ª Tranche"`). Reuse it; don't re-format inline.
- Reuse the existing design system in `src/styles.css` (blue/navy, 8pt spacing rhythm,
  `.card`/`.topbar`/`.dropzone`/`.status-*`/`.auth-shell` etc.) rather than inventing
  new visual patterns. **Front rewiring keeps the approved visual unchanged** — change
  behavior, not the look, unless asked.
- After completing a phase or making a notable decision, record it in **`planning/PLAN.md`**
  (dated), not in PROJECT_BUILDING.md.

## Repo layout & ignored paths

This **is** a git repository; `origin` is
`github.com/GiovanniCharret/sistema_gclt.git` (default branch `main`). The `.gitignore`
follows a **"commit everything" policy** — so **`manuais/`** (domain source material +
**the official model**), **`planning/`**, and this **`CLAUDE.md`** are **committed**
(they ride `git pull` to the VPS). **Gitignored** (regenerable or secret only): `node_modules/`,
`dist/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `bug_fix/`, `minhas_notas/`, logs, and
secrets (`backend/usuarios.json`, `.env*`, `senha e-mail hostinger`). The front app source
is under `modelo/src/`; the backend under `backend/`.

**`entrada/`** holds the backend's reference data (`entrada/lpt/`, `entrada/mla/` with
`consolidado*.csv`; BOM UTF-8, `;`-separated). It **is committed** (versioned). It is
**not** front code — don't import it into `modelo/src/`. `backend/referencia.py` reads it.

**Daily update of `entrada/` (provisional):** the reference CSVs are refreshed daily in
production. As of **2026-07-09** the transport moved from git-pull to **SSH/scp** (script
lives in the neighboring `atualizacao_clientes` project; see PLAN.md + `VERSOES.md`).
Consequence: scp'ed CSVs diverge from the VPS working tree — **before any `git pull` on
the VPS, run `git checkout -- entrada/` first**; there is no VPS pull cron.

### Secrets — never commit

`.env` / `backend/.env`, **`backend/usuarios.json`** (production users live **only** on the
VPS; provisioned via the `criar_usuario` CLI / reset via "esqueci minha senha"), the SSH
private key (only the `.pub` goes to the VPS), and `senha e-mail hostinger` (repo root).
`usuarios.json` was briefly versioned (MVP 2026-07-07) then reverted 2026-07-08 — a
versioned copy would overwrite real production users. Old hashes remain in git history, so
**the repo must stay PRIVATE**. On the VPS, always run git/npm as `sudo -u deploy`; the
git remote uses a read-only PAT; no force-push, no touching tags.

## Coding Style

Toda função com docstring explicando, nesta ordem: por que a função existe (o problema que ela resolve / o motivo de ser função separada); a lógica do input ao output, em fases numeradas (Entrada → Fase 1 → Fase 2 → … → Saída), descrevendo o que cada bloco transforma. Além disso, toda linha de código comentada — inclusive as que parecem óbvias.

## Tests

Always include e2e tests to cover important paths. You should always make sure that the plans include a test suite that covers the happy paths and edge cases. Your tests should be high quality and give confidence while covering most of the implementation.
