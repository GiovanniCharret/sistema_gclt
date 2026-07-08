1 - Monitoramento de Beneficiários
2 - Atualização da data do termo json dos contratos - "ECOT 016/2017": {
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