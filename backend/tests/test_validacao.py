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


def test_uc_duplicada_com_odis_diferentes_e_erro():
    """Mesma UC em duas linhas, mesmo com ODIs diferentes → erro 'UC duplicada'."""
    linhas = [linha_valida(_linha=3, **{"Número ODI": "210001"}),
              linha_valida(_linha=4, **{"Número ODI": "210002"})]  # mesma UC, ODIs distintos
    achados = regras_formato_dominio(linhas, DOM)
    assert ("err", "UC duplicada") in _regras(achados)


def test_uc_duplicada_aponta_todas_as_linhas():
    """Cada linha com a UC repetida vira um achado; o problema lista as linhas envolvidas."""
    linhas = [linha_valida(_linha=3, **{"Número ODI": "210001"}),
              linha_valida(_linha=4, **{"Número ODI": "210002"}),
              linha_valida(_linha=7, **{"Número ODI": "210003"})]  # mesma UC em 3 linhas
    duplicadas = [a for a in regras_formato_dominio(linhas, DOM) if a["regra"] == "UC duplicada"]
    # Um achado por linha repetida, cada um na sua localização.
    assert [a["loc"] for a in duplicadas] == ["L3", "L4", "L7"]
    # O texto do problema mostra em quais linhas a UC se repete.
    assert all("linhas 3, 4, 7" in a["problema"] for a in duplicadas)


def test_uc_duplicada_normaliza_id():
    """UC lida como número (70012345) e como texto com zero à esquerda ('070012345')
    são a mesma UC → erro 'UC duplicada'."""
    linhas = [linha_valida(_linha=3, **{"Número ODI": "210001",
                                        "Número da Unidade Consumidora": 70012345}),
              linha_valida(_linha=4, **{"Número ODI": "210002",
                                        "Número da Unidade Consumidora": "070012345"})]
    achados = regras_formato_dominio(linhas, DOM)
    assert ("err", "UC duplicada") in _regras(achados)


def test_ucs_distintas_nao_geram_erro_de_duplicidade():
    """Linhas com UCs diferentes não acionam 'UC duplicada'."""
    linhas = [linha_valida(_linha=3),
              linha_valida(_linha=4, **{"Número ODI": "210002",
                                        "Número da Unidade Consumidora": "70099999"})]
    achados = regras_formato_dominio(linhas, DOM)
    assert ("err", "UC duplicada") not in _regras(achados)


def test_coordenada_invalida_e_aviso():
    """Latitude fora da faixa (91.5) → aviso 'Coordenadas inválidas' (não bloqueia)."""
    achados = regras_formato_dominio([linha_valida(**{"Latitude": "91.5"})], DOM)
    assert ("warn", "Coordenadas inválidas") in _regras(achados)


def test_data_de_qualquer_ano_e_aceita():
    """Qualquer ano é aceito (regra 'fora de 2026' excluída em 2026-07-09) → nenhum achado."""
    achados = regras_formato_dominio([linha_valida(**{"Data de Energização da UC": "12/11/2025"})], DOM)
    assert achados == []


def test_data_em_branco_continua_erro():
    """Data vazia segue sendo erro de campo obrigatório (única restrição de data)."""
    achados = regras_formato_dominio([linha_valida(**{"Data de Energização da UC": ""})], DOM)
    assert ("err", "Campos obrigatórios vazios") in _regras(achados)
    assert any(a["campo"] == "Data de Energização da UC" for a in achados)


def test_tipologia_diferente_de_sim_nao_e_aviso():
    """Coluna de tipologia com valor fora de Sim/Não → aviso."""
    achados = regras_formato_dominio([linha_valida(**{"I - Baixa renda": "X"})], DOM)
    assert ("warn", "Valor de tipologia ≠ Sim/Não") in _regras(achados)


def test_zero_sim_com_outra_tipologia_sim_e_erro():
    """Cláusula 1 (erro desde 2026-07-09): '0' = Sim exige todas as demais tipologias = Não."""
    linha = linha_valida(**{"0 - Não é prioridade": "Sim", "I - Baixa renda": "Sim"})
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "“0 - Não é prioridade” + outra tipologia") in _regras(achados)


def test_zero_sim_com_demais_nao_e_ok():
    """'0' = Sim com as demais tipologias = Não é uma linha válida (nenhum achado)."""
    linha = linha_valida(**{"0 - Não é prioridade": "Sim", "I - Baixa renda": "Não"})
    assert regras_formato_dominio([linha], DOM) == []


def test_zero_nao_sem_nenhum_sim_e_erro():
    """Cláusula 2 (erro desde 2026-07-09): '0' = Não exige pelo menos uma tipologia = Sim."""
    linha = linha_valida(**{"0 - Não é prioridade": "Não", "I - Baixa renda": "Não"})
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "Nenhuma tipologia assinalada") in _regras(achados)


def test_zero_nao_com_tipologias_em_branco_e_erro():
    """'0' = Não com as demais em branco também viola a cláusula 2 (não há nenhum Sim)."""
    linha = linha_valida(**{"0 - Não é prioridade": "Não", "I - Baixa renda": ""})
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "Nenhuma tipologia assinalada") in _regras(achados)


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


def test_cruzamento_ignora_zero_a_esquerda_do_odi():
    """ODI lido como número (zero perdido) casa com a referência normalizada.

    Reproduz o bug: planilha traz ODI 102500087 (int); a base tem "0102500087"
    (normalizada para "102500087"). Não deve acusar 'não consta'.
    """
    linhas = [linha_valida(**{"Número ODI": 102500087, "Número da Unidade Consumidora": 789950})]
    achados = regras_cruzamento(linhas, chaves_uc={("102500087", "789950")}, odi_ref={})
    assert ("err", "ODI + UC não consta na referência") not in _regras(achados)


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
