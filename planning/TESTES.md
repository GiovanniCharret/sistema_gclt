# Mapa de Testes — Backend (validação + envio + autenticação)

Este documento explica **o que testar** e **como testar** cada parte do **backend
FastAPI** (`backend/`), espelhando a §13 da spec
(`planning/specs/2026-06-26-backend-validacao-envio-anexo-v-design.md`) e as sub-fases
A–G (§17). Toda sub-fase é **testável isoladamente**; e2e cobre os caminhos importantes
(happy path + edge cases), conforme a governança.

> O front (`modelo/`) segue sem testes automatizados (mock de UX). O escopo aqui é o
> backend. O **anexo** ao fim documenta os testes do pipeline que **gera** `entrada/`.

## Como rodar

```powershell
cd backend
python -m venv .venv ; .venv\Scripts\activate     # Python 3.12/3.13
pip install -r requirements.txt
pytest -v                          # toda a suíte
pytest tests/test_validacao.py -v  # só um módulo
pytest -k "coordenada" -v          # só casos que batem no padrão
```

Pré-requisitos: `requirements.txt` instalado; o modelo
`manuais/Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.xlsx` presente (lido
para domínios e para `/api/modelo`); CSVs de `entrada/` presentes (carga da referência).

> **Sobre e-mail:** na suíte **automatizada** o SMTP é **sempre mockado** (nunca envia de
> verdade) — testa a lógica, não a entrega. O **envio real** é validado num **smoke test
> manual** (seção "Teste manual com SMTP real" ao fim deste documento), executado ao fim
> do Bloco E (caixa de teste) e no Bloco G (homologação/produção).

### Fixtures (`tests/fixtures/`)
- **Gerador de `.xlsx`** com openpyxl: cria planilhas de teste com a aba `Preenchimento`
  (cabeçalho na linha 2), parametrizável por linha/célula para acionar cada regra.
- **Referência mock**: pequenos dicionários `chaves_uc`/`odi_ref` por contrato, para não
  depender do volume real de `entrada/`.
- **`usuarios.json` temporário** (`tmp_path`) para os testes de auth.

---

## `test_auth.py` — Autenticação (Bloco B)

**O que:** store em arquivo + hash + token + fluxo de 1º acesso.

| Caso | Como | Esperado |
|---|---|---|
| Hash verifica senha certa | `verificar(senha, hash, salt)` | `True` |
| Hash rejeita senha errada | idem com senha trocada | `False` |
| CLI cria usuário | `admin_usuarios add email` | usuário em `usuarios.json`, `precisa_trocar_senha=true`; **SMTP mock recebe e-mail de credenciais ao usuário** |
| Login correto | `POST /api/login` senha temp. | `{precisaTrocarSenha: true}` (sem token pleno) |
| Login senha errada | `POST /api/login` | `401` |
| Troca no 1º acesso | `POST /api/trocar-senha` | grava novo hash, zera flag, retorna `{token}` |
| Login após troca | `POST /api/login` nova senha | `{token}` |
| Token expirado/ inválido | chamar rota protegida | `401` |
| Esqueci senha (self-service) | `POST /api/esqueci-senha` | `200` genérico; nova senha temp. gravada; **SMTP mock envia nova senha ao usuário** |
| Reset rate-limited | vários `esqueci-senha` seguidos | bloqueia após o limite |

**Como:** `usuarios.json` em `tmp_path`; `SECRET_KEY` de teste; SMTP mockado.

---

## `test_referencia.py` — Carga de `entrada/` (Bloco A)

**O que:** ler os CSVs, montar índices e recarregar quando o arquivo muda.

| Caso | Como | Esperado |
|---|---|---|
| Índice ODI+UC | carregar CSVs de teste | `chaves_uc[contrato]` tem os pares `(odi, uc)` |
| Índice ODI→UF/município | idem | `odi_ref[contrato][odi] == (uf, municipio)` |
| Normalização da chave | contrato com espaços/caixa | casa com `base_contratos.json` |
| Recarga por mtime | alterar o CSV e consultar de novo | reflete sem reiniciar |
| Integridade vs base | comparar com `base_contratos.json` | classifica com/sem referência; órfãos = 0 |

---

## `test_acesso.py` — Filtro por login (Blocos A4/C)

**O que:** e-mail → grupo → contratos/UFs visíveis (2 camadas).

| Caso | Como | Esperado |
|---|---|---|
| Domínio → grupo | `grupo_do_email("x@equatorialenergia.com.br")` | `"EQUATORIAL"` |
| Grupo → contratos | filtrar por EQUATORIAL | só contratos de sigla EQUATORIAL (18) |
| ENBPAR curinga | `grupo == "ENBPAR"` | todos os 41 selecionáveis |
| AMAZONAS/RORAIMA → ÂMBAR | filtrar por ÂMBAR | inclui ÂMBAR, AMAZONAS, RORAIMA |
| Domínio desconhecido | e-mail fora do mapa | listas vazias |
| Enforcement no validar | contrato fora do grupo do token | `403` |

---

## `test_planilha.py` — Parsing do `.xlsx` (Bloco D)

**O que:** ler a aba `Preenchimento` e definir o que é "linha de dados".

| Caso | Como | Esperado |
|---|---|---|
| Leitura básica | fixture com 3 linhas | 3 linhas estruturadas, mapeadas por cabeçalho |
| Mapeamento por nome | colunas reordenadas | mapeia certo mesmo assim |
| Linha vazia ignorada | linha sem ODI/UC | não conta em `linhasLidas` |
| Data defensiva | `DD/MM/AAAA` e serial do Excel | ambos viram data |
| Coordenada defensiva | `-3,30` e `-3.30` | ambos viram número |
| Sem a aba | xlsx sem `Preenchimento` | `400` |
| Não-.xlsx | enviar `.txt`/`.csv` | `400` |
| Planilha sem dados | 0 linhas com ODI/UC | erro "Planilha sem linhas de dados" (não envia) |

---

## `test_validacao.py` — Regras (Bloco D)

**O que:** cada regra acende o grupo certo com a severidade certa; totais e preview.

| Caso (severidade) | Fixture | Esperado |
|---|---|---|
| Campo obrigatório vazio (**erro**) | linha c/ ODI/UC e Latitude vazia | grupo "Campos obrigatórios vazios", `sev=err` |
| ODI/UC faltante (**erro**) | linha c/ ODI e UC vazio | erro (campo-chave) |
| Valor fora do domínio (**erro**) | Tipo de Atendimento inválido | erro (lido da aba `Dominios`) |
| Chave ODI+UC duplicada (**erro**) | par repetido na planilha | erro |
| ODI+UC não consta (**erro**) | par ausente da referência | erro |
| UF/município divergente (**erro**) | UF ≠ referência do ODI | erro |
| Coordenadas inválidas (**aviso**) | Latitude `91.5` | `sev=warn` (não bloqueia) |
| UCs faltando (**aviso**) | UC da referência ausente | aviso (count agregado) |
| "0 - Não é prioridade" + outra (**aviso**) | `0`=Sim e `I`=Sim | aviso |
| Data fora de 2026 (**aviso**) | `12/11/2025` | aviso |
| Tipologia ≠ Sim/Não (**aviso**) | `X` numa coluna de tipologia | aviso |
| Planilha 100% limpa | tudo correto | `totalErros=0`, `ok=true` |
| Totais e preview | mista | `totalErros/totalAvisos` corretos; `previewRows` com `flags` |

---

## `test_email.py` — Envio (Bloco E)

**O que:** envio normal, alerta crítico e dry-run — com SMTP **mockado**.

| Caso | Como | Esperado |
|---|---|---|
| Envio normal | 0 erros | SMTP mock recebe 1 mensagem aos `DESTINATARIOS` |
| Anexo intacto | comparar bytes | anexo == arquivo enviado (sem reescrever) |
| Nome do anexo | inspecionar | `Anexo V preenchido - {contrato}.xlsx` (`/`→`-`) |
| Alerta crítico | contrato sem referência | mensagem ao `ALERTA_EMAIL`, sem e-mail de planilha |
| Credenciais (criação) | CLI cria usuário | e-mail com senha temporária **ao usuário** |
| Credenciais (reset) | `esqueci-senha` | e-mail com nova senha temporária **ao usuário** |
| Dry-run | `SMTP_DRYRUN=1` | nada enviado; só log |
| Falha de SMTP | mock levanta erro | `enviado=false` + `erroEnvio` |

---

## `test_api.py` — End-to-end (TestClient) (Blocos C/E/G)

**O que:** os caminhos completos da API, com auth e SMTP mockados.

| Caminho | Como | Esperado |
|---|---|---|
| Rota protegida sem token | `GET /api/contexto` sem header | `401` |
| Contexto filtrado | login + `GET /api/contexto` | UFs/contratos do grupo |
| Validar com erros | upload de planilha suja | `200`, painel (grupos/preview), **sem** e-mail |
| Validar limpo | upload de planilha limpa | `200`, `ok=true`, SMTP mock disparado |
| Contrato fora do grupo | upload de contrato de outro grupo | `403` |
| Contrato sem referência | contrato sem `chaves_uc` | `409` + alerta ao admin |
| Requisição inválida | sem arquivo / não-.xlsx | `400` |
| Baixar modelo | `GET /api/modelo` (token) | `200` + `Content-Disposition` + bytes |
| Health | `GET /api/health` | status + cobertura de referência |

---

## Teste manual com SMTP real (fora da suíte automatizada)

A suíte `pytest` mocka o SMTP. O **envio de verdade** é validado **manualmente**, em dois
momentos, com uma "escada" segura: **dry-run → caixa de teste → destinatários reais**.

### Quando
- **Fim do Bloco E** — SMTP real apontando para uma **caixa de teste sua** (em
  `DESTINATARIOS` e `ALERTA_EMAIL` use o seu e-mail).
- **Bloco G (deploy)** — no VPS, 1 envio real para destinatário de **homologação** antes
  de ligar os destinatários oficiais.

### Como
```powershell
cd backend ; .venv\Scripts\activate
# .env com SMTP real (host/porta/usuário/senha), SMTP_DRYRUN=0,
# DESTINATARIOS e ALERTA_EMAIL = seu e-mail de teste
```

### Checklist (os 3 tipos de e-mail, conferir na caixa de entrada real)
| Tipo | Como disparar | Conferir |
|---|---|---|
| **Credenciais / senha temporária** | `python -m backend.admin_usuarios add seu@email` | e-mail chega ao usuário com a senha temporária e instrução de troca |
| **Planilha validada** | login → upload de planilha **limpa** | e-mail chega aos `DESTINATARIOS` com o anexo `Anexo V preenchido - {contrato}.xlsx` abrindo no Excel |
| **Alerta crítico** | forçar um contrato sem referência | e-mail chega ao `ALERTA_EMAIL` |
| **Reset (esqueci senha)** | `POST /api/esqueci-senha` com seu e-mail | e-mail chega com nova senha temporária |

Critério: os e-mails chegam, com remetente/assunto/corpo corretos e o anexo íntegro.
Só depois disso configurar os **destinatários oficiais** em produção.

---

## Observações

- Na suíte automatizada, SMTP é **sempre** mockado; nenhum teste envia e-mail real (o
  envio real é o smoke manual acima).
- Testes de regra/parsing usam **fixtures gerados** (openpyxl), não a planilha real.
- Auth usa `usuarios.json` e `SECRET_KEY` de teste em `tmp_path` — nunca o arquivo real.
- Critério de pronto por sub-fase: o teste correspondente em verde + checagem manual
  descrita na §17 da spec; registrar em `planning/PLAN.md`.
