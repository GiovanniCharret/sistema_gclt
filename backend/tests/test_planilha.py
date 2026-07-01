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


def test_normalizar_coordenada_aceita_virgula_e_ponto():
    """`normalizar_coordenada` aceita decimal com `,` ou `.` e números."""
    assert normalizar_coordenada("-3,3018") == pytest.approx(-3.3018)
    assert normalizar_coordenada("-3.3018") == pytest.approx(-3.3018)
    assert normalizar_coordenada(-3.3018) == pytest.approx(-3.3018)
    assert normalizar_coordenada("abc") is None
    assert normalizar_coordenada(None) is None
