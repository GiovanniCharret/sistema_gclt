"""Testes do filtro de acesso por login (`backend/acesso.py`) — Bloco A4.

Por que existe: a §5.1 da spec define o filtro de escopo em duas camadas
(domínio do e-mail → grupo econômico → siglas/contratos visíveis), com `ENBPAR`
como curinga. Estes testes cobrem a resolução do grupo, o curinga, o caso
ÂMBAR (3 siglas) e o domínio desconhecido. As contagens reais (18 / 41 / 7) usam
a `base_contratos.json` de verdade — é o critério de aceite da A4.

Nota: a sigla "ÂMBAR" usa o caractere precomposto U+00C2 (`Â`); referencia-se
por escape para evitar pegadinhas de normalização Unicode.
"""

# Funções/constantes sob teste do módulo de acesso.
from backend.acesso import grupo_do_email, siglas_do_grupo, contratos_visiveis
# Autoridade real (lista de contratos selecionáveis com sigla) para as contagens.
from backend.referencia import carregar_base_contratos

# Sigla/grupo ÂMBAR com o codepoint exato (U+00C2 = Â precomposto).
AMBAR = "ÂMBAR"


def _contratos_reais():
    """Lista de contratos selecionáveis reais (com `sigla`), da autoridade.

    Entrada: nenhuma.
    Fase 1: lê `base_contratos.json` real via `carregar_base_contratos`.
    Saída: a lista `contratos` (um dict por contrato selecionável).
    """
    # Fase 1/Saída: usa o caminho padrão (raiz) e devolve a lista de detalhe.
    return carregar_base_contratos()["contratos"]


def test_grupo_do_email_resolve_dominio():
    """Domínio do e-mail resolve o grupo econômico (camada 1).

    Entrada: e-mails com domínios conhecidos.
    Fase 1: resolve equatorial e enbpar.
    Saída: grupos corretos; case-insensitive no domínio.
    """
    # Fase 1/Saída: domínios mapeados (inclusive com caixa mista no e-mail).
    assert grupo_do_email("fulano@equatorialenergia.com.br") == "EQUATORIAL"
    assert grupo_do_email("Fulano@ENBPAR.GOV.BR") == "ENBPAR"


def test_dominio_desconhecido_nao_tem_grupo():
    """Domínio fora do mapa → sem grupo (None).

    Entrada: e-mail de domínio desconhecido e e-mail malformado.
    Saída: None nos dois casos.
    """
    # Domínio não mapeado → None.
    assert grupo_do_email("alguem@desconhecido.com") is None
    # E-mail sem "@" → None (defensivo).
    assert grupo_do_email("semarroba") is None


def test_contratos_visiveis_equatorial_sao_18():
    """EQUATORIAL enxerga só os 18 contratos de sigla EQUATORIAL (camada 2).

    Entrada: contratos reais + grupo resolvido do e-mail equatorial.
    Fase 1: resolve o grupo e filtra os contratos visíveis.
    Fase 2: confere a contagem (18) e que todos têm sigla EQUATORIAL.
    Saída: asserções.
    """
    # Fase 1: e-mail → grupo → contratos visíveis.
    grupo = grupo_do_email("op@equatorialenergia.com.br")
    visiveis = contratos_visiveis(grupo, _contratos_reais())
    # Fase 2: 18 contratos, todos da sigla EQUATORIAL.
    assert len(visiveis) == 18
    assert all(c["sigla"] == "EQUATORIAL" for c in visiveis)


def test_enbpar_curinga_ve_todos_os_41():
    """ENBPAR é curinga: enxerga todos os 41 contratos selecionáveis.

    Entrada: contratos reais + grupo ENBPAR.
    Saída: 41 contratos visíveis.
    """
    # ENBPAR (curinga) → todos os selecionáveis.
    visiveis = contratos_visiveis("ENBPAR", _contratos_reais())
    assert len(visiveis) == 41


def test_ambar_inclui_amazonas_e_roraima():
    """ÂMBAR cobre as siglas ÂMBAR, AMAZONAS e RORAIMA (7 contratos).

    Entrada: o conjunto de siglas do grupo e os contratos reais.
    Fase 1: confere que o conjunto de siglas tem as três.
    Fase 2: confere a contagem real (2 ÂMBAR + 1 AMAZONAS + 4 RORAIMA = 7).
    Saída: asserções.
    """
    # Fase 1: as três siglas pertencem ao grupo ÂMBAR.
    siglas = siglas_do_grupo(AMBAR)
    assert {AMBAR, "AMAZONAS", "RORAIMA"} <= siglas
    # Fase 2: na base real, somam 7 contratos selecionáveis.
    visiveis = contratos_visiveis(AMBAR, _contratos_reais())
    assert len(visiveis) == 7


def test_grupo_desconhecido_nao_ve_contratos():
    """Grupo inexistente → nenhuma sigla → lista vazia.

    Entrada: um grupo que não está no mapa.
    Saída: 0 contratos visíveis.
    """
    # Grupo desconhecido não enxerga nada.
    assert contratos_visiveis("INEXISTENTE", _contratos_reais()) == []
