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
from backend.acesso import grupo_do_email, siglas_do_grupo, contratos_visiveis, montar_contexto
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


def test_dominios_das_distribuidoras_resolvem_grupos():
    """Todos os domínios das distribuidoras (config real, .com.br) resolvem o grupo certo.

    Trava o mapa domínio→grupo usado para testar cada empresa do base_contratos.json.
    """
    esperado = {
        "op@equatorialenergia.com.br": "EQUATORIAL",
        "op@energisa.com.br": "ENERGISA",
        "op@neoenergia.com.br": "NEOENERGISA",
        "op@coelba.com.br": "NEOENERGISA",
        "op@ambarenergia.com.br": AMBAR,
        "op@cerci.com.br": "CERCI",
        "op@enbpar.gov.br": "ENBPAR",
    }
    # Cada domínio deve mapear ao grupo esperado.
    for email, grupo in esperado.items():
        assert grupo_do_email(email) == grupo
    # amazonasenergia/roraimaenergia ficam FORA do mapa até decisão dos engenheiros
    # (hoje só duplicariam a visão do grupo ÂMBAR de ambarenergia) → não registrados.
    assert grupo_do_email("op@amazonasenergia.com.br") is None
    assert grupo_do_email("op@roraimaenergia.com.br") is None


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


# Detalhe de contratos usado nos testes de contexto (formato de carregar_base_contratos).
_CONTRATOS_FIX = [
    {"numero": "C1", "uf": "PA", "sigla": "EQUATORIAL", "tipo_contrato": "MLA", "tranche": "2ª Tranche", "vigente": "Andamento"},
    {"numero": "C2", "uf": "PA", "sigla": "EQUATORIAL", "tipo_contrato": "LPT", "tranche": "1ª Tranche", "vigente": "Encerramento"},
    {"numero": "C3", "uf": "MA", "sigla": "ENERGISA", "tipo_contrato": "LPT", "tranche": "1ª Tranche", "vigente": "Andamento"},
]


def test_montar_contexto_filtra_grupo_e_agrega_ufs():
    """`montar_contexto` filtra pelo grupo do e-mail, traz UCs e agrega UFs.

    Entrada: e-mail equatorial, o detalhe de contratos e um mapa de UCs por contrato.
    Fase 1: monta o contexto.
    Fase 2: grupo EQUATORIAL; só os contratos EQUATORIAL (C1, C2); UCs do mapa; detalhe.
    Fase 3: UFs agregadas (PA com 2 contratos, nome resolvido "Pará").
    Saída: asserções.
    """
    # Fase 1: contexto para o e-mail equatorial (C1 tem 10 UCs; C2 nenhuma).
    ctx = montar_contexto("op@equatorialenergia.com.br", _CONTRATOS_FIX, {"C1": 10, "C2": 0})
    # Fase 2: grupo e contratos filtrados (só EQUATORIAL).
    assert ctx["grupo"] == "EQUATORIAL"
    assert {c["numero"] for c in ctx["contratos"]} == {"C1", "C2"}
    c1 = next(c for c in ctx["contratos"] if c["numero"] == "C1")
    assert c1["ucs"] == 10 and c1["uf"] == "PA" and c1["tipo_contrato"] == "MLA"
    assert c1["vigente"] == "Andamento"   # badge do front vem do contexto
    # Fase 3: UFs agregadas com nome e contagem.
    assert ctx["ufs"] == [{"sigla": "PA", "nome": "Pará", "contratos": 2}]


def test_montar_contexto_enbpar_ve_todos():
    """ENBPAR (curinga) enxerga todos os contratos, de qualquer sigla."""
    # E-mail enbpar → todos os contratos do detalhe.
    ctx = montar_contexto("chefe@enbpar.gov.br", _CONTRATOS_FIX, {})
    assert ctx["grupo"] == "ENBPAR"
    assert len(ctx["contratos"]) == 3


def test_montar_contexto_dominio_desconhecido_vazio():
    """Domínio fora do mapa → grupo None e listas vazias."""
    # E-mail desconhecido → nada visível.
    ctx = montar_contexto("alguem@desconhecido.com", _CONTRATOS_FIX, {})
    assert ctx["grupo"] is None
    assert ctx["ufs"] == []
    assert ctx["contratos"] == []
