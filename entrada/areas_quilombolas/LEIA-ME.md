# `entrada/areas_quilombolas/` — áreas de quilombolas do INCRA

**O que é:** o shapefile das **áreas de quilombolas** reconhecidas pelo INCRA, usado pela regra
de validação *"Comunidade quilombola fora de território do INCRA"* (`backend/validacao.py`).

**Quem lê:** `backend/geo_territorios.py::carregar_quilombolas()`. Mais ninguém.
⚠️ `backend/referencia.py` **não** vê esta pasta: ele faz `glob("**/*.csv")`, e aqui não há `.csv`.

## Os arquivos

| arquivo | o que é | sem ele |
|---|---|---|
| `areas_quilombolas.shp` | a geometria (390 polígonos, 147.305 vértices) | nada funciona |
| `areas_quilombolas.shx` | índice do `.shp` | leitura falha |
| `areas_quilombolas.dbf` | os atributos (23 colunas) | leitura falha |
| `areas_quilombolas.prj` | o sistema de coordenadas (SIRGAS 2000) | lê igual; fica sem procedência |

**São um conjunto: os quatro andam juntos.** Apagar um quebra a leitura dos outros.

## Origem e atualização

- **Fonte:** INCRA, camada *Áreas de Quilombolas*. O download vem num `.zip`; **o `.zip` não entra
  aqui** (decisão do usuário, 2026-10-21) — ele é extraído e os quatro arquivos ficam soltos, com
  nome canônico em ASCII. O arquivo original fica em `manuais/areas_quilombolas.zip`, **fora do
  git** (`.gitignore`).
- **Para atualizar:** extrair o novo download, renomear os quatro para `areas_quilombolas.*`,
  substituir aqui e **rodar a suíte** — `backend/tests/test_geo_territorios.py` fixa a contagem de
  **390** áreas e vai acusar a mudança. Isso é intencional: trocar a base muda quais UCs passam a
  ser reprovadas, e isso é decisão, não detalhe.
- **Recarga:** o backend relê sozinho quando o `.shp` muda (mtime + tamanho), como `entrada/**.csv`.
  Não precisa reiniciar.
- **Deploy:** `entrada/` é versionado e entra na imagem por `COPY . .` — nada de scp. **2,6 MB.**

## Duas coisas que o dado tem de ruim, e que o código já trata

1. ⚠️ **`nr_area_ha` é lixo em pelo menos um registro.** `MONGE BELO` (MA) declara
   **72.466.129 ha**; a geometria dá **5.693 ha** (e o campo `area_calc_`, do próprio INCRA, dá
   5.655 ha). Esse único registro responde por 96% da soma do campo na base inteira.
   **Decisão do usuário (2026-10-21): a área sai sempre do cálculo do polígono, nunca da célula.**
   É o que `Area.hectares()` faz, e um teste fixa isso.
2. ⚠️ **O `.dbf` é latin-1 e o `.cpg`/`.cst` do download vem VAZIO** — a codificação é passada à
   mão no código. Sem isso, "PAREDÃO" apareceria como "PAREDÃO" na tela do operador.
   Também há sujeira de digitação em `esfera`: `FEDERAL` (283), `Federal` (21), `FEDEERAL` (1).

## O que a base cobre — e o que não cobre

São **390 territórios com processo de regularização fundiária**, por fase: RTID 118,
**TITULADO 104**, PORTARIA 65, DECRETO 48, TÍTULO PARCIAL 25, em branco 15. Por UF: PA 80, MA 61,
BA 39, RS 26, RJ 20, SE 17, MG 16, SP 16, CE 15, PI 13, PR 9, PB 9 e outras.

⚠️ **Não é o mapa das comunidades quilombolas.** O Censo 2022 do IBGE mapeou **8.441 localidades**;
estas 390 são as que têm processo no INCRA. **Uma comunidade real sem processo cai fora de todos
os polígonos** — e a regra, sendo **erro** (decisão do usuário), bloqueia o envio dessa planilha.
Todas as fases contam como território reconhecido: filtrar por "TITULADO" deixaria 104 áreas.
