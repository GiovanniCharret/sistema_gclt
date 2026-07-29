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
    "TIPO_COMUNIDADE": [
        "1 - Comunidade indígena", "2 - Comunidade quilombola", "3 - Comunidade ribeirinha",
        "4 - Comunidade extrativista",
        "11 - Rural geral / demais comunidades rurais",
    ],
    "ENQUADRAMENTO_BENEFICIARIO": [
        "0 - Não é prioridade", "1 - Famílias de baixa renda",
        "2 - Famílias inscritas no CadÚnico", "4 - Povos tradicionais",
    ],
}


def linha_valida(**over):
    """Monta uma linha 100% válida; `over` sobrescreve campos para acionar uma regra.

    O `Tipo de Comunidade` base é NÃO-tradicional (11) de propósito: a regra de
    correspondência comunidade×família (erro) só vale para 1/2/3/4, então a linha base
    não a aciona — cada teste dessa regra seta o tipo tradicional.

    O `Enquadramento do beneficiário` base é "1 - Famílias de baixa renda" pelo mesmo
    motivo: desde 2026-07-29 os enquadramentos "0" e "2 - CadÚnico" amarram a coluna
    "0 - Não é prioridade", e a base precisa ficar fora dessas duas regras.
    """
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
        "Tipo de Comunidade": "11 - Rural geral / demais comunidades rurais",
        "Enquadramento do beneficiário": "1 - Famílias de baixa renda",
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


def test_zero_em_branco_e_erro():
    """'0 - Não é prioridade' em branco → erro (obrigatório desde 2026-07-14), mesmo
    com a linha classificada em outra tipologia (caso do arquivo ECO-030-A-2025)."""
    linha = linha_valida(**{"0 - Não é prioridade": "", "I - Baixa renda": "Sim"})
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "“0 - Não é prioridade” em branco") in _regras(achados)


def test_zero_em_branco_fecha_furo_da_linha_sem_classificacao():
    """Linha sem nenhuma classificação ('0' e demais em branco) agora é erro: o '0'
    obrigatório fecha o furo em que a linha toda vazia passava calada."""
    linha = linha_valida(**{"0 - Não é prioridade": "", "I - Baixa renda": ""})
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "“0 - Não é prioridade” em branco") in _regras(achados)


# ── D3 (cont.) · Correspondência Tipo de Comunidade × tipologia de família ──
# Regra de ERRO (bloqueia o envio) desde 2026-07-29, válida só p/ os tipos 1/2/3/4:
# 1→IV.1 (U), 2→IV.2 (V), 3→IV.3 (W), 4→IV.4 (X). As demais famílias são livres.

def test_comunidade_indigena_sem_familia_iv1_e_erro():
    """(a) Tipo 1 exige IV.1='Sim'; com 'Não' → erro (bloqueia)."""
    linha = linha_valida(**{
        "Tipo de Comunidade": "1 - Comunidade indígena",
        "IV.1 - Família indígena": "Não",                             # deveria ser "Sim"
    })
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "Tipologia de família ≠ Tipo de Comunidade") in _regras(achados)


def test_comunidade_quilombola_com_familia_iv2_nao_gera_achado():
    """(b) Tipo 2 com IV.2='Sim' satisfaz a regra → sem achados."""
    linha = linha_valida(**{
        "Tipo de Comunidade": "2 - Comunidade quilombola",
        "IV.2 - Família quilombola": "Sim",
    })
    assert regras_formato_dominio([linha], DOM) == []


def test_comunidade_ribeirinha_com_familia_iv3_nao_gera_achado():
    """(c) Tipo 3 com IV.3='Sim' satisfaz a regra → sem achados."""
    linha = linha_valida(**{
        "Tipo de Comunidade": "3 - Comunidade ribeirinha",
        "IV.3 - Família ribeirinha": "Sim",
    })
    assert regras_formato_dominio([linha], DOM) == []


def test_comunidade_extrativista_exige_familia_iv4():
    """(d) Tipo 4 (novo em 2026-07-29) exige IV.4='Sim' na coluna X; 'Não' → erro."""
    linha = linha_valida(**{
        "Tipo de Comunidade": "4 - Comunidade extrativista",
        "IV.4 - Família extrativista": "Não",                         # deveria ser "Sim"
    })
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "Tipologia de família ≠ Tipo de Comunidade") in _regras(achados)


def test_comunidade_extrativista_com_familia_iv4_nao_gera_achado():
    """(d) Tipo 4 com IV.4='Sim' satisfaz a regra → sem achados."""
    linha = linha_valida(**{
        "Tipo de Comunidade": "4 - Comunidade extrativista",
        "IV.4 - Família extrativista": "Sim",
    })
    assert regras_formato_dominio([linha], DOM) == []


def test_demais_familias_sim_nao_geram_achado():
    """**A simplificação de 2026-07-29**: satisfeita a correspondência (tipo 1 + IV.1='Sim'),
    as OUTRAS famílias podem ser 'Sim' à vontade — a exclusividade mútua saiu de cena."""
    linha = linha_valida(**{
        "Tipo de Comunidade": "1 - Comunidade indígena",
        "IV.1 - Família indígena": "Sim",                             # a exigida pela regra
        "IV.2 - Família quilombola": "Sim", "IV.3 - Família ribeirinha": "Sim",
        "IV.4 - Família extrativista": "Sim",                         # antes: aviso; agora: livre
    })
    assert regras_formato_dominio([linha], DOM) == []


def test_familia_esperada_em_branco_e_erro():
    """A família exigida sem 'Sim' (célula em branco) também é erro."""
    linha = linha_valida(**{
        "Tipo de Comunidade": "3 - Comunidade ribeirinha",
        "IV.3 - Família ribeirinha": "",                              # deveria ser "Sim"
    })
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "Tipologia de família ≠ Tipo de Comunidade") in _regras(achados)


def test_comunidade_nao_tradicional_nao_aciona_a_regra():
    """Escopo: a regra só vale p/ Tipo de Comunidade 1/2/3/4. Comunidade não-tradicional
    não gera achado, mesmo com uma família 'Sim' (não há direção reversa)."""
    linha = linha_valida(**{
        "Tipo de Comunidade": "11 - Rural geral / demais comunidades rurais",
        "IV.1 - Família indígena": "Sim",
    })
    titulos = {a["regra"] for a in regras_formato_dominio([linha], DOM)}
    assert "Tipologia de família ≠ Tipo de Comunidade" not in titulos


def test_enquadramento_fora_de_povos_tradicionais_nao_gera_mais_achado():
    """A regra do Enquadramento (coluna N = '4 - Povos tradicionais') foi REMOVIDA em
    2026-07-29: comunidade tradicional com outro enquadramento não gera mais achado."""
    linha = linha_valida(**{
        "Tipo de Comunidade": "1 - Comunidade indígena",
        "Enquadramento do beneficiário": "1 - Famílias de baixa renda",  # ≠ "4 - Povos tradicionais"
        "IV.1 - Família indígena": "Sim",
    })
    assert regras_formato_dominio([linha], DOM) == []


# ── D3 (cont.) · Enquadramento (N) × “0 - Não é prioridade” (O) e tipologias (P:AZ) ──
# Duas regras de ERRO pedidas em 2026-07-29:
#   (1) N = "2 - Famílias inscritas no CadÚnico" → O obrigatoriamente "Não";
#       N = "0 - Não é prioridade"               → O obrigatoriamente "Sim".
#   (2) N = "2 - Famílias inscritas no CadÚnico" → ao menos um "Sim" em P:AZ.

def test_cadunico_com_zero_sim_e_erro():
    """(1) CadÚnico exige “0 - Não é prioridade” = “Não”; com “Sim” → erro."""
    linha = linha_valida(**{
        "Enquadramento do beneficiário": "2 - Famílias inscritas no CadÚnico",
        "0 - Não é prioridade": "Sim", "I - Baixa renda": "Não",
    })
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "Enquadramento × “0 - Não é prioridade”") in _regras(achados)


def test_cadunico_com_zero_nao_nao_gera_achado():
    """(1) CadÚnico com “0” = “Não” e uma tipologia “Sim” → linha limpa."""
    linha = linha_valida(**{
        "Enquadramento do beneficiário": "2 - Famílias inscritas no CadÚnico",
        "0 - Não é prioridade": "Não", "I - Baixa renda": "Sim",
    })
    assert regras_formato_dominio([linha], DOM) == []


def test_enquadramento_zero_exige_coluna_zero_sim():
    """(1) Enquadramento “0 - Não é prioridade” exige a coluna “0” = “Sim”; “Não” → erro."""
    linha = linha_valida(**{
        "Enquadramento do beneficiário": "0 - Não é prioridade",
        "0 - Não é prioridade": "Não", "I - Baixa renda": "Sim",
    })
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "Enquadramento × “0 - Não é prioridade”") in _regras(achados)


def test_enquadramento_zero_com_coluna_zero_sim_nao_gera_achado():
    """(1) Enquadramento “0” com a coluna “0” = “Sim” (e nada mais marcado) → limpa."""
    linha = linha_valida(**{
        "Enquadramento do beneficiário": "0 - Não é prioridade",
        "0 - Não é prioridade": "Sim", "I - Baixa renda": "Não",
    })
    assert regras_formato_dominio([linha], DOM) == []


def test_cadunico_sem_nenhum_sim_nas_tipologias_e_erro():
    """(2) CadÚnico exige ao menos um “Sim” entre P:AZ; nenhuma marcada → erro próprio.

    A cláusula 2 do “0 - Não é prioridade” acusa a mesma linha por outro ângulo — são
    achados distintos de propósito (mensagens diferentes para o operador).
    """
    linha = linha_valida(**{
        "Enquadramento do beneficiário": "2 - Famílias inscritas no CadÚnico",
        "0 - Não é prioridade": "Não", "I - Baixa renda": "Não",
    })
    regras = _regras(regras_formato_dominio([linha], DOM))
    assert ("err", "CadÚnico sem tipologia assinalada") in regras
    assert ("err", "Nenhuma tipologia assinalada") in regras


def test_cadunico_em_caixa_alta_e_reconhecido():
    """As duas regras ignoram a caixa (casefold, como o resto do vocabulário)."""
    linha = linha_valida(**{
        "Enquadramento do beneficiário": "2 - FAMÍLIAS INSCRITAS NO CADÚNICO",
        "0 - Não é prioridade": "SIM", "I - Baixa renda": "Não",
    })
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "Enquadramento × “0 - Não é prioridade”") in _regras(achados)


def test_outros_enquadramentos_nao_amarram_a_coluna_zero():
    """Escopo: só os enquadramentos “0” e “2 - CadÚnico” amarram a coluna “0”; os demais
    (ex.: “4 - Povos tradicionais”) ficam livres."""
    linha = linha_valida(**{
        "Enquadramento do beneficiário": "4 - Povos tradicionais",
        "0 - Não é prioridade": "Não", "I - Baixa renda": "Sim",
    })
    titulos = {a["regra"] for a in regras_formato_dominio([linha], DOM)}
    assert "Enquadramento × “0 - Não é prioridade”" not in titulos
    assert "CadÚnico sem tipologia assinalada" not in titulos


# ── D3 (cont.) · Comparações ignoram caixa alta/baixa (pedido 2026-07-15) ──

def test_tipologia_sim_maiusculo_nao_gera_aviso():
    """'SIM' (caixa alta) é aceito como 'Sim' → sem aviso de tipologia (bug do arquivo
    revisado, coluna II-A = 'SIM')."""
    linha = linha_valida(**{"0 - Não é prioridade": "Não", "I - Baixa renda": "SIM"})
    assert regras_formato_dominio([linha], DOM) == []


def test_zero_sim_maiusculo_aciona_clausula1():
    """'0'='SIM' com outra tipologia='SIM' aciona a cláusula 1, ignorando a caixa."""
    linha = linha_valida(**{"0 - Não é prioridade": "SIM", "I - Baixa renda": "Sim"})
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "“0 - Não é prioridade” + outra tipologia") in _regras(achados)


def test_zero_nao_reconhece_sim_maiusculo():
    """'0'='Não' com uma tipologia='SIM' satisfaz a cláusula 2 (SIM conta como Sim)."""
    linha = linha_valida(**{"0 - Não é prioridade": "Não", "I - Baixa renda": "SIM"})
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "Nenhuma tipologia assinalada") not in _regras(achados)


def test_dominio_ignora_caixa():
    """Valor de domínio em caixa diferente ('am' vs 'AM') é aceito → sem erro de domínio."""
    linha = linha_valida(**{"UF": "am"})
    achados = regras_formato_dominio([linha], DOM)
    assert ("err", "Valor fora do domínio") not in _regras(achados)


def test_comunidade_coerente_em_caixa_alta_nao_gera_achado():
    """Correspondência satisfeita toda em CAIXA ALTA não gera achado (case-insensitive no
    Tipo de Comunidade e na família exigida)."""
    linha = linha_valida(**{
        "Tipo de Comunidade": "4 - COMUNIDADE EXTRATIVISTA",
        "IV.4 - Família extrativista": "sim",
    })
    assert regras_formato_dominio([linha], DOM) == []


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


def test_municipio_diverge_so_no_acento_nao_gera_erro():
    """Município que difere só por acento (planilha 'RORAINÓPOLIS' vs base 'RORAINOPOLIS')
    não deve acusar 'UF / município divergente' (caso Roraima Energia)."""
    linhas = [linha_valida(**{"Número ODI": "O1", "Número da Unidade Consumidora": "U1",
                              "UF": "RR", "Município": "RORAINÓPOLIS"})]
    achados = regras_cruzamento(linhas, chaves_uc={("O1", "U1")},
                                odi_ref={"O1": ("RR", "RORAINOPOLIS")})
    assert ("err", "UF / município divergente") not in _regras(achados)


def test_municipio_diverge_so_no_espaco_nao_gera_erro():
    """Município que difere só por espaço no meio ('SANTA LUZ' vs 'SANTALUZ') não diverge."""
    linhas = [linha_valida(**{"Número ODI": "O1", "Número da Unidade Consumidora": "U1",
                              "UF": "RR", "Município": "SANTA LUZ"})]
    achados = regras_cruzamento(linhas, chaves_uc={("O1", "U1")},
                                odi_ref={"O1": ("RR", "SANTALUZ")})
    assert ("err", "UF / município divergente") not in _regras(achados)


def test_municipio_realmente_divergente_ainda_gera_erro():
    """Município de fato diferente continua acusando divergência (a normalização não
    afrouxa nomes distintos)."""
    linhas = [linha_valida(**{"Número ODI": "O1", "Número da Unidade Consumidora": "U1",
                              "UF": "RR", "Município": "BOA VISTA"})]
    achados = regras_cruzamento(linhas, chaves_uc={("O1", "U1")},
                                odi_ref={"O1": ("RR", "RORAINOPOLIS")})
    assert ("err", "UF / município divergente") in _regras(achados)


def test_ucs_faltando_lista_cada_uc_ausente():
    """UCs da referência ausentes → aviso 'UCs faltando', UMA ocorrência por UC.

    Antes era um agregado só com a contagem; agora lista ODI+UC de cada faltante
    (pedido: o operador precisa saber QUAIS UCs reenviar).
    """
    linhas = [linha_valida(**{"Número ODI": "O1", "Número da Unidade Consumidora": "U1"})]
    chaves = {("O1", "U1"), ("O1", "U2"), ("O2", "U3")}  # faltam 2 na planilha
    achados = regras_cruzamento(linhas, chaves_uc=chaves, odi_ref={})
    # A regra está presente como aviso.
    assert ("warn", "UCs faltando") in _regras(achados)
    # Uma ocorrência por UC faltante (U2 e U3), não um único agregado.
    faltando = [a for a in achados if a["regra"] == "UCs faltando"]
    assert len(faltando) == 2
    # Cada faltante identifica a sua UC (e o ODI) no texto.
    problemas = " | ".join(a["problema"] for a in faltando)
    assert "U2" in problemas and "O1" in problemas
    assert "U3" in problemas and "O2" in problemas
    # A UC enviada (U1) não aparece como faltante.
    assert "U1" not in problemas


def test_agrupar_limita_rows_mas_mantem_count_real():
    """`_agrupar` limita as linhas de detalhe a `_ROWS_MAX`, mas `count` = total real.

    Assim o front lista as primeiras e resume o resto como "+N outras…", sem inflar
    o payload quando uma regra tem milhares de ocorrências.
    """
    from backend.validacao import _agrupar, _ROWS_MAX
    # Fabrica _ROWS_MAX + 5 achados da mesma regra.
    achados = [
        {"sev": "warn", "regra": "UCs faltando", "loc": "—", "campo": "UC",
         "problema": f"UC U{i}", "sug": "x"}
        for i in range(_ROWS_MAX + 5)
    ]
    grupos = _agrupar(achados)
    grupo = grupos[0]
    # count reflete TODAS as ocorrências; rows fica no teto.
    assert grupo["count"] == _ROWS_MAX + 5
    assert len(grupo["rows"]) == _ROWS_MAX


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
