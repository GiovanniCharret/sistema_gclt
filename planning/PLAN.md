# PLAN.md — Site mock "Classificação de Beneficiários do Programa"

> **Diretrizes de governança (não remover)**
> - **Não faça alterações em `PROJECT_BUILDING.md`.** As fases e controles de
>   progresso devem ser feitos e registrados **aqui em `PLAN.md`**.
> - **How to deliver code:** o desenvolvimento do site deve ser feito em pequenas
>   partes para facilitar o teste humano.
> - Glossário de status (de `PROJECT_BUILDING.md`): `[x]` concluído · `[ ]` pendente ·
>   `[a]` anulado · `[f]` revisão futura · `[n]` não se aplica · `[r]` rollback/falhou.

---

## Contexto

O MME (via SNEE/DUPS, Ofícios 283 e 305/2026) determinou à **ENBPar** (Agente
Operacionalizador do Programa Luz para Todos) o envio mensal da planilha
**"Anexo V — Painel de Monitoramento - MME-CC_UF"**, detalhando as unidades
consumidoras (UCs) energizadas em 2026. Base legal: **art. 12-A do Decreto
12.964/2026**, que dá ao MME a competência de identificar, registrar, monitorar e
verificar o atendimento aos beneficiários (incluídos os prioritários).

**Objetivo de longo prazo:** site que recebe o upload dessa planilha
(`['Preenchimento']`), valida a completude por regras (fases futuras), critica na
própria tela e pede correção; se tudo estiver certo, salva na base.

**Esta fase é só um MOCK estático para apresentação aos gestores** — provar a
experiência de uso e o design. Se aprovado, evolui para as regras validadoras reais.

### Decisões do usuário (registradas)
1. Validação **roteirada** (não lê o arquivo real); foco em mostrar como a crítica
   funciona e o design dos elementos.
2. Crítica como **painel de inconsistências** estruturado (não chat).
3. **Não** construir motor de regras nem abstrações para o futuro — gastar esforço
   na experiência de uso.
4. Incluir **tela de entrada** e **seleção** antes do envio. Nome provisório:
   **"Classificação de beneficiários do programa"**.

### Perguntas em aberto — RESPONDIDAS (2026-06-22)
1. Seleção antes do envio = **por UF**.
2. Avisos **não bloqueiam** o salvamento — só erros bloqueiam (assumido nesta entrega).
3. **Sim** — mostrar **preview da planilha** (primeiras linhas) ao lado do painel.
4. Granularidade do envio = **por UF**.

### Refatoração (2026-06-23) — contrato como chave principal
O usuário adicionou **`base_contratos.json`** (113 contratos reais) e corrigiu a
orientação: cada UF possui **um ou mais contratos**, e a **chave principal de cada
registro é o contrato** (não a UF). Fluxo passa a ter **3 passos de seleção**:
- Passo 2: **UF** (painel mantido) — agora lista só UFs com contratos não encerrados,
  com a contagem de contratos por UF.
- Passo 3 (**novo**): **Contrato** — lista os contratos da UF cujo `vigente` ≠
  `"Encerrado"` (inclui "Andamento" e "Encerramento"). Texto:
  `«{numero} - {tipo_contrato}, {tranche}»` (ex.: "ECFS 101/2005 - LPT, 2ª Tranche").
- O contrato selecionado é exibido na topbar, no painel e no sucesso.
- `base_contratos.json` foi copiado para `modelo/src/` (Vite importa de dentro
  do projeto); `seedData.js` deriva `UFS`, `CONTRATOS` e os helpers a partir dele.
- Dados reais: 41 contratos não encerrados em 14 UFs (AC, AM, AP, BA, GO, MA, MT, PA,
  PB, PI, RJ, RO, RR, TO); `tipo_contrato` ∈ {LPT, MLA}.

### Ajustes nas telas de seleção (2026-06-23)
- Passo 2 (UF) — eyebrow “Selecione a UF e o contrato”; sem parágrafo de ajuda nem
  contagem de UFs; cada card mostra **sigla · nome · “{N} contratos”**.
- Passo 2 (contrato, sublista) — eyebrow “Selecione o contrato”; título
  “Contrato — {UF}”; contratos em **grade de cartões** (`.contrato-grid`/
  `.contrato-tile`) espelhando o painel de UFs (lados parecidos), em vez de lista de
  largura total. Cada cartão mostra **“{N} UCs cadastradas” por contrato**.
- Espaçamento título→cartões padronizado em **24px** nas duas telas (ritmo do 8pt
  grid, coerente com o `margin-top: 24px` do `login-form`).
- **UCs cadastradas é POR CONTRATO e é MOCK** (`mockUcsContrato` em `seedData.js`,
  valor estável derivado do número) — não vem de `base_contratos.json`; no sistema
  real virá do backend.

### Relatório de inconsistências em .csv (2026-06-23)
- Botão **“Baixar relatório (.csv)”** no painel agora **baixa o arquivo de verdade**
  (gerado no navegador via Blob/anchor — `src/lib/relatorioCsv.js`). BOM UTF-8 +
  separador `;` (Excel pt-BR); aspas só quando o campo tem `;`/`"`. A limpeza do
  ObjectURL é adiada (`setTimeout 0`) — revogar na hora cancelava o download.
- Formato: cabeçalho (título, Contrato, UF, Versão, total) + linha em branco +
  tabela `Severidade · Regra · Linha · Campo · Problema · Sugestão`.
- **`modelo_relatorio_inconsistencias.csv`** (raiz do projeto) é o arquivo-modelo
  para revisão/aprovação — espelha o que o download gera.

### Passo 3 — conferência da versão da planilha (2026-06-23)
- Novo passo entre a escolha do contrato e o envio (`VersaoPlanilha.jsx`), gated por
  `versaoOk` no `App`. Eyebrow “Passo 3 · Confira a versão da sua planilha”; subtítulo
  alertando que versão desatualizada não pode enviar; cartão “Modelo oficial” com
  botão **Baixar modelo** e rodapé **“Versão de 23/06/2026”**; botão **Avançar para o
  envio**. “Baixar modelo” é stub (mock, sem download real); a data da versão é
  constante no componente.

### Simplificação de implementação (BEHAVIORAL_GUIDELINES — simplicidade)
Como a validação é 100% roteirada e não há backend, o mock usa **estado React +
dados roteirados (`seedData.js`)** diretamente, **sem** o interceptador de
`window.fetch` (`installMockApi`). O padrão de interceptação era para espelhar um
frontend real; aqui não há contraparte, então estado local é mais simples.

### Decisões de design assumidas (ajustáveis)
- **Projeto** em `modelo/` (Vite/React), reaproveitando o design system
  (`styles.css`) e os padrões de componentes. Dev server na **porta 5175**.
  (Originalmente um projeto irmão `modelo_anexo_v/` ao lado do mock de NF/GFIP;
  o mock de NF foi removido e este projeto consolidado em `modelo/` — ver nota final.)
- **Seleção** = **por UF** (tela `UfSelector`); o envio é por UF.
- **Painel de inconsistências** = **agrupado por tipo de regra**, cada grupo com
  contagem + severidade (✗ erro / ⚠ aviso), expansível para as linhas afetadas
  (linha · UC · campo · valor · sugestão).
- **Validação roteirada com 2 cenários**: 1º envio → painel com erros/avisos; após
  **"Corrigir e reenviar"** → 2º envio limpo → **estado de sucesso** "salvo na base".
- **Upload de 1 arquivo `.xlsx`** (não múltiplos PDFs). Sem parsing real.
- **Estilo**: mantém o design system azul/navy existente; troca marca/títulos para o
  contexto **MME · Luz para Todos · ENBPar**.
- **Extras** (consulta da base, histórico de envios): fora do escopo agora.

---

## Atores e domínio (do conteúdo de `manuais/`)

- **MME** coordena o Programa; **ENBPar** = Agente Operacionalizador (quem envia a
  planilha — usuário do sistema); **distribuidoras** = Agentes Executores; cada uma
  executa via **Contrato de Operacionalização** (nº ECM/ECFS, por UF/tranche/tipo).
- **Chave de integração:** Número ODI + Número da UC.
- **Tipos de atendimento:** Extensão de Rede · Sistemas de Geração Descentralizados ·
  Sistemas de Geração (Amazônia Legal) · Metas Excepcionais.
- A planilha tem **52 colunas**: 14 de identificação/localização/classificação +
  **38 colunas Sim/Não de "Tipologia do Benefício"** (batem 1-a-1 com as prioridades
  do art. 3º do Decreto). Domínios e regras vivem nas abas `Dicionario_Campos`,
  `Dominios` e `Instruções` da própria planilha.

---

## Fluxo de telas

`loading → AuthScreen (login genérico) → MenuPrincipal (hub de módulos) →
UfSelector (escolhe UF) → ContratoSelector (escolhe contrato não encerrado) →
VersaoPlanilha (Passo 3 — confere versão) → shell logado`.
No shell, o fluxo central:

**Upload** → (Validar e enviar) → **Painel de inconsistências** → (Corrigir e
reenviar) → **Upload** → **Sucesso ("validada e salva na base")**.

---

## Reuso do `modelo/` (já inventariado)

- **Dropzone** (`App.jsx`): `.dropzone`, `.dropzone-icon`, `.dropzone-label` — trocar
  `accept` para `.xlsx`, single-file.
- **Progress block** (3 fases): renomear para **① Leitura · ② Validação · ③ Conferência**.
- **Cards/topbar/seções**: `.app-shell`, `.topbar`, `.main-content`, `.card`,
  `.card-header`, `.section-kicker`, `.card-title`.
- **Status badges** e cores `.status-*` para severidade.
- **Telas cheias** `.auth-shell`/`.auth-card` (login e seletor).
- **Seletor**: `.contrato-list/-item/-primary/-secondary`, `.estado-item`,
  `.breadcrumb`, `.btn-back`.
- **Mock**: padrão `installMockApi.js` (intercepta `window.fetch`) + `seedData.js`,
  importado em `main.jsx` antes do `App`.

---

## Arquivos (em `modelo/`)

- `package.json`, `vite.config.js` (porta 5175), `index.html`, `src/main.jsx`,
  `src/styles.css` (cópia + classes novas do painel).
- `src/App.jsx` — orquestrador e gating; estado do fluxo de upload/validação.
- `src/components/AuthScreen.jsx` — login (versão enxuta).
- `src/components/UfSelector.jsx` — escolha da UF.
- `src/components/ContratoSelector.jsx` — escolha do contrato (vigente ≠ Encerrado).
- `src/components/VersaoPlanilha.jsx` — Passo 3: conferência da versão (Baixar modelo
  + “Versão de DD/MM/AAAA” + avançar para o envio).
- `src/base_contratos.json` — cópia da base real de contratos (fonte das UFs/contratos).
- `src/components/UploadAnexoV.jsx` — dropzone + progress + dispara validação.
- `src/components/PainelInconsistencias.jsx` — **entregável central** (grupos por
  regra + preview da planilha).
- `src/components/SucessoEnvio.jsx` — estado "validada e salva na base".
- `src/seedData.js` — UFs + cenário roteirado de inconsistências + linhas de preview.

---

## Spec do Painel de Inconsistências (coração da demo)

Cabeçalho-resumo: arquivo, contrato/UF, nº de UCs "lidas", **✗ X erros · ⚠ Y avisos**.
Linha conversacional curta do "Assistente de validação" (toque de "diálogo").
Grupos por tipo de regra (roteirados, baseados nos domínios reais), expansíveis:
- Campos obrigatórios vazios · Valor fora do domínio · Coordenadas inválidas ·
  Chave ODI + UC duplicada · Consistência "0 - Não é prioridade" + outra tipologia ·
  Data de energização fora de 2026 · Tipologia ≠ Sim/Não.
Item: `Linha 47 · UC 70012345 · Latitude — célula vazia → preencher em graus decimais`.
Ações: **Baixar relatório** (stub) · **Corrigir e reenviar**. Erros bloqueiam o
salvamento; avisos não.

---

## Fases — Mock estático (F1–F6) — **CONCLUÍDO**

> Esta é a **primeira fase do projeto** (mock de design, validação roteirada),
> aprovada pelos gestores e verificada. A fase atual de desenvolvimento é o
> **backend real** — ver "Fases de implementação do backend (Blocos A–G)" no fim
> deste documento, onde o progresso passa a ser registrado.

Cada fase é testável por humano isoladamente.

- [x] **F1 · Scaffold** do projeto irmão (Vite/React, `styles.css` reaproveitado,
  topbar/shell, porta 5175). *Teste:* `npm run dev` abre o shell. ✓ verificado.
- [x] **F2 · Entrada**: login (mock) + `UfSelector` (escolha de UF).
  *Teste:* login → seleciona UF → entra no shell; UF na topbar. ✓ verificado.
- [x] **F3 · Upload + progress**: dropzone `.xlsx` + 3 fases de progresso.
  *Teste:* seleciona `.xlsx`, vê o progresso até o resultado. ✓ verificado.
- [x] **F4 · Painel de inconsistências** (roteirado, agrupado por regra, expansível)
  + **preview** da planilha com células sinalizadas.
  *Teste:* upload → painel (14 erros · 10 avisos) + preview. ✓ verificado.
- [x] **F5 · Loop corrigir/reenviar + sucesso**: 2ª tentativa limpa → "salvo na base".
  *Teste:* "Corrigir e reenviar" → reenvia → tela de sucesso. ✓ verificado.
- [x] **F6 · Verificação**: `npm install` + `npm run build` (OK, 35 módulos) +
  `npm run dev` (:5175) + fluxo completo conferido no navegador (sem erros de
  runtime; só 404 inócuo de favicon).
- [ ] **Polimento futuro** (se necessário): favicon, estados vazios extras,
  ajustes de copy após feedback dos gestores.

### Pré-requisitos
- [x] Aprovação do plano pelos gestores (via protótipo HTML explicativo).
- [x] Decisão sobre as perguntas em aberto (respondidas em 2026-06-22).

---

## Verificação (end-to-end)

```powershell
cd modelo
npm install
npm run dev            # abre em http://localhost:5175
```

Roteiro de demo a validar manualmente:
1. Login mock → ContratoSelector → escolher UF e um Contrato de Operacionalização.
2. Aba Upload → arrastar qualquer `.xlsx` → "Validar e enviar".
3. Conferir o **painel de inconsistências** (grupos por regra, expandir, severidades).
4. "Corrigir e reenviar" → reenviar → **tela de sucesso** "validada e salva na base".
5. Conferir reuso visual (mesma identidade do `modelo/`) e textos do contexto MME.

Sem testes automatizados nesta fase (mock de design; foco em UX).

---

## Perguntas em aberto

1. O "contrato" selecionado antes do envio deve ser o **Contrato de
   Operacionalização** (assumido), a **distribuidora + competência**, ou só a **UF**?
2. Avisos devem permitir **salvar mesmo assim** (com ressalva), ou sempre exigir revisão?
3. Faz sentido um **preview da planilha** (primeiras linhas) ao lado do painel?
4. O envio é por **contrato**, por **UF**, ou um único arquivo consolidado por
   **competência mensal**?

---

## Login genérico + Menu principal (2026-06-23)
- **Login** genericizado (espelha `minhas_notas/login.jpg`): eyebrow “MME · Luz para
  Todos”, título “Entrar”, subtítulo genérico, campos vazios com placeholder,
  “Esqueci minha senha”. O texto específico (Anexo V / Decreto) saiu do login.
- Novo **`MenuPrincipal`** (hub) entre login e seleção de UF — pensado para receber
  mais módulos no futuro (ex.: upload de notas fiscais). Por ora 1 cartão:
  “Classificação de Beneficiários do Programa — Upload de Informações Sobre Unidades
  Consumidoras — Decreto Nº 12.964…”, com **ilustração em marca d'água** (cena de
  eletrificação rural: sol + casa + poste). Clicar → `UfSelector`.

## Consolidação de pastas (2026-06-23)

O mock antigo de NF/GFIP em `modelo/` foi **deletado** e o projeto deste site
(antes em `modelo_anexo_v/`) foi **movido para `modelo/`** — agora há **uma única
pasta** com o projeto. `npm install` + `npm run build` validados no novo `modelo/`.

> **Pendência de documentação:** o `CLAUDE.md` da raiz ainda descreve o antigo mock
> de NF/GFIP (que não existe mais). Precisa ser reescrito para descrever este projeto
> (Classificação de Beneficiários / Anexo V). `planning/PLAN.md` é o documento-chave.

## Backend real — validação + envio por e-mail (2026-06-26) — **PLANO APROVADO (2026-06-27)**

Decisão de evoluir do mock estático para um **backend FastAPI** (`backend/`) que valida
a planilha de verdade contra `entrada/` e envia o `.xlsx` validado por e-mail. **O visual
aprovado do front não muda** — só o comportamento é religado à API real.

Spec detalhada: **`planning/specs/2026-06-26-backend-validacao-envio-anexo-v-design.md`**
(sub-fases A–G na §17). Mapa de testes: **`planning/TESTES.md`**. Implementação começa
pelo **Bloco A** (uma sub-fase testável por vez, registrando o resultado aqui).

Resumo das decisões (perguntas respondidas em 2026-06-26):
- Validar = cruzar ODI+UC com `entrada/` + conferir UF/município + regras de
  formato/domínio (domínios lidos da aba `Dominios` do modelo). UC faltando = aviso.
  **Coordenadas inválidas = aviso** (não erro).
- Stack: FastAPI + uvicorn atrás do Nginx em `/api`.
- **Autenticação real (revisado 2026-06-27):** login/senha; admin cria usuário (CLI) e o
  sistema **envia a senha temporária por e-mail ao usuário**, troca no 1º acesso;
  "Esqueci senha" é **self-service** (gera nova temporária e envia por e-mail);
  `usuarios.json` com hash pbkdf2; token de sessão. Exige **1 tela nova** (trocar senha)
  reusando o design. `usuarios.json` fora do git.
- **E-mails (4 tipos):** planilha validada (→ destinatários), alerta crítico (→ admin),
  credenciais/senha temporária (→ usuário, na criação e no reset). Suíte automatizada
  **mocka SMTP**; envio real é **smoke manual** (Bloco E em caixa de teste; Bloco G no VPS).
- **Células vazias:** em linha preenchida (ODI/UC), campo obrigatório vazio = erro
  (inclui ODI/UC faltante); planilha com 0 linhas de dados = erro (não envia vazio).
- **Filtro de acesso por login em 2 camadas:** domínio do e-mail → grupo econômico
  (EQUATORIAL, ENERGISA, NEOENERGISA, ÂMBAR, CERCI, ENBPAR) → contratos/UFs visíveis.
  `ENBPAR` vê todos. Mapa `sigla→grupo` confirmado (AMAZONAS e RORAIMA → ÂMBAR); falta o
  mapa `domínio_email→grupo`. Endpoint `GET /api/contexto`. É escopo, não segurança.
- Uma chamada `POST /api/validar`: se passa (0 erros), **envia o e-mail automaticamente**
  com o `.xlsx` anexado **como veio**, anexo nomeado `Anexo V preenchido - {contrato}.xlsx`.
- SMTP e **lista única** de destinatários via `.env`.
- **Git: commitar tudo**; fora do git só artefatos regeneráveis e segredos (`.env`).
- Contrato sem referência em `entrada/` é **anomalia** → e-mail de **alerta crítico** ao
  admin (no fluxo real todo contrato tem ODI+UC); `base_contratos.json` é a autoridade.
- **Gap de dados:** os sem UC hoje são os **19 contratos MLA (Mais Luz para a Amazônia)**
  + 3 LPT (`ECO 034/2026`, `039/2025`, `042/2025`) = 22/41; atualizações diárias precisam
  gerar o `entrada/mla/consolidado_ucs.csv` antes do deploy.
- Testes pytest obrigatórios (auth, regras, parsing, acesso, e-mail mockado, e2e).
- **Plano aberto em sub-fases testáveis** (Blocos A–G; A fundação, B auth, C contexto,
  D validação, E envio, F front, G deploy) na §17 da spec.

---

## Fases de implementação do backend (Blocos A–G) — **registrar progresso aqui**

> Espelha a §17 da spec (`planning/specs/2026-06-26-backend-validacao-envio-anexo-v-design.md`)
> e o §04 do render `PLAN.html`. Cada sub-fase é **pequena e testável por humano
> isoladamente**. Marcar `[x]` ao concluir, anotando o resultado do teste. Marcador de
> teste em *itálico*. Estado inicial: tudo pendente (`backend/` ainda não existe).

### Bloco A — Backend: fundação
- [x] **A1 · Scaffold FastAPI.** App, `requirements.txt`, `.env.example`, CORS p/ dev,
  `GET /api/health` mínimo. *Teste: `uvicorn` sobe; `GET /api/health` → 200.*
  ✓ **(2026-06-30)** Criados `backend/{__init__.py, app.py, requirements.txt, .env.example}`
  + `backend/tests/{__init__.py, conftest.py, test_api.py}` (`config.py` fica para A2);
  `.venv` (uv, CPython 3.12) com deps instaladas;
  `.gitignore` ganhou seção Python. `pytest` → **1 passed** (health 200 / `{"status":"ok"}`);
  uvicorn real confirmado (`127.0.0.1:8000/api/health` → 200). Obs.: starlette 1.3 exige
  `httpx2` (não `httpx`) no TestClient.
- [x] **A2 · Carga da referência.** `referencia.py` lê `entrada/**/*.csv` em memória,
  monta `chaves_uc` e `odi_ref`, recarrega por mtime. *Teste: health expõe contagem;
  alterar um CSV reflete sem reiniciar.*
  ✓ **(2026-06-30)** `backend/referencia.py` (classe `Referencia` + singleton
  `obter_referencia`): índice por arquivo decidido pelas colunas do cabeçalho (tem `uc`
  → `chaves_uc`; tem `uf`+`municipio` → `odi_ref`), chave de contrato normalizada
  (trim+colapso+upper), recarga por comparação de mtimes. Health passou a expor `resumo()`.
  `pytest` → **6 passed** (4 unit em `test_referencia.py` + health). Servidor real:
  `contratosComChavesUc=19, contratosComOdiRef=45, totalChavesUc=145674, totalOdiRef=30183`.
  (Os 45 contratos em `odi_ref` vs 41 selecionáveis e os só-19 com UC serão reconciliados
  na A3.)
- [x] **A3 · Integridade vs `base_contratos.json`.** Classifica contratos com/sem
  referência; expõe no health. *Teste: health lista os 22 sem UC (19 MLA + 3 LPT).*
  ✓ **(2026-06-30)** `referencia.py` ganhou `carregar_base_contratos` (lê a raiz
  `base_contratos.json`; selecionável = `vigente ≠ "Encerrado"`), `Referencia.integridade`
  (com referência = tem `chaves_uc`; sem = selecionável sem `chaves_uc`; órfão = em
  `entrada/` fora da autoridade) e o singleton `obter_base_contratos`. Health passou a
  expor `integridade`. `pytest` → **10 passed** (3 unit novos + e2e). Servidor real:
  **comReferencia=19, semReferencia=22, orfaos=0** (os 22 incluem os 3 LPT
  `ECO 034/2026, 039/2025, 042/2025`).
- [x] **A4 · Acesso (mapas).** `acesso.py`: `domínio→grupo`, `grupo→siglas`, `ENBPAR`
  curinga, via config. *Teste unit: e-mail equatorial→EQUATORIAL→18 contratos; enbpar→41.*
  ✓ **(2026-06-30)** `backend/acesso.py`: `MAPA_GRUPO_SIGLAS` (invertido da tabela §5.1:
  NEOENERGISA→COELBA; ÂMBAR→{ÂMBAR,AMAZONAS,RORAIMA}; ENBPAR=curinga/`None`),
  `MAPA_DOMINIO_GRUPO` (**provisório** — domínios reais ainda são pendência, risco #3),
  e funções `grupo_do_email`/`siglas_do_grupo`/`contratos_visiveis`. `carregar_base_contratos`
  passou a expor `contratos` (selecionáveis com `sigla`). Sigla "ÂMBAR" = U+00C2 (literal
  casou). `pytest` → **16 passed** (6 de acesso, contagens reais: EQUATORIAL=18, ENBPAR=41,
  ÂMBAR=7). Sem rota nova (consumido pelo `/api/contexto` no Bloco C). **Bloco A (fundação)
  concluído.**

### Bloco B — Backend: autenticação (login/senha)
- [ ] **B1 · Store + hash + CLI + e-mail de credenciais.** `auth.py` (usuarios.json,
  pbkdf2 + salt), `email_envio.py` (senha temporária) e `admin_usuarios.py` (cria/desativa
  usuário, gera senha temporária e **envia por e-mail ao usuário**). *Teste: CLI cria
  usuário; hash verifica certo/errado; `precisa_trocar_senha=true`; e-mail de credenciais
  disparado (mock).*
- [ ] **B2 · `POST /api/login`.** Valida hash; emite token ou sinaliza troca. *Teste:
  senha certa→token; errada→401; flag ligada→`precisaTrocarSenha`.*
- [ ] **B3 · `POST /api/trocar-senha`.** Grava novo hash, zera a flag, emite token.
  *Teste: 1º acesso troca e depois loga normal.*
- [ ] **B4 · Guard de rota + `POST /api/esqueci-senha` (self-service).** Middleware de
  token (401 sem token); esqueci-senha gera nova temporária e **envia ao usuário**;
  resposta genérica + rate-limit. *Teste: rota protegida sem token→401; reset envia
  e-mail (mock).*

### Bloco C — Backend: contexto de login
- [ ] **C1 · `GET /api/contexto` (protegida).** E-mail do token → grupo → UFs/contratos
  filtrados. *Teste: equatorial → só EQUATORIAL; enbpar → 41; domínio desconhecido → vazio.*

### Bloco D — Backend: parsing + validação
- [ ] **D1 · Parser do `.xlsx`.** `planilha.py`: aba `Preenchimento`, cabeçalho linha 2,
  mapeamento por nome, leitura defensiva de data/coordenada, definição de linha de dados
  (ODI/UC). *Teste: fixture → linhas; sem aba/não-.xlsx → 400; 0 linhas → guarda de erro.*
- [ ] **D2 · Domínios do modelo.** Lê listas válidas da aba `Dominios`. *Teste: retorna
  Tipo de Atendimento/UF/Tipo de Comunidade/Enquadramento/Sim-Não.*
- [ ] **D3 · Regras de formato/domínio.** Campos vazios=erro (em linha com ODI/UC),
  domínio=erro, duplicado ODI+UC=erro; coordenadas=**aviso**, data fora 2026=aviso,
  tipologia≠Sim/Não=aviso, "0"+outra=aviso. *Teste: fixture por regra acende o grupo
  certo c/ severidade.*
- [ ] **D4 · Regras de cruzamento com `entrada/`.** ODI+UC inexistente=erro, UF/município
  divergente=erro, UCs faltando=aviso. *Teste: fixtures vs referência mock.*
- [ ] **D5 · Montagem da resposta.** `grupos` + `previewRows` + totais + `ok`. *Teste:
  planilha limpa → ok=true, 0 erros; suja → grupos/totais corretos.*

### Bloco E — Backend: envio + endpoints finais
- [ ] **E1 · E-mail (`email_envio.py`).** smtplib via `.env`, dry-run, anexo
  `Anexo V preenchido - {contrato}.xlsx` (byte a byte), destinatários únicos; alerta
  crítico; credenciais/senha temporária ao usuário. *Teste: SMTP mock confirma nome do
  anexo, anexo intacto, destinos.*
- [ ] **E1-smoke · Smoke manual com SMTP real.** Configurar `.env` real e disparar para
  uma **caixa de teste** os 3 tipos: planilha validada (anexo chega), alerta crítico,
  credenciais. *Teste manual: e-mails reais chegam corretos (ver `TESTES.md`).*
- [ ] **E2 · `POST /api/validar` (orquestra, protegida).** Token→email; checa grupo (403),
  referência (409+alerta), erros→painel, ok→envia. *Teste e2e (TestClient, SMTP mock).*
- [ ] **E3 · `GET /api/modelo` (protegida).** Baixa o modelo oficial. *Teste: 200 +
  Content-Disposition + bytes do arquivo.*

### Bloco F — Front: religação (visual inalterado; +1 tela de troca de senha)
- [ ] **F1 · Camada de API.** `src/lib/api.js` (token no header) + `VITE_API_BASE`.
  *Teste: dev aponta p/ backend local.*
- [ ] **F2 · Login real + troca de senha.** `AuthScreen` → `/api/login`; nova `TrocarSenha`
  (reusa design system) no 1º acesso; "Esqueci minha senha" → `/api/esqueci-senha`.
  *Teste: 1º acesso força troca; depois entra direto.*
- [ ] **F3 · Contexto nos seletores.** `UfSelector`/`ContratoSelector` usam listas de
  `/api/contexto`. *Teste: equatorial só EQUATORIAL; enbpar tudo. Visual idêntico.*
- [ ] **F4 · Upload real.** `UploadAnexoV` envia `FormData` (arquivo+contrato+uf, token);
  mantém barra 3 fases. *Teste: upload real → resposta real.*
- [ ] **F5 · Roteamento real + painel por props.** `App` roteia painel/sucesso, remove
  `attempt`; `PainelInconsistencias` por props; `relatorioCsv` usa grupos reais; "Baixar
  modelo" → `/api/modelo`. *Teste: suja→painel; limpa→sucesso+e-mail.*

### Bloco G — Integração e deploy
- [ ] **G1 · E2E completo (local).** login→(troca)→contexto→upload→painel→corrige→sucesso→
  e-mail (dry-run). *Teste: roteiro ponta a ponta no navegador.*
- [ ] **G2 · Deploy + smoke real.** `DEPLOY.md`: uvicorn (systemd) + Nginx `/api` +
  `client_max_body_size` + `.env` + onde fica `usuarios.json`. *Teste: build + smoke no
  VPS, **com 1 envio real** (planilha validada + credenciais) para destinatário de
  homologação.*

> Ordem de implementação: **começa pelo Bloco A** (A1). Cada sub-fase concluída é
> marcada `[x]` aqui com o resultado do teste.
