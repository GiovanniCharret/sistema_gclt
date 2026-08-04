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

# Normalização defensiva de coordenada, de ID (ODI/UC) e de nome (município/UF) — do parser.
from backend.planilha import normalizar_coordenada, normalizar_id, normalizar_nome, normalizar_uf

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
# Tipologias de família dos povos tradicionais (colunas U/V/W/X do modelo) — usadas na
# regra de correspondência com o Tipo de Comunidade (erro).
COL_FAM_INDIGENA = "IV.1 - Família indígena"
COL_FAM_QUILOMBOLA = "IV.2 - Família quilombola"
COL_FAM_RIBEIRINHA = "IV.3 - Família ribeirinha"
COL_FAM_EXTRATIVISTA = "IV.4 - Família extrativista"

# Tipo de Comunidade tradicional (coluna M) → coluna de família que deve estar "Sim".
# Pedido dos clientes da planilha (2026-07-29): a regra é SÓ esta correspondência, e vale
# apenas para estes quatro tipos; as demais colunas de família ficam livres (podem ser
# "Sim" sem gerar achado) e os tipos 5–12 não disparam checagem alguma.
_COMUNIDADE_FAMILIA = {
    "1 - Comunidade indígena": COL_FAM_INDIGENA,
    "2 - Comunidade quilombola": COL_FAM_QUILOMBOLA,
    "3 - Comunidade ribeirinha": COL_FAM_RIBEIRINHA,
    "4 - Comunidade extrativista": COL_FAM_EXTRATIVISTA,
}
# Versão casefold do mapa acima, para casar o Tipo de Comunidade ignorando a caixa.
_COMUNIDADE_FAMILIA_CF = {k.casefold(): v for k, v in _COMUNIDADE_FAMILIA.items()}

# Enquadramentos (coluna N) que amarram a coluna "0 - Não é prioridade" (O) — pedido dos
# clientes da planilha em 2026-07-29. Os demais enquadramentos não restringem a coluna O.
_ENQUAD_CADUNICO = "2 - Famílias inscritas no CadÚnico"
_ENQUAD_NAO_PRIORIDADE = "0 - Não é prioridade"
# Enquadramento → valor exigido na coluna "0 - Não é prioridade".
_ENQUAD_EXIGE_ZERO = {
    # Inscrito no CadÚnico é, por definição, prioridade → a coluna "0" tem que ser "Não".
    _ENQUAD_CADUNICO: "Não",
    # Enquadrado como "não é prioridade" → a coluna "0" tem que ser "Sim" (coerência).
    _ENQUAD_NAO_PRIORIDADE: "Sim",
}

# Faixa geográfica aceita para as coordenadas (aviso). Desde 2026-07-30 é a do território
# brasileiro, não mais a mundial (±90/±180): o Anexo V só recebe UC do Brasil, então a
# faixa fechada pega sinal invertido e coordenada de outro país, que a mundial deixava
# passar. Limites: +6,0 cobre o extremo norte (Oiapoque/AP e Roraima), −34,5 o Chuí/RS,
# −74,5 o extremo oeste no Acre e −34,0 a costa leste.
# (Fernando de Noronha/PE, em −32,4, fica fora da faixa — ilha sem UC de LPT.)
_FAIXA_LAT = (-34.5, 6.0)
_FAIXA_LON = (-74.5, -34.0)

# Campos obrigatórios em toda linha preenchida (§7). Desde 2026-07-30 a lista cobre TODAS
# as colunas de identificação — o pedido é "nenhuma célula em branco numa linha com
# ODI/UC", e antes disso Distribuidora, Tipo de Atendimento, os dois campos de Nome, Tipo
# de Comunidade e Enquadramento podiam ficar vazios sem crítica. As 51 colunas de
# tipologia são cobertas pela regra "Tipologia em branco", logo abaixo.
OBRIGATORIOS = [
    "Distribuidora", COL_TIPO_ATEND, COL_ODI, COL_UC, COL_IBGE, COL_MUNICIPIO, COL_UF,
    "Nome da Comunidade", "Nome da Unidade Consumidora", COL_LAT, COL_LON, COL_DATA,
    COL_TIPO_COM, COL_ENQUAD,
]

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


def _eh(linha, coluna, alvo):
    """Diz se a célula `coluna` vale `alvo`, ignorando a caixa (maiúsc./minúsc.) e bordas.

    Por que existe: os preenchimentos de vocabulário (Sim/Não, domínios, enquadramento,
    tipo de comunidade) podem chegar em qualquer caixa ("SIM"/"sim"/"Sim"); as regras
    comparam com o texto canônico, então a comparação precisa ser case-insensitive
    (pedido 2026-07-15). `casefold` é mais robusto que `lower` para acentos/Unicode.

    Entrada: `linha` (dict), `coluna` (nome) e `alvo` (texto esperado).
    Saída: True se iguais ignorando a caixa; False caso contrário.
    """
    # Compara os dois lados normalizados por casefold (o lado da célula já vem sem bordas).
    return _txt(linha, coluna).casefold() == alvo.casefold()


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


def _ucs_duplicadas(linhas):
    """Detecta a mesma UC em mais de uma linha, independentemente do ODI (erro).

    Por que existe: a chave composta ODI+UC não captura a repetição da UC com ODIs
    diferentes — sem esta regra, a mesma UC poderia ser enviada duas vezes e passar.
    Entrada: `linhas` (lista de dicts do parser).
    Fase 1: agrupa as linhas por UC normalizada (ignora UCs vazias).
    Fase 2: para cada UC com 2+ linhas, gera um achado de erro por linha, listando no
            texto todas as linhas onde a UC se repete.
    Saída: lista de achados.
    """
    # Acumulador de achados.
    achados = []
    # Fase 1: dict UC normalizada → linhas onde ela aparece.
    vistas = {}
    for linha in linhas:
        # Normaliza a UC (Excel int vs texto, zeros à esquerda).
        uc = normalizar_id(linha.get(COL_UC))
        # Só considera quando a UC está preenchida (vazia já é erro de obrigatório).
        if uc:
            vistas.setdefault(uc, []).append(linha)
    # Fase 2: cada UC repetida gera um achado por linha envolvida.
    for uc, repetidas in vistas.items():
        if len(repetidas) > 1:
            # Lista das linhas envolvidas ("3, 4, 7") — vai no texto do problema.
            numeros = ", ".join(str(l.get("_linha", "?")) for l in repetidas)
            for linha in repetidas:
                achados.append(_achado("err", "UC duplicada", _loc(linha), COL_UC,
                                        f'UC "{uc}" repetida (linhas {numeros})',
                                        "cada UC deve aparecer em uma única linha"))
    # Saída: achados de UC duplicada.
    return achados


def _coordenadas_duplicadas(linhas):
    """Detecta o mesmo par (latitude, longitude) em mais de uma linha da planilha (erro).

    Por que existe: duas unidades consumidoras distintas não podem ocupar exatamente o
    mesmo ponto de GPS — quando isso acontece é, na prática, coordenada copiada de outra
    linha (pedido dos clientes da planilha em 2026-07-30). É a contrapartida geográfica da
    `_ucs_duplicadas`, e vale **dentro do arquivo enviado**, não contra a base histórica.

    Entrada: `linhas` (lista de dicts do parser).
    Fase 1: agrupa as linhas pelo par de coordenadas normalizado, ignorando as linhas em
            que latitude ou longitude está ausente/ilegível (a célula vazia já é erro de
            campo obrigatório; deixá-las entrar faria todas “casarem” entre si).
    Fase 2: para cada par repetido, gera um achado de erro por linha, citando no texto
            todas as linhas onde o ponto se repete.
    Saída: lista de achados.
    """
    # Acumulador de achados.
    achados = []
    # Fase 1: dict (lat, lon) → linhas onde o par aparece.
    vistas = {}
    for linha in linhas:
        # Normaliza aceitando vírgula ou ponto decimal (mesma regra do aviso de faixa).
        lat = normalizar_coordenada(linha.get(COL_LAT))
        lon = normalizar_coordenada(linha.get(COL_LON))
        # Só compara quando as DUAS coordenadas são legíveis.
        if lat is None or lon is None:
            continue
        vistas.setdefault((lat, lon), []).append(linha)
    # Fase 2: cada ponto repetido gera um achado por linha envolvida.
    for (lat, lon), repetidas in vistas.items():
        if len(repetidas) > 1:
            # Lista das linhas envolvidas ("3, 8") — vai no texto do problema.
            numeros = ", ".join(str(l.get("_linha", "?")) for l in repetidas)
            for linha in repetidas:
                achados.append(_achado("err", "Coordenada duplicada", _loc(linha), COL_LAT,
                                        f'ponto ({lat}, {lon}) repetido (linhas {numeros})',
                                        "cada UC deve ter a sua própria coordenada"))
    # Saída: achados de coordenada duplicada.
    return achados


def regras_formato_dominio(linhas, dominios):
    """Aplica as regras de formato/domínio (D3) a todas as linhas.

    Entrada: `linhas` (lista de dicts do parser) e `dominios` (dict de listas válidas).
    Fase 1: por linha — campos obrigatórios vazios (erro), domínio (erro), coordenadas
            (aviso), tipologia ≠ Sim/Não (aviso), consistência da classificação (erro,
            3 cláusulas: "0" em branco é obrigatório e bloqueia; "0"="Sim" exige demais
            tipologias "Não"; "0"="Não" exige ao menos uma tipologia "Sim"), e coerência
            do Tipo de Comunidade tradicional (1/2/3) com o Enquadramento "4 - Povos
            tradicionais" e com a família IV.1/IV.2/IV.3 (dois avisos). Data de
            energização: qualquer ano é aceito
            (regra "fora de 2026" excluída em 2026-07-09); vazia continua erro por ser
            campo obrigatório.
    Fase 2: entre linhas — chave ODI+UC duplicada (erro) e UC duplicada (erro).
    Saída: lista de achados.

    Observação: todas as comparações de vocabulário (Sim/Não, domínios, enquadramento,
    tipo de comunidade) **ignoram a caixa** (maiúsc./minúsc.) via `casefold` — "SIM",
    "sim" e "Sim" são equivalentes (pedido 2026-07-15).
    """
    # Acumulador de achados.
    achados = []
    # Vocabulário Sim/Não e domínios normalizados por casefold — todas as comparações de
    # preenchimento ignoram a caixa (maiúsc./minúsc.), pedido de 2026-07-15.
    sim_nao = {v.casefold() for v in dominios.get("SIM_NAO", ["Sim", "Não"])}
    dominios_cf = {chave: {d.casefold() for d in dominios.get(chave, [])}
                   for chave in _MAPA_DOMINIO.values()}

    # Fase 1: regras por linha.
    for linha in linhas:
        loc = _loc(linha)

        # (erro) Campos obrigatórios vazios.
        for coluna in OBRIGATORIOS:
            if _txt(linha, coluna) == "":
                achados.append(_achado("err", "Campos obrigatórios vazios", loc, coluna,
                                        "célula vazia", "preencher o campo obrigatório"))

        # (erro) Valor fora do domínio (só quando a célula tem valor; ignora a caixa).
        for coluna, chave in _MAPA_DOMINIO.items():
            v = _txt(linha, coluna)
            if v != "" and v.casefold() not in dominios_cf[chave]:
                achados.append(_achado("err", "Valor fora do domínio", loc, coluna,
                                        f'valor "{v}" fora do domínio', "usar um valor da aba Dominios"))

        # (aviso) Coordenadas inválidas (não numéricas ou fora da faixa do Brasil).
        for coluna, (minimo, maximo) in ((COL_LAT, _FAIXA_LAT), (COL_LON, _FAIXA_LON)):
            v = _txt(linha, coluna)
            if v == "":
                continue  # vazio já é erro (obrigatório)
            numero = normalizar_coordenada(linha.get(coluna))
            if numero is None or not (minimo <= numero <= maximo):
                achados.append(_achado("warn", "Coordenadas inválidas", loc, coluna,
                                        f'valor "{v}" inválido', f"deve estar entre {minimo} e {maximo}"))

        # (aviso) Tipologia ≠ Sim/Não (ignora a caixa: "SIM"/"sim" valem como "Sim").
        for coluna in _colunas_tipologia(linha):
            v = _txt(linha, coluna)
            if v != "" and v.casefold() not in sim_nao:
                achados.append(_achado("warn", "Valor de tipologia ≠ Sim/Não", loc, coluna,
                                        f'valor "{v}" inválido', 'usar "Sim" ou "Não"'))

        # (erro) Consistência da classificação — "0 - Não é prioridade" vs demais
        # tipologias (colunas P–AZ do modelo). Erro desde 2026-07-09 (antes era aviso).
        # Valor da coluna "0" e lista das demais colunas de tipologia da linha.
        zero = _txt(linha, COL_TIPOLOGIA_ZERO)
        demais = [c for c in _colunas_tipologia(linha) if c != COL_TIPOLOGIA_ZERO]
        if zero == "":
            # Cláusula 0 (erro desde 2026-07-14): a coluna "0" é de preenchimento
            # obrigatório (Sim/Não). Em branco bloqueia — antes escapava das duas
            # cláusulas abaixo (nem "Sim" nem "Não"), deixando a linha sem crítica de
            # classificação; isto também fecha o furo da linha totalmente sem marcação.
            achados.append(_achado("err", "“0 - Não é prioridade” em branco", loc,
                                    COL_TIPOLOGIA_ZERO, "célula em branco",
                                    'preencher “Sim” ou “Não” na coluna “0 - Não é prioridade”'))
        elif _eh(linha, COL_TIPOLOGIA_ZERO, "Sim"):
            # Cláusula 1: com "0" = "Sim", nenhuma outra tipologia pode estar "Sim".
            conflitos = [c for c in demais if _eh(linha, c, "Sim")]
            if conflitos:
                achados.append(_achado("err", "“0 - Não é prioridade” + outra tipologia", loc,
                                        "Tipologia", f'“Sim” também em: {", ".join(conflitos)}',
                                        'se “0 - Não é prioridade” for “Sim”, todas as demais células devem ser “Não”'))
        elif _eh(linha, COL_TIPOLOGIA_ZERO, "Não"):
            # Cláusula 2: com "0" = "Não", pelo menos uma outra tipologia deve estar "Sim".
            # Exceção (fallback de 2026-08-04, modelo v260804): enquadramento
            # "2 - Famílias inscritas no CadÚnico" ISENTA a linha desta cláusula — com
            # CadÚnico as tipologias P:AZ são livres (todas "Não" é válido).
            if not _eh(linha, COL_ENQUAD, _ENQUAD_CADUNICO) \
                    and not any(_eh(linha, c, "Sim") for c in demais):
                achados.append(_achado("err", "Nenhuma tipologia assinalada", loc,
                                        "Tipologia", "nenhuma tipologia marcada com “Sim”",
                                        'assinalar “Sim” em pelo menos uma tipologia ou marcar “0 - Não é prioridade” = “Sim”'))

        # (erro) Tipologia em branco — toda coluna de tipologia (P:AZ) exige "Sim" ou "Não"
        # numa linha com ODI/UC (pedido de 2026-07-30: "nenhuma célula em branco"). A
        # coluna "0 - Não é prioridade" fica de fora porque já tem regra própria acima —
        # senão o operador veria a mesma célula criticada duas vezes.
        # Um único achado por LINHA, nomeando as colunas: no arquivo real são 19 colunas
        # vazias em 490 linhas, e um achado por célula geraria 9.310 ocorrências.
        brancas = [c for c in demais if _txt(linha, c) == ""]
        if brancas:
            # Mostra as 5 primeiras e resume o resto (mensagem legível no painel).
            amostra = ", ".join(brancas[:5])
            resto = f" e mais {len(brancas) - 5}" if len(brancas) > 5 else ""
            achados.append(_achado("err", "Tipologia em branco", loc, "Tipologia",
                                    f"{len(brancas)} coluna(s) de tipologia em branco: {amostra}{resto}",
                                    'preencher “Sim” ou “Não” em todas as colunas de tipologia'))

        # (erro) Enquadramento (coluna N) × coluna "0 - Não é prioridade" (O) — pedido
        # dos clientes da planilha em 2026-07-29. Só os enquadramentos "2 - Famílias
        # inscritas no CadÚnico" e "0 - Não é prioridade" restringem a coluna O; os
        # demais ficam livres. Comparações ignoram a caixa (via `_eh`).
        # A antiga "Regra 2" (CadÚnico exigia ao menos um "Sim" em P:AZ) CAIU em
        # 2026-08-04 (fallback, modelo v260804): com CadÚnico as tipologias são livres
        # — ver também a isenção da cláusula 2 do "0", logo acima.
        for enquadramento, zero_exigido in _ENQUAD_EXIGE_ZERO.items():
            # Só age quando a linha está NESTE enquadramento (um casa por vez).
            if not _eh(linha, COL_ENQUAD, enquadramento):
                continue
            # A coluna "0" tem que ter exatamente o valor exigido pelo enquadramento.
            if not _eh(linha, COL_TIPOLOGIA_ZERO, zero_exigido):
                achados.append(_achado("err", "Enquadramento × “0 - Não é prioridade”", loc,
                                        COL_TIPOLOGIA_ZERO,
                                        f'Enquadramento “{enquadramento}” exige “{zero_exigido}” '
                                        f'em “{COL_TIPOLOGIA_ZERO}” (valor atual: "{zero}")',
                                        f'preencher “{COL_TIPOLOGIA_ZERO}” com “{zero_exigido}”'))

        # (erro) Correspondência do Tipo de Comunidade tradicional (coluna M) com a sua
        # tipologia de família: 1→IV.1 (U), 2→IV.2 (V), 3→IV.3 (W), 4→IV.4 (X).
        # Simplificação pedida pelos clientes da planilha (2026-07-29): checa-se APENAS se
        # a família correspondente está "Sim" — as demais colunas de família são livres
        # (podem ser "Sim" sem gerar achado). Bloqueia o envio (severidade "err").
        tipo_com = _txt(linha, COL_TIPO_COM)
        # Casa o Tipo de Comunidade ignorando a caixa; None se não for 1/2/3/4.
        esperada = _COMUNIDADE_FAMILIA_CF.get(tipo_com.casefold())
        # Só os quatro tipos mapeados disparam a regra (sem direção reversa).
        if esperada is not None:
            # A família correspondente deve estar "Sim" (branco conta como não marcada).
            if not _eh(linha, esperada, "Sim"):
                achados.append(_achado("err", "Tipologia de família ≠ Tipo de Comunidade", loc, esperada,
                                        f'“{tipo_com}” exige “{esperada}” = “Sim”',
                                        f'preencher “{esperada}” com “Sim”'))

    # Fase 2: chave ODI+UC duplicada (entre linhas).
    vistos = {}
    for linha in linhas:
        chave = (normalizar_id(linha.get(COL_ODI)), normalizar_id(linha.get(COL_UC)))
        # Só considera quando ODI e UC estão ambos preenchidos.
        if chave[0] and chave[1]:
            vistos.setdefault(chave, []).append(linha)
    for (odi, uc), repetidas in vistos.items():
        if len(repetidas) > 1:
            for linha in repetidas:
                achados.append(_achado("err", "Chave ODI + UC duplicada", _loc(linha),
                                        "ODI + UC", f'ODI "{odi}" + UC "{uc}" repetida',
                                        "cada UC deve aparecer uma única vez"))

    # Fase 2 (cont.): UC duplicada, independentemente do ODI (erro).
    achados.extend(_ucs_duplicadas(linhas))

    # Fase 2 (cont.): mesmo ponto de GPS em duas linhas da planilha (erro, 2026-07-30).
    achados.extend(_coordenadas_duplicadas(linhas))

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
        odi = normalizar_id(linha.get(COL_ODI))
        uc = normalizar_id(linha.get(COL_UC))
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
            # Compara por forma canônica (ignora acento, caixa e espaços — inclusive no
            # meio): base e planilha divergem nesses ruídos sem ser erro. A UF usa
            # `normalizar_uf` (equivale sigla "AP" ao nome "Amapá", pois a base pode
            # trazer qualquer um dos dois); o município usa `normalizar_nome`.
            if (normalizar_uf(uf) != normalizar_uf(uf_ref)
                    or normalizar_nome(mun) != normalizar_nome(mun_ref)):
                achados.append(_achado("err", "UF / município divergente", loc, "UF/Município",
                                        f"linha: {uf}/{mun} · referência: {uf_ref}/{mun_ref}",
                                        "corrigir para bater com a referência do ODI"))

    # Fase 2: UCs da referência que não vieram na planilha (aviso — UMA ocorrência
    # por UC, listando ODI+UC, para o operador saber exatamente quais reenviar; antes
    # era um único agregado só com a contagem). Ordena por (odi, uc) p/ saída estável;
    # o teto de linhas por grupo (o "+N outras" do front) é aplicado em `_agrupar`.
    faltando = chaves_uc - enviados
    for odi, uc in sorted(faltando):
        achados.append(_achado("warn", "UCs faltando", "—", "UC",
                                f'UC {uc} (ODI {odi}) não está na planilha',
                                "incluir na planilha ou confirmar a exclusão da UC"))

    # Saída: achados de cruzamento.
    return achados


# Descrição curta por regra (aparece no cabeçalho de cada grupo do painel).
_DESCRICOES = {
    "Campos obrigatórios vazios": "Colunas obrigatórias vazias em linhas preenchidas",
    "Valor fora do domínio": "Valor não consta na lista de domínios válidos (aba Dominios)",
    "Chave ODI + UC duplicada": "Mesma combinação Número ODI + Número da UC em mais de uma linha",
    "UC duplicada": "Mesma Unidade Consumidora em mais de uma linha, mesmo com ODIs diferentes",
    "ODI + UC não consta na referência": "A combinação não existe em entrada/ para o contrato",
    "UF / município divergente": "Não bate com a referência de entrada/ para aquele ODI",
    "Coordenadas inválidas": "Latitude/Longitude fora da faixa do território brasileiro ou não numéricas",
    "Coordenada duplicada": "Mesmo par de Latitude/Longitude em mais de uma linha da planilha",
    "UCs faltando": "UCs da referência do contrato ausentes da planilha",
    "“0 - Não é prioridade” em branco": "A coluna “0 - Não é prioridade” é obrigatória: preencher com “Sim” ou “Não”",
    "“0 - Não é prioridade” + outra tipologia": "Se “0 - Não é prioridade” for “Sim”, todas as demais células devem ser assinaladas como “Não”",
    "Nenhuma tipologia assinalada": "Todas as células de classificação não podem ser assinaladas como “Não” (exceção: enquadramento “2 - CadÚnico”, cujas tipologias são livres desde 04/08/2026)",
    "Valor de tipologia ≠ Sim/Não": "Colunas de tipologia aceitam apenas “Sim” ou “Não”",
    "Tipologia em branco": "Toda coluna de tipologia deve conter “Sim” ou “Não” — nenhuma pode ficar vazia",
    "Tipologia de família ≠ Tipo de Comunidade": "Tipo de Comunidade 1/2/3/4 exige “Sim” na família correspondente (IV.1/IV.2/IV.3/IV.4)",
    "Enquadramento × “0 - Não é prioridade”": "Enquadramento “2 - CadÚnico” exige “Não” e “0 - Não é prioridade” exige “Sim” na coluna “0 - Não é prioridade”",
    "Planilha sem dados": "Nenhuma linha com ODI/UC na aba Preenchimento",
}

# Coluna do achado → chave do preview (para marcar a célula certa).
_CAMPO_PREVIEW = {
    COL_ODI: "odi", COL_UC: "uc", COL_MUNICIPIO: "municipio", COL_UF: "uf",
    COL_IBGE: "ibge", COL_LAT: "latitude", COL_DATA: "energizacao", COL_TIPO_ATEND: "tipoAtend",
}

# Quantas linhas mostrar no preview.
_PREVIEW_MAX = 7

# Teto de linhas de DETALHE por grupo no payload. `count` continua sendo o total real;
# o front mostra as primeiras `_ROWS_MAX` e resume o resto como "+N outra(s)…". Evita
# payloads gigantes quando uma regra tem milhares de ocorrências (ex.: UCs faltando de
# um contrato grande enviado parcialmente).
_ROWS_MAX = 200


def _agrupar(achados):
    """Agrupa os achados por regra, preservando a ordem de 1º aparecimento.

    Entrada: lista de achados.
    Saída: lista de grupos `{sev, title, desc, count, rows:[{loc,field,problem,sug}]}`.
           `count` = total de ocorrências; `rows` é limitado a `_ROWS_MAX` (o excedente
           vira "+N outras…" no front).
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
        # `count` conta TODAS as ocorrências; só as `_ROWS_MAX` primeiras viram detalhe.
        grupo["count"] += 1
        if len(grupo["rows"]) < _ROWS_MAX:
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
