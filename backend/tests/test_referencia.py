"""Testes da carga de referência (`backend/referencia.py`) — Bloco A2.

Por que existe: a §13 da spec exige cobrir a carga dos CSVs de `entrada/`, a
montagem dos índices (`chaves_uc`, `odi_ref`), a normalização da chave de contrato
e a recarga por mudança de mtime. Estes testes usam **CSVs-fixture pequenos** em
`tmp_path` (não o volume real de `entrada/`), para serem rápidos e determinísticos.
"""

# `os.utime` força o mtime de um arquivo (evita flakiness na detecção de recarga).
import os
# `json` grava o `base_contratos.json`-fixture do teste de integridade.
import json

# `Referencia` é a classe sob teste; `carregar_base_contratos` lê a autoridade (A3).
from backend.referencia import Referencia, carregar_base_contratos


def _escrever_csv(caminho, cabecalho, linhas):
    """Cria um CSV no layout de `entrada/` (BOM UTF-8, separador `;`).

    Por que existe: todos os testes precisam fabricar CSVs idênticos aos reais
    (BOM + `;`); centralizar aqui evita repetir o boilerplate de escrita.

    Entrada: `caminho` (Path do arquivo), `cabecalho` (lista de colunas),
             `linhas` (lista de listas de valores).
    Fase 1: garante que a pasta-pai exista.
    Fase 2: abre o arquivo com encoding `utf-8-sig` (escreve o BOM) e monta o
            conteúdo juntando cada registro por `;`.
    Saída: o arquivo gravado em disco (sem retorno).
    """
    # Fase 1: cria os diretórios intermediários (ex.: lpt/, mla/) se faltarem.
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # Monta todas as linhas (cabeçalho + dados) já unidas por `;`.
    conteudo = "\n".join(";".join(registro) for registro in [cabecalho, *linhas])
    # Fase 2: grava com `utf-8-sig` para reproduzir o BOM dos arquivos reais.
    caminho.write_text(conteudo + "\n", encoding="utf-8-sig")


def test_indice_chaves_uc_monta_pares_odi_uc(tmp_path):
    """Um `*_ucs.csv` vira `chaves_uc[contrato] = {(odi, uc), ...}`.

    Entrada: dir temporário com `lpt/consolidado_ucs.csv` (2 pares).
    Fase 1: grava o CSV de UCs.
    Fase 2: instancia `Referencia` apontando para o dir.
    Fase 3: confere que os dois pares (odi, uc) estão no set do contrato.
    Saída: asserções.
    """
    # Fase 1: CSV de UCs com 2 linhas para o mesmo contrato.
    _escrever_csv(
        tmp_path / "lpt" / "consolidado_ucs.csv",
        ["contrato", "odi", "uc"],
        [["ECO 011/2018", "ODR001", "2959348"],
         ["ECO 011/2018", "ODR001", "2959550"]],
    )
    # Fase 2: carrega a referência a partir do dir temporário.
    ref = Referencia(tmp_path)
    # Fase 3: ambos os pares devem estar indexados sob o contrato.
    assert ("ODR001", "2959348") in ref.chaves_uc["ECO 011/2018"]
    assert ("ODR001", "2959550") in ref.chaves_uc["ECO 011/2018"]


def test_indice_odi_ref_mapeia_odi_para_uf_municipio(tmp_path):
    """Um `consolidado.csv` vira `odi_ref[contrato][odi] = (uf, municipio)`.

    Entrada: dir temporário com `lpt/consolidado.csv`.
    Fase 1: grava o CSV de ODI→localização.
    Fase 2: instancia `Referencia`.
    Fase 3: confere o mapeamento odi → (uf, municipio).
    Saída: asserções.
    """
    # Fase 1: CSV com uma linha de ODI/localização.
    _escrever_csv(
        tmp_path / "lpt" / "consolidado.csv",
        ["contrato", "odi", "uf", "municipio"],
        [["ECO 011/2018", "136PROJ", "AP", "PORTO GRANDE"]],
    )
    # Fase 2: carrega a referência.
    ref = Referencia(tmp_path)
    # Fase 3: o ODI deve mapear para a tupla (uf, municipio).
    assert ref.odi_ref["ECO 011/2018"]["136PROJ"] == ("AP", "PORTO GRANDE")


def test_normaliza_chave_de_contrato(tmp_path):
    """A chave de contrato é normalizada (trim + colapso de espaços + upper).

    Por que: o número do contrato em `entrada/` precisa casar com
    `base_contratos.json` mesmo com espaços extras ou caixa diferente (§5).

    Entrada: CSV com contrato "  eco  011/2018 " (sujo).
    Fase 1: grava o CSV.
    Fase 2: carrega.
    Fase 3: confere que o índice usa a forma canônica "ECO 011/2018".
    Saída: asserções.
    """
    # Fase 1: contrato propositalmente "sujo" (espaços duplos, minúsculas, bordas).
    _escrever_csv(
        tmp_path / "lpt" / "consolidado.csv",
        ["contrato", "odi", "uf", "municipio"],
        [["  eco  011/2018 ", "136PROJ", "AP", "PORTO GRANDE"]],
    )
    # Fase 2: carrega a referência.
    ref = Referencia(tmp_path)
    # Fase 3: a chave canônica deve existir; a forma suja, não.
    assert "ECO 011/2018" in ref.odi_ref
    assert "  eco  011/2018 " not in ref.odi_ref


def test_recarga_por_mtime_reflete_mudanca_sem_reiniciar(tmp_path):
    """Alterar um CSV faz `recarregar_se_preciso()` recarregar (e só então).

    Entrada: CSV de UCs com 1 par; depois acrescido de outro par.
    Fase 1: grava o CSV inicial e carrega (1 par).
    Fase 2: reescreve o CSV com 2 pares e força o mtime para o futuro.
    Fase 3: `recarregar_se_preciso()` deve retornar True e refletir o novo par.
    Fase 4: chamar de novo (sem mudança) deve retornar False.
    Saída: asserções.
    """
    # Caminho do CSV de UCs usado no teste.
    csv_ucs = tmp_path / "lpt" / "consolidado_ucs.csv"
    # Fase 1: estado inicial com 1 par e carga.
    _escrever_csv(csv_ucs, ["contrato", "odi", "uc"],
                  [["ECO 011/2018", "ODR001", "111"]])
    ref = Referencia(tmp_path)
    # Confirma o estado inicial (apenas 1 par).
    assert len(ref.chaves_uc["ECO 011/2018"]) == 1
    # Fase 2: reescreve com 2 pares.
    _escrever_csv(csv_ucs, ["contrato", "odi", "uc"],
                  [["ECO 011/2018", "ODR001", "111"],
                   ["ECO 011/2018", "ODR001", "222"]])
    # Força um mtime claramente posterior (evita flakiness em FS de baixa resolução).
    futuro = os.stat(csv_ucs).st_mtime + 10
    os.utime(csv_ucs, (futuro, futuro))
    # Fase 3: detecta a mudança, recarrega e passa a enxergar o 2º par.
    assert ref.recarregar_se_preciso() is True
    assert ("ODR001", "222") in ref.chaves_uc["ECO 011/2018"]
    # Fase 4: sem nova mudança, não recarrega.
    assert ref.recarregar_se_preciso() is False


def test_carregar_base_contratos_separa_selecionaveis(tmp_path):
    """`carregar_base_contratos` separa todos × selecionáveis (≠ "Encerrado").

    Por que: `base_contratos.json` é a autoridade (§8); selecionável = `vigente`
    diferente de "Encerrado" (inclui "Andamento" e "Encerramento"). As chaves são
    normalizadas como no resto da referência.

    Entrada: um `base.json`-fixture com 3 contratos (1 encerrado, 1 sujo de espaços).
    Fase 1: grava o JSON.
    Fase 2: chama `carregar_base_contratos`.
    Fase 3: confere `todos` (3, normalizados) e `selecionaveis` (só os não-encerrados).
    Saída: asserções.
    """
    # Fase 1: base com um encerrado e um com espaços/caixa "sujos".
    base = tmp_path / "base.json"
    base.write_text(json.dumps({
        "ECO 1/2020": {"vigente": "Andamento"},
        "ECO 2/2020": {"vigente": "Encerrado"},
        "  eco  3/2020 ": {"vigente": "Encerramento"},
    }), encoding="utf-8")
    # Fase 2: carrega a autoridade a partir do arquivo.
    dados = carregar_base_contratos(base)
    # Fase 3: todos os 3 contratos, com a chave suja normalizada.
    assert dados["todos"] == {"ECO 1/2020", "ECO 2/2020", "ECO 3/2020"}
    # Selecionáveis = não-"Encerrado" (Andamento + Encerramento).
    assert dados["selecionaveis"] == {"ECO 1/2020", "ECO 3/2020"}


def test_integridade_classifica_com_e_sem_referencia(tmp_path):
    """`integridade` separa selecionáveis com UC (referência) dos sem UC.

    Por que: a A3 marca como "sem referência" o contrato selecionável que não tem
    `chaves_uc` em `entrada/` (caso dos MLA, que têm só `consolidado.csv`).

    Entrada: `entrada/` com UC só para C1; autoridade selecionável = {C1, C2}.
    Fase 1: grava o CSV de UCs (só C1).
    Fase 2: carrega a referência e chama `integridade`.
    Fase 3: C1 tem referência; C2 (selecionável, sem UC) está em sem-referência.
    Saída: asserções.
    """
    # Fase 1: só C1 tem par (odi, uc).
    _escrever_csv(tmp_path / "lpt" / "consolidado_ucs.csv",
                  ["contrato", "odi", "uc"], [["C1", "O1", "100"]])
    # Fase 2: carrega e classifica contra a autoridade.
    ref = Referencia(tmp_path)
    integ = ref.integridade(selecionaveis={"C1", "C2"}, todos_base={"C1", "C2"})
    # Fase 3: 1 com referência (C1); C2 listado como sem referência.
    assert integ["contratosComReferencia"] == 1
    assert integ["contratosSemReferencia"] == ["C2"]


def test_integridade_detecta_orfaos(tmp_path):
    """`integridade` lista como órfão o contrato de `entrada/` ausente da autoridade.

    Por que: §8 — contrato em `entrada/` que não existe em `base_contratos.json` é
    um dado órfão (hoje: zero), digno de log de alerta.

    Entrada: `entrada/` com o contrato "XX" (não está na autoridade).
    Fase 1: grava um `consolidado.csv` com "XX".
    Fase 2: carrega e chama `integridade` com autoridade que não tem "XX".
    Fase 3: "XX" aparece em `orfaos`.
    Saída: asserções.
    """
    # Fase 1: entrada com um contrato fora da autoridade.
    _escrever_csv(tmp_path / "lpt" / "consolidado.csv",
                  ["contrato", "odi", "uf", "municipio"],
                  [["XX", "O1", "AP", "PORTO GRANDE"]])
    # Fase 2: autoridade só conhece "YY".
    ref = Referencia(tmp_path)
    integ = ref.integridade(selecionaveis=set(), todos_base={"YY"})
    # Fase 3: "XX" é órfão (existe em entrada/, não na base).
    assert integ["orfaos"] == ["XX"]
