"""Carga e cache em memória dos dados de referência de `entrada/` (Bloco A2).

Por que existe: a validação real (Blocos D) precisa cruzar cada `ODI+UC` da
planilha enviada com a base de referência, e conferir UF/município por ODI. Ler os
~176k registros de `entrada/**/*.csv` a cada requisição seria desperdício; este
módulo carrega tudo **uma vez** em dicionários/sets e **recarrega só quando um CSV
muda** (atualização diária), sem reiniciar o uvicorn. É a fonte única dos índices.

Índices montados, por contrato (chave normalizada):
  - `chaves_uc[contrato]` = set de `(odi, uc)`           ← arquivos `*_ucs.csv`
  - `odi_ref[contrato]`   = dict `odi -> (uf, municipio)` ← arquivos `consolidado.csv`

Lógica (Entrada → Saída):
  Entrada: um diretório-base (por padrão `entrada/` na raiz do repo).
  Fase 1: varre os `**/*.csv` do diretório.
  Fase 2: para cada arquivo, decide o índice pelo conjunto de colunas do cabeçalho
          (tem `uc` → chaves_uc; tem `uf`+`municipio` → odi_ref).
  Fase 3: normaliza a chave de contrato e popula os índices.
  Saída: atributos `chaves_uc`/`odi_ref` prontos para consulta; `recarregar_se_preciso`
         mantém-nos atualizados conforme os arquivos mudam.
"""

# `csv` faz o parsing robusto do separador `;` e do cabeçalho.
import csv
# `json` lê o `base_contratos.json` (autoridade dos contratos).
import json
# `re` colapsa espaços internos na normalização da chave de contrato.
import re
# `Path` manipula caminhos e expõe `stat().st_mtime` para a detecção de mudança.
from pathlib import Path

# Diretório-base padrão = `entrada/` na raiz do repositório.
# `__file__` = backend/referencia.py → parent = backend/ → parent.parent = raiz.
_DIR_PADRAO = Path(__file__).resolve().parent.parent / "entrada"

# `base_contratos.json` (autoridade dos contratos, §8) também fica na raiz do repo.
_BASE_PADRAO = Path(__file__).resolve().parent.parent / "base_contratos.json"


def _norm_contrato(valor):
    """Normaliza o número do contrato para casar com `base_contratos.json`.

    Por que existe: o mesmo contrato pode aparecer com espaços extras ou caixa
    diferente; a junção (§5 da spec) usa a forma canônica (trim + colapso de
    espaços + maiúsculas).

    Entrada: `valor` (string crua do CSV).
    Fase 1: remove espaços das bordas.
    Fase 2: colapsa qualquer sequência de espaços internos em um único espaço.
    Fase 3: converte para maiúsculas.
    Saída: a string canônica do contrato.
    """
    # Fase 1+2: tira bordas e colapsa espaços internos (\s+ → " ").
    sem_espacos = re.sub(r"\s+", " ", valor.strip())
    # Fase 3: maiúsculas para casar independentemente de caixa.
    return sem_espacos.upper()


class Referencia:
    """Mantém os índices de `entrada/` em memória, com recarga por mtime."""

    def __init__(self, base_dir=None):
        """Carrega a referência a partir de um diretório-base.

        Entrada: `base_dir` (Path/str do diretório; None usa `entrada/` padrão).
        Fase 1: resolve o diretório-base efetivo.
        Fase 2: inicializa os índices e o mapa de mtimes vazios.
        Fase 3: faz a carga inicial (lê todos os CSVs).
        Saída: instância pronta para consulta.
        """
        # Fase 1: usa o diretório informado ou o padrão `entrada/`.
        self._base_dir = Path(base_dir) if base_dir is not None else _DIR_PADRAO
        # Fase 2: estruturas vazias (preenchidas em `carregar`).
        self._mtimes = {}            # caminho -> mtime, para detectar mudança
        self.chaves_uc = {}          # contrato -> set((odi, uc))
        self.odi_ref = {}            # contrato -> {odi: (uf, municipio)}
        # Fase 3: carga inicial no startup (spec §5).
        self.carregar()

    def _arquivos_csv(self):
        """Lista, ordenados, todos os CSVs sob o diretório-base.

        Entrada: nenhuma (usa `self._base_dir`).
        Fase 1: varre recursivamente `**/*.csv`.
        Saída: lista de Paths ordenada (estável entre execuções).
        """
        # Se o diretório não existe, retorna lista vazia (não quebra a carga).
        if not self._base_dir.exists():
            # Sem `entrada/`, os índices ficam vazios.
            return []
        # Fase 1/Saída: glob recursivo, ordenado para determinismo.
        return sorted(self._base_dir.glob("**/*.csv"))

    def carregar(self):
        """(Re)constrói os índices lendo todos os CSVs do diretório-base.

        Entrada: nenhuma (lê os arquivos atuais).
        Fase 1: zera estruturas locais.
        Fase 2: para cada CSV, registra o mtime e decide o índice pelas colunas.
        Fase 3: percorre as linhas, normaliza o contrato e popula o índice certo.
        Saída: substitui `self.chaves_uc`, `self.odi_ref` e `self._mtimes`.
        """
        # Fase 1: acumuladores locais (trocados de uma vez no fim — carga atômica).
        chaves_uc = {}
        odi_ref = {}
        mtimes = {}
        # Fase 2: percorre cada CSV encontrado.
        for caminho in self._arquivos_csv():
            # Guarda o mtime do arquivo para a detecção de mudança posterior.
            mtimes[str(caminho)] = caminho.stat().st_mtime
            # Abre com `utf-8-sig` para descartar o BOM; `newline=""` p/ o csv.
            with open(caminho, encoding="utf-8-sig", newline="") as fh:
                # DictReader mapeia por nome de coluna (robusto a reordenação).
                leitor = csv.DictReader(fh, delimiter=";")
                # Conjunto de colunas do cabeçalho — decide o tipo do arquivo.
                campos = set(leitor.fieldnames or [])
                # Flags do tipo de arquivo (calculadas uma vez por arquivo).
                eh_ucs = "uc" in campos
                eh_localizacao = "uf" in campos and "municipio" in campos
                # Fase 3: percorre as linhas de dados do arquivo.
                for linha in leitor:
                    # Normaliza a chave de contrato (trim + colapso + upper).
                    contrato = _norm_contrato(linha.get("contrato") or "")
                    # Linha sem contrato não tem como ser indexada — pula.
                    if not contrato:
                        continue
                    # ODI é comum aos dois tipos de arquivo.
                    odi = (linha.get("odi") or "").strip()
                    if eh_ucs:
                        # Arquivo de UCs → adiciona o par (odi, uc) ao set do contrato.
                        uc = (linha.get("uc") or "").strip()
                        chaves_uc.setdefault(contrato, set()).add((odi, uc))
                    elif eh_localizacao:
                        # Arquivo de localização → mapeia odi → (uf, municipio).
                        uf = (linha.get("uf") or "").strip()
                        municipio = (linha.get("municipio") or "").strip()
                        odi_ref.setdefault(contrato, {})[odi] = (uf, municipio)
        # Saída: troca os índices e o mapa de mtimes de uma vez.
        self.chaves_uc = chaves_uc
        self.odi_ref = odi_ref
        self._mtimes = mtimes

    def recarregar_se_preciso(self):
        """Recarrega os índices se algum CSV mudou (mtime) desde a última carga.

        Por que existe: a atualização diária de `entrada/` deve refletir sem
        reiniciar o uvicorn; chamado a cada requisição (custo desprezível: só lê
        mtimes, não os arquivos).

        Entrada: nenhuma.
        Fase 1: coleta os mtimes atuais de todos os CSVs.
        Fase 2: compara com o snapshot da última carga (cobre add/remove/edição).
        Fase 3: se mudou, recarrega tudo.
        Saída: True se recarregou; False se nada mudou.
        """
        # Fase 1: snapshot atual {caminho: mtime}.
        atuais = {str(p): p.stat().st_mtime for p in self._arquivos_csv()}
        # Fase 2: dicionários diferentes ⇒ algum arquivo mudou/entrou/saiu.
        if atuais != self._mtimes:
            # Fase 3: recarrega e sinaliza que houve recarga.
            self.carregar()
            return True
        # Saída: sem mudança.
        return False

    def resumo(self):
        """Resumo numérico dos índices, para o `/api/health` (A2).

        Entrada: nenhuma.
        Fase 1: conta contratos e pares/mapeamentos de cada índice.
        Saída: dict com as contagens (serializável em JSON).
        """
        # Fase 1/Saída: contagens agregadas dos dois índices.
        return {
            # Nº de contratos que têm pelo menos um par (odi, uc).
            "contratosComChavesUc": len(self.chaves_uc),
            # Nº de contratos que têm mapeamento odi → (uf, municipio).
            "contratosComOdiRef": len(self.odi_ref),
            # Total de pares (odi, uc) somando todos os contratos.
            "totalChavesUc": sum(len(pares) for pares in self.chaves_uc.values()),
            # Total de ODIs mapeados somando todos os contratos.
            "totalOdiRef": sum(len(mapa) for mapa in self.odi_ref.values()),
        }

    def integridade(self, selecionaveis, todos_base):
        """Classifica os contratos cruzando os índices com a autoridade (§8, A3).

        Por que existe: `base_contratos.json` é a autoridade sobre quais contratos
        existem e quais são selecionáveis; `entrada/` é validado contra ela. Esta
        classificação torna o gap de cobertura **observável** no `/api/health` e nos
        logs (no fluxo real todo contrato selecionável tem ODI+UC).

        Definição de "ter referência": ter `chaves_uc` (pares ODI+UC). Um contrato
        com apenas `odi_ref` (caso dos MLA, que têm só `consolidado.csv`) é "sem
        referência".

        Entrada: `selecionaveis` (set de contratos com `vigente ≠ "Encerrado"`) e
                 `todos_base` (set de todos os contratos da autoridade) — já normalizados.
        Fase 1: separa os selecionáveis com `chaves_uc` (com referência) dos sem.
        Fase 2: detecta órfãos = contratos presentes em `entrada/` (chaves_uc ∪ odi_ref)
                que não existem na autoridade.
        Saída: dict com contagem de com-referência, lista de sem-referência e lista
               de órfãos (ordenadas, serializáveis em JSON).
        """
        # Fase 1: selecionáveis que têm (ou não) pares ODI+UC na referência.
        com_referencia = sorted(c for c in selecionaveis if c in self.chaves_uc)
        sem_referencia = sorted(c for c in selecionaveis if c not in self.chaves_uc)
        # Fase 2: tudo que aparece em entrada/ (qualquer um dos dois índices).
        contratos_entrada = set(self.chaves_uc) | set(self.odi_ref)
        # Órfão = está em entrada/ mas não na autoridade.
        orfaos = sorted(c for c in contratos_entrada if c not in todos_base)
        # Saída: resumo da integridade.
        return {
            # Quantos selecionáveis têm referência (pares ODI+UC).
            "contratosComReferencia": len(com_referencia),
            # Lista dos selecionáveis SEM referência (esperado: 22 hoje — 19 MLA + 3 LPT).
            "contratosSemReferencia": sem_referencia,
            # Lista de órfãos (dados em entrada/ fora da autoridade; esperado: vazio).
            "orfaos": orfaos,
        }


def carregar_base_contratos(caminho=None):
    """Lê `base_contratos.json` (autoridade) e separa todos × selecionáveis.

    Por que existe: a autoridade sobre quais contratos existem/são selecionáveis é
    o `base_contratos.json` (§8). Esta função normaliza as chaves (para casar com a
    referência) e marca como selecionável quem tem `vigente ≠ "Encerrado"`.

    Entrada: `caminho` (Path/str do JSON; None usa o `base_contratos.json` da raiz).
    Fase 1: lê o JSON (dict `numero -> {sigla, vigente, ...}`).
    Fase 2: normaliza cada número e monta o set `todos`.
    Fase 3: monta o set `selecionaveis` (vigente diferente de "Encerrado").
    Fase 4: monta `contratos` = lista (detalhe) dos selecionáveis, com a `sigla`
            usada pelo filtro de acesso (camada 2, §5.1).
    Saída: dict `{"todos": set, "selecionaveis": set, "contratos": list}`.
    """
    # Fase 1: resolve o caminho e carrega o JSON da autoridade.
    alvo = Path(caminho) if caminho is not None else _BASE_PADRAO
    with open(alvo, encoding="utf-8") as fh:
        base = json.load(fh)
    # Fase 2: todos os contratos, com a chave normalizada.
    todos = {_norm_contrato(numero) for numero in base}
    # Fase 3: selecionáveis = vigente diferente de "Encerrado".
    selecionaveis = {
        _norm_contrato(numero)
        for numero, dados in base.items()
        if (dados.get("vigente") != "Encerrado")
    }
    # Fase 4: detalhe dos selecionáveis (número normalizado + sigla) p/ o filtro de acesso.
    contratos = [
        {"numero": _norm_contrato(numero), "sigla": dados.get("sigla")}
        for numero, dados in base.items()
        if (dados.get("vigente") != "Encerrado")
    ]
    # Saída: conjuntos normalizados + lista de detalhe dos selecionáveis.
    return {"todos": todos, "selecionaveis": selecionaveis, "contratos": contratos}


# Singleton do processo: a referência apontando para o `entrada/` real.
# Carregado sob demanda (1ª chamada) para não pagar a carga em imports de ferramentas.
_singleton = None


def obter_referencia():
    """Devolve a instância única de `Referencia` ligada ao `entrada/` real.

    Por que existe: o app e as rotas devem compartilhar **um** cache de referência
    (não recarregar por handler). Cria sob demanda e reaproveita nas próximas chamadas.

    Entrada: nenhuma.
    Fase 1: se ainda não existe, instancia (dispara a carga inicial).
    Saída: o singleton de `Referencia`.
    """
    # Permite reatribuir a variável de módulo `_singleton`.
    global _singleton
    # Fase 1: cria na primeira vez; depois reaproveita.
    if _singleton is None:
        _singleton = Referencia()
    # Saída: instância compartilhada.
    return _singleton


# Cache da autoridade `base_contratos.json` (estática; sem recarga por mtime — muda
# raramente, não diariamente como `entrada/`).
_base_singleton = None


def obter_base_contratos():
    """Devolve a autoridade `base_contratos.json` carregada uma vez (cache).

    Por que existe: o health (A3) e os seletores (Bloco C) precisam dos conjuntos
    de contratos da autoridade; carregar o JSON a cada requisição é desnecessário.

    Entrada: nenhuma.
    Fase 1: carrega na primeira chamada; depois reaproveita.
    Saída: dict `{"todos": set, "selecionaveis": set}`.
    """
    # Permite reatribuir a variável de módulo `_base_singleton`.
    global _base_singleton
    # Fase 1: carrega sob demanda e memoiza.
    if _base_singleton is None:
        _base_singleton = carregar_base_contratos()
    # Saída: autoridade compartilhada.
    return _base_singleton
