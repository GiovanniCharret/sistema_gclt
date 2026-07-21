"""Testes do parser da planilha (`backend/planilha.py`) — Bloco D1.

Por que existe: a §13 da spec exige cobrir a leitura da aba `Preenchimento` (cabeçalho
na linha 2, mapeamento por nome), a definição de "linha de dados" (tem ODI/UC), os erros
estruturais (sem aba / não-.xlsx) e a leitura defensiva de data/coordenada.
"""

# `datetime` compara as datas normalizadas.
import datetime

# `pytest` para asserções aproximadas e checagem de exceção.
import pytest

# Funções/erros sob teste do parser.
from backend.planilha import (
    ler_preenchimento,
    normalizar_data,
    normalizar_coordenada,
    normalizar_id,
    normalizar_nome,
    normalizar_uf,
    PlanilhaInvalida,
)
# Gerador de .xlsx-fixture.
from backend.tests.fixtures import gerar_xlsx


def test_ler_preenchimento_mapeia_por_cabecalho_e_marca_linha():
    """Lê as linhas de dados mapeadas por nome de coluna, com o nº da linha real.

    Entrada: .xlsx com 2 linhas (ODI/UC/UF).
    Fase 1: parseia.
    Fase 2: 2 registros; valores mapeados por cabeçalho; `_linha` = linha real (3, 4).
    """
    # Fase 1: 2 linhas de dados.
    conteudo = gerar_xlsx([
        {"Número ODI": "210001", "Número da Unidade Consumidora": "70012345", "UF": "AM"},
        {"Número ODI": "210002", "Número da Unidade Consumidora": "70012890", "UF": "PA"},
    ])
    linhas = ler_preenchimento(conteudo)
    # Fase 2: mapeamento e número de linha.
    assert len(linhas) == 2
    assert linhas[0]["Número ODI"] == "210001"
    assert linhas[0]["UF"] == "AM"
    assert linhas[0]["_linha"] == 3
    assert linhas[1]["_linha"] == 4


def test_ler_preenchimento_ignora_linhas_sem_odi_e_uc():
    """Linhas sem ODI e sem UC são ignoradas (não contam como dados)."""
    # Linha do meio vazia → ignorada.
    conteudo = gerar_xlsx([
        {"Número ODI": "210001", "Número da Unidade Consumidora": "70012345"},
        {},
        {"Número ODI": "210002", "Número da Unidade Consumidora": "70012890"},
    ])
    assert len(ler_preenchimento(conteudo)) == 2


def test_ler_preenchimento_mapeia_com_cabecalho_reordenado():
    """O mapeamento é por NOME — colunas fora de ordem ainda casam."""
    # Cabeçalho em ordem diferente da padrão.
    cab = ["UF", "Número da Unidade Consumidora", "Número ODI"]
    conteudo = gerar_xlsx(
        [{"UF": "RR", "Número ODI": "1", "Número da Unidade Consumidora": "9"}],
        cabecalho=cab,
    )
    linhas = ler_preenchimento(conteudo)
    assert linhas[0]["Número ODI"] == "1"
    assert linhas[0]["UF"] == "RR"


def test_ler_preenchimento_sem_aba_preenchimento_levanta_erro():
    """Planilha sem a aba `Preenchimento` → PlanilhaInvalida (→ 400 na rota)."""
    # Aba com outro nome.
    conteudo = gerar_xlsx([{"Número ODI": "1"}], aba="Outra")
    with pytest.raises(PlanilhaInvalida):
        ler_preenchimento(conteudo)


def test_ler_preenchimento_arquivo_nao_xlsx_levanta_erro():
    """Bytes que não são um .xlsx válido → PlanilhaInvalida (→ 400)."""
    with pytest.raises(PlanilhaInvalida):
        ler_preenchimento(b"isto nao e um arquivo xlsx")


def test_ler_preenchimento_zero_linhas_de_dados_retorna_vazio():
    """Planilha só com linhas vazias → lista vazia (guarda de 'sem dados' fica na validação)."""
    # Duas linhas totalmente vazias.
    conteudo = gerar_xlsx([{}, {}])
    assert ler_preenchimento(conteudo) == []


def test_normalizar_data_aceita_texto_e_serial_do_excel():
    """`normalizar_data` aceita `DD/MM/AAAA` (texto) e datetime (serial do Excel)."""
    assert normalizar_data("14/02/2026") == datetime.date(2026, 2, 14)
    assert normalizar_data(datetime.datetime(2026, 2, 14)) == datetime.date(2026, 2, 14)
    assert normalizar_data("não é data") is None
    assert normalizar_data(None) is None


def test_normalizar_id_tira_zero_a_esquerda_e_sufixo_float():
    """`normalizar_id` casa IDs que o Excel mangla (zero à esquerda, número, float).

    Motivação: o Excel guarda ODI/UC como número, perdendo zeros à esquerda; a
    referência (CSV, texto) preserva. Normalizar dos dois lados faz casar.
    """
    assert normalizar_id("0102500087") == "102500087"   # zero à esquerda (CSV)
    assert normalizar_id(102500087) == "102500087"       # int (Excel)
    assert normalizar_id(102500087.0) == "102500087"     # float (Excel)
    assert normalizar_id("789950") == "789950"           # sem zero → inalterado
    assert normalizar_id("ODR142PROJ001") == "ODR142PROJ001"  # alfanumérico intacto
    assert normalizar_id("0") == "0"                     # zero puro preservado
    assert normalizar_id(None) == ""                     # vazio


def test_normalizar_nome_ignora_acento_caixa_e_espacos():
    """`normalizar_nome` casa nomes que divergem só por acento, caixa e espaços
    (inclusive no meio): 'RORAINÓPOLIS' == 'RORAINOPOLIS', 'SANTA LUZ' == 'SANTALUZ'."""
    # Acento (caso reportado: planilha com acento, base sem).
    assert normalizar_nome("RORAINÓPOLIS") == normalizar_nome("RORAINOPOLIS")
    # Bordas + acento + caixa.
    assert normalizar_nome(" Rorainópolis ") == normalizar_nome("RORAINOPOLIS")
    # Espaço no meio ignorado.
    assert normalizar_nome("SANTA LUZ") == normalizar_nome("SANTALUZ")
    assert normalizar_nome("São João  do  Norte") == normalizar_nome("SAOJOAODONORTE")
    # Caixa.
    assert normalizar_nome("MUCAJAÍ") == normalizar_nome("mucajai")
    # Forma canônica: sem acento, sem espaço, minúscula.
    assert normalizar_nome("  Cantá ") == "canta"
    # Vazio.
    assert normalizar_nome(None) == ""
    # Nomes de fato diferentes NÃO colidem.
    assert normalizar_nome("BOA VISTA") != normalizar_nome("RORAINOPOLIS")


def test_normalizar_uf_equivale_sigla_e_nome_completo():
    """`normalizar_uf` trata sigla e nome completo como a MESMA UF.

    Caso real (2026-07-21): a planilha preenche a sigla ('AP') e o novo
    `consolidado_ucs_modelo.csv` do LPT passou a trazer o nome por extenso
    ('Amapá'). `normalizar_nome` sozinho não resolve ('ap' != 'amapa'); a UF é
    um conjunto fechado (27), então canonizamos para a sigla dos dois lados.
    """
    # Sigla × nome por extenso (com e sem acento, caixa e espaços) devem coincidir.
    assert normalizar_uf("AP") == normalizar_uf("Amapá")
    assert normalizar_uf("ap") == normalizar_uf("AMAPA")
    assert normalizar_uf("RJ") == normalizar_uf("Rio de Janeiro")
    assert normalizar_uf("SP") == normalizar_uf("São Paulo")
    assert normalizar_uf("RO") == normalizar_uf("Rondônia")
    assert normalizar_uf("PA") == normalizar_uf("Pará")
    # UFs diferentes NÃO colidem (não afrouxa a checagem).
    assert normalizar_uf("AP") != normalizar_uf("AM")
    assert normalizar_uf("Amapá") != normalizar_uf("Amazonas")
    # Vazio é tolerado (não quebra).
    assert normalizar_uf(None) == ""
    # Valor desconhecido cai na forma canônica de nome (comparável, não quebra).
    assert normalizar_uf("Xingu") == normalizar_nome("Xingu")


def test_normalizar_coordenada_aceita_virgula_e_ponto():
    """`normalizar_coordenada` aceita decimal com `,` ou `.` e números."""
    assert normalizar_coordenada("-3,3018") == pytest.approx(-3.3018)
    assert normalizar_coordenada("-3.3018") == pytest.approx(-3.3018)
    assert normalizar_coordenada(-3.3018) == pytest.approx(-3.3018)
    assert normalizar_coordenada("abc") is None
    assert normalizar_coordenada(None) is None
