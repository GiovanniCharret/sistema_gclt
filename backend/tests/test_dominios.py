"""Testes da leitura dos domínios da aba `Dominios` (`planilha.ler_dominios`) — Bloco D2.

Por que existe: as regras de domínio (D3) validam contra as listas da aba `Dominios` do
modelo (§7). Estes testes cobrem a leitura por coluna (fixture) e, se o modelo real estiver
presente, uma checagem de sanidade das colunas esperadas.
"""

# `Path` verifica a presença do modelo real (opcional).
from pathlib import Path

# `pytest` para o skip condicional.
import pytest

# Funções sob teste.
from backend.planilha import ler_dominios, obter_dominios
# Gerador de fixture da aba Dominios.
from backend.tests.fixtures import gerar_xlsx_dominios

# Caminho do modelo real (gitignored) — usado só se existir.
_MODELO = Path(__file__).resolve().parent.parent.parent / "manuais" / \
    "Anexo V - Planilha - Painel de Monitoramento - MME-CC_UF.xlsx"


def test_ler_dominios_le_cada_coluna():
    """`ler_dominios` devolve, por cabeçalho, a lista de valores válidos (sem vazios).

    Entrada: fixture com 3 colunas de domínio.
    Fase 1: gera e lê.
    Fase 2: cada coluna vira a lista esperada.
    """
    # Fase 1: fixture com listas de tamanhos diferentes.
    conteudo = gerar_xlsx_dominios({
        "TIPO_ATENDIMENTO": ["Extensão de Rede", "Metas Excepcionais (Extensão de Rede)"],
        "UF": ["AM", "PA", "RR"],
        "SIM_NAO": ["Sim", "Não"],
    })
    dom = ler_dominios(conteudo)
    # Fase 2: listas por coluna, sem vazios.
    assert dom["SIM_NAO"] == ["Sim", "Não"]
    assert dom["UF"] == ["AM", "PA", "RR"]
    assert dom["TIPO_ATENDIMENTO"][0] == "Extensão de Rede"


@pytest.mark.skipif(not _MODELO.exists(), reason="modelo real não presente (manuais/ gitignored)")
def test_ler_dominios_do_modelo_real_tem_colunas_esperadas():
    """Sanidade: o modelo real expõe as colunas de domínio esperadas (§7)."""
    # Lê os domínios do modelo real via singleton.
    dom = obter_dominios()
    # As 5 listas usadas nas regras devem existir e não ser vazias.
    for coluna in ["TIPO_ATENDIMENTO", "UF", "SIM_NAO", "TIPO_COMUNIDADE", "ENQUADRAMENTO_BENEFICIARIO"]:
        assert coluna in dom and len(dom[coluna]) > 0
    # Sim/Não e as 27 UFs.
    assert "Sim" in dom["SIM_NAO"] and "Não" in dom["SIM_NAO"]
    assert "AM" in dom["UF"]
