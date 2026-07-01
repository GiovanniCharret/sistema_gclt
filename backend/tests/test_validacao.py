"""Testes das regras de validação (`backend/validacao.py`) — Blocos D3/D4/D5.

Por que existe: a §7/§13 da spec definem as regras (erros e avisos), o cruzamento com
`entrada/` e a montagem da resposta. Aqui os testes usam **linhas como dicts** (o parser
já é coberto no D1) e domínios/referência **mock**, para acionar cada regra isoladamente.
"""

# Funções sob teste (D3 formato/domínio; D4 cruzamento; D5 montagem).
from backend.validacao import regras_formato_dominio, regras_cruzamento, validar

# Domínios mock (subconjunto suficiente para as regras).
DOM = {
    "TIPO_ATENDIMENTO": ["Extensão de Rede"],
    "UF": ["AM", "PA", "RR"],
    "SIM_NAO": ["Sim", "Não"],
    "TIPO_COMUNIDADE": ["1 - Comunidade indígena"],
    "ENQUADRAMENTO_BENEFICIARIO": ["0 - Não é prioridade"],
}


def linha_valida(**over):
    """Monta uma linha 100% válida; `over` sobrescreve campos para acionar uma regra."""
    base = {
        "_linha": 3,
        "Número ODI": "210001",
        "Número da Unidade Consumidora": "70012345",
        "Código IBGE do Município": "1302603",
        "Município": "MANACAPURU",
        "UF": "AM",
        "Latitude": "-3.30",
        "Longitude": "-60.0",
        "Data de Energização da UC": "14/02/2026",
        "Tipo de Atendimento": "Extensão de Rede",
        "Tipo de Comunidade": "1 - Comunidade indígena",
        "Enquadramento do beneficiário": "0 - Não é prioridade",
        "0 - Não é prioridade": "Não",
        "I - Baixa renda": "Sim",
    }
    base.update(over)
    return base


def _regras(achados):
    """Conjunto de (severidade, regra) presentes nos achados — facilita as asserções."""
    return {(a["sev"], a["regra"]) for a in achados}


def test_linha_valida_nao_gera_achados():
    """Uma linha correta não gera nenhum achado."""
    assert regras_formato_dominio([linha_valida()], DOM) == []


def test_campo_obrigatorio_vazio_e_erro():
    """Latitude vazia (em linha com ODI/UC) → erro 'Campos obrigatórios vazios'."""
    achados = regras_formato_dominio([linha_valida(**{"Latitude": ""})], DOM)
    assert ("err", "Campos obrigatórios vazios") in _regras(achados)
    assert any(a["campo"] == "Latitude" for a in achados)


def test_valor_fora_do_dominio_e_erro():
    """UF fora da lista de domínios → erro 'Valor fora do domínio'."""
    achados = regras_formato_dominio([linha_valida(**{"UF": "XX"})], DOM)
    assert ("err", "Valor fora do domínio") in _regras(achados)


def test_chave_odi_uc_duplicada_e_erro():
    """Mesma (ODI, UC) em duas linhas → erro 'Chave ODI + UC duplicada'."""
    linhas = [linha_valida(_linha=3), linha_valida(_linha=4)]  # mesmos ODI/UC
    achados = regras_formato_dominio(linhas, DOM)
    assert ("err", "Chave ODI + UC duplicada") in _regras(achados)


def test_coordenada_invalida_e_aviso():
    """Latitude fora da faixa (91.5) → aviso 'Coordenadas inválidas' (não bloqueia)."""
    achados = regras_formato_dominio([linha_valida(**{"Latitude": "91.5"})], DOM)
    assert ("warn", "Coordenadas inválidas") in _regras(achados)


def test_data_fora_de_2026_e_aviso():
    """Data com ano ≠ 2026 → aviso 'Data de energização fora de 2026'."""
    achados = regras_formato_dominio([linha_valida(**{"Data de Energização da UC": "12/11/2025"})], DOM)
    assert ("warn", "Data de energização fora de 2026") in _regras(achados)


def test_tipologia_diferente_de_sim_nao_e_aviso():
    """Coluna de tipologia com valor fora de Sim/Não → aviso."""
    achados = regras_formato_dominio([linha_valida(**{"I - Baixa renda": "X"})], DOM)
    assert ("warn", "Valor de tipologia ≠ Sim/Não") in _regras(achados)


def test_zero_nao_e_prioridade_com_outra_tipologia_e_aviso():
    """'0 - Não é prioridade' = Sim junto de outra tipologia = Sim → aviso."""
    linha = linha_valida(**{"0 - Não é prioridade": "Sim", "I - Baixa renda": "Sim"})
    achados = regras_formato_dominio([linha], DOM)
    assert ("warn", "“0 - Não é prioridade” + outra tipologia") in _regras(achados)


# ── D4 · Cruzamento com entrada/ (chaves_uc / odi_ref por contrato) ──

def test_odi_uc_nao_consta_na_referencia_e_erro():
    """(ODI, UC) ausente de `chaves_uc` → erro 'ODI + UC não consta na referência'."""
    linhas = [linha_valida(**{"Número ODI": "O9", "Número da Unidade Consumidora": "U9"})]
    achados = regras_cruzamento(linhas, chaves_uc={("O1", "U1")}, odi_ref={})
    assert ("err", "ODI + UC não consta na referência") in _regras(achados)


def test_uf_municipio_divergente_e_erro():
    """ODI existe na referência mas UF/município da linha diferem → erro."""
    linhas = [linha_valida(**{"Número ODI": "O1", "Número da Unidade Consumidora": "U1",
                              "UF": "AM", "Município": "MANAUS"})]
    achados = regras_cruzamento(linhas, chaves_uc={("O1", "U1")},
                                odi_ref={"O1": ("PA", "PORTO GRANDE")})
    assert ("err", "UF / município divergente") in _regras(achados)


def test_ucs_faltando_e_aviso():
    """UCs da referência ausentes da planilha → aviso agregado 'UCs faltando'."""
    linhas = [linha_valida(**{"Número ODI": "O1", "Número da Unidade Consumidora": "U1"})]
    chaves = {("O1", "U1"), ("O1", "U2"), ("O2", "U3")}  # faltam 2 na planilha
    achados = regras_cruzamento(linhas, chaves_uc=chaves, odi_ref={})
    assert ("warn", "UCs faltando") in _regras(achados)


def test_cruzamento_consistente_sem_achados():
    """Linha que bate 100% com a referência não gera achado."""
    linhas = [linha_valida(**{"Número ODI": "O1", "Número da Unidade Consumidora": "U1",
                              "UF": "AM", "Município": "MANACAPURU"})]
    achados = regras_cruzamento(linhas, chaves_uc={("O1", "U1")},
                                odi_ref={"O1": ("AM", "MANACAPURU")})
    assert achados == []


# ── D5 · Montagem da resposta ──

def test_validar_planilha_limpa_ok():
    """Planilha limpa e consistente → ok=True, 0 erros, sem grupos."""
    linha = linha_valida(**{"Número ODI": "O1", "Número da Unidade Consumidora": "U1",
                            "UF": "AM", "Município": "MANACAPURU"})
    r = validar([linha], DOM, chaves_uc={("O1", "U1")}, odi_ref={"O1": ("AM", "MANACAPURU")})
    assert r["ok"] is True
    assert r["totalErros"] == 0
    assert r["linhasLidas"] == 1
    assert r["grupos"] == []


def test_validar_planilha_suja_agrupa_e_marca_preview():
    """Planilha com erro → ok=False, grupo do erro e flag no preview."""
    linha = linha_valida(**{"UF": "XX", "Número ODI": "O1", "Número da Unidade Consumidora": "U1"})
    r = validar([linha], DOM, chaves_uc={("O1", "U1")}, odi_ref={})
    assert r["ok"] is False
    assert r["totalErros"] >= 1
    assert "Valor fora do domínio" in {g["title"] for g in r["grupos"]}
    # A célula UF do preview fica marcada como erro.
    assert r["previewRows"][0]["flags"].get("uf") == "err"


def test_validar_zero_linhas_e_erro_sem_dados():
    """Nenhuma linha de dados → ok=False com o grupo 'Planilha sem dados'."""
    r = validar([], DOM, chaves_uc=set(), odi_ref={})
    assert r["ok"] is False
    assert r["linhasLidas"] == 0
    assert any(g["title"] == "Planilha sem dados" for g in r["grupos"])
