# -*- coding: utf-8 -*-
"""Testes das rotas de versão (`/api/versao` e `/api/versao/historico`).

Por que este arquivo existe: a rota aberta alimenta o rodapé, que aparece **na tela de
login** — ou seja, o que ela devolve é público para a internet. O risco não é a rota
quebrar; é ela passar a devolver mais do que deveria, no dia em que alguém "melhorar" o
retorno incluindo o título da última entrada ou as fases. Os dois testes de recorte existem
para que isso falhe a suíte em vez de ir ao ar.

O resto cobre as três maneiras de o arquivo não servir (ausente, JSON quebrado, sem o campo
esperado), porque todas as três já aconteceram neste projeto com outros arquivos de
configuração, e a diferença entre 503 com motivo e 500 mudo é o tempo de diagnóstico num
servidor sem terminal.
"""

# `io`/`json` escrevem os arquivos temporários de cada caso.
import io
import json

# `pytest` para os casos parametrizados e as fixtures.
import pytest

# Alvos: o módulo de leitura e, pelo cliente, as rotas.
from backend import versao as mod_versao
# `gerar_token` e o idioma do projeto para autenticar um teste (ver test_api.py).
from backend.auth import gerar_token


# --- a camada de leitura, sem servidor ----------------------------------

def _documento_valido():
    """Documento mínimo com a forma do arquivo real.

    Por que existe: cada teste precisa de um arquivo próprio, e repetir o dicionário em
    cinco lugares faria uma mudança de formato exigir cinco edições.
    """
    # Mesma forma do `controle_versao/historico.json`, reduzida ao que as rotas leem.
    return {
        "esquema": "1.0",
        "versao_app": "V9.9.3112",
        "ultima_atualizacao": {
            "data": "2026-12-31",
            "fase": "F9",
            "subfase": "F9.9",
            "titulo": "Título que NÃO pode sair na rota aberta",
            "resumo": "Resumo que NÃO pode sair na rota aberta",
        },
        "contadores": {"fases": 1, "subfases": 1},
        "fases": [{"id": "F9", "nome": "Fase de teste", "estado": "concluida",
                   "subfases": [{"id": "F9.9", "data": "2026-12-31", "tipo": "entrega",
                                 "titulo": "t", "resumo": "r"}]}],
    }


@pytest.fixture()
def arquivo(tmp_path):
    """Grava o documento válido num arquivo temporário e devolve o caminho."""
    # `tmp_path` dá uma pasta exclusiva por teste — nenhum caso enxerga o arquivo do outro.
    destino = tmp_path / "historico.json"
    destino.write_text(json.dumps(_documento_valido()), encoding="utf-8")
    return str(destino)


def test_le_o_documento_do_disco(arquivo):
    """O documento volta inteiro, como está no arquivo."""
    documento = mod_versao.ler_historico(arquivo)
    assert documento["versao_app"] == "V9.9.3112"
    assert documento["fases"][0]["id"] == "F9"


def test_arquivo_ausente_diz_qual_caminho_procurou(tmp_path):
    """Ausência é a falha mais provável num deploy — a mensagem tem de nomear o caminho.

    Sem o caminho na mensagem, descobrir que o arquivo não foi publicado exigiria acesso ao
    servidor, que este projeto não tem.
    """
    faltante = str(tmp_path / "nao_existe.json")
    with pytest.raises(mod_versao.HistoricoIndisponivel) as erro:
        mod_versao.ler_historico(faltante)
    assert "nao_existe.json" in str(erro.value)


def test_json_quebrado_vira_erro_explicado(tmp_path):
    """Vírgula sobrando numa edição à mão é erro de edição, não defeito do sistema."""
    ruim = tmp_path / "historico.json"
    ruim.write_text('{"versao_app": "V0.0.0101",}', encoding="utf-8")
    with pytest.raises(mod_versao.HistoricoIndisponivel) as erro:
        mod_versao.ler_historico(str(ruim))
    assert "JSON inválido" in str(erro.value)


def test_json_valido_mas_sem_versao_e_recusado(tmp_path):
    """Arquivo que lê mas não serve: recusar é melhor que devolver `null` ao rodapé."""
    incompleto = tmp_path / "historico.json"
    incompleto.write_text('{"esquema": "1.0"}', encoding="utf-8")
    with pytest.raises(mod_versao.HistoricoIndisponivel) as erro:
        mod_versao.ler_historico(str(incompleto))
    assert "versao_app" in str(erro.value)


def test_resumo_publico_leva_so_versao_data_e_esquema():
    """⚠️ Teste de fronteira: o recorte público tem exatamente três chaves.

    Se alguém acrescentar um campo ao resumo, este teste falha e obriga a decisão a ser
    consciente — porque o destino é a tela de login, visível sem autenticação.
    """
    resumo = mod_versao.resumo_publico(_documento_valido())
    assert set(resumo) == {"versao", "data", "esquema"}
    assert resumo["versao"] == "V9.9.3112"
    assert resumo["data"] == "2026-12-31"


def test_resumo_publico_nao_leva_narrativa():
    """O título e o resumo da última entrada NÃO podem aparecer sem autenticação.

    O histórico narra incidentes de produção e um risco aceito; a tela de login é pública.
    """
    resumo = mod_versao.resumo_publico(_documento_valido())
    serializado = json.dumps(resumo, ensure_ascii=False)
    assert "NÃO pode sair" not in serializado
    assert "fases" not in resumo


def test_resumo_publico_tolera_documento_sem_ultima_atualizacao():
    """Arquivo editado à mão pode não ter o bloco derivado — a data vem `None`, sem estourar."""
    resumo = mod_versao.resumo_publico({"esquema": "1.0", "versao_app": "V0.0.0101"})
    assert resumo == {"versao": "V0.0.0101", "data": None, "esquema": "1.0"}


# --- as rotas, pelo cliente HTTP ----------------------------------------

def test_rota_aberta_responde_sem_token(client):
    """`/api/versao` é aberta: o rodapé aparece antes do login."""
    resposta = client.get("/api/versao")
    assert resposta.status_code == 200
    corpo = resposta.json()
    # O arquivo real do repositório é lido aqui — então o que se afirma é a FORMA.
    assert set(corpo) == {"versao", "data", "esquema"}
    assert corpo["versao"].startswith("V")


def test_rota_aberta_le_o_arquivo_real_do_repositorio(client):
    """A rota lê `controle_versao/historico.json` — a mesma fonte do `HISTORICO.md`.

    Por que afirmar isso: se o caminho padrão mudar por engano, a rota passaria a servir
    outro arquivo (ou nada) e só o rodapé em produção denunciaria.
    """
    do_disco = mod_versao.ler_historico()
    assert client.get("/api/versao").json()["versao"] == do_disco["versao_app"]


def test_historico_completo_exige_token(client):
    """Sem token, 401: a narrativa não é pública."""
    assert client.get("/api/versao/historico").status_code == 401


def test_historico_completo_com_token_traz_as_fases(client):
    """Com token, o documento inteiro — é o que a futura página de evolução vai consumir."""
    resposta = client.get("/api/versao/historico",
                          headers={"Authorization": "Bearer %s" % gerar_token("enbpar")})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["esquema"]
    assert isinstance(corpo["fases"], list) and corpo["fases"]
    # A narrativa está aqui, e só aqui.
    assert "subfases" in corpo["fases"][0]


def test_edicao_do_arquivo_vale_na_requisicao_seguinte(client, monkeypatch, tmp_path):
    """Sem cache: publicar um JSON novo vale no pedido seguinte, sem reiniciar o processo.

    É a razão de a rota existir em vez de uma constante no código do front — e a razão de
    `ler_historico` não guardar nada em memória.
    """
    # Primeiro arquivo.
    alvo = tmp_path / "historico.json"
    documento = _documento_valido()
    alvo.write_text(json.dumps(documento), encoding="utf-8")
    monkeypatch.setattr(mod_versao, "CAMINHO_PADRAO", str(alvo))
    assert client.get("/api/versao").json()["versao"] == "V9.9.3112"

    # Mesmo processo, arquivo trocado — sem reiniciar nada.
    documento["versao_app"] = "V9.9.0102"
    documento["ultima_atualizacao"]["data"] = "2027-01-02"
    alvo.write_text(json.dumps(documento), encoding="utf-8")
    corpo = client.get("/api/versao").json()
    assert corpo["versao"] == "V9.9.0102"
    assert corpo["data"] == "2027-01-02"


def test_arquivo_ausente_responde_503_com_motivo(client, monkeypatch, tmp_path):
    """Arquivo não publicado é falha de serviço, não do visitante: 503, com o caminho."""
    monkeypatch.setattr(mod_versao, "CAMINHO_PADRAO", str(tmp_path / "ausente.json"))
    resposta = client.get("/api/versao")
    assert resposta.status_code == 503
    assert "ausente.json" in resposta.json()["detail"]
