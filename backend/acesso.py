"""Filtro de acesso por login (grupo econômico) em duas camadas — Bloco A4 (§5.1).

Por que existe: o site é acessado por **grupos econômicos** de distribuidoras, e o
que cada usuário vê na seleção depende do **domínio do e-mail** informado no login.
Este módulo resolve as duas camadas do filtro:
  Camada 1 — domínio do e-mail → grupo econômico (`grupo_do_email`).
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

# Camada 1 — mapa domínio do e-mail → grupo econômico.
# **Configurável e provisório**: os domínios reais de cada distribuidora ainda são
# pendência (risco #3 da spec); estes são placeholders plausíveis, a confirmar antes
# do deploy. Domínio fora do mapa ⇒ usuário sem grupo (sem contratos).
MAPA_DOMINIO_GRUPO = {
    # Equatorial.
    "equatorialenergia.com.br": "EQUATORIAL",
    # Energisa.
    "energisa.com.br": "ENERGISA",
    # Neoenergia / Coelba.
    "neoenergia.com.br": "NEOENERGISA",
    "coelba.com.br": "NEOENERGISA",
    # CERCI.
    "cerci.com.br": "CERCI",
    # Grupo ÂMBAR — só o domínio ambarenergia por ora (vê o grupo econômico inteiro:
    # ÂMBAR + AMAZONAS + RORAIMA). Os domínios `amazonasenergia`/`roraimaenergia` ficam
    # FORA até os engenheiros decidirem se serão cadastrados (hoje duplicariam esta visão).
    "ambarenergia.com.br": "ÂMBAR",
    # ENBPar (Agente Operacionalizador) — curinga.
    "enbpar.gov.br": "ENBPAR",
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


def montar_contexto(email, contratos_detalhe, ucs_por_contrato, mapa_dominio=None, mapa_grupo=None):
    """Monta o payload do `/api/contexto`: grupo + UFs/contratos visíveis (C1, §5.1/§6).

    Por que existe: o front, após o login, precisa das UFs e contratos que o usuário
    pode selecionar — já filtrados pelo grupo do e-mail (camada 1→2) e enriquecidos com
    a contagem de UCs por contrato (que no mock vinha de `mockUcsContrato`, e agora vem
    do backend). Concentrar essa montagem aqui a torna testável sem HTTP.

    Entrada: `email` (do token), `contratos_detalhe` (lista de dicts com numero/uf/sigla/
             tipo_contrato/tranche — de `carregar_base_contratos`), `ucs_por_contrato`
             (dict numero→nº de UCs na referência), e os mapas opcionais de acesso.
    Fase 1: resolve o grupo do e-mail (camada 1).
    Fase 2: filtra os contratos visíveis do grupo (camada 2) e monta cada item com a
            contagem de UCs (0 se o contrato não tem referência).
    Fase 3: agrega as UFs distintas (sigla, nome, nº de contratos), ordenadas por sigla.
    Saída: dict `{email, grupo, ufs, contratos}` (grupo None e listas vazias se o domínio
           não mapeia a nenhum grupo).
    """
    # Fase 1: grupo econômico derivado do domínio do e-mail.
    grupo = grupo_do_email(email, mapa_dominio)
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
    return {"email": email, "grupo": grupo, "ufs": ufs, "contratos": contratos}


def grupo_do_email(email, mapa_dominio=None):
    """Resolve o grupo econômico a partir do domínio do e-mail (camada 1).

    Por que existe: o grupo do usuário (que define o escopo da seleção) é derivado
    do domínio após o `@`, não armazenado por usuário (§5.2).

    Entrada: `email` (string) e `mapa_dominio` (mapa opcional; None usa o padrão).
    Fase 1: valida o formato mínimo (precisa ter `@`).
    Fase 2: extrai o domínio (depois do último `@`), normaliza (trim + minúsculas).
    Fase 3: consulta o mapa domínio→grupo.
    Saída: o grupo (string) ou None se o e-mail é inválido / domínio não mapeado.
    """
    # Mapa efetivo (permite injeção em teste/config).
    mapa = mapa_dominio if mapa_dominio is not None else MAPA_DOMINIO_GRUPO
    # Fase 1: e-mail precisa existir e conter "@".
    if not email or "@" not in email:
        # E-mail malformado → sem grupo.
        return None
    # Fase 2: pega o que vem depois do último "@", tira espaços e baixa a caixa.
    dominio = email.rsplit("@", 1)[1].strip().lower()
    # Fase 3/Saída: grupo do domínio, ou None se não mapeado.
    return mapa.get(dominio)


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
