# `entrada/areas_indigenas/` — Terras Indígenas da FUNAI

**O que é:** o shapefile das **Terras Indígenas** (poligonais) da FUNAI, usado pela regra de
validação *"Tipo de Comunidade divergente da localização"* (`backend/validacao.py`,
`regras_tipo_comunidade_territorial`): a relação é uma **equivalência** — se a coordenada da
UC cai **dentro** de uma destas TIs, a coluna M tem de declarar `1 - Comunidade indígena`; e se a coluna M
declara `1 - Comunidade indígena`, a coordenada tem de cair dentro de uma delas. Os dois sentidos são **erro**.

**Quem lê:** `backend/geo_territorios.py::carregar_indigenas()`. Mais ninguém.
⚠️ `backend/referencia.py` **não** vê esta pasta: ele faz `glob("**/*.csv")`, e aqui não há `.csv`.

## Os arquivos

| arquivo | o que é | sem ele |
|---|---|---|
| `areas_indigenas.shp` | a geometria (665 TIs, 1.819.506 vértices) | nada funciona |
| `areas_indigenas.shx` | índice do `.shp` | leitura falha |
| `areas_indigenas.dbf` | os atributos (18 colunas) | leitura falha |
| `areas_indigenas.prj` | o sistema de coordenadas (SIRGAS 2000) | lê igual; fica sem procedência |

**São um conjunto: os quatro andam juntos.**

## Origem e atualização

- **Fonte:** GeoServer da FUNAI, camada `Funai:tis_poligonais`, serviço WFS com
  `outputFormat=SHAPE-ZIP`. ⚠️ **O endpoint responde `403 Forbidden` a `curl` sem
  `User-Agent` de navegador** — quem automatizar a atualização precisa mandar o cabeçalho, ou vai
  depurar um 403 achando que é permissão.
- **O `.zip` não entra aqui** (decisão do usuário, 2026-10-21): ele é extraído e os quatro arquivos
  ficam soltos, renomeados de `tis_poligonais.*` para `areas_indigenas.*`. O download original fica
  em `manuais/indigena.zip`, **fora do git** (`.gitignore`).
- ⚠️ O `.cst` do download (10 bytes, vazio) **foi descartado de propósito**: um arquivo de
  codificação vazio é pior que nenhum, porque o leitor acreditaria nele. A codificação do `.dbf`
  (**latin-1**) é passada à mão no código.
- **Para atualizar:** substituir os quatro e **rodar a suíte** — `test_geo_territorios.py` fixa a
  contagem de **665** TIs e vai acusar a mudança, que é decisão e não detalhe.
- **Recarga:** automática por mtime, como `entrada/**.csv`. Sem reinício.
- **Deploy:** `entrada/` é versionado e entra na imagem por `COPY . .`. **31,4 MB** — é a maior
  coisa do repositório, e foi uma escolha consciente (o `.zip` tem 21,1 MB, mas o backend precisa
  dos arquivos abertos).

## O que a base cobre

**665 Terras Indígenas**, 25 UFs (a coluna `uf_sigla` vem **composta** quando a TI cruza divisa:
"AM, RR", "AP,PA" — e é mostrada como veio), por `fase_ti`: **Regularizada 494**, Declarada 73,
Delimitada 45, Encaminhada RI 28, Homologada 17, Em Estudo 8. Por `modalidade`: Tradicionalmente
ocupada 580, Reserva Indígena 66, Dominial Indígena 11, Interditada 8.

**Todas as fases contam** como território reconhecido — "Em Estudo" e "Delimitada" são processos em
curso, não ausência de terra indígena.

⚠️ **Existe comunidade indígena fora de TI**: aldeia urbana, retomada sem processo aberto, grupo em
área ainda não identificada. Isso **não** é mais um risco desde que a regra foi invertida em
2026-10-21: ela só dispara quando a coordenada está **dentro** de uma TI e a coluna M diz outra
coisa, então uma aldeia fora de TI não é olhada. Medido na planilha de teste do contrato
ECO 011/2018: **197 UCs** chamadas "MANGA", em OIAPOQUE/AP, caem dentro da TI **Uaçá**
(Regularizada) declaradas como `11 - Rural geral`.

## Custo medido (2026-10-21)

| operação | medida |
|---|---|
| carga do shapefile | **0,43 s** (uma vez por processo) |
| memória da base carregada | **29,2 MB** (`array('d')` achatado; como tuplas seriam ~160 MB) |
| consulta "está dentro?" em planilha real de 490 linhas | **0,071 ms por linha** |
| pior caso: ponto dentro da caixa da TI Yanomami (61.562 vértices num anel) | **10,1 ms por linha** |

⚠️ O pior caso é real: uma planilha de 490 UCs dentro da área do Yanomami custaria ~5 s de
validação. Cabe na rota, mas é o limite — se aparecer na prática, o caminho é indexar os vértices
por faixa de latitude, e não trocar de biblioteca.
