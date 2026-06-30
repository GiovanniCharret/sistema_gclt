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
    "neoenergia.com": "NEOENERGISA",
    "coelba.com.br": "NEOENERGISA",
    # CERCI.
    "cerci.com.br": "CERCI",
    # Grupo ÂMBAR (ÂMBAR / Amazonas / Roraima Energia).
    "ambarenergia.com.br": "ÂMBAR",
    "amazonasenergia.com": "ÂMBAR",
    "roraimaenergia.com.br": "ÂMBAR",
    # ENBPar (Agente Operacionalizador) — curinga.
    "enbpar.gov.br": "ENBPAR",
}


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
