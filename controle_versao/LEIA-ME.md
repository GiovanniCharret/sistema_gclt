# `controle_versao/` — a história do projeto, em fases e sub-fases

Esta pasta guarda **o que mudou no sistema, quando e por quê**, de um jeito que serve para
três leitores diferentes: uma pessoa que quer entender o projeto, o rodapé do site que mostra
a última atualização, e uma futura página que desenhe a evolução na tela.

## Os arquivos

| Arquivo | Para quem | Edita à mão? |
|---|---|---|
| **`historico.json`** | máquina (rodapé do site, página futura) | **Sim — é a fonte única** |
| `HISTORICO.md` | gente | **Não — é gerado** |
| `atualizar.py` | ferramenta | só se quiser mudar o formato do `.md` |
| `LEIA-ME.md` | gente (este arquivo) | sim |

A regra que mantém isso saudável: **existe uma fonte, e tudo o mais é derivado dela.** O
`.md` é gerado pelo `atualizar.py`; se você editar o `.md` à mão, a próxima execução apaga o
que escreveu. É de propósito — duas histórias mantidas à mão divergem em uma semana.

## Três coisas diferentes chamadas "controle de versão"

Vale separar, porque o nome é o mesmo e o significado não:

1. **Git** — guarda o *código*, linha por linha, com autor e data. Já existia neste projeto
   desde 23/06/2026. É o que permite voltar atrás. Não serve para contar a história a
   alguém: são centenas de mensagens técnicas curtas.
2. **Versão do produto** (`V0`, `V1`) — o marco comercial/funcional, registrado em
   `planning/VERSOES.md`. V0 foi entregue em 07/07/2026; a V1 está em planejamento.
3. **Esta pasta** — a narrativa: fases, sub-fases, motivo de cada decisão. É a ponte entre
   os dois de cima, e é o que o rodapé do site e a página futura vão ler.

O registro detalhado de cada decisão continua em `planning/PLAN.md` (que fica só na máquina
local). Esta pasta é o **resumo curado** dele: menos detalhe técnico, mais história.

## O formato do `historico.json`

```jsonc
{
  "esquema": "1.0",                  // versão do formato; muda se a estrutura mudar
  "produto": { ... },                // nome, subtítulo, órgão, URL de produção
  "gerado_em": "2026-10-02",
  "versao_app": "V0.0.1002",         // ← DERIVADO: o que o rodapé exibe
  "ultima_atualizacao": { ... },     // ← DERIVADO: data, fase, sub-fase, título, resumo
  "contadores": { ... },             // ← DERIVADO: quantas fases, quantas sub-fases, período
  "legenda_tipos": { ... },          // o que cada tipo significa, em uma linha
  "fases": [ ... ]                   // a história
}
```

**Os três campos marcados como DERIVADO não são escritos à mão.** O `atualizar.py` os
recalcula a partir das sub-fases. É o que impede o rodapé de exibir uma data velha: a última
atualização é, por construção, a sub-fase mais recente.

### Uma fase

```jsonc
{
  "id": "F9",                                  // F + número, na ordem cronológica
  "nome": "Depois do merge: o e-mail de acesso",
  "periodo": { "inicio": "2026-10-01", "fim": null },   // fim: null = fase aberta
  "estado": "em_andamento",                    // concluida | em_andamento | planejada
  "resumo": "Dois ou três períodos explicando o tema da fase.",
  "subfases": [ ... ]
}
```

### Uma sub-fase

```jsonc
{
  "id": "F9.1",                 // id da fase + ponto + número
  "data": "2026-10-01",         // SEMPRE AAAA-MM-DD (é o que ordena corretamente)
  "tipo": "correcao",           // ver a tabela abaixo
  "titulo": "O e-mail de criação de senha não saía",
  "resumo": "O que aconteceu, em uma ou duas frases, sem jargão.",
  "impacto": "Opcional: a consequência prática para quem usa o sistema.",
  "fonte": "commit 80e2634"     // onde conferir: commit, documento, merge
}
```

| `tipo` | Quando usar |
|---|---|
| `entrega` | funcionalidade nova, visível para quem usa |
| `decisao` | escolha de rumo, com o motivo registrado |
| `correcao` | defeito encontrado e consertado |
| `incidente` | algo quebrou em produção — fica registrado para não repetir |
| `seguranca` | redução de risco (segredo, permissão, exposição) |
| `infra` | servidor, banco, rede, publicação |
| `dados` | base de referência e cadastros |

O vocabulário é **fechado de propósito**: o `atualizar.py` recusa um tipo que não esteja
nessa lista. Sem isso, em dois meses haveria `fix`, `bugfix`, `conserto` e `correção`
significando a mesma coisa, e nenhuma filtragem possível na página futura.

## Como acrescentar uma entrada (o passo a passo)

1. Abra o `historico.json`.
2. Ache a fase onde o fato se encaixa. Se for um tema novo, crie uma fase nova no **fim** da
   lista `fases`, com o próximo número (`F10`), `estado: "em_andamento"` e `fim: null`.
3. Acrescente a sub-fase no fim da lista `subfases` daquela fase, com o próximo número.
4. Rode, da raiz do repositório:

   ```bash
   python controle_versao/atualizar.py
   ```

5. Leia o relatório. Se o JSON estiver torto (vírgula sobrando, data errada, tipo
   desconhecido), ele **não grava nada** e diz exatamente o que corrigir.

Para só conferir, sem gravar: `python controle_versao/atualizar.py --conferir`. É um bom
hábito antes de publicar o código.

## A numeração da versão exibida

O rodapé do site mostra algo como **`V0.0.1002`**:

| Parte | Significa | Quem decide |
|---|---|---|
| `V0` | versão do produto | **você** (`V1` quando a V1 for entregue) |
| `.0` | marco dentro da versão | **você** |
| `.1002` | dia da última atualização (MMDD) | o `atualizar.py`, automaticamente |

O script **preserva** os dois primeiros números e recalcula só o sufixo de data. Para marcar
um avanço grande, edite `versao_app` para, por exemplo, `V0.1.0000` e rode o script: ele
manterá o `V0.1` e corrigirá a data.

## Como o site lê isso (ligado em 02/10/2026)

O caminho da ponta à ponta, hoje:

```
controle_versao/historico.json  →  backend/versao.py  →  GET /api/versao  →  rodapé
```

O rodapé mostra, por exemplo: **`V0.0.1002 · atualizado em 02/10/2026 · Monitoramento dos
Beneficiários do Programa`**. Antes era a constante `VERSAO_APP`, escrita no código do front
— e justamente por isso ficou parada em `V0.0.0804` por quase dois meses. **A constante foi
removida**: não há mais onde a versão envelhecer sem ninguém notar.

| Rota | Acesso | Conteúdo | Quem usa |
|---|---|---|---|
| `GET /api/versao` | **aberta** | `{versao, data, esquema}` | o rodapé, inclusive na tela de login |
| `GET /api/versao/historico` | protegida | o documento inteiro | a futura página de evolução |

Três decisões que vale conhecer:

1. **A rota aberta devolve só três campos, e isso é regra.** O rodapé aparece **antes do
   login**, então tudo o que ele mostra é público para a internet. O histórico completo narra
   incidentes e traz uma entrada que descreve um risco aceito — material que não pode sair
   sem autenticação. Dois testes travam essa fronteira.
2. **Lê do disco a cada pedido, sem cache.** Editar o JSON e publicar vale na requisição
   seguinte. É a razão de ser uma rota, e não um arquivo embutido na construção do site.
3. **Falha sem mentir.** Se a rota não responder (arquivo não publicado → 503, ou rede fora),
   o rodapé mostra só o nome do produto, **sem versão**. Exibir um número velho seria repetir
   o defeito que originou tudo isto.

## O que esta pasta **não** é

- **Não é backup.** Quem guarda o código é o git; quem guarda o banco é o backup da Azure.
- **Não é a história do banco de dados.** Mudança de estrutura de tabela não tem registro
  versionado hoje — é uma lacuna conhecida do projeto, anotada aqui para não ser esquecida.
- **Não é documentação técnica.** Para "como funciona", veja o `CLAUDE.md`; para o detalhe de
  cada decisão, o `planning/PLAN.md`.

## Próximos passos possíveis

1. ~~Ligar o rodapé ao JSON~~ — **feito em 02/10/2026** (ver a seção acima).
2. **Página estática de evolução**: um `.html` nesta pasta que leia o `historico.json` e
   desenhe a linha do tempo, com filtro por tipo de fato. Como o JSON já traz `legenda_tipos`
   e os tipos são fechados, a página sai sem precisar de mais nada.
3. **Esquema formal** (JSON Schema): um arquivo que descreve o formato de maneira que
   editores validem enquanto você digita. O `atualizar.py` já faz essa checagem; o esquema
   só a traria para dentro do editor.
