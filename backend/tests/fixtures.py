"""Gerador de `.xlsx`-fixture da aba `Preenchimento` (openpyxl) — Bloco D.

Por que existe: os testes de parsing/validação (§13 da spec) precisam fabricar planilhas
com a aba `Preenchimento` (cabeçalho na linha 2, dados a partir da linha 3), parametrizáveis
por linha/célula para acionar cada regra — sem depender de um arquivo real (que não existe).
"""

# `io.BytesIO` devolve o .xlsx em memória (bytes), como chega no upload.
import io
# `openpyxl` monta a planilha.
import openpyxl

# Subconjunto realista de colunas (as de identificação/localização + 3 tipologias),
# suficiente para exercitar as regras. O parser mapeia por NOME, então a ordem/qtd é livre.
# `IV.1 - Família indígena` entrou em 2026-07-29: a regra de correspondência Tipo de
# Comunidade × família virou ERRO, então uma linha "limpa" com comunidade indígena precisa
# ter a coluna disponível para marcar "Sim". Célula em branco continua inerte nas demais
# linhas (as regras de tipologia ignoram vazio).
CABECALHO_PADRAO = [
    "Distribuidora", "Tipo de Atendimento", "Número ODI",
    "Número da Unidade Consumidora", "Código IBGE do Município", "Município",
    "UF", "Nome da Comunidade", "Nome da Unidade Consumidora",
    "Latitude", "Longitude", "Data de Energização da UC",
    "Tipo de Comunidade", "Enquadramento do beneficiário",
    "0 - Não é prioridade", "I - Baixa renda", "IV.1 - Família indígena",
    # Última coluna do modelo real (BA), obrigatória desde 2026-08-28. Fica no fim aqui
    # também: as colunas são casadas por NOME, mas manter a ordem do modelo evita que um
    # teste futuro que dependa de posição divirja da planilha de verdade.
    "CPF/CNPJ",
]


def gerar_xlsx(linhas, cabecalho=None, aba="Preenchimento"):
    """Cria um .xlsx (bytes) com a aba dada, cabeçalho na linha 2 e dados da linha 3.

    Entrada: `linhas` (lista de dicts {nome_coluna: valor}), `cabecalho` (lista de nomes;
             None usa o padrão) e `aba` (nome da planilha).
    Fase 1: cria o workbook e nomeia a aba.
    Fase 2: escreve o cabeçalho na linha 2 (linha 1 fica como cabeçalho de seção, em branco).
    Fase 3: escreve cada linha de dados a partir da linha 3 (célula vazia p/ chave ausente).
    Saída: os bytes do arquivo .xlsx.
    """
    # Cabeçalho efetivo.
    cabecalho = cabecalho if cabecalho is not None else CABECALHO_PADRAO
    # Fase 1: workbook + aba.
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba
    # Fase 2: cabeçalho real na linha 2 (linha 1 reservada p/ cabeçalho de seção).
    for c, nome in enumerate(cabecalho, start=1):
        ws.cell(row=2, column=c, value=nome)
    # Fase 3: dados a partir da linha 3.
    for i, linha in enumerate(linhas):
        for c, nome in enumerate(cabecalho, start=1):
            ws.cell(row=3 + i, column=c, value=linha.get(nome))
    # Saída: serializa em bytes.
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def gerar_xlsx_dominios(colunas, aba="Dominios"):
    """Cria um .xlsx (bytes) com a aba `Dominios`: cabeçalho na linha 1, valores abaixo.

    Entrada: `colunas` (dict {nome_coluna: [valores]}) e `aba`.
    Fase 1: cria o workbook e nomeia a aba.
    Fase 2: escreve cada cabeçalho na linha 1 e sua lista de valores nas linhas seguintes.
    Saída: os bytes do arquivo .xlsx.
    """
    # Fase 1: workbook + aba.
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba
    # Fase 2: para cada coluna, cabeçalho na linha 1 e valores a partir da linha 2.
    for c, (nome, valores) in enumerate(colunas.items(), start=1):
        ws.cell(row=1, column=c, value=nome)
        for r, valor in enumerate(valores, start=2):
            ws.cell(row=r, column=c, value=valor)
    # Saída: serializa em bytes.
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ───────────────────────── Bases territoriais sintéticas (2026-10-21) ─────────────────────────
# Por que sintéticas: as regras territoriais são testadas contra uma geometria CONHECIDA, não
# contra os shapefiles reais de `entrada/`. Um teste que depende da base real falharia no dia em
# que o INCRA publicasse uma atualização — e falharia dizendo "regra quebrada", que é mentira.
# Os arquivos reais têm dois testes próprios, em `test_geo_territorios.py`, e é lá que o
# acoplamento com o dado externo fica confinado.

# `array` é o formato em que `geo_territorios.Area` guarda os vértices (achatado, float64).
import array as _array

# As classes sob teste: importadas aqui para as duas suítes montarem a base do mesmo jeito.
from backend.geo_territorios import Area, BaseTerritorial


def area_retangular(nome, lat_min, lat_max, lon_min, lon_max, uf="AM", municipio="MANACAPURU",
                    fase="TITULADO"):
    """Monta uma `Area` retangular — a geometria mais simples cujo "dentro" é óbvio.

    Por que retângulo: o teste precisa afirmar com certeza que um ponto está dentro ou fora. Com
    um polígono irregular, uma falha deixaria a dúvida entre "a regra errou" e "eu errei a conta".

    Entrada: nome, os limites em graus e os atributos de identificação.
    Fase 1: monta os quatro vértices em sentido anti-horário, fechando no primeiro.
    Fase 2: achata em `array('d')` na ordem (lon, lat) — a mesma do shapefile.
    Saída: `Area` pronta para `contem`/`distancia_km`/`hectares`.
    """
    # Fase 1: anel fechado (o shapefile repete o primeiro vértice no fim).
    vertices = [(lon_min, lat_min), (lon_max, lat_min), (lon_max, lat_max),
                (lon_min, lat_max), (lon_min, lat_min)]
    # Fase 2: ⚠️ a ordem é (longitude, latitude), como no `.shp` — trocar os dois é o erro
    # silencioso clássico desse formato, e é por isso que esta função existe.
    xy = _array.array("d")
    for lon, lat in vertices:
        xy.append(lon)
        xy.append(lat)
    # `partes` guarda índices de VÉRTICE: um anel só, com a sentinela do total ao final.
    return Area(nome=nome, uf=uf, municipio=municipio, fase=fase, xy=xy,
                partes=(0, len(vertices)), bbox=(lon_min, lat_min, lon_max, lat_max))


def base_sintetica(*areas, rotulo="base de teste"):
    """Monta uma `BaseTerritorial` com as áreas dadas (sem arquivo e sem mtime).

    Entrada: `Area`s e um rótulo.
    Saída: `BaseTerritorial` consultável, com `caminho=None` (nada em disco).
    """
    # `caminho=None` é o que distingue base de teste de base carregada: `resumo()` devolve
    # `arquivo: None`, e nenhuma recarga por mtime é possível.
    return BaseTerritorial(rotulo, list(areas), None)
