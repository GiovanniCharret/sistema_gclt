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
Nginx at **`/api`** (Docker compose on Azure; the Hostinger test bed runs natively — see
"Deploy"). Modules under `backend/`:

- **`app.py`** — the ASGI `app`; dev CORS (Vite :5175); all routes:
  `GET /api/health`, `POST /api/login`, `POST /api/trocar-senha`,
  `POST /api/esqueci-senha`, `POST /api/validar` (multipart upload → painel),
  `GET /api/modelo` (download the official model), `GET /api/contexto` (grupo → UFs/contratos).
- **`auth.py`** — real login/senha; signed token on protected routes; first-access
  password change; self-service reset. **Login is by `operador`, not by e-mail** (see
  below). `admin_usuarios.py` is the CLI that provisions users
  (`python -m backend.admin_usuarios add <operador>` / `disable <operador>`) and **prints**
  the temporary password (the credentials e-mail is not wired in the operador fallback).
  Users live in **`backend/parametros/usuarios.json`** (pbkdf2 hashes) — **tracked again since the
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

### `backend/parametros/` — business config out of `.env` (2026-09-29)

**The e-mail business data lives in `backend/parametros/email.json`, not in `.env`.** Server,
port, TLS, user, sender, dry-run, the recipient list and the alert address are **business
config**: they change often and are not secrets. Living in `.env`, changing one recipient meant
opening the same file that holds `SMTP_PASS` and `SECRET_KEY`, and shipping a deploy.

- **`config.py::obter_parametros_email()`** merges the two: **the JSON wins**, and any key it
  omits falls back to the old `.env` variable, so the transition breaks nothing and tests without
  the file stay valid. A config passed explicitly (tests) short-circuits the JSON entirely.
- **The password never comes from the JSON** — `smtp_pass` is read from `.env` only, and a test
  fixes that (a `senha` key inside the JSON is ignored).
- **Reloaded by mtime**, like `entrada/`: editing the file counts on the next request, no
  restart. That is the operational gain — swapping a recipient no longer needs a deploy.
- **`GET /api/health/detalhado`** publishes `email.origem` = `json` or `env`, so the browser says
  which source is in force. Without a terminal on the VM, that is the only way to tell. ⚠️ It moved
  out of the public `/api/health` on 2026-10-01 and **now needs a token** — same information, same
  shape, one header more.
- ⚠️ **The two repos' `email.json` diverge on purpose**: dev ships `"dryrun": true` (nothing
  ever leaves a developer's machine), production `false`. Same rule as `modelo/src/lib/api.js`:
  **edit, never copy**.
- **`usuarios.json` moved too** — it is now `backend/parametros/usuarios.json`, so the backend's
  JSON files sit together. `config.usuarios_path`, `auth._USUARIOS_PADRAO` and the **four paths
  in the deploy workflow** follow it.
- Dropped in the same change: `ACESSO_DOMINIO_GRUPO` and `ACESSO_GRUPOS_CURINGA` were in `.env`
  but **no module ever read them** (the maps are hardcoded in `acesso.py`).
- ⚠️ This split **does not reduce exposure** while `.env` stays versioned in the production repo:
  both files are in git. The gain is operational; secrecy only improves when `.env` leaves the
  repository.

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
> after flipping**. It touches **only that rule**, and only under a **per-ODI completeness**
> condition (**since 2026-09-23**; `regras_cruzamento`, Fase 0 counts the missing base UCs **per
> ODI**): the contract's base is **not empty** and the **line's own ODI** has no already-registered
> UC missing from the sheet. An ODI absent from the base counts zero — it is a new ODI and passes.
> Then that pair becomes **warn** ("dado novo — ainda não cadastrado na base"); otherwise it stays
> **err**, and the suggestion names the ODI: *"o ODI "X" tem N UCs já cadastradas ausentes na
> planilha; UCs novas de um ODI só são aceitas como aviso quando todas as dele estiverem
> presentes"*. "UCs faltando" rows also read "já cadastrada na base". ⚠️ **The first version
> (2026-09-16) required the WHOLE contract in the sheet and was replaced on 2026-09-23**: measured
> on the `ECM 026/2025` ticket, a monthly sheet of 5 UCs against a base of 11 928 could never
> satisfy it, so the flag refused exactly the case it exists for. Per-ODI keeps the typo guard —
> a mistyped UC of a **known** ODI leaves that ODI incomplete, so the typo keeps erroring — but a
> mistyped UC under a **new** ODI has nothing to compare against and passes as a warning.
> **Unchanged:** the **409** for a contract with no reference at all (only contracts that
> already received ODIs qualify), "UF / município divergente" (err), and every other rule.
> The severity reaches the pure `validar`/`regras_cruzamento` as a **parameter**
> (`novo_como_aviso`; their `False` default only keeps the functions pure — the system default
> comes from `config.py`); only `app.py` reads the config. Same value and same text on the
> production repo's `main` **and** both feature branches (kept identical so merges don't conflict).

`_DESCRICOES` (`validacao.py`) is the authoritative list of rule titles + panel blurbs —
read it rather than trusting a prose summary.

> **The old "Data de energização fora de 2026" rule was removed (2026-07-09)** — any date
> is accepted; a **blank** date is still an error (it's a required field).

### `SECRET_KEY` has no default: the process refuses to start without one (2026-10-01)

`config.py` used to carry `secret_key = "dev-inseguro-troque-em-producao-com-uma-chave-longa"`. With
`.env` missing — a fresh clone, an image built without the file, a misspelled variable — **nothing
failed**: the system signed session tokens with a public constant that anyone with repo access knows.
That is silent identity forgery for any account, and it is the same fail-open shape the database had
until 2026-09-23. **Demonstrated** in a worktree at the previous commit with `.env` absent: the old
code issued a valid JWT signed with that constant; the new code refuses to sign.

Three layers, deliberately:
1. **`config.py`**: `secret_key: str = ""`, and `exigir_secret_key()` holds the rule — minimum **32
   characters** (RFC 7518's floor for HS256).
2. **`app.py`**: a `lifespan` check **at startup**, so uvicorn never opens the port and the failure
   lands in the container log, where whoever deployed is looking. Uses `asynccontextmanager`, the
   non-deprecated form (`on_event` still exists in starlette 1.7 but is on its way out).
3. **`auth.py`**: the check runs **before signing**, covering anyone who imports the module without
   starting the server — a CLI, a maintenance script, a test.

- ⚠️ **The error message never contains the key**, not even part of it or its real length, and a test
  pins that by searching the message for the short key it rejected. Error messages reach logs, screens
  and, sooner or later, a support ticket.
- ⚠️ **Operational consequence:** a clone **without `.env` no longer starts**, and its API tests fail.
  The production repo is unaffected (its `.env` is tracked); the dev repo is. That is the price of
  failing closed, and it was the user's call.
- The other half of this finding — pydantic's `Config` repr printing `secret_key` in tracebacks —
  was closed the same day with `SecretStr`; see the next block.
- 6 tests per branch. Suites: **198** (main), **438** (login), **517** (fase2).

### Secrets are `SecretStr`: no accidental leak through repr or traceback (2026-10-01)

`secret_key`, `smtp_pass` and `banco_senha` are `SecretStr`, so the configuration object's repr shows
`**********`. **This closed a real leak, not a hypothetical one:** while running the suite against the
previous commit, an `AttributeError` made pytest print the `Config` repr **with the whole SECRET_KEY**
on screen. The vector is not an attack — it is a traceback, a log line, a `print(config)`, a support
ticket with the output pasted in.

The value leaves the box at **four** points, each at the moment of use: `exigir_secret_key`
(validation), `jwt.decode` in `auth.py`, `sessao.login` in `email_envio.py`, and the URL assembly in
`config_identidade.py`. `texto_do_segredo` concentrates the unwrapping.

- ⚠️ **`texto_do_segredo` accepts `SecretStr` *and* `str`, and that is measured, not defensive
  habit**: the same field receives a plain `str` through two legitimate paths —
  `types.SimpleNamespace(smtp_pass="…")` in `test_parametros_email`, and the `senha` parameter the
  database CLI passes by hand. A bare `.get_secret_value()` there would raise `AttributeError`. Each
  call to it marks exactly where a secret leaves the box, which is what you want to be able to audit.
- ⚠️ **What this does not do:** `.env` is still versioned (the user's decision), so read access to the
  repo still yields the key from the file. This closes carelessness, not access. And a deliberate
  `print(get_secret_value())` would still leak — the type protects the object, not the programmer.
- The regression test **reproduces the finding**: it searches `repr(cfg)` and `str(cfg)` for the key
  and the SMTP password. Verified against the previous commit in a throwaway worktree, where it fails
  with `assert 'kkk…' not in 'Config(secr…'`.
- Checked on the real configuration (no e-mail sent): `obter_parametros_email()` still reads
  `origem: json`, the password unwraps to a non-empty `str`, and neither secret appears in the repr.
- Suites: **202** (main), **444** (login), **523** (fase2).

### Health split, and the database diagnosis the VM never had (2026-10-01)

| Route | Who sees it | Body |
|---|---|---|
| `GET /api/health` | **public** | `{"status": "ok"}` — plus `loginOperador` on the branches |
| `GET /api/health/detalhado` | **token** | what used to be public: `referencia`, `integridade`, `email` |
| `GET /api/health/banco` | **token**, branches only | `ok` / `faltam_tabelas` / `inacessivel` / `nao_configurado` |

Measured before touching it: **the front does not consume `/api/health`** (no component calls it) and
no healthcheck in compose, the Dockerfile, nginx or the workflow points at it — so the cut broke
nothing. `loginOperador` stays public on purpose: the login screen needs it **before** a token exists,
and it is a boolean about which door exists, not about what is inside.

- ⚠️ **`/api/health/banco` does NOT use `usuario_autenticado`.** That dependency loads the account
  **from the database**, so the route would be useless exactly when the database is down. It uses
  `token_valido` (signature only, no query), which covers both logins because both tokens come from
  the same `gerar_token`.
- ⚠️ **No response carries the URL, host, user or password.** "Unreachable" returns only the
  exception's **class name** — SQLAlchemy's message embeds host and user, and this is an HTTP body.
  A test proves it by searching the body for the password, the host and the user.
- The `faltam_tabelas` answer **only became possible because of the change above**: while
  `obter_engine` created the schema, the check created what it was looking for.
- The route opens **its own** engine and disposes it (`finally`): the process singleton raises when a
  table is missing, which would collapse "database down" and "schema incomplete" into one exception.
- Smoke-tested end to end (uvicorn on :8123, real MySQL): public health returns status +
  `loginOperador`; detalhado answers 401 without a token and the full body with one; banco answers
  401 without a token and `{"status":"ok","tabelas":["convite","evento","usuario"]}` with one.
- Suites: **192** (main), **432** (login), **511** (fase2) — 3 tests on main were **migrated** from the
  public route, not deleted.

### `obter_engine` verifies the schema; creating it is a human command (2026-10-01)

**No DDL on the request path any more.** Until today the first identity request to arrive ran
`create_all` — schema creation triggered by web traffic, in a production database, with a user that
can `DROP`. It also made an honest "tables are missing" diagnosis impossible, because the check
would create what it was looking for.

⚠️ This is **not** the homonym-table fear, which was dismissed on 2026-09-23 (the database is ours
alone). The reason is different: least privilege, and no DDL by traffic.

- **`bd.tabelas_ausentes(engine)`** compares the database catalogue with `METADATA` and returns the
  sorted list of missing names. It **returns a list instead of raising** because two callers want the
  same question with different answers: the assembly wants to fail, a diagnosis wants to show.
- **`montagem.obter_engine`** now verifies. Missing a table, it raises naming which ones **and the
  command that fixes it**. The singleton is still filled only at the end (fase2's M3 preserved —
  its test was re-pointed at `tabelas_ausentes` and proves the same guarantee).
- **`backend/identidade/admin_schema.py`** (new, identical on both branches): `conferir` and `criar`.
  It deliberately **does not accept a URL argument** — a target typed on a command line is exactly
  how a parallel database gets created by accident. `criar()` returns what it created, because "ok"
  is not an account of what changed in a production database.
- **Measured against the real `db_lpt`** (catalogue read only): missing tables **none**, so the
  switch does not break production. **424** tests on the login branch, **503** on fase2.
- ⚠️ **Operational consequence:** a brand-new database (or a future environment) now needs
  `python -m backend.identidade.admin_schema criar` **once**, by hand, before the identity routes
  work. That is the point, not an oversight.

## Security audit against `planning/seguranca_saas_vibecoding.md` (2026-10-01)

Audited all three branches of the production repo against the guide's 5 categories. **What the
guide calls "vibe coding" failures is mostly already handled here** — the real gaps are elsewhere.

**Passed, with evidence** (don't "fix" these; they are already right): no client→database path at
all (nothing like Supabase/`anon` keys), so RLS is not applicable; **zero** `localStorage`/
`sessionStorage` in the front; the perfil is **re-read from the database on every request**
(`usuario_autenticado`), never trusted from the token, and an inactive account is refused;
sensitive routes gate on `matriz_perfis.pode_fazer` and **fail closed**; `/api/validar` enforces
contract ownership (`acesso.py`); ids are UUIDv4 and the invite token is `secrets.token_urlsafe(32)`
stored as **sha256**; no raw SQL anywhere (SQLAlchemy Core, bound params); React escapes by default
with **zero** `dangerouslySetInnerHTML`; and the exported CSV **neutralizes formulas** (`=+-@	`).

**Open findings, worst first** (full write-up in PLAN.md, 2026-10-01):
1. **`POST /api/esqueci-senha` resets any operador to the public `Senha123` with no
   authentication** — open on all three branches today. Operador names are guessable. The
   `login_operador_habilitado` flag that kills it ships `True`, so the merge does not close it.
   ⚠️ **The user decided on 2026-10-01 NOT to fix it**: the operador login is being discontinued
   shortly, and the flag already exists for the day it is. **Do not "fix" this unasked** — it is a
   known, accepted exposure with a decided end date, not an oversight. Until then it remains the
   only remotely exploitable finding on this list: a guessable operador name buys a password reset,
   a login, and the ability to send Anexo V as that distribuidora — while locking the legitimate
   operador out, because the reset forces a password change.
2. **`backend/.env` is tracked** (⚠️ the *code* half of this finding was closed on 2026-10-01 — see
   "SECRET_KEY has no default" below; what remains is the file being in git) (SECRET_KEY, SMTP_PASS and, since 2026-10-01, BANCO_SENHA), and
   `.gitignore` does not cover it: read access to the repo means **forging a JWT for any account**
   and connecting to production MySQL. ⚠️ **The user decided on 2026-10-01 to keep it in git**
   (moving to GitHub Secrets would deepen the dependency on the company's IT) — so the repo staying
   **private** is a load-bearing operational control, not a nicety. Related, found while testing:
   pydantic's `Config` repr **printed `secret_key` in tracebacks** — **fixed on 2026-10-01 with
   `SecretStr`**, see below.
3. **No rate limiting** anywhere except `LimitadorReset` (3/h per e-mail, **in-process memory**, so
   a restart clears it and workers don't share it). `/api/login`, `/api/login-email`,
   `/api/solicitar-acesso` and `/api/validar` take requests as fast as they arrive.
4. **`usr_lpt` can `DROP`/`ALTER`** (`WITH GRANT OPTION`), and `create_all` runs **on the first
   identity request** — schema change triggered by web traffic. Splitting into a DML-only app user
   needs **IT for one command** (`CREATE USER`; the global scope here is `USAGE` only, and a `GRANT`
   has not created users since MySQL 5.7). Self-revoking our own DDL is possible but **one-way** and
   would block the P5–P9 migrations, so it was rejected.
5. **TLS to MySQL does not verify the CA** (`ssl={}` lands in PyMySQL's PREFERRED branch, measured
   2026-09-28). Encrypted because Azure demands it, not because we ask.
6. `/api/logout` does not revoke: a leaked token lives up to 8h (`TOKEN_TTL`).

**Decided NOT to do** (user, 2026-10-01): take `.env` out of git; soften the 403/409 diagnostic
`detail` strings (naming the owning distribuidora stays for now).

### Fixed the same day — input limits (commits `7d3f94d` / `67aabf7` / `f639ad2`)

`max_length` on every input model (operador 64, senha 200, e-mail 254, token 128, perfil 32,
`contrato`/`uf` 40) — a 10 MB password used to reach pbkdf2's 200 000 iterations, which is
unauthenticated CPU exhaustion; `_ler_upload_limitado` in `app.py` checks the extension and reads
in 1 MB chunks up to `config.upload_max_mb` (20), answering **413**; and `_conferir_expansao` in
`planilha.py` sums the zip's declared sizes before openpyxl and refuses above 300 MB (a zip bomb is
tiny compressed, so it sails through Nginx). ⚠️ **Measured on the way: a valid `.xlsx` renamed to
`.txt` used to return 200 and send the e-mail** — the extension was never looked at. The access
check still runs **before** any byte is read. 9–11 tests per branch, each verified to fail against
the previous commit in a throwaway worktree: **189 / 419 / 498**.

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
carries the new model (Azure: the workflow's `git pull`; Hostinger: the `git pull` in its clone)
— **no separate scp needed**. See the latest model-swap decision in PLAN.md.

### Deploy — two live targets

1. **Hostinger VPS (`gerenciador-gclt.com`) — TEST BED, not production.** It is where the
   branch **`feature/login-canonico-e-perfis`** is tested before being merged (see "Branches"
   under the sibling repo), and it is **operated by that branch's project**
   (`../site_sistema_amostral_com_os`), not by this one. State **verified on 2026-09-22**:

   > ⚠️ **It dies with the successful merge (user, 2026-10-01).** Once the login branch is
   > merged and the Azure deploy works, **this VPS is wiped**: the server gets formatted and
   > sits empty, waiting for new code to test. It comes back **in the later phases**, when
   > the heavier features arrive (the sibling project's **P5–P9**, see "Roadmap" below).
   > Consequence for planning: **do not treat Hostinger as a prerequisite for the merge, and
   > do not spend effort repairing it** — its hand-edited `.env`, its blocked `git pull` and
   > its unknown service manager stop mattering the day the merge lands. Anything below about
   > this machine describes a state with an expiry date.
   - The VPS was **reinstalled again around 2026-09-10** (host key `Z2Hc…` → `GeYEX…`). Whatever
     was built before is gone — including the Docker stack this project set up on 2026-09-02
     in `/opt/enbpar` (runbook `DEPLOY_VPS_DOCKER_VIA_SSH.md`, gitignored — still valid as a
     generic recipe, **not** as a description of this server).
   - **No Docker** is installed. The app runs **natively from a git clone at
     `/var/www/gclt-branch`** (the feature branch). An update is `git pull` there — **after**
     pushing the branch from here, or the pull brings nothing — plus a **backend restart**.
     ⚠️ **How the backend is started there (systemd / pm2 / other) is still UNKNOWN** — find
     out before restarting anything (`systemctl list-units --type=service | grep -i -E
     "gclt|uvicorn|api"`, `ps aux | grep uvicorn`).
   - **This project has no shell access**: the `deploy-dev` SSH key was wiped by the
     reinstall. The user runs commands in the Hostinger **browser terminal**. Remember the
     terminal opens in `~` (`/root`), which is not the repo — `cd /var/www/gclt-branch` first.
   - Older docs describe stacks that no longer exist: `DEPLOY.md`, `DEPLOY_HOSTINGER.html`,
     `deploy_hostinger.sh` (pre-2026-09-02, systemd `anexov-api` in `/opt/anexov`) and the
     2026-09-02 Docker layout above.
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

> **⚠️ How configuration reaches production — and the failure that killed the first merge
> (2026-09-28).** **`backend/.env` is TRACKED in the production repo** (added by the company's
> first commit, `Nova Aplicação`; that repo's `.gitignore` never covered it), and that is how
> config reaches the Azure VM: compose declares `env_file: ../backend/.env`, and the deploy
> workflow's `git pull` is what updates it. **So the file production reads is the one in git,
> not a file someone edits on the VM.** The versioned copy had **no `BANCO_URL`** — the database
> data had been typed into the *Hostinger* file (`/var/www/…`), another machine — so every
> identity route answered **500** after the merge. That, and not "code to rewrite", is what the
> first merge attempt failed on.
>
> - **A hand edit on the VM freezes every future deploy.** `git pull` refuses (*"Your local
>   changes to the following files would be overwritten by merge: backend/.env"*), the step dies
>   (`bash -e`), `docker compose` never runs, **and the site keeps serving the previous build**.
>   Run **#68** failed exactly so: the VM stayed at the merge commit `e31b51a`, so reverting
>   `main` had **no effect on production**, and the four `.env` commits made after the merge
>   never arrived either. The only signal is the **Actions tab** — the site looks fine.
> - The workflow's **first** line, `docker cp docker-backend-1:…/usuarios.json`, aborts the whole
>   deploy when that container is absent or renamed.
> - **Fixed 2026-09-28** (`339f98f`): `|| true` on the backup; `git fetch` + **`git reset --hard
>   origin/main`** in place of `git pull` — the VM is now always equal to `main`, and a manual
>   edit there is **discarded silently**, which is the policy already implied by versioning
>   `.env`; plus `workflow_dispatch`, so a deploy can be triggered without a push.
> - **The two environments diverge on purpose, and the divergence is the trap.** Hostinger runs
>   the **feature branch**, **natively**, from `/var/www/…`, with a `.env` **edited by hand**;
>   Azure runs **`main`**, in **Docker**, from `/home/gclt/enbpar-sistema-gclt`, with the `.env`
>   **from git**. Configuring one teaches nothing about the other. ⚠️ The Hostinger clone was
>   hand-edited on 2026-09-28 as well, so **its** `git pull` is blocked the same way.
> - Measured while planning, and it contradicts `bd.py`'s own comment: **`ssl={}` does not
>   "require" TLS.** In PyMySQL 2.2.8 an empty dict is falsy, so it lands in the **PREFERRED**
>   branch (`_ssl_required = False`, no certificate check). The Azure connection is still
>   encrypted — the server offers and demands TLS — but the reasoning in the comment is wrong.
> - The prerequisites for a second merge attempt are listed in **`planning/PLAN.md`**
>   (2026-09-28); do not retry the merge without them.

> **⚠️ "Planilha enviada." was a lie in production (2026-09-29).** `POST /api/validar` always
> returned `enviado` (and `erroEnvio`), but **no front component reads either field** —
> `SucessoEnvio.jsx` prints *"Planilha enviada."* unconditionally. The versioned `backend/.env`
> of the production repo carries `SMTP_DRYRUN=1` and `SMTP_HOST=smtp.exemplo.com.br`, so
> `email_envio.enviar` returned **False without raising**: every operator of the seven companies
> saw success while **nothing was delivered**, since the Azure deploy went live.
> **Fixed in the backend** (the front is the sibling project's truth, untouched): when the sheet
> is valid, the send did **not** happen and **dry-run is off**, the route answers **502** naming
> the reason — the SMTP exception, or *"SMTP não configurado (SMTP_HOST vazio)"*. It reaches the
> screen through the raw status+detail `UploadAnexoV.jsx` already shows (2026-07-22 decision).
> **Dry-run still answers 200 on purpose** — it is a developer's choice, not a defect; what
> denounces dry-run *in production* is **`GET /api/health/detalhado`** (public `/api/health` until
> 2026-10-01, token-gated since), which publishes `email: {dryrun, smtpConfigurado, destinatarios}`
> — booleans and a count, never an address or a credential. 4 tests, applied to **both repos**, 172 green each.
> ⚠️ **Ordering that matters:** flipping `SMTP_DRYRUN=0` while `SMTP_HOST` is still the example
> value turns every upload into a **502** — set the real SMTP in the same change, never before.
> And the screen still says "Planilha enviada." whenever a send *does* happen; reading `enviado`
> honestly is the sibling project's call.

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
  `2026-09-15-…`). The branch is tested on the Hostinger VPS and only then merged into `main`.

  > **⚠️ Truth split (user, 2026-09-23).** `../site_sistema_amostral_com_os` is the truth for
  > the **frontend**; **this repository is the truth for architecture and backend.** So on
  > those branches: **frontend and product decisions are theirs** (screens, the `gerente`
  > admin + audit area, which is their P2) — don't touch them. **Backend and architecture
  > changes are this project's call**, and several have already been made there at the user's
  > request (the `odi_uc_novo_como_aviso` flag, per-ODI completeness, the database rule
  > below). Still: **never push those branches or merge them without being asked**, keep the
  > shared files textually identical across `main` and both branches so merges don't conflict,
  > and tell them what changed.

  > **⚠️ The identity subsystem has ONE database: MySQL (2026-09-23).** Its connection data is
  > **mandatory and has no default** — and ⚠️ **since 2026-10-01 it no longer comes from
  > `BANCO_URL`**, but from `backend/parametros/banco.json` plus `BANCO_SENHA` (see the next
  > block). Missing it, or an unreachable server,
  > **raises `RuntimeError` with an instruction** (`montagem.obter_engine`) — the message
  > names the database with the **password masked** (`bd.url_sem_senha`) and states that no
  > alternative database will be created. Rationale, measured: the old default
  > `sqlite:///backend/dados/gclt.db` made a missing/mistyped variable open a **local file
  > silently** — people registered there and the next deploy wiped it, with no error line.
  > ⚠️ **SQLite still exists, but only as the test substrate**: 83 tests pass an explicit
  > URL, so none of them goes through that default. The engine is **lazy** (opened on the
  > first identity call), so an unreachable database does **not** take the site down — the
  > operador login and the upload keep working; only the identity routes fail.

  > **✅ `db_lpt` é NOSSO — inventário medido em 2026-10-01 (leitura pura).** Decisão do usuário:
  > *"O db é nosso! Nós podemos usá-lo como quisermos."* Medido com
  > `minhas_notas/verificar_banco_identidade.py` (gitignored; só leitura, nenhum `CREATE`/`INSERT`/
  > `UPDATE`/`DELETE`) contra `lpt-mysql-geral-prd-brs.mysql.database.azure.com:3306`:
  > - **O banco tem 3 tabelas, e são as nossas**: `usuario`, `convite`, `evento`. **Zero tabelas de
  >   outro sistema** — apesar do nome "geral", nada mais mora ali. As colunas conferem
  >   **exatamente** com o que o código declara (nenhuma faltando, nenhuma a mais).
  > - ⚠️ **Consequência que cancela um pré-requisito do merge:** o medo de `create_all(checkfirst=True)`
  >   achar uma `usuario` alheia — não criar, não avisar, e os repositórios gravarem no cadastro de
  >   outro sistema — **não se aplica**. `obter_engine` pode continuar como está; não há necessidade
  >   de trocar criar por conferir.
  > - `usr_lpt` tem `SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES, INDEX, ALTER, …,
  >   TRIGGER ON db_lpt.*` **com `GRANT OPTION`**.
  > - **Primeiro `gerente` já existe**: `giovanni.charret@enbpar.gov.br` (criado 2026-09-16) — o
  >   único perfil com `alterar_perfil`, então a promoção de novos perfis já tem quem faça.
  > - **A conexão sai cifrada de fato**: cifra negociada `TLS_AES_256_GCM_SHA384` (o servidor está
  >   com `ssl-mode=require`). Isso **não** contradiz a medição de 28/09: quem exige o TLS é o
  >   servidor, não o `ssl={}` do `bd.py`.
  > - ⚠️ **O cadastro já está em uso, e é compartilhado com a produção**: 7 contas ativas e 85
  >   linhas em `evento` (auditoria), entre elas **uma de distribuidora** (`@energisa.com.br`,
  >   perfil `usuario`). Um cadastro "de teste" com domínio de distribuidora cria conta **real**,
  >   capaz de enviar Anexo V — teste só com `@enbpar.gov.br`.
  > - O firewall do MySQL **já libera o IP da estação** (o erro de senha errada chegou como 1045,
  >   não timeout). Falta confirmar o **IP de saída da VM da Azure**, que é outro endereço.
  > - **A senha do `usr_lpt` fica em `minhas_notas/dados_bd_lpt.md`** (gitignored, só local);
  >   nenhum documento versionado a contém.

  > **⚠️ Database config: data in `backend/parametros/banco.json`, password in `.env` (2026-10-01).**
  > `BANCO_URL` **is no longer read**. The JSON is the **single source** of `host`, `porta`, `base`
  > and `usuario`; `backend/.env` keeps **only `BANCO_SENHA`**. Same split as `email.json`
  > (2026-09-29) — business/infra data out of the secrets file — with **one deliberate difference**:
  > `email.json` missing falls back to `.env` on purpose, while here **there is nothing to fall back
  > to**, so a missing file, an unreadable one, a blank key or an empty password each raise
  > `RuntimeError` **naming what is missing**, and no alternative database is opened (the 2026-09-23
  > rule). Why it changed: the first merge died (2026-09-28) because `BANCO_URL` existed only in the
  > *Hostinger* `.env`, and changing a database address meant opening the same file that holds
  > `SECRET_KEY` and `SMTP_PASS`.
  > - **`config_identidade.py`** gained `ler_parametros_banco` (mtime cache, like `email.json`) and
  >   `montar_url_banco(caminho=None, senha=None)` — an explicit `senha` wins, which is how tests
  >   inject without touching `.env`. `montagem.obter_engine` calls it; `bd.py` is untouched.
  > - The URL is built with `sa.engine.URL.create` and returned by
  >   `render_as_string(hide_password=False)`. **Not by concatenation**: a password containing `@`,
  >   `:` or `/` would silently turn half of itself into the server address. A test pins it with
  >   `p@ss:w/ord#1`. ⚠️ `str(URL)` would mask the password as `***` and the driver would fail.
  > - ⚠️ **mtime reload buys nothing here**: the engine is a per-process singleton, so switching
  >   databases **requires restarting** the backend. The docstring says so.
  > - **Driver is fixed** (`mysql+pymysql`), not configurable — a `driver` key in the JSON would be
  >   an invitation to point somewhere else.
  > - Measured against the real server on 2026-10-01: the URL built by this path **connects**
  >   (`TLS_AES_256_GCM_SHA384`, the 3 tables in place). **12 tests** in
  >   `test_montagem_banco.py` (were 3). Applied to **both feature branches**, suites at
  >   **408** (login) and **487** (fase2).
  > - ⚠️ **It lives only on the feature branches**, like every identity file — `main` has no
  >   `backend/identidade/`, so nothing there reads it. The JSON is **tracked**, so the merge
  >   carries it to Azure; what the user still has to add to the versioned `.env` is
  >   **`BANCO_SENHA`** (plus `BASE_URL_PUBLICA`, `CONVITE_TTL_MIN`, `PERFIL_INICIAL_ENBPAR`,
  >   `DOMINIOS_PATH`).

  > **Roadmap of the sibling project (`../site_sistema_amostral_com_os/docs/PLAN.md`), read 2026-10-01.**
  > Its production phases are numbered **P1–P9**, and the naming is deliberate so "Fase 2" and "P2"
  > never collide. **P1–P4 are implemented and live on the two feature branches** — P1 perfis de
  > acesso, P2 área administrativa e auditoria, P3 conta e senha no banco, P4 perfil de gerente +
  > revisão. **P5–P9 are the heavier features still untouched**: P5 trilha de amostra e OS (só a
  > operadora), P6 coordenador/gerente/superintendente na trilha, P7 diretor + emissão de documentos,
  > P8 documentos da OS para o coordenador, P9 menu de planejamento da inspeção. That is the work the
  > reinstalled Hostinger will serve as test bed for (see "Deploy", target 1). Specs per phase live in
  > that repo's `docs/` (`2026-09-08-…`, `2026-09-15-…` for the login, `2026-09-21-…` for the gerente
  > area) and `docs/aproved/` holds the approved reference of each step.

  > **⚠️ NEVER `git merge main` into the feature branches — it deletes `backend/identidade/`
  > (measured 2026-10-01).** `main` carries the **revert of merge #1** (`b660a37`, merge `f2fa9eb`),
  > and that revert is **not** an ancestor of either branch. A `git merge main` therefore applies it:
  > the 7 identity files this project has edited would show up as `modify/delete` conflicts, and
  > **every identity file nobody touched would be deleted silently**, with no conflict to warn you.
  > The branches are 21 commits behind `main` and will stay that way. Consequences:
  > - To bring something from `main` into a branch, **cherry-pick that commit**, never merge. Measured
  >   cost for the two 2026-09-29 e-mail commits (`ac5d26c`, `0639c0c`): both conflict on
  >   `backend/app.py` and `backend/tests/test_api.py` (the branches' `app.py` carries the identity
  >   router and the `login_operador_habilitado` guard). Resolvable, not free.
  > - The re-merge path stays the one in PLAN.md's prerequisite 9: **revert the revert**
  >   (`git revert b660a37` on a new branch), not a plain merge.
  >
  > **`backend/.env` is now byte-identical on all three branches (2026-10-01).** It was not: `main`
  > holds the post-`parametros/` shape (only `SECRET_KEY`, `TOKEN_TTL`, `SMTP_PASS` — the e-mail
  > business data moved to `email.json` on 2026-09-29), while both branches still carried the old
  > shape, 10 keys more, with placeholder values (`smtp.exemplo.com.br`, `SMTP_DRYRUN=1`) and two keys
  > **no module reads** (`ACESSO_DOMINIO_GRUPO`, `ACESSO_GRUPOS_CURINGA`). Normalized by copying
  > `main`'s file (its real `SMTP_PASS` and rotated `SECRET_KEY` win) and appending the **identity
  > block that until today existed only in the hand-edited Hostinger `.env`** — the very absence that
  > made the first merge answer 500: `BANCO_SENHA`, `BASE_URL_PUBLICA`, `CONVITE_TTL_MIN`,
  > `PERFIL_INICIAL_ENBPAR`, `DOMINIOS_PATH`. ⚠️ **`PERFIL_INICIAL_ENBPAR=analista`**, which reproduces
  > the behavior already in use (every internal account in `db_lpt` is `analista`); `sem_perfil` is the
  > tighter alternative. On `main` none of it has any effect — there is no `backend/identidade/`
  > there to read it; the keys start mattering the day the merge lands. **This closes prerequisite 4.**
  > Suites after the change: **180** (`main`), **408** (login), **487** (fase2).

  > **`backend/parametros/` now holds every config file — on the login branch (2026-10-01).** The
  > user asked for `usuarios.json` and `dominios_autorizados.json` to join `email.json` and
  > `banco.json` there, so `backend/` keeps only code. Done with `git mv` (history preserved) plus
  > **12 reference fixes** found by `git grep`: `config.py::usuarios_path`, `auth.py::_USUARIOS_PADRAO`,
  > `config_identidade.py::dominios_path`, four tests, `.env.example`, `.gitignore`, that repo's
  > `CLAUDE.md` and the `Dockerfile-backend` comment. The deploy workflow was **aligned with `main`'s**,
  > which has pointed at `parametros/usuarios.json` since 2026-09-29 (the branch still had the old path
  > and lacked the `|| true` / `reset --hard` of 2026-09-28).
  > - ⚠️ **`DOMINIOS_PATH` was removed from `.env`** instead of being updated. The variable **wins over
  >   the code default**, and the default is the only value that knows where the file lives **on that
  >   branch** — a fixed path in `.env` would break whichever branch didn't move the file. Removing it
  >   keeps the three `.env` byte-identical and lets each branch use its own default.
  > - The three tests that read the **real** files (`test_premissa_roteamento`, `test_autorizacao`,
  >   `test_dominios_arquivo`) are the proof the new paths resolve — they'd fail on a missing file.
  >   **408 pass.**
  > - **Applied to `fase2` too** (same day, commit `9d9f962`, 487 pass) — the same 12 references, none
  >   unique to that branch: its gerente/audit code never touches these paths. Keeping the two
  >   identity branches on the same paths is what stops a rename conflict at merge time.
  > - **Per-branch layout now**, which is what a merge will see: `main` has
  >   `parametros/{email,usuarios}.json`; **both identity branches** have
  >   `parametros/{banco,dominios_autorizados,usuarios}.json` (**no `email.json`** — they lack the
  >   2026-09-29 commit). Verified identical across all three: `backend/.env`, the **deploy workflow**,
  >   `config.py::usuarios_path` and `auth.py::_USUARIOS_PADRAO`; and `config_identidade.py`'s
  >   `dominios_path` line matches on both branches. `usuarios.json` now sits at the **same path**
  >   everywhere, which removes a rename-vs-path ambiguity the merge would otherwise resolve by guess.

  > **⚠️ Flag `login_operador_habilitado` — turning the `usuarios.json` login off (2026-09-28).**
  > In `backend/config.py`, env `LOGIN_OPERADOR_HABILITADO`, **ships `True`** (stage 1: both
  > logins coexist). Set to **`False`** (stage 2: e-mail only) and the three legacy routes —
  > `POST /api/login`, `/api/trocar-senha`, `/api/esqueci-senha` — answer **403** with
  > *"Entre com o seu e-mail corporativo; se ainda não tem senha, use 'Solicitar acesso' na
  > tela de entrada."* (one guard, `_exigir_login_operador_habilitado`, so no route can be
  > forgotten). **This is where the documented vulnerability dies**: `esqueci-senha` resets
  > any operador to the public `Senha123` **without authentication**; with the flag off it
  > refuses and does not touch the store (a test compares the hash before and after).
  > **403 with text, not 404**, because the login screen already shows the `detail`, so the
  > person gets the instruction without the front changing. `GET /api/health` publishes
  > `loginOperador` so the front can hide the old path when it wants.
  > ⚠️ **Lives only on the feature branches, on purpose**: flipping it to `False` where the
  > e-mail login does not exist (i.e. `main` today) locks everyone out. It reaches `main`
  > with the merge. Unlike the sibling spec's §9 (delete the route in a single deploy), the
  > flag is **reversible**. Untouched: `usuarios.json`, the workflow and the front; operador
  > tokens already issued stay valid until they expire (up to 8h), so the cut is complete at
  > most 8 hours after flipping.
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
- **`backend/parametros/usuarios.json`** — production holds real password hashes. Never touch it.
  Its deploy workflow (`.github/workflows/compose-gclt.yml`) **deliberately discards any
  `usuarios.json` arriving via git** and restores the container's copy, so a new operador
  pushed through git never reaches production — it has to be created on the VM with
  `docker exec docker-backend-1 python -m backend.admin_usuarios add <operador>`.
  ⚠️ **Corollary paid on 2026-09-22:** because each deploy copies the **container's own**
  `usuarios.json` out and back, a broken copy placed in the container **survives every push** —
  git never repairs it. Symptom: **every** real operador gets **500** on `/api/login`, while an
  unknown operador still gets 403, `/api/health` 200, and a protected route with a fake token
  401 (config fine). `carregar_usuarios` returns `{}` (→ 401) when the file is missing, so a 500
  means it exists but can't be read. The file handed to IT was valid; the copy that landed in
  the container was not. Diagnose on the VM with `docker exec docker-backend-1 sha256sum
  /app/backend/parametros/usuarios.json` (compare with `git show origin/main:backend/parametros/usuarios.json |
  sha256sum`) and `docker logs docker-backend-1 --tail 30`; fix with `docker cp` of an intact
  file (sent by scp/upload, never pasted into a terminal editor). No restart needed — the store
  is re-read on every login.
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

**`ferramentas/` (tracked, 2026-10-01)** holds **reusable** diagnostics — the `db_lpt` inspector and
the SMTP tester — with their own `LEIA-ME.md`. Two rules worth knowing before adding to it: a
**one-shot migration script does not belong there** (it runs, the change is committed, and the script
is deleted — its reasoning lives in the commit message and in PLAN.md), and **no tool carries a
secret** (passwords come from `getpass` at the moment of use, or from a gitignored file; host, port
and user may stay). This repository deploys nothing — production comes from the sibling repo — so
nothing here reaches a server.

This **is** a git repository; `origin` is
`github.com/GiovanniCharret/sistema_gclt.git` (default branch `main`). The `.gitignore`
started as a **"commit everything" policy** — **`manuais/`** (domain source material +
**the official model**), **`entrada/`**, **`backend/parametros/usuarios.json`** and this **`CLAUDE.md`**
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

**`backend/parametros/usuarios.json` is the exception, and its status has flipped three times** — check
`.gitignore` before assuming: versioned (MVP 2026-07-07) → gitignored (2026-07-08, because a
versioned copy overwrites real production users) → **versioned again (2026-07-17 handoff)**,
now shipped as a *seed* (6 operadores, public documented password `Senha123`, forced change
on first access). Consequence to keep in mind: **anything that replaces the file on a server
resets every password to the seed** (a `git pull`, or a Docker `--build`) — back the file up
first, or re-provision via
`admin_usuarios add <operador>` / "esqueci minha senha". Old real hashes remain in git
history, so **the repo must stay PRIVATE**. No force-push, no touching tags. (`sudo -u deploy`
and the read-only PAT were rules of the pre-2026-09-02 Hostinger stack. The current Hostinger
server does have a git clone, `/var/www/gclt-branch`, set up by the other project — how its
remote authenticates is unknown here.)

## Coding Style

Toda função com docstring explicando, nesta ordem: por que a função existe (o problema que ela resolve / o motivo de ser função separada); a lógica do input ao output, em fases numeradas (Entrada → Fase 1 → Fase 2 → … → Saída), descrevendo o que cada bloco transforma. Além disso, toda linha de código comentada — inclusive as que parecem óbvias.

## Tests

Always include e2e tests to cover important paths. You should always make sure that the plans include a test suite that covers the happy paths and edge cases. Your tests should be high quality and give confidence while covering most of the implementation.
