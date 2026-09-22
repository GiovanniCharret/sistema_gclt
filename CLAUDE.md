# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Governance (do not remove)

- **Do not edit `planning/PROJECT_BUILDING.md`.** All phases and progress tracking
  are recorded in **`planning/PLAN.md`**.
- All documentation lives in the **`planning/`** directory; the key document is
  **`planning/PLAN.md`** — read it first for current state and dated decisions.
  ⚠️ Since the **handoff of 2026-07-17**, `planning/` (and `.claude/`) are **gitignored
  and untracked** — they exist on the local machine only and no longer reach the server,
  and they are invisible to anyone who clones the repo. They are still the working log:
  keep writing to them, and **cross-check `git log`** when reading history (decisions from
  2026-07-16 → 07-22 were backfilled into PLAN.md on 2026-07-29 from the commit messages).
- **Product versioning (since 2026-07-07): V0 DELIVERED** (first live at
  `gerenciador-gclt.com`; **production is now the Azure deploy**, and the Hostinger VPS is a
  test bed — see "Deploy"); **V1 in planning**. Version scope, known limitations and
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
Nginx at **`/api`** (Docker compose in both live targets — see "Deploy"). Modules
under `backend/`:

- **`app.py`** — the ASGI `app`; dev CORS (Vite :5175); all routes:
  `GET /api/health`, `POST /api/login`, `POST /api/trocar-senha`,
  `POST /api/esqueci-senha`, `POST /api/validar` (multipart upload → painel),
  `GET /api/modelo` (download the official model), `GET /api/contexto` (grupo → UFs/contratos).
- **`auth.py`** — real login/senha; signed token on protected routes; first-access
  password change; self-service reset. **Login is by `operador`, not by e-mail** (see
  below). `admin_usuarios.py` is the CLI that provisions users
  (`python -m backend.admin_usuarios add <operador>` / `disable <operador>`) and **prints**
  the temporary password (the credentials e-mail is not wired in the operador fallback).
  Users live in **`backend/usuarios.json`** (pbkdf2 hashes) — **tracked again since the
  handoff (2026-07-17)**, seeded with the 6 operadores at `Senha123` + forced change on
  first access. ⚠️ Anything that replaces the file on a server **resets passwords to the
  seed** — a `git pull`, or a Docker `--build` that bakes the repo's copy into the image.
- **`acesso.py`** — two-layer access filter: **operador** → grupo econômico
  (EQUATORIAL, ENERGISA, NEOENERGISA, ÂMBAR, CERCI, CEMIG, ENBPAR) → visible UFs/contratos.
  ENBPAR sees all. `MAPA_OPERADOR_GRUPO` / `grupo_do_operador` / `siglas_do_grupo` /
  `contratos_visiveis`; `motivo_acesso_negado` builds the **diagnostic reason** behind a
  403 (operador's grupo × the contract's distribuidora/UF, "contrato inexistente",
  "operador sem grupo"). `montar_contexto` builds `/api/contexto` (payload key `operador`).
  (ÂMBAR sigla uses U+00C2.)

  > **Login by `operador` (2026-07-15, temporary fallback; e-mail login deferred to V1/V2).**
  > The operador is the domain label without `nome@` and without `.com.br`/`.gov.br`:
  > `equatorialenergia`, `energisa`, `neoenergia`, `ambarenergia`, `cerci`, `cemig`, `enbpar`
  > (wildcard). Anything in the older docs/spec that says "e-mail domain → grupo",
  > `MAPA_DOMINIO_GRUPO` or `grupo_do_email` describes the **pre-2026-07-15** shape.
- **`referencia.py`** — loads `entrada/**/*.csv` into memory (`chaves_uc`, `odi_ref`),
  **reloads on mtime change** (no restart). Which index a file feeds is decided **by its
  header columns, not by filename** (`uc` → `chaves_uc`; `uf`+`municipio` → `odi_ref`;
  the branches are independent, so one file carrying all four columns feeds **both**).
  `carregar_base_contratos` reads the authority
  `base_contratos.json` (repo root) — **cached once per process, so a restart is needed
  if it changes.** `integridade()` classifies contracts com/sem referência + órfãos.
  Singletons `obter_referencia` / `obter_base_contratos`.
- **`planilha.py`** — `.xlsx` parser (`ler_preenchimento` reads the **`Preenchimento`**
  sheet, header on row 2, maps columns **by header name**, keeps only rows with ODI/UC).
  `ler_dominios`/`obter_dominios` read the model's **`Dominios`** sheet. Structural errors
  → `PlanilhaInvalida` (→ HTTP 400). Defensive normalizers, all used by the cross-check:
  `normalizar_id` (ODI/UC), `normalizar_coordenada`, `normalizar_data`,
  **`normalizar_nome`** (canonical form: strips accents, strips **all** spaces, casefold —
  "RORAINÓPOLIS" == "RORAINOPOLIS") and **`normalizar_uf`** (equates the sigla "AP" to the
  spelled-out "Amapá", since the LPT reference file spells UFs out).
  `_MODELO_PADRAO` is the path to the versioned model file (see below).
- **`validacao.py`** — the validation core (see "Validation rules" below) + panel assembly.
  All **vocabulary** comparisons are **case-insensitive** (`casefold`, since 2026-07-15:
  "SIM" == "Sim") — but **accents still matter** ("NAO" is invalid). Detail rows per group
  are capped at `_ROWS_MAX` (200) in the payload while `count` stays the real total.
- **`email_envio.py`** — the 4 email types (validated spreadsheet → recipients;
  critical alert → admin; credentials/temp password → user on creation and reset).
  Automated tests **mock SMTP**; real sending is a **manual smoke test** (`planning/TESTES.md`).
  Note: `enviar_credenciais` is **not called** in the current operador fallback (the CLI
  prints the password; `esqueci-senha` resets to `Senha123`) — it is kept for V1/V2.
- **`config.py`** — process config (user store path, SMTP/secrets via `.env`), plus the
  flag `odi_uc_novo_como_aviso` — **`True` is the rule since 2026-09-22** (see the note
  under "Validation rules").

### Validation rules (`backend/validacao.py`) — only `sev="err"` blocks the send

Per-line — **no blank cell is allowed in a row that has ODI/UC** (since 2026-07-30): all
15 identification columns are in `OBRIGATORIOS` → "Campos obrigatórios vazios" (**err**),
and all 51 tipologia columns must hold Sim/Não → **"Tipologia em branco" (err)**, emitted
**once per row** naming the blank columns (a per-cell finding would mean 9 310 occurrences
on a real 490-row file). Column O keeps its own older rule, so it is excluded from this one.
Asymmetry worth knowing: identification columns are checked even when the column is
**absent** from the sheet (fixed list), while tipologia is only checked for columns the
sheet actually has.

> **`CPF/CNPJ` — the 15th identification column (2026-08-28).** The MME appended it as the
> **last column** of `Preenchimento` (BA; 52 → 53 columns). `COL_CPF` carries **exactly one
> rule, the same as its peers: it must not be blank** — no mask, no digit count, no check
> digit, so `123.456.789-01`, `12345678901` and free text all pass. It must sit in **both**
> `OBRIGATORIOS` **and** `COLS_IDENTIFICACAO`: `_colunas_tipologia` defines tipologia by
> exclusion, so an identification column left out of that set would be demanded as Sim/Não.
> Test fixtures follow — `CABECALHO_PADRAO` (`tests/fixtures.py`) and both valid-line
> builders carry the column.
>
> Historical note: for one day the plan was a **`Preenchimento_AUX.`** mirror sheet
> (formulas `=Preenchimento!…` over the original 52 columns) so the parser would not have to
> change. **That was rolled back on 2026-08-28** and never implemented — `_ABA` stays
> `"Preenchimento"`. Ignore any reference to `Preenchimento_AUX.` or to a `STATUS` column.

Also per-line: value out of domain vs `Dominios` sheet
(**err**), coordinates non-numeric or outside **Brazil's range** (**warn** — `_FAIXA_LAT`
= −34.5…+6.0, `_FAIXA_LON` = −74.5…−34.0, tightened from the world range on 2026-07-30),
tipologia filled with something other than Sim/Não (**warn**),
and **"0 - Não é prioridade" consistency (err, 3 clauses)**: (0) column "0" is mandatory
— **blank "0" = err** (since 2026-07-14; also closes the "row with nothing marked" hole);
(1) if "0" = "Sim", all other tipologia columns must be "Não"; (2) if "0" = "Não",
at least one other tipologia must be "Sim" (clauses 1–2 err since 2026-07-09) —
**clause 2 EXEMPTS rows with N = CadÚnico since 2026-08-04** (see below).
**Enquadramento (col N) × "0 - Não é prioridade" (col O) — err, since 2026-07-29,
relaxed 2026-08-04:** N = `2 - Famílias inscritas no CadÚnico` forces **O = "Não"**, and
N = `0 - Não é prioridade` forces **O = "Sim"** (`_ENQUAD_EXIGE_ZERO`); every other
enquadramento leaves O free. The old rule (2) — CadÚnico requiring **at least one "Sim"
among P:AZ** — was **dropped on 2026-08-04** (fallback, model v260804): with N = CadÚnico
the tipologias are free (all "Não" is valid), which required exempting those rows from
"0"-clause-2 too (title "CadÚnico sem tipologia assinalada" no longer exists).
⚠️ Consequence: M ∈ {1,2,3,4} **combined with** N = `0 - Não é prioridade` is
**unsatisfiable** (N=0 → O="Sim" → clause 1 forces every tipologia to "Não", but M forces
the family column to "Sim") — the operator must change M or N.

**Tipo de Comunidade × família (err, since 2026-07-29)** — direction M→U:X only, no reverse
check: when column M is `1 - indígena` / `2 - quilombola` / `3 - ribeirinha` /
`4 - extrativista`, the **matching** family column must be "Sim" — 1→IV.1 (U), 2→IV.2 (V),
3→IV.3 (W), 4→IV.4 (X). **The other family columns are free** (may be "Sim"); types 5–12
trigger nothing. This replaced the 2026-07-14 pair of warnings: the mutual-exclusivity half
("the other families must be Não") and the whole **Enquadramento = `4 - Povos tradicionais`
rule (column N) were dropped**, and the severity went warn → **err**.

Cross-line: duplicate ODI+UC key (**err**),
duplicate UC regardless of ODI (**err**), **duplicate (lat, lon) pair within the uploaded
sheet** (**err**, since 2026-07-30 — `_coordenadas_duplicadas`; rows with an unreadable
coordinate are skipped so they don't all "match" each other). Cross-check vs `entrada/`: ODI+UC not in the
contract's reference (**err**), UF/município divergent from the ODI's reference (**err**,
compared via `normalizar_uf`/`normalizar_nome`, so accent/space/sigla noise in the base
does not trigger it), reference UCs missing from the sheet (**warn** — lists each missing
ODI+UC, not just the count). Zero data rows → "Planilha sem dados" (**err**).

> **⚠️ "Dado novo" as a warning — flag `odi_uc_novo_como_aviso` (created 2026-09-16; THE RULE
> since 2026-09-22).** Born as a workaround: the legacy SQL that feeds `entrada/` broke, so
> newly energized UCs never reached the reference and "ODI + UC não consta na referência" would
> block every send. The flag in `backend/config.py` is **`True` — the rule** (the user switched
> production on with web commit `aa53514` and declared it the default); **`False` is the second
> path**: every ODI+UC outside the base is an error again, as before 2026-09-16, used only by
> explicit decision. Env override `ODI_UC_NOVO_COMO_AVISO`; read once per process → **restart
> after flipping**. It touches **only that rule**, and only under a **strict** condition decided
> over the whole sheet in `regras_cruzamento` (Fase 0): the contract's base is **not empty**
> **and every UC already in the base ("já cadastrada") is present in the sheet**. Then each
> unknown pair becomes **warn** ("dado novo — ainda não cadastrado na base"); otherwise it
> stays **err**, and the suggestion says why: *"a base tem X UCs ausentes na planilha; UCs novas
> só são aceitas como aviso quando todas as UCs já cadastradas estiverem presentes"*. "UCs
> faltando" rows also read "já cadastrada na base". The strict all-or-nothing check is
> deliberate: a mistyped existing UC removes the correct pair from the sheet, so the typo keeps
> erroring. **Unchanged:** the **409** for a contract with no reference at all (only contracts
> that already received ODIs qualify), "UF / município divergente" (err), and every other rule.
> The severity reaches the pure `validar`/`regras_cruzamento` as a **parameter**
> (`novo_como_aviso`; their `False` default only keeps the functions pure — the system default
> comes from `config.py`); only `app.py` reads the config. Same value and same text on the
> production repo's `main` **and** both feature branches (kept identical so merges don't conflict).

`_DESCRICOES` (`validacao.py`) is the authoritative list of rule titles + panel blurbs —
read it rather than trusting a prose summary.

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
results. (`modelo/package.json`'s description still calls the app a "mock estatico
nao-funcional" — a leftover, like the footer; ignore it.) See "Deploy" below.

**Backend** commands run from the **repo root** (`.venv` lives at root, created with `uv`):

```bash
uv venv                                    # create .venv (CPython 3.12) — first time only
uv pip install -r backend/requirements.txt
.venv\Scripts\python.exe -m pytest backend/tests/ -v            # run the suite (166 green)
.venv\Scripts\python.exe -m pytest backend/tests/test_validacao.py -v -k tipologia   # single file / -k filter
.venv\Scripts\python.exe -m uvicorn backend.app:app --port 8000 # run the API
```

The **backend HAS pytest tests** (`backend/tests/`, **166 green** as of 2026-09-16; see
`planning/TESTES.md`)
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

`AuthScreen` (real login — field is **"Operador"**, plain text, not e-mail) →
*(first access →)* `TrocarSenha` → `MenuPrincipal` →
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

### `base_contratos.json` — the contract authority (and its stale front twin)

**`base_contratos.json` at the repo root is the single authority** (115 contracts as of
2026-09-01), read only by `backend/referencia.py::carregar_base_contratos` and **cached
once per process** — edit it and you must restart uvicorn (unlike `entrada/`, which
reloads on mtime). Each entry is keyed by the contract number and carries:
`sigla`, `cnpj`, `tranche`, `uf`, `valor_contrato`, `valor_cde`, `participacao_cde`,
`tipo_contrato`, `vigente`, **`data_operacionalizacao`** and **`qtd_ucs`**.

- **`sigla` is the *distribuidora*, not the economic group** — deliberately. It is the
  value `MAPA_GRUPO_SIGLAS` (`acesso.py`) matches against, so "fixing" it to the group
  label silently breaks the access filter. The BI spreadsheets use the group form; that
  divergence is expected, not a bug.
- **`data_operacionalizacao` (2026-08-27) and `qtd_ucs` (2026-08-28) are carried but read
  by no code yet** — no backend module and no front component references either. They are
  data staged for a future feature; don't assume a consumer exists.
- Selectable contracts = `vigente != "Encerrado"` (**43** today, what the ENBPAR wildcard
  sees; two `test_api.py`/`test_acesso.py` tests hardcode that number — bump both when a
  non-encerrado contract is added).
- The file is **CRLF**. Rewrite it with a Python script (`json.dump`, `indent=2`,
  `ensure_ascii=False`), never `sed -i`, or the whole file shows as changed.

⚠️ **`modelo/src/base_contratos.json` is a SECOND, STALE copy** (113 contracts, missing
`data_operacionalizacao`/`qtd_ucs`). It exists only because `seedData.js` imports it to
build the **dead** `CONTRATOS`/`UFS`/`contratosDaUf` exports (see above). **Do not sync it**
— the real contract list reaches the front through `/api/contexto`. It is removable along
with the rest of the mock vestiges.

### The official model file is VERSIONED

The Anexo V model lives in **`manuais/`** (committed to the repo) with a **version-stamped
name**: `Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.vDDMMAA.xlsx`, plus an
optional `-N` suffix for a same-day revision (current: **`.v260828.xlsx`** = model of
28/08/2026 — `VERSAO_DATA` = `28/08/2026`; **`Dominios` byte-identical to `.v260804`**, the
only change being the new **`CPF/CNPJ`** column at the end of `Preenchimento`, 52 → 53
columns). `GET /api/modelo` serves it from disk each request (no
restart to swap contents). **Per new model version, update all of:** `_MODELO_PADRAO`
(`backend/planilha.py`), the `a.download` filename (`modelo/src/lib/api.js`), `VERSAO_DATA`
(`VersaoPlanilha.jsx` + `relatorioCsv.js`), and the download test (`backend/tests/test_api.py`
asserts the version string). Then **commit the `.xlsx`** — `manuais/` is tracked, so the deploy
carries the new model (Azure: the workflow's `git pull`; Hostinger: inside the `git archive`
package) — **no separate scp needed**. See the latest model-swap decision in PLAN.md.

### Deploy — two live targets

1. **Hostinger VPS (`gerenciador-gclt.com`) — TEST BED, not production.** Rebuilt from
   scratch on **2026-09-02**: the old stack (`/opt/anexov`, systemd `anexov-api`,
   `git pull` + `npm run build`) **no longer exists**. It now runs the **production repo**
   (`enbpar-sistema-gclt`) with its `docker/docker-compose.yml` in `/opt/enbpar`; a
   `docker-compose.override.yml` binds the front container to `127.0.0.1:8080`, behind the
   host's Nginx + certbot. There are **no git credentials on the server**: updates are
   `git archive` + `scp` + `docker compose up -d --build` (runbook
   `DEPLOY_VPS_DOCKER_VIA_SSH.md`, gitignored). It is where the branch
   **`feature/login-canonico-e-perfis`** is tested before being merged (see "Branches" under
   the sibling repo). `DEPLOY.md`, `DEPLOY_HOSTINGER.html` and `deploy_hostinger.sh`
   (gitignored at the 2026-07-17 handoff) describe the **pre-2026-09-02** stack.
2. **Azure / Ubuntu 24 + Docker — PRODUCTION (handed to the company's engineers)**, deployed
   from the production repo's `main` — **`DEPLOY_AZURE.md`**
   (+ `.html`) is the current guide, aimed at `monitoramentolpt.enbpar.gov.br`.
   `docker/docker-compose.yml` builds two images from the repo root: `Dockerfile-backend`
   (python:3.12-slim, `uvicorn backend.app:app` on :8000, **runs from the repo root** because
   `config.py`/`planilha.py`/`referencia.py` read relative paths) and `Dockerfile-frontend`
   (a Node stage **runs `npm run build` inside the image**, then nginx:alpine serves that
   `dist/` + `modelo/nginx.conf` — no pre-built `dist/` needed; published on
   :80). In compose the front proxies `/api/` to `http://backend:8000` (service name, not
   `127.0.0.1`), `client_max_body_size 50m`.

Note that `POST /api/validar` returns **diagnostic** `detail` strings (403 says which grupo
vs which owner; 409 says the contract is visible but has no ODIs/UCs loaded), and
`UploadAnexoV.jsx` shows the raw status + detail on screen. That is deliberate (2026-07-22)
— don't "soften" those messages back.

### The sibling production repo (`monitoramentolpt_producao_enbpar/`)

Deploy target 2 lives in a **separate local repo and separate GitHub remote**:
`../monitoramentolpt_producao_enbpar` → **`github.com/enbpar/enbpar-sistema-gclt`**
(this repo's remote is `github.com/GiovanniCharret/sistema_gclt`). It is a near-copy of
this codebase, and **backend/front changes must be applied to both by hand** — there is no
automation. Push to its `main` **triggers the production deploy**, so commit/push there
only when explicitly asked.

**Branches — check `git branch --show-current` before touching that clone.**
- **`main`** — what production (Azure) runs; a push deploys. **Everything this project changes
  in that repo goes to `main`**, including the routine data commits (`base MM-DD` =
  `entrada/`).
- **`feature/login-canonico-e-perfis`** — the new login (e-mail + perfis: `backend/identidade/`,
  SQLAlchemy, tests under `backend/tests/identidade/`). **Owned by another project** — the
  Claude Code project in **`../site_sistema_amostral_com_os`**, whose `docs/PLAN.md` numbers the
  production phases **P1–P9** and whose `docs/` holds the specs (login: `2026-09-08-…`,
  `2026-09-15-…`). **The admin + audit area of the `gerente` profile is its P2**, not work for
  this project. The branch is tested on the Hostinger VPS and only then merged into `main`.
  From here, **don't commit, stash, merge, rebase or push on it — and don't suggest doing so**
  (not even merging `main` into it).
- Pitfalls already paid: (2026-09-16) the clone was left on the feature branch and a
  workaround was applied there by mistake, then moved to `main`; (2026-09-21) a daily data
  commit (`base 09-18`) went to the feature branch, so production never got `ECO 045/2026`'s
  base and answered **409** — fixed with `git checkout <commit> -- <csv>` on `main` (a
  cherry-pick would conflict on `base_contratos.json`). **If the branch isn't `main`, stop and
  ask before editing anything.** When diagnosing what production serves, read
  **`origin/main`** (`git show origin/main:<path>`), never the clone's working tree — it may be
  on the feature branch; and before concluding data "doesn't exist", check the other branch too.

Files that must **not** be blindly copied across:
- **`modelo/src/lib/api.js`** — line 9 diverges *on purpose*: production uses
  `http://backend:8000/api` (the compose service name), this repo `http://127.0.0.1:8000/api`.
  **Edit, never copy.**
- **`backend/usuarios.json`** — production holds real password hashes. Never touch it.
  Its deploy workflow (`.github/workflows/compose-gclt.yml`) **deliberately discards any
  `usuarios.json` arriving via git** and restores the container's copy, so a new operador
  pushed through git never reaches production — it has to be created on the VM with
  `docker exec docker-backend-1 python -m backend.admin_usuarios add <operador>`.
- **`base_contratos.json`** — sync field-by-field with a script that asserts nothing else
  changed; the two copies have known pre-existing divergences (`data_termo`,
  `meta_excepcional`) where **production is the correct one**.

Most untouched files differ only by line endings (CRLF here, LF there) — that is noise;
compare normalized (`tr -d '\r'`) before concluding a file is out of sync.

Architectural changes in that repo require the company's IT — keep changes there minimal.

**Testing that repo (on `main`):** from its root, either this repo's `.venv`
(`..\site_classificacao_beneficiarios_programa\.venv\Scripts\python.exe -m pytest backend/tests/ -q`)
or an ephemeral env built from **its own** requirements:
`uv run --no-project --python 3.12 --with-requirements backend/requirements.txt python -m pytest backend/`.
(A venv under the session scratchpad fails on Windows: the path exceeds 260 chars.)

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
started as a **"commit everything" policy** — **`manuais/`** (domain source material +
**the official model**), **`entrada/`**, **`backend/usuarios.json`** and this **`CLAUDE.md`**
are **committed** and ride `git pull` to the server. The **2026-07-17 handoff** carved out a
second, non-secret exclusion: **`planning/`, `.claude/`, `claude resume.txt`, `DEPLOY.md`,
`DEPLOY_HOSTINGER.html`, `deploy_hostinger.sh`** are gitignored so the company's engineers
don't see internal planning/Hostinger artifacts — they still exist locally. Also gitignored:
`node_modules/`, `dist/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `bug_fix/`,
`minhas_notas/`, `.playwright-mcp/`, logs, and the real secrets (`.env*`,
`senha e-mail hostinger`). The front app source is under `modelo/src/`; the backend under
`backend/`. (`modelo/mock/mock_site_atual.html` is an untracked reference snapshot, not code.)

**`entrada/`** holds the backend's reference data, BOM UTF-8, `;`-separated, **committed**:
- `entrada/lpt/consolidado_ucs_modelo.csv` — **single file since 2026-07-21**
  (`contrato;odi;uc;uf;municipio`), replacing the old two-file LPT layout; it feeds
  **both** `chaves_uc` and `odi_ref`. It spells UFs out ("Amapá") — hence `normalizar_uf`.
- `entrada/mla/consolidado_ucs.csv` (`contrato;odi;uc`) + `entrada/mla/consolidado.csv`
  (`contrato;odi;uf;municipio`) — still the old two-file layout.

It is **not** front code — don't import it into `modelo/src/`. `backend/referencia.py` reads it.

**Daily update of `entrada/`:** the reference CSVs come daily from legacy systems (scripts in
the neighboring `atualizacao_clientes` project) and are **committed to the production repo's
`main`** as `base MM-DD`; the Azure deploy picks them up. ⚠️ In the Docker images `entrada/`
is **baked in** (`COPY . .`, no volume): copying CSVs onto a server's disk has **no effect**
until the image is rebuilt. (From 2026-07-09 to 2026-09-02 the old Hostinger stack received
them by scp and needed `git checkout -- entrada/` before pulling — that stack is gone.)

### Secrets — never commit

`.env` / `backend/.env`, the SSH private key (only the `.pub` goes to the server), and
`senha e-mail hostinger` (repo root).

**`backend/usuarios.json` is the exception, and its status has flipped three times** — check
`.gitignore` before assuming: versioned (MVP 2026-07-07) → gitignored (2026-07-08, because a
versioned copy overwrites real production users) → **versioned again (2026-07-17 handoff)**,
now shipped as a *seed* (6 operadores, public documented password `Senha123`, forced change
on first access). Consequence to keep in mind: **anything that replaces the file on a server
resets every password to the seed** (a `git pull`, or a Docker `--build`) — back the file up
first, or re-provision via
`admin_usuarios add <operador>` / "esqueci minha senha". Old real hashes remain in git
history, so **the repo must stay PRIVATE**. No force-push, no touching tags. (`sudo -u deploy`
and the read-only PAT were rules of the pre-2026-09-02 Hostinger stack; the rebuilt VPS has
no git remote.)

## Coding Style

Toda função com docstring explicando, nesta ordem: por que a função existe (o problema que ela resolve / o motivo de ser função separada); a lógica do input ao output, em fases numeradas (Entrada → Fase 1 → Fase 2 → … → Saída), descrevendo o que cada bloco transforma. Além disso, toda linha de código comentada — inclusive as que parecem óbvias.

## Tests

Always include e2e tests to cover important paths. You should always make sure that the plans include a test suite that covers the happy paths and edge cases. Your tests should be high quality and give confidence while covering most of the implementation.
