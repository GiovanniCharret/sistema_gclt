1 - Atualização da data do termo json dos contratos - "ECOT 016/2017": {
    "sigla": "EQUATORIAL",
    "cnpj": "01543032000104",
    "tranche": "3ª Tranche",
    "uf": "GO",
    "valor_contrato": 0,
    "valor_cde": 0,
    "participacao_cde": 0.0,
    "tipo_contrato": "LPT",
    "vigente": "Encerrado",
    "metas": false,
    "data_termo": "2025-25-11"
  }

  2 - Validação de GPS por estado
  3 - Ucs com data de Meta Excepcional (refere-se ao item 1)
  4 - Coluna CPF/CNPJ
  5 - Filtros de latitute e longitude
    a. número errado
    b. por estado


---

## Decisão (2026-07-08) — atualização diária de `entrada/` via git (provisória)

O conteúdo de `entrada/` precisa ser atualizado diariamente em produção; as bases
são geradas pelo projeto vizinho `atualizacao_clientes` (automação de GUI Windows —
a geração não pode ir para o VPS). Opções avaliadas: (1) git como transporte,
(2) scp/rsync direto, (3) endpoint de upload na API, (4) storage intermediário.

**Escolhida a opção 1 (git):** o script diário local copia os 4 CSVs para este repo,
commita (add cirúrgico, só os 4 caminhos) e pusha; no VPS um cron do usuário `deploy`
faz `git pull --ff-only` em `/opt/anexov`. Sem restart: `referencia.py` recarrega os
CSVs por mtime (atenção: `base_contratos.json` NÃO recarrega — se mudar, restart).

**Provisória** até estrutura mais robusta nas próximas versões (candidata: endpoint
de upload autenticado — backlog da V1+ em `VERSOES.md`). O desenvolvimento do script
de sync é feito no projeto `atualizacao_clientes`; orientações escritas em
`atualizacao_clientes/planning/2026-07-08-atualizacao-diaria-entrada-site.md`.

## Decisão (2026-07-08) — `backend/usuarios.json` volta ao .gitignore (reversão)

Consequência direta da decisão acima: com o `git pull` diário no VPS, o
`usuarios.json` versionado (decisão MVP de 2026-07-07) **sobrescreveria os usuários
reais de produção a cada pull** (senhas trocadas pelos operadores seriam desfeitas).
Revertido: `git rm --cached backend/usuarios.json` + ignore restaurado. O arquivo de
produção passa a ser gerido exclusivamente no VPS (criação de usuário via CLI
`criar_usuario`, reset via "esqueci minha senha"). Os hashes antigos permanecem no
histórico do git — o repositório **segue obrigatoriamente privado**; recomendado
trocar as senhas de produção que coincidirem com as do histórico.

⚠️ Operacional: o primeiro `git pull` no VPS após essa reversão **apaga**
`/opt/anexov/backend/usuarios.json` do working tree (o commit remove o arquivo
rastreado). Procedimento: backup antes do pull, restaurar depois (sem restart — o
arquivo é lido a cada requisição).

## Decisão (2026-07-09) — sincronização diária de `entrada/` muda de git para SSH/scp

Substitui a decisão de 2026-07-08 (transporte via git). O script diário do projeto
`atualizacao_clientes` passará a enviar os 4 CSVs por **scp direto** para
`/opt/anexov/entrada/` no VPS (host `gerenciador-gclt.com` = `82.25.68.143`, porta 22;
login alvo `deploy` com chave ed25519 — setup único pendente: gerar chave no DEV,
que ainda não tem `~/.ssh`, e instalar a `.pub` em `/home/deploy/.ssh/authorized_keys`).
Sem restart (recarga por mtime); envio com rename atômico (`.new` → `mv`).

Consequência: os CSVs enviados por scp divergem do HEAD no working tree do VPS —
antes de qualquer `git pull` de deploy, rodar `git checkout -- entrada/` primeiro;
o cron de pull planejado em 2026-07-08 **não será criado**. Em aberto: tirar os CSVs
de `entrada/` do versionamento (gitignore + `git rm --cached`) para eliminar a
divergência. Orientações completas (perguntas de infra respondidas) em
`atualizacao_clientes/planning/2026-07-08-atualizacao-diaria-entrada-site.md`.
Continua **provisória** até o mecanismo robusto da V1+ (endpoint de upload autenticado).

## Decisão (2026-07-09) — regra "Data de energização fora de 2026" excluída

Mudança crítica 1/2 pedida pelo usuário: a data de energização deixa de ser restrita a
2026 — **qualquer data é aceita**; a única restrição que permanece é **data em branco**,
que continua erro por já ser campo obrigatório (`OBRIGATORIOS` em `validacao.py`).

- `backend/validacao.py`: removido o bloco do aviso, a entrada em `_DESCRICOES` e o
  import de `normalizar_data` (que segue existindo em `planilha.py`, com testes).
- `backend/tests/test_validacao.py`: teste da regra antiga substituído por dois novos —
  data de outro ano não gera achado; data vazia continua erro. **Suíte: 102 verdes.**
- `modelo/src/components/UploadAnexoV.jsx`: removido do hint do dropzone o trecho
  "unidades consumidoras ligadas em 2026" (build do front OK).
- `modelo/src/seedData.js` ainda cita a regra em `RULE_GROUPS`, mas é código morto da
  era mock (não é importado por ninguém desde o Bloco F) — deixado como está.

Pendente para valer em produção: commit/push + no VPS `git pull` + `systemctl restart
anexov-api` (regra vive no processo Python) + `npm run build` (texto do front).

## Decisão (2026-07-09) — classificação "0 - Não é prioridade" vira ERRO com 2 cláusulas

Mudança crítica 2/2 pedida pelo usuário: a antiga regra de aviso "“0 - Não é
prioridade” + outra tipologia" passa a ser **erro** (bloqueia o envio), desdobrada em
duas cláusulas sobre as colunas de tipologia (O = "0 - Não é prioridade"; P–AZ = demais):

1. **"0" = "Sim"** → todas as demais tipologias devem ser "Não". Qualquer outra com
   "Sim" gera o erro "“0 - Não é prioridade” + outra tipologia" (o achado lista as
   colunas em conflito).
2. **"0" = "Não"** → pelo menos uma das demais tipologias deve ser "Sim". Linha toda
   "Não" (ou sem nenhum "Sim", mesmo com células em branco) gera o erro novo
   "Nenhuma tipologia assinalada" ("Todas as células de classificação não podem ser
   assinaladas como “Não”").

Premissas assumidas (confirmar com o usuário se necessário): na cláusula 1, células em
branco não disparam o erro (só "Sim" explícito conflita — branco não é "assinalada");
com a coluna "0" em branco, nenhuma das duas cláusulas se aplica.

Implementação: `backend/validacao.py` (bloco reescrito + `_DESCRICOES`);
`backend/tests/test_validacao.py` — teste do aviso antigo substituído por 4 novos
(cláusula 1 erro; "0"=Sim com demais "Não" ok; cláusula 2 erro com tudo "Não";
cláusula 2 erro com demais em branco). **Suíte: 105 verdes.** Mesma pendência de
produção da decisão anterior (pull + restart; front não mudou nesta).

## Decisão (2026-07-09) — modelo oficial do Anexo V substituído (versão 09/07/2026)

A planilha nova (entregue em `manuais/nova/`) substituiu a antiga em
`manuais/Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.xlsx` (mesmo nome;
a antiga foi apagada na sobrescrita, a pedido do usuário). Comparação estrutural antes
da troca: **idêntica** em tudo que o backend consome — mesmas 4 abas, mesmos 52
cabeçalhos da aba Preenchimento (mesma ordem), aba Dominios igual → nenhuma mudança
de código no parser/validação. `VERSAO_DATA` do front atualizada de 23/06/2026 para
**09/07/2026** (`VersaoPlanilha.jsx` e `relatorioCsv.js`). Suíte 105 verdes + build OK.

⚠️ Produção: `manuais/` está FORA do git — o `git pull` no VPS **não** leva o modelo
novo. É preciso enviá-lo por scp (ver comando atualizado na decisão seguinte).
O download `/api/modelo` serve o arquivo do disco a cada requisição (atualiza sem
restart), mas o restart já é exigido pelas outras duas mudanças do dia.

## Decisão (2026-07-09) — nome do modelo passa a ser VERSIONADO (`.v070926.xlsx`)

Complemento da troca acima, após o usuário reportar que o download "sempre baixa a
versão anterior": (a) produção ainda não recebeu o modelo (deploy pendente) e (b) o
front fixava o nome do arquivo baixado — versões novas chegariam com o mesmo nome,
indistinguíveis das antigas. O usuário renomeou o arquivo em `manuais/` para
**`Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.v070926.xlsx`** e o nome
versionado virou o padrão em toda a cadeia:

- `backend/planilha.py` — `_MODELO_PADRAO` aponta para o nome versionado (docstring
  instrui o que atualizar a cada versão nova).
- `backend/app.py` — `/api/modelo` serve com `filename=_MODELO_PADRAO.name` (deixa de
  duplicar o nome).
- `modelo/src/lib/api.js` — `a.download` com o nome versionado (deve acompanhar o back).
- `backend/tests/test_api.py` — teste do download agora exige `v070926` no
  Content-Disposition; `test_dominios.py` passou a importar `_MODELO_PADRAO` em vez de
  duplicar o caminho (o skip silencioso pós-rename foi o sintoma). **Suíte: 105 verdes.**

A cada modelo novo: renomear com `vDDMMAA` novo + atualizar os 3 pontos acima +
`VERSAO_DATA` do front + scp ao VPS:
`scp "manuais/Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.v070926.xlsx" root@gerenciador-gclt.com:/opt/anexov/manuais/`
(o arquivo antigo em `/opt/anexov/manuais/` pode ser removido depois).

## Decisão (2026-07-14) — coluna "0 - Não é prioridade" em branco vira ERRO (obrigatório)

Bug reportado a partir do arquivo `bug_fix/…ECO-030-A-2025_.xlsx`: a planilha (654
linhas, contrato ECO 030/2024, AC) foi **aceita sem bloqueio** mesmo com a coluna "0 -
Não é prioridade" (col O) **em branco em 100% das linhas**. Diagnóstico com os dados
reais: as linhas **estão classificadas** (toda linha tem ≥1 "Sim" numa tipologia
prioritária — dominante col AA "IV.7 - Família de agricultores familiares", "Sim" em
650/654), então a aceitação era substantivamente correta quanto à classificação. O que
escapava era a própria célula "0" em branco: a condicional de consistência só tratava
`"0"="Sim"` (cláusula 1) e `"0"="Não"` (cláusula 2), e "0" **não** estava em
`OBRIGATORIOS` — então "0" vazio não acionava nada. Isso contradizia a premissa
documentada em 2026-07-09 ("com a coluna '0' em branco, nenhuma das duas cláusulas se
aplica"), que **fica revertida** aqui.

Decisão do usuário: **"0" em branco = erro bloqueante** (a coluna passa a ser de
preenchimento obrigatório, Sim/Não). Efeito colateral positivo: fecha o furo em que uma
linha **totalmente sem classificação** ("0" e demais em branco) passava calada — agora
o "0" obrigatório já a bloqueia. As duas cláusulas anteriores seguem inalteradas.

- `backend/validacao.py`: nova cláusula 0 (`if zero == ""` → erro
  `"“0 - Não é prioridade” em branco"`) antes das cláusulas 1/2; entrada em `_DESCRICOES`;
  docstring de `regras_formato_dominio` atualizada (3 cláusulas).
- `backend/tests/test_validacao.py`: +2 testes (`test_zero_em_branco_e_erro` reproduz o
  arquivo; `test_zero_em_branco_fecha_furo_da_linha_sem_classificacao`). **Suíte: 107 verdes.**
- Verificado no arquivo real: antes 0 achados de "0 em branco" → depois **654 erros** (bloqueia).

Pendente para produção: commit/push + no VPS `git pull` + `systemctl restart anexov-api`
(regra vive no processo Python; front não mudou). ⚠️ Impacto operacional: planilhas com a
coluna "0" em branco (prática atual de alguns operadores, como este arquivo) passam a ser
**rejeitadas** — avisar os operadores a preencher "Não" na coluna "0" quando a UC tiver
outra tipologia.

## Decisão (2026-07-14) — modelo oficial atualizado para a versão v260714 (14/07/2026)

Nova planilha-modelo entregue em `manuais/Anexo V - Planilha - Painel de Monitoramento -
MME-CC_UF.v260714.xlsx` (1.637.721 bytes), substituindo a `v070926`. Seguindo o checklist
de troca de versão (decisão 2026-07-09), atualizados **todos** os pontos da cadeia do nome
versionado:

- `backend/planilha.py` — `_MODELO_PADRAO` → `…v260714.xlsx` (+ comentário).
- `modelo/src/lib/api.js` — `a.download` → `…v260714.xlsx` (+ comentário).
- `modelo/src/components/VersaoPlanilha.jsx` e `modelo/src/lib/relatorioCsv.js` —
  `VERSAO_DATA` de "09/07/2026" → **"14/07/2026"**.
- `backend/tests/test_api.py` — `test_modelo_baixa_o_arquivo` agora exige `v260714` no
  Content-Disposition. `test_dominios.py` lê o modelo real via `_MODELO_PADRAO` (sem
  mudança) e passou contra o arquivo novo. **Suíte: 107 verdes + build do front OK.**

`/api/modelo` serve o arquivo do disco a cada requisição (troca de conteúdo não exige
restart), mas o restart já é exigido pela mudança de regra "0 em branco" do mesmo dia.
⚠️ Produção: `manuais/` está FORA do git — o `git pull` no VPS **não** leva o modelo novo;
é preciso enviá-lo por scp:
`scp "manuais/Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.v260714.xlsx" root@gerenciador-gclt.com:/opt/anexov/manuais/`
(o `v070926` no VPS pode ser removido depois).

## Decisão (2026-07-14) — 2 avisos de coerência do "Tipo de Comunidade" tradicional

Pedido do usuário: duas regras **não-bloqueantes (avisos)**, aplicáveis **somente** quando
a coluna M "Tipo de Comunidade" é uma comunidade tradicional — `1 - Comunidade indígena`,
`2 - Comunidade quilombola` ou `3 - Comunidade ribeirinha` (referência: 4 linhas
propositais no modelo `v260714`, todas coerentes):

1. **Enquadramento ≠ Povos tradicionais** — comunidade tradicional exige coluna N
   "Enquadramento do beneficiário" = `4 - Povos tradicionais`; qualquer outro valor
   (inclusive em branco) gera aviso.
2. **Tipologia de família ≠ Tipo de Comunidade** — a família correspondente deve casar:
   indígena→`IV.1 - Família indígena` (col U), quilombola→`IV.2` (V), ribeirinha→`IV.3`
   (W). A esperada deve ser "Sim" e as outras duas ≠ "Sim"; senão, aviso.

Premissas assumidas (avisos, então liberais): (a) escopo **só na direção M→N/U/V/W** — não
há checagem reversa (ex.: `Família indígena=Sim` numa comunidade não-tradicional **não**
gera aviso); (b) na regra 2, célula em branco nas duas famílias "não-esperadas" é tolerada
(conta como "não marcada"), mas a família esperada em branco (sem "Sim") gera aviso.

Implementação: `backend/validacao.py` (constantes `COL_FAM_*`, mapa `_COMUNIDADE_FAMILIA`,
`_ENQUAD_POVOS_TRADICIONAIS`; bloco de avisos no loop por linha; 2 entradas em
`_DESCRICOES`; docstring). `backend/tests/test_validacao.py`: base `linha_valida`/`DOM`
ajustada (Tipo base agora é `11 - Rural geral`, não-tradicional, p/ não disparar as novas
regras) + **5 testes novos**. **Suíte: 112 verdes.** Front **não muda** — o painel e o
sucesso já renderizam os `grupos`/avisos vindos do backend.

Verificado contra o arquivo real: as 4 linhas corretas → 0 avisos novos; enquadramento
errado → aviso 1; família trocada → aviso 2. Pendente p/ produção: commit/push + `git pull`
no VPS + `systemctl restart anexov-api` (regra vive no processo Python).