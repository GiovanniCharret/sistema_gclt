"""Regras de validação do Anexo V (Blocos D3–D5, §7).

Por que existe: é o núcleo da crítica. Recebe as linhas já parseadas (`planilha.py`), os
domínios do modelo e a referência de `entrada/`, e produz a lista de **achados** (erros e
avisos). O D5 agrupa esses achados no formato que o painel do front consome.

Um achado é um dict:
  {"sev": "err"|"warn", "regra": <título>, "loc": "L47", "campo": <coluna>,
   "problema": <texto>, "sug": <sugestão>}
Só `sev="err"` bloqueia o envio (§7). Este arquivo (D3) cobre as regras de
formato/domínio; o cruzamento com `entrada/` (D4) e a montagem (D5) vêm em seguida.
"""

# Normalização defensiva de data/coordenada (do parser).
from backend.planilha import normalizar_data, normalizar_coordenada

# ── Nomes de coluna (cabeçalhos reais do modelo) ──
COL_ODI = "Número ODI"
COL_UC = "Número da Unidade Consumidora"
COL_IBGE = "Código IBGE do Município"
COL_MUNICIPIO = "Município"
COL_UF = "UF"
COL_LAT = "Latitude"
COL_LON = "Longitude"
COL_DATA = "Data de Energização da UC"
COL_TIPO_ATEND = "Tipo de Atendimento"
COL_TIPO_COM = "Tipo de Comunidade"
COL_ENQUAD = "Enquadramento do beneficiário"
COL_TIPOLOGIA_ZERO = "0 - Não é prioridade"

# Campos obrigatórios em toda linha preenchida (§7).
OBRIGATORIOS = [COL_ODI, COL_UC, COL_IBGE, COL_MUNICIPIO, COL_UF, COL_LAT, COL_LON, COL_DATA]

# As 14 colunas de identificação/localização/classificação (não são tipologia).
COLS_IDENTIFICACAO = {
    "Distribuidora", COL_TIPO_ATEND, COL_ODI, COL_UC, COL_IBGE, COL_MUNICIPIO, COL_UF,
    "Nome da Comunidade", "Nome da Unidade Consumidora", COL_LAT, COL_LON, COL_DATA,
    COL_TIPO_COM, COL_ENQUAD,
}

# Mapa coluna → chave da lista de domínios (para a regra de domínio).
_MAPA_DOMINIO = {
    COL_TIPO_ATEND: "TIPO_ATENDIMENTO",
    COL_UF: "UF",
    COL_TIPO_COM: "TIPO_COMUNIDADE",
    COL_ENQUAD: "ENQUADRAMENTO_BENEFICIARIO",
}


def _txt(linha, coluna):
    """Valor de uma célula como texto limpo ('' se vazia)."""
    # Normaliza None/valor para string sem bordas.
    v = linha.get(coluna)
    return "" if v is None else str(v).strip()


def _loc(linha):
    """Localização 'L{n}' a partir do número real da linha."""
    # `_linha` é anexado pelo parser.
    return f"L{linha.get('_linha', '?')}"


def _achado(sev, regra, loc, campo, problema, sug):
    """Monta um achado no formato padrão."""
    # Estrutura única consumida pelo agrupamento (D5) e pelo relatório.
    return {"sev": sev, "regra": regra, "loc": loc, "campo": campo, "problema": problema, "sug": sug}


def _colunas_tipologia(linha):
    """Colunas de tipologia da linha = todas menos as de identificação e `_linha`."""
    # Tipologia = o que sobra depois de tirar as 14 colunas de identificação.
    return [c for c in linha if c not in COLS_IDENTIFICACAO and c != "_linha"]


def regras_formato_dominio(linhas, dominios):
    """Aplica as regras de formato/domínio (D3) a todas as linhas.

    Entrada: `linhas` (lista de dicts do parser) e `dominios` (dict de listas válidas).
    Fase 1: por linha — campos obrigatórios vazios (erro), domínio (erro), coordenadas
            (aviso), data fora de 2026 (aviso), tipologia ≠ Sim/Não (aviso), "0"+outra (aviso).
    Fase 2: entre linhas — chave ODI+UC duplicada (erro).
    Saída: lista de achados.
    """
    # Acumulador de achados.
    achados = []
    # Conjunto de valores Sim/Não válidos (para as tipologias).
    sim_nao = set(dominios.get("SIM_NAO", ["Sim", "Não"]))

    # Fase 1: regras por linha.
    for linha in linhas:
        loc = _loc(linha)

        # (erro) Campos obrigatórios vazios.
        for coluna in OBRIGATORIOS:
            if _txt(linha, coluna) == "":
                achados.append(_achado("err", "Campos obrigatórios vazios", loc, coluna,
                                        "célula vazia", "preencher o campo obrigatório"))

        # (erro) Valor fora do domínio (só quando a célula tem valor).
        for coluna, chave in _MAPA_DOMINIO.items():
            v = _txt(linha, coluna)
            if v != "" and v not in dominios.get(chave, []):
                achados.append(_achado("err", "Valor fora do domínio", loc, coluna,
                                        f'valor "{v}" fora do domínio', "usar um valor da aba Dominios"))

        # (aviso) Coordenadas inválidas (não numéricas ou fora da faixa).
        for coluna, (minimo, maximo) in ((COL_LAT, (-90, 90)), (COL_LON, (-180, 180))):
            v = _txt(linha, coluna)
            if v == "":
                continue  # vazio já é erro (obrigatório)
            numero = normalizar_coordenada(linha.get(coluna))
            if numero is None or not (minimo <= numero <= maximo):
                achados.append(_achado("warn", "Coordenadas inválidas", loc, coluna,
                                        f'valor "{v}" inválido', f"deve estar entre {minimo} e {maximo}"))

        # (aviso) Data de energização fora de 2026.
        if _txt(linha, COL_DATA) != "":
            data = normalizar_data(linha.get(COL_DATA))
            if data is not None and data.year != 2026:
                achados.append(_achado("warn", "Data de energização fora de 2026", loc, COL_DATA,
                                        f"ano {data.year}", "enviar apenas UCs energizadas em 2026"))

        # (aviso) Tipologia ≠ Sim/Não.
        for coluna in _colunas_tipologia(linha):
            v = _txt(linha, coluna)
            if v != "" and v not in sim_nao:
                achados.append(_achado("warn", "Valor de tipologia ≠ Sim/Não", loc, coluna,
                                        f'valor "{v}" inválido', 'usar "Sim" ou "Não"'))

        # (aviso) "0 - Não é prioridade" = Sim junto de outra tipologia = Sim.
        if _txt(linha, COL_TIPOLOGIA_ZERO) == "Sim":
            outras = [c for c in _colunas_tipologia(linha)
                      if c != COL_TIPOLOGIA_ZERO and _txt(linha, c) == "Sim"]
            if outras:
                achados.append(_achado("warn", "“0 - Não é prioridade” + outra tipologia", loc,
                                        "Tipologia", "marcada junto de outra tipologia",
                                        'desmarcar "0" quando houver outra tipologia'))

    # Fase 2: chave ODI+UC duplicada (entre linhas).
    vistos = {}
    for linha in linhas:
        chave = (_txt(linha, COL_ODI), _txt(linha, COL_UC))
        # Só considera quando ODI e UC estão ambos preenchidos.
        if chave[0] and chave[1]:
            vistos.setdefault(chave, []).append(linha)
    for (odi, uc), repetidas in vistos.items():
        if len(repetidas) > 1:
            for linha in repetidas:
                achados.append(_achado("err", "Chave ODI + UC duplicada", _loc(linha),
                                        "ODI + UC", f'ODI "{odi}" + UC "{uc}" repetida',
                                        "cada UC deve aparecer uma única vez"))

    # Saída: todos os achados de formato/domínio.
    return achados


def regras_cruzamento(linhas, chaves_uc, odi_ref):
    """Aplica as regras de cruzamento com `entrada/` (D4, §7) para UM contrato.

    Entrada: `linhas` (parseadas), `chaves_uc` (set de `(odi, uc)` da referência do
             contrato) e `odi_ref` (dict `odi -> (uf, municipio)` do contrato).
    Fase 1: por linha — (ODI,UC) inexistente na referência (erro); UF/município divergente
            do ODI (erro). Acumula os pares enviados.
    Fase 2: UCs da referência ausentes da planilha → aviso agregado.
    Saída: lista de achados.
    """
    # Acumuladores.
    achados = []
    enviados = set()

    # Fase 1: checagens por linha.
    for linha in linhas:
        odi = _txt(linha, COL_ODI)
        uc = _txt(linha, COL_UC)
        loc = _loc(linha)
        # Par (odi, uc) — existência na referência.
        if odi and uc:
            enviados.add((odi, uc))
            if (odi, uc) not in chaves_uc:
                achados.append(_achado("err", "ODI + UC não consta na referência", loc,
                                        "ODI + UC", f'ODI "{odi}" + UC "{uc}" não existe na base do contrato',
                                        "conferir ODI e UC contra a base de referência"))
        # UF/município divergentes do que a referência tem para aquele ODI.
        if odi and odi in odi_ref:
            uf_ref, mun_ref = odi_ref[odi]
            uf = _txt(linha, COL_UF)
            mun = _txt(linha, COL_MUNICIPIO)
            if uf.upper() != (uf_ref or "").upper() or mun.upper() != (mun_ref or "").upper():
                achados.append(_achado("err", "UF / município divergente", loc, "UF/Município",
                                        f"linha: {uf}/{mun} · referência: {uf_ref}/{mun_ref}",
                                        "corrigir para bater com a referência do ODI"))

    # Fase 2: UCs da referência que não vieram na planilha (aviso agregado).
    faltando = chaves_uc - enviados
    if faltando:
        achados.append(_achado("warn", "UCs faltando", "—", "UC",
                                f"{len(faltando)} UC(s) da referência não estão na planilha",
                                "conferir se todas as UCs do contrato foram enviadas"))

    # Saída: achados de cruzamento.
    return achados


# Descrição curta por regra (aparece no cabeçalho de cada grupo do painel).
_DESCRICOES = {
    "Campos obrigatórios vazios": "Colunas obrigatórias vazias em linhas preenchidas",
    "Valor fora do domínio": "Valor não consta na lista de domínios válidos (aba Dominios)",
    "Chave ODI + UC duplicada": "Mesma combinação Número ODI + Número da UC em mais de uma linha",
    "ODI + UC não consta na referência": "A combinação não existe em entrada/ para o contrato",
    "UF / município divergente": "Não bate com a referência de entrada/ para aquele ODI",
    "Coordenadas inválidas": "Latitude/Longitude fora da faixa geográfica ou não numéricas",
    "UCs faltando": "UCs da referência do contrato ausentes da planilha",
    "“0 - Não é prioridade” + outra tipologia": "Marcar “0” só quando nenhuma outra tipologia se aplica",
    "Data de energização fora de 2026": "A planilha deve conter apenas UCs ligadas em 2026",
    "Valor de tipologia ≠ Sim/Não": "Colunas de tipologia aceitam apenas “Sim” ou “Não”",
    "Planilha sem dados": "Nenhuma linha com ODI/UC na aba Preenchimento",
}

# Coluna do achado → chave do preview (para marcar a célula certa).
_CAMPO_PREVIEW = {
    COL_ODI: "odi", COL_UC: "uc", COL_MUNICIPIO: "municipio", COL_UF: "uf",
    COL_IBGE: "ibge", COL_LAT: "latitude", COL_DATA: "energizacao", COL_TIPO_ATEND: "tipoAtend",
}

# Quantas linhas mostrar no preview.
_PREVIEW_MAX = 7


def _agrupar(achados):
    """Agrupa os achados por regra, preservando a ordem de 1º aparecimento.

    Entrada: lista de achados.
    Saída: lista de grupos `{sev, title, desc, count, rows:[{loc,field,problem,sug}]}`.
    """
    # Dict título→grupo + lista de ordem (para saída estável).
    grupos = {}
    ordem = []
    for a in achados:
        titulo = a["regra"]
        if titulo not in grupos:
            grupos[titulo] = {"sev": a["sev"], "title": titulo,
                              "desc": _DESCRICOES.get(titulo, ""), "count": 0, "rows": []}
            ordem.append(titulo)
        grupo = grupos[titulo]
        grupo["count"] += 1
        grupo["rows"].append({"loc": a["loc"], "field": a["campo"],
                              "problem": a["problema"], "sug": a["sug"]})
    return [grupos[t] for t in ordem]


def _preview(linhas, achados):
    """Monta as primeiras linhas do preview, marcando as células com achado.

    Entrada: `linhas` (parseadas) e `achados` (para as flags).
    Fase 1: indexa achados por (loc, coluna) → severidade (err prevalece sobre warn).
    Fase 2: para as primeiras linhas, monta o dict do preview + flags por célula.
    Saída: lista de previewRows.
    """
    # Fase 1: severidade por (loc, coluna) — err tem prioridade sobre warn.
    sev_por_celula = {}
    for a in achados:
        chave = (a["loc"], a["campo"])
        if a["sev"] == "err" or chave not in sev_por_celula:
            sev_por_celula[chave] = a["sev"]
    # Fase 2: monta o preview das primeiras linhas.
    preview = []
    for linha in linhas[:_PREVIEW_MAX]:
        loc = _loc(linha)
        # Flags por célula do preview (mapeando coluna→chave do preview).
        flags = {}
        for coluna, chave_preview in _CAMPO_PREVIEW.items():
            sev = sev_por_celula.get((loc, coluna))
            if sev:
                flags[chave_preview] = sev
        preview.append({
            "linha": loc,
            "odi": _txt(linha, COL_ODI) or "(vazio)",
            "uc": _txt(linha, COL_UC) or "(vazio)",
            "municipio": _txt(linha, COL_MUNICIPIO) or "(vazio)",
            "uf": _txt(linha, COL_UF) or "(vazio)",
            "ibge": _txt(linha, COL_IBGE) or "(vazio)",
            "latitude": _txt(linha, COL_LAT) or "(vazio)",
            "energizacao": _txt(linha, COL_DATA) or "(vazio)",
            "tipoAtend": _txt(linha, COL_TIPO_ATEND) or "(vazio)",
            "flags": flags,
        })
    return preview


def validar(linhas, dominios, chaves_uc, odi_ref):
    """Valida a planilha inteira e monta a resposta do painel (D5, §6/§7).

    Entrada: `linhas` (parseadas), `dominios` (aba Dominios), `chaves_uc`/`odi_ref` (da
             referência do contrato).
    Fase 1: guarda — 0 linhas de dados → erro 'Planilha sem dados' (não envia).
    Fase 2: roda as regras (formato/domínio + cruzamento) e agrupa os achados.
    Fase 3: calcula totais e monta o preview.
    Saída: dict `{ok, linhasLidas, totalErros, totalAvisos, grupos, previewRows}`.
    """
    # Fase 1: planilha sem linhas de dados = erro que bloqueia o envio.
    if len(linhas) == 0:
        return {
            "ok": False, "linhasLidas": 0, "totalErros": 1, "totalAvisos": 0,
            "grupos": [{"sev": "err", "title": "Planilha sem dados",
                        "desc": _DESCRICOES["Planilha sem dados"], "count": 1,
                        "rows": [{"loc": "—", "field": "—",
                                  "problem": "nenhuma linha com ODI/UC na aba Preenchimento",
                                  "sug": "preencher ao menos uma UC"}]}],
            "previewRows": [],
        }
    # Fase 2: regras + agrupamento.
    achados = regras_formato_dominio(linhas, dominios) + regras_cruzamento(linhas, chaves_uc, odi_ref)
    grupos = _agrupar(achados)
    # Fase 3: totais, preview e ok.
    total_erros = sum(g["count"] for g in grupos if g["sev"] == "err")
    total_avisos = sum(g["count"] for g in grupos if g["sev"] == "warn")
    return {
        "ok": total_erros == 0,               # só erros bloqueiam
        "linhasLidas": len(linhas),           # nº de linhas preenchidas
        "totalErros": total_erros,
        "totalAvisos": total_avisos,
        "grupos": grupos,
        "previewRows": _preview(linhas, achados),
    }
