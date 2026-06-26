# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Governance (do not remove)

- **Do not edit `planning/PROJECT_BUILDING.md`.** All phases and progress tracking
  are recorded in **`planning/PLAN.md`**.
- All documentation lives in the **`planning/`** directory; the key document is
  **`planning/PLAN.md`** — read it first for current state and decisions.
- Deliver in **small, individually human-testable parts** (see PLAN.md "Fases").
- `planning/BEHAVIORAL_GUIDELINES.md` applies: state assumptions, prefer the minimum
  code that solves the problem, make surgical changes, no speculative abstractions.
- UI strings are **Brazilian Portuguese**. Keep them that way.

## What this repository is

A **non-functional static mock** of a web app called **"Classificação de
Beneficiários do Programa"** (a.k.a. *Anexo V — Painel de Monitoramento*). It exists
to demo the upload-and-validation UX to managers before any real validation engine is
built. There is **no backend and no real file parsing** — validation is fully
**scripted/routed** ("roteirada").

Domain (Programa Luz para Todos / MME / ENBPar): an operator uploads the monthly
"Anexo V" spreadsheet of energized consumer units (UCs) for a given **contract**; the
app would validate completeness against domain rules and either show an inconsistency
panel asking for corrections or save to the base. Here, that whole interaction is
faked with hardcoded data.

> Note: the all-source app lives under `modelo/`. An **earlier, unrelated NF/GFIP
> mock** used to occupy `modelo/` and was deleted (PLAN.md "Consolidação de pastas").
> If you find references anywhere to "Recebimento de Notas Fiscais", SSE uploads, or a
> `installMockApi.js` fetch interceptor, they belong to that dead project — they do
> **not** describe this one.

## Backend (approved 2026-06-27 — not yet implemented)

The mock is approved to evolve into a real backend. **Read the spec first:**
`planning/specs/2026-06-26-backend-validacao-envio-anexo-v-design.md` (and `planning/PLAN.md`).
Summary of what's coming (don't assume it exists until built):

- **`backend/`** — FastAPI + uvicorn behind the same Nginx at **`/api`**. Validates the
  uploaded Anexo V **for real** against the CSVs in **`entrada/`**, then **emails** the
  validated `.xlsx` (as-is, attachment `Anexo V preenchido - {contrato}.xlsx`) to a
  configurable list. SMTP/secrets via `.env`.
- **Auth (real):** login/senha; admin provisions users via CLI; the system **emails the
  temporary password to the user** (change on first access); "esqueci minha senha" is
  self-service (emails a new temporary password). Users in **`backend/usuarios.json`**
  (pbkdf2 hashes, gitignored); signed token on protected routes. Adds **one new screen**
  (TrocarSenha) reusing the design.
- **Emails (4 types):** validated spreadsheet (→ recipients), critical alert (→ admin),
  credentials/temp password (→ user, on creation and reset). Automated tests **mock SMTP**;
  real sending is a **manual smoke test** (`planning/TESTES.md`).
- **Two-layer access filter:** email domain → grupo econômico (EQUATORIAL, ENERGISA,
  NEOENERGISA, ÂMBAR, CERCI, ENBPAR) → visible UFs/contratos. ENBPAR sees all.
- **Validation:** ODI+UC cross-check + UF/município vs `entrada/` + format/domain rules
  (domains read from the model's `Dominios` sheet). Coordenadas inválidas = **aviso**;
  empty required cells in filled rows (with ODI/UC) = **erro**; zero data rows = erro.
- **Front rewiring keeps the approved visual unchanged** — only behavior changes
  (real upload, real painel data via props, auto-email).
- Tests are **pytest** under `backend/tests/` (see `planning/TESTES.md`). Implementation
  is split into human-testable sub-phases (Blocos A–G, §17 of the spec).

## Commands

All **front** commands run from `modelo/`. Requires **Node.js 20.19+ or 22.x** (Vite 7).

```bash
npm install
npm run dev      # Vite dev server on port 5175
npm run build    # produces modelo/dist/ (static SPA; this IS the deployable artifact)
npm run preview
```

There are **no tests, linter, or type-checker**. Don't claim test/lint results.
`DEPLOY.md` (repo root) covers hosting `modelo/dist/` on an Nginx VPS.

## Architecture

### Pure local-state mock — no fetch interceptor

Unlike the old NF mock, this project does **not** intercept `window.fetch`. Because
validation is 100% routed and there is no real frontend counterpart to mirror, the app
drives everything from **React state + routed data in `src/seedData.js`** directly
(PLAN.md "Simplificação de implementação"). A page reload resets to the login screen.

### App flow (`src/App.jsx`)

`App.jsx` is the single stateful container. Gating sequence, each guard returning a
full-screen step until satisfied:

`AuthScreen` (login, mock) → `MenuPrincipal` (module hub) → `UfSelector` (pick UF) →
`ContratoSelector` (pick a non-"Encerrado" contract) → `VersaoPlanilha` (Passo 3:
confirm spreadsheet version) → **logged-in shell**.

Inside the shell, `view` switches between `upload` → `painel` → `sucesso`. The
**contract is the primary key** of the flow; UF is just the grouping above it. The
topbar shows `UF · contrato.numero` and offers "Trocar Contrato" (clears both).

### The scripted two-attempt validation loop

This is the core illusion and it lives in two places:

- `UploadAnexoV.jsx` **ignores the real dropped/selected file** — it synthesizes a
  filename (`Anexo V - …_{UF}.xlsx`), runs a fixed 3-phase progress timer
  (① Leitura · ② Validação · ③ Conferência), then calls `onComplete()`.
- `App.handleValidated()` routes by attempt number: **attempt 1 → `painel`**
  (show errors), then "Corrigir e reenviar" bumps to **attempt 2 → `sucesso`**
  ("validada e salva na base"). The 2nd upload is always treated as clean.

So the inconsistency panel always shows the same routed findings on the first pass and
never on the second.

### Data: real contracts, faked everything else (`src/seedData.js`)

- `src/base_contratos.json` is **real** contract data (≈113 contracts). `seedData.js`
  derives the exported `CONTRATOS` (filtered to `vigente !== "Encerrado"`) and `UFS`
  (only UFs that have a selectable contract) from it. **Treat `base_contratos.json` as
  source data — don't hand-edit it to change UI behavior.**
- `mockUcsContrato(numero)` — the "N UCs cadastradas" count shown per contract is
  **MOCK**, a stable hash of the contract number, *not* from the real base. In the real
  system it comes from the backend.
- `RULE_GROUPS`, `PREVIEW_COLS`, `PREVIEW_ROWS`, `LINHAS_LIDAS`, `TOTAL_ERROS`,
  `TOTAL_AVISOS` — the entire inconsistency panel and spreadsheet preview are routed
  here. Severity `"err"` blocks saving; `"warn"` does not. The rule names mirror the
  real Anexo V domains (empty required fields, value out of domain, invalid
  coordinates, duplicate ODI+UC key, "0 - Não é prioridade" conflicts, energization
  date outside 2026, tipologia ≠ Sim/Não) but the rows are illustrative, not computed.

### Real client-side download (`src/lib/relatorioCsv.js`)

The panel's "Baixar relatório (.csv)" actually generates and downloads a file in the
browser (Blob + anchor): UTF-8 BOM, `;` separator (Excel pt-BR), quotes only when a
field contains `;`/`"`, ObjectURL revocation deferred via `setTimeout(0)` (revoking
immediately cancels the download). `modelo_relatorio_inconsistencias.csv` at the repo
root is the model/reference for what that download should produce.

## Conventions when editing

- **`descreverContrato(c)`** in `seedData.js` is the canonical contract label
  (`"ECM 018/2025 - MLA, 2ª Tranche"`). Reuse it; don't re-format inline.
- Reuse the existing design system in `src/styles.css` (blue/navy, 8pt spacing rhythm,
  `.card`/`.topbar`/`.dropzone`/`.status-*`/`.auth-shell` etc.) rather than inventing
  new visual patterns.
- "Baixar modelo" in `VersaoPlanilha.jsx` is a deliberate stub (no real download); the
  version date is a constant in the component. Keep stubs as stubs unless asked.
- After completing a phase or making a notable design decision, record it in
  `planning/PLAN.md` (not in PROJECT_BUILDING.md).

## Repo layout & ignored paths

This **is** a git repository; `origin` is
`github.com/GiovanniCharret/sistema_gclt_demo.git` (default branch `main`). Gitignored
(treat as personal/out-of-scope inputs, not app code): **`manuais/`** (domain source
material), **`minhas_notas/`**, **`planning/`**, **`bug_fix/`**, plus `node_modules/`,
`dist/`, this `CLAUDE.md`, and `plano_classificacao_beneficiarios.html`. The app source
is entirely under `modelo/src/`.

**`entrada/`** is an untracked working-data folder (`entrada/lpt/`, `entrada/mla/`
hold `consolidado*.csv` extracts). It is **not** gitignored but is **not** app
code — treat it as scratch/input data, don't import from it into `modelo/src/`, and
don't commit it unless asked.

## Coding Style

Toda função com docstring explicando, nesta ordem: por que a função existe (o problema que ela resolve / o motivo de ser função separada); a lógica do input ao output, em fases numeradas (Entrada → Fase 1 → Fase 2 → … → Saída), descrevendo o que cada bloco transforma. Além disso, toda linha de código comentada — inclusive as que parecem óbvias.

## Tests

Always include e2e tests to cover important paths. You should always make sure that the plans include a test suite that covers the happy paths and edge cases. Your tests should be high quality and give confidence while covering most of the implementation.
