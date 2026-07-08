# VERSOES.md — Controle de versão do produto

> Documento-mestre do versionamento do **Sistema Gerenciador do Programa Luz para
> Todos** (Classificação de Beneficiários / Anexo V). Cada versão registra: escopo
> entregue, limitações conhecidas e o que foi transferido para a versão seguinte.
> O histórico detalhado de construção (fases, decisões, testes) segue em `PLAN.md`.

---

## V0 — MVP entregue ✅ (2026-07-07)

**Produto em produção:** https://gerenciador-gclt.com (VPS Hostinger, Nginx + uvicorn
systemd `anexov-api` em `/opt/anexov`; HTTPS apex+www via certbot).

### Escopo entregue

- **Front (React/Vite, `modelo/`)** — visual aprovado pelos gestores: login →
  menu → UF → contrato → versão da planilha → upload → painel de inconsistências
  (erros bloqueiam, avisos não) → sucesso ("Planilha enviada.") com export do
  relatório `.csv` no navegador.
- **Backend real (FastAPI, `backend/`)** — Blocos A–F do plano:
  - Autenticação login/senha (pbkdf2 + salt, token JWT HS256), troca obrigatória no
    1º acesso, rate-limit no reset.
  - Filtro de acesso em duas camadas: domínio do e-mail → grupo econômico → UFs e
    contratos visíveis (ENBPAR vê tudo).
  - Validação **real** do `.xlsx` contra a referência `entrada/` (ODI+UC, UF/município,
    formato/domínios da aba `Dominios`, UC duplicada, datas, tipologias); avisos ×
    erros conforme a spec.
  - `GET /api/health` com integridade da referência; recarga automática por mtime.
  - E-mails implementados (planilha validada, alerta crítico 409, credenciais) — em
    produção parcialmente ativos (ver limitações).
- **Suíte de testes:** 101 pytest verdes (`backend/tests/`); E2E de navegador
  (G1) executado com dados reais.
- **Deploy:** `deploy_hostinger.sh` idempotente + `DEPLOY.md`; atualização por
  `git pull` + `npm run build` + `systemctl restart anexov-api`.

### Decisões/workarounds do MVP (registrados, reversíveis)

1. **"Esqueci minha senha" sem e-mail:** reseta para a senha padrão de inicialização
   (`Senha123`, constante `_SENHA_PADRAO_MVP`) com troca obrigatória; tela crua
   "Sua senha foi resetada para o padrão de inicialização" + Voltar.
2. ~~**`backend/usuarios.json` versionado no git**~~ — **REVERTIDO em 2026-07-08**:
   com o `git pull` diário de `entrada/` no VPS, o arquivo versionado sobrescreveria
   os usuários reais de produção a cada pull. Voltou ao `.gitignore`; o arquivo de
   produção é gerido só no VPS. Os hashes antigos permanecem no histórico do git →
   o repositório **continua tendo que ser privado** (token fine-grained read-only
   no remoto do VPS).
3. **Mensagem 409 orientadora:** "Sem ODIs/UCs cadastradas. Por favor, atualize os
   dados no gerenciador antes." + alerta crítico ao admin.

### Limitações conhecidas (transferidas para a V1)

- **Envio real de e-mail não homologado** (G2 ⏳): SMTP Hostinger configurado no
  `.env`, mas o smoke de produção (planilha validada + alerta 409 chegando à caixa
  de entrada) não foi concluído — falhas de envio hoje são silenciosas (dry-run
  retorna `False` sem log; exceção SMTP vira `erroEnvio` no JSON, invisível no
  journalctl).
- **Validação de arquivo grande "congela" a tela** (~1 min percebido no
  ECO-038-2025): validação em si leva ~1,3 s; suspeito é o envio SMTP síncrono
  dentro da requisição. Correção proposta: `BackgroundTasks` + timeout no smtplib +
  barra de progresso que nunca congela.
- **5 contratos sem referência** (ECM 025/2026, ECM 029/2026, ECO 034/2026,
  ECO 039/2025, ECO 042/2025) — dependem do pipeline externo `alimentacao_UCs`.
- **Domínios de e-mail provisórios** no mapa de acesso (amazonasenergia.com.br /
  roraimaenergia.com.br pendentes de decisão dos engenheiros).
- Workaround 1 acima deve ser revertido quando o envio de credenciais por e-mail
  entrar (o 2 já foi revertido em 2026-07-08, ver acima).

---

## V1 — Em planejamento 🚧 (aberta em 2026-07-07)

**Objetivo:** série de melhorias sobre o V0 em produção. Backlog inicial abaixo —
itens a confirmar/priorizar com o usuário; novos itens entram aqui.

### Backlog candidato (herdado do V0)

- [ ] Homologar **envio real de e-mail** em produção (planilha validada,
      alerta crítico, credenciais) + **log explícito de envio** no
      `email_envio.py` (sucesso/falha/dry-run) para nunca mais depurar às cegas.
- [ ] Reverter o workaround do "esqueci minha senha" (voltar à senha temporária
      aleatória enviada por e-mail) quando o SMTP estiver homologado.
- [ ] **Desempenho/UX do upload grande:** e-mail via `BackgroundTasks` + timeout no
      smtplib; barra de progresso do front sem congelamento (trickle + mensagens
      rotativas + tempo decorrido).
- [ ] Completar a referência dos **5 contratos** pendentes (pipeline externo).
- [ ] Definir domínios reais dos grupos (mapa `acesso.py`).
- [ ] Substituir a sincronização diária de `entrada/` **via git** (decisão provisória
      de 2026-07-08, ver PLAN.md; desenvolvida no projeto `atualizacao_clientes`) por
      mecanismo mais robusto — candidata: endpoint de upload autenticado na API.

### Novas melhorias da V1 (a definir pelo usuário)

- [ ] *(aguardando a lista de melhorias)*

---

## Convenções de versionamento

- Versões de produto: **V0, V1, V2…** — marcos de entrega ao usuário/gestores, não
  releases técnicas; cada fechamento ganha uma **tag git** (`v0`, `v1`, …).
- Dentro de uma versão, o trabalho segue o método do `PLAN.md`: partes pequenas,
  humanamente testáveis, TDD no backend, decisões registradas com data.
