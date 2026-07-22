"""Filtro de acesso por login (grupo econômico) em duas camadas — Bloco A4 (§5.1).

Por que existe: o site é acessado por **grupos econômicos** de distribuidoras, e o
que cada usuário vê na seleção depende do **operador** informado no login (fallback
temporário 2026-07-15; o login por e-mail foi adiado para V1/V2). Este módulo resolve
as duas camadas do filtro:
  Camada 1 — operador → grupo econômico (`grupo_do_operador`).
  Camada 2 — grupo → siglas/contratos visíveis (`siglas_do_grupo`, `contratos_visiveis`).
`ENBPAR` é **curinga** (vê todos os contratos). **Não é segurança** — é um filtro de
escopo da seleção (não há, aqui, controle de senha forte vinculado a isso); por isso
os mapas são configuráveis e ficam centralizados como fonte única no backend.

Importante: a sigla "ÂMBAR" usa o caractere precomposto U+00C2 (`Â`); para evitar
pegadinhas de normalização Unicode, escreve-se com escape `Â`.
"""

# Camada 2 — mapa grupo → conjunto de siglas de distribuidora.
# `None` marca o **curinga** (vê todos os contratos), usado pelo ENBPAR.
# Invertido da tabela `sigla → grupo` confirmada na §5.1 da spec.
MAPA_GRUPO_SIGLAS = {
    # Equatorial → só os contratos de sigla EQUATORIAL (18 selecionáveis hoje).
    "EQUATORIAL": {"EQUATORIAL"},
    # Energisa → sigla ENERGISA (13).
    "ENERGISA": {"ENERGISA"},
    # Neoenergia → opera sob a sigla COELBA na base (2).
    "NEOENERGISA": {"COELBA"},
    # CERCI → sigla CERCI (1).
    "CERCI": {"CERCI"},
    # ÂMBAR concentra ÂMBAR + AMAZONAS + RORAIMA (2 + 1 + 4 = 7).
    "ÂMBAR": {"ÂMBAR", "AMAZONAS", "RORAIMA"},
    # ENBPAR é curinga (vê todos os 41 selecionáveis).
    "ENBPAR": None,
}

# Camada 1 — mapa **operador** (login) → grupo econômico.
# Fallback temporário (pedido dos engenheiros, 2026-07-15): o login por e-mail foi adiado
# para V1/V2; por ora o usuário entra com um **operador** simples (o rótulo do domínio, sem
# `nome@` nem `.com.br`/`.gov.br`). Operador fora do mapa ⇒ usuário sem grupo (sem contratos).
MAPA_OPERADOR_GRUPO = {
    # Equatorial.
    "equatorialenergia": "EQUATORIAL",
    # Energisa.
    "energisa": "ENERGISA",
    # Neoenergia / Coelba.
    "neoenergia": "NEOENERGISA",
    "coelba": "NEOENERGISA",
    # CERCI.
    "cerci": "CERCI",
    # Grupo ÂMBAR — só o operador ambarenergia por ora (vê o grupo econômico inteiro:
    # ÂMBAR + AMAZONAS + RORAIMA). Os operadores `amazonasenergia`/`roraimaenergia` ficam
    # FORA até os engenheiros decidirem se serão cadastrados (hoje duplicariam esta visão).
    "ambarenergia": "ÂMBAR",
    # ENBPar (Agente Operacionalizador) — curinga.
    "enbpar": "ENBPAR",
}

# Nomes das UFs (sigla → nome), para o payload do /api/contexto. Espelha o
# `UF_NOMES` do front (`seedData.js`), mantendo os rótulos idênticos aos aprovados.
UF_NOMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}


def montar_contexto(operador, contratos_detalhe, ucs_por_contrato, mapa_operador=None, mapa_grupo=None):
    """Monta o payload do `/api/contexto`: grupo + UFs/contratos visíveis (C1, §5.1/§6).

    Por que existe: o front, após o login, precisa das UFs e contratos que o usuário
    pode selecionar — já filtrados pelo grupo do operador (camada 1→2) e enriquecidos com
    a contagem de UCs por contrato (que no mock vinha de `mockUcsContrato`, e agora vem
    do backend). Concentrar essa montagem aqui a torna testável sem HTTP.

    Entrada: `operador` (do token), `contratos_detalhe` (lista de dicts com numero/uf/sigla/
             tipo_contrato/tranche — de `carregar_base_contratos`), `ucs_por_contrato`
             (dict numero→nº de UCs na referência), e os mapas opcionais de acesso.
    Fase 1: resolve o grupo do operador (camada 1).
    Fase 2: filtra os contratos visíveis do grupo (camada 2) e monta cada item com a
            contagem de UCs (0 se o contrato não tem referência).
    Fase 3: agrega as UFs distintas (sigla, nome, nº de contratos), ordenadas por sigla.
    Saída: dict `{operador, grupo, ufs, contratos}` (grupo None e listas vazias se o
           operador não mapeia a nenhum grupo).
    """
    # Fase 1: grupo econômico derivado do operador.
    grupo = grupo_do_operador(operador, mapa_operador)
    # Fase 2: contratos que o grupo enxerga, com o detalhe + UCs.
    visiveis = contratos_visiveis(grupo, contratos_detalhe, mapa_grupo)
    contratos = [
        {
            "numero": c["numero"],                       # número do contrato (normalizado)
            "uf": c.get("uf"),                           # UF do contrato
            "tipo_contrato": c.get("tipo_contrato"),     # LPT / MLA
            "tranche": c.get("tranche"),                 # tranche
            "sigla": c.get("sigla"),                     # distribuidora
            "vigente": c.get("vigente"),                 # Andamento / Encerramento (badge no front)
            "ucs": ucs_por_contrato.get(c["numero"], 0), # nº de UCs na referência (0 se sem)
        }
        for c in visiveis
    ]
    # Fase 3: agrega as UFs (sigla → contagem de contratos visíveis).
    contagem_uf = {}
    for c in contratos:
        # Conta contratos por UF (ignora contrato sem UF definida).
        if c["uf"]:
            contagem_uf[c["uf"]] = contagem_uf.get(c["uf"], 0) + 1
    ufs = [
        {"sigla": sigla, "nome": UF_NOMES.get(sigla, sigla), "contratos": n}
        for sigla, n in sorted(contagem_uf.items())   # ordena por sigla
    ]
    # Saída: contexto pronto para o front.
    return {"operador": operador, "grupo": grupo, "ufs": ufs, "contratos": contratos}


def grupo_do_operador(operador, mapa=None):
    """Resolve o grupo econômico a partir do operador (login) — camada 1.

    Por que existe: o grupo do usuário (que define o escopo da seleção) é derivado do
    operador informado no login (fallback temporário; antes vinha do domínio do e-mail),
    não armazenado por usuário.

    Entrada: `operador` (string do login) e `mapa` (mapa opcional; None usa o padrão).
    Fase 1: normaliza (trim + minúsculas); vazio → None.
    Fase 2: consulta o mapa operador→grupo.
    Saída: o grupo (string) ou None se o operador é vazio / não mapeado.
    """
    # Mapa efetivo (permite injeção em teste/config).
    mapa = mapa if mapa is not None else MAPA_OPERADOR_GRUPO
    # Fase 1: operador precisa existir; normaliza caixa/bordas.
    if not operador:
        return None
    chave = operador.strip().lower()
    # Fase 2/Saída: grupo do operador, ou None se não mapeado.
    return mapa.get(chave)


def siglas_do_grupo(grupo, mapa_grupo=None):
    """Devolve as siglas visíveis de um grupo (camada 2).

    Entrada: `grupo` (string) e `mapa_grupo` (mapa opcional; None usa o padrão).
    Fase 1: grupo desconhecido → conjunto vazio (não vê nada).
    Fase 2: grupo conhecido → o conjunto de siglas, ou None se for **curinga**.
    Saída: `set` de siglas, `None` (curinga = vê todos) ou `set()` vazio (desconhecido).
    """
    # Mapa efetivo (permite injeção em teste/config).
    mapa = mapa_grupo if mapa_grupo is not None else MAPA_GRUPO_SIGLAS
    # Fase 1: grupo fora do mapa não enxerga nenhuma sigla.
    if grupo not in mapa:
        return set()
    # Fase 2/Saída: siglas do grupo (ou None p/ curinga).
    return mapa[grupo]


def contratos_visiveis(grupo, contratos, mapa_grupo=None):
    """Filtra a lista de contratos pelas siglas visíveis do grupo (camada 2).

    Por que existe: reduz as duas etapas de seleção do front (UF e contrato) ao
    escopo do grupo do usuário; o `ENBPAR` (curinga) vê tudo.

    Entrada: `grupo` (string), `contratos` (lista de dicts com chave `sigla`),
             `mapa_grupo` (opcional).
    Fase 1: obtém as siglas do grupo.
    Fase 2: se curinga (None), devolve todos os contratos.
    Fase 3: senão, mantém só os contratos cuja `sigla` está no conjunto.
    Saída: lista (novo objeto) dos contratos visíveis.
    """
    # Fase 1: siglas do grupo (set, None=curinga, ou set() desconhecido).
    siglas = siglas_do_grupo(grupo, mapa_grupo)
    # Fase 2: curinga → cópia de todos os contratos.
    if siglas is None:
        return list(contratos)
    # Fase 3/Saída: filtra pelos contratos cuja sigla é visível ao grupo.
    return [c for c in contratos if c.get("sigla") in siglas]


def motivo_acesso_negado(operador, contrato_num, contratos, mapa_operador=None, mapa_grupo=None):
    """Explica POR QUE um contrato está fora do acesso do operador (para o `detail` do 403).

    Por que existe: um 403 "sem acesso" não diz onde a regra barrou; quem depura precisa
    saber o motivo concreto. Este helper usa os dados que o backend já tem no ponto da
    recusa — o grupo do operador (camada 1), as siglas que o grupo enxerga (camada 2) e,
    buscando na base, de qual distribuidora/UF é o contrato negado — para montar a razão.

    Entrada: `operador` (do token), `contrato_num` (número normalizado), `contratos`
             (lista de detalhe da base, com `numero`/`sigla`/`uf`), e os mapas opcionais.
    Fase 1: resolve o grupo do operador e as siglas visíveis do grupo.
    Fase 2: localiza o contrato na base (mesmo fora do acesso) para descrever de quem é.
    Fase 3: escolhe a explicação conforme o caso (sem grupo / inexistente / outro grupo).
    Saída: uma frase (str) com o motivo, sem ponto final (o chamador compõe a mensagem).
    """
    # Fase 1: grupo do operador (camada 1) e siglas que o grupo vê (camada 2).
    grupo = grupo_do_operador(operador, mapa_operador)
    siglas = siglas_do_grupo(grupo, mapa_grupo)
    # Fase 2: acha o contrato na base ainda que ele esteja fora do acesso do operador.
    alvo = next((c for c in contratos if c.get("numero") == contrato_num), None)
    # Descreve o escopo visível: curinga, o conjunto de siglas, ou nenhuma.
    escopo = "todos os contratos (curinga)" if siglas is None else (", ".join(sorted(siglas)) or "nenhuma sigla")
    # Fase 3 — caso 1: operador não mapeado a grupo nenhum (login fora da lista).
    if grupo is None:
        return (f'o operador "{operador}" não está mapeado a nenhum grupo econômico '
                f'(login fora da lista de operadores), então não enxerga contrato algum')
    # Caso 2: o contrato nem existe na base (número inválido ou não cadastrado).
    if alvo is None:
        return (f'o contrato "{contrato_num}" não existe na base de contratos '
                f'(número inválido ou não cadastrado); o operador "{operador}" pertence ao '
                f'grupo {grupo} (siglas visíveis: {escopo})')
    # Caso 3/Saída: existe, mas é de outra distribuidora/grupo.
    return (f'o operador "{operador}" pertence ao grupo {grupo} (vê as siglas: {escopo}); '
            f'o contrato {contrato_num} é da distribuidora {alvo.get("sigla")} '
            f'(UF {alvo.get("uf")}), fora desse grupo')
