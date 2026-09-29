# -*- coding: utf-8 -*-
"""Testes do JSON de parâmetros de e-mail (`backend/parametros/email.json`).

Por que este arquivo existe: desde 29/09/2026 os dados de negócio do envio —
servidor, porta, usuário, remetente, dry-run, destinatários e e-mail de alerta —
moram no JSON, e o `.env` ficou só com o que não pode vazar. A troca de fonte tem
três riscos que só um teste segura: o JSON deixar de vencer o `.env`, a senha
começar a vir do JSON (que é versionado e legível), e a recarga por mtime parar de
funcionar — caso em que trocar um destinatário voltaria a exigir reinício.

Cada teste monta uma config falsa: nenhum deles lê o `.env` real nem o JSON real.
"""

# `json` escreve os arquivos temporários; `os` ajusta o mtime; `types` faz a config falsa.
import json
import os
import types

# Alvos do teste: a classe de mescla, o leitor com cache e a função de junção.
from backend.config import ParametrosEmail, ler_parametros_email, obter_parametros_email


def _config_falsa():
    """Config de `.env` falsa, com os mesmos atributos que a `Config` real expõe.

    Por que existe: os testes precisam de uma reserva conhecida para provar que o
    JSON vence — e usar a config real do processo tornaria o resultado dependente
    do `.env` da máquina de quem roda.

    Entrada: nenhuma.
    Saída: objeto com os atributos de e-mail preenchidos com valores reconhecíveis.
    """
    # `SimpleNamespace` basta: o código só lê atributos, nunca valida tipo.
    return types.SimpleNamespace(
        smtp_host="host-do-env",
        smtp_port=25,
        smtp_tls=False,
        smtp_user="user-do-env",
        smtp_pass="senha-do-env",
        smtp_from="from-do-env",
        smtp_dryrun=True,
        destinatarios="a@env.br,b@env.br",
        alerta_email="alerta-do-env",
    )


def _dados_json():
    """Dicionário equivalente ao `email.json` de produção."""
    # Mesma forma do arquivo real, com valores distintos dos do `.env`.
    return {
        "smtp": {"host": "smtp.office365.com", "porta": 587, "tls": True,
                 "usuario": "smtp@enbpar.gov.br", "remetente": "smtp@enbpar.gov.br",
                 "dryrun": False},
        "destinatarios": ["gestaolpt@enbpar.gov.br", "lais.brito@enbpar.gov.br"],
        "alerta": "alerta@enbpar.gov.br",
    }


def test_sem_json_tudo_vem_do_env():
    """JSON ausente (dicionário vazio) → a reserva do `.env` vale inteira."""
    # Fase 1: mescla sem dados nenhum do arquivo.
    p = ParametrosEmail(_config_falsa(), {})
    # Fase 2: cada campo veio do `.env`.
    assert p.smtp_host == "host-do-env"
    assert p.smtp_port == 25
    assert p.smtp_dryrun is True
    assert p.destinatarios == "a@env.br,b@env.br"
    assert p.alerta_email == "alerta-do-env"
    # A origem precisa dizer a verdade, porque o /api/health a publica.
    assert p.origem == "env"


def test_json_vence_o_env_campo_a_campo():
    """JSON presente → cada campo dele sobrescreve o do `.env`."""
    p = ParametrosEmail(_config_falsa(), _dados_json())
    assert p.smtp_host == "smtp.office365.com"
    assert p.smtp_port == 587
    assert p.smtp_tls is True
    assert p.smtp_user == "smtp@enbpar.gov.br"
    assert p.smtp_from == "smtp@enbpar.gov.br"
    # dry-run desligado no JSON tem de chegar desligado.
    assert p.smtp_dryrun is False
    assert p.alerta_email == "alerta@enbpar.gov.br"
    assert p.origem == "json"


def test_a_senha_nunca_vem_do_json():
    """Mesmo que alguém escreva uma senha no JSON, ela é ignorada."""
    # Um JSON malicioso/descuidado tentando injetar credencial.
    dados = _dados_json()
    dados["smtp"]["senha"] = "senha-que-nao-deve-valer"
    dados["smtp_pass"] = "outra-tentativa"
    p = ParametrosEmail(_config_falsa(), dados)
    # A senha continua sendo a do `.env`, que é o único lugar de segredo.
    assert p.smtp_pass == "senha-do-env"


def test_lista_de_destinatarios_normalizada():
    """Lista do JSON vira a mesma string separada por vírgula que o envio já divide."""
    dados = _dados_json()
    # Espaços sobrando e entradas vazias são o erro de digitação típico.
    dados["destinatarios"] = ["  um@enbpar.gov.br ", "", "   ", "dois@enbpar.gov.br"]
    p = ParametrosEmail(_config_falsa(), dados)
    assert p.destinatarios == "um@enbpar.gov.br,dois@enbpar.gov.br"


def test_json_parcial_mantem_o_resto_do_env():
    """Chave ausente no JSON não apaga o valor: cai para a reserva."""
    # Só o host foi definido no arquivo.
    p = ParametrosEmail(_config_falsa(), {"smtp": {"host": "so-o-host"}})
    assert p.smtp_host == "so-o-host"
    # O resto continua vindo do `.env`.
    assert p.smtp_port == 25
    assert p.smtp_user == "user-do-env"
    assert p.destinatarios == "a@env.br,b@env.br"


def test_arquivo_ausente_ou_quebrado_nao_estoura(tmp_path):
    """Falha fechada: sem arquivo, ou com JSON inválido, devolve vazio."""
    # Caminho que não existe.
    assert ler_parametros_email(tmp_path / "nao-existe.json") == {}
    # Arquivo com conteúdo que não é JSON.
    quebrado = tmp_path / "quebrado.json"
    quebrado.write_text("{isto nao e json", encoding="utf-8")
    assert ler_parametros_email(quebrado) == {}
    # JSON válido mas que não é objeto (uma lista, por exemplo).
    lista = tmp_path / "lista.json"
    lista.write_text("[1, 2, 3]", encoding="utf-8")
    assert ler_parametros_email(lista) == {}


def test_recarrega_quando_o_arquivo_muda(tmp_path):
    """Editar o arquivo vale sem reiniciar — é o ganho operacional da mudança."""
    alvo = tmp_path / "email.json"
    # Fase 1: primeira versão, lida e cacheada.
    alvo.write_text(json.dumps({"alerta": "antes@enbpar.gov.br"}), encoding="utf-8")
    assert ler_parametros_email(alvo)["alerta"] == "antes@enbpar.gov.br"
    # Fase 2: reescreve e força um mtime diferente (no Windows a resolução é grossa).
    alvo.write_text(json.dumps({"alerta": "depois@enbpar.gov.br"}), encoding="utf-8")
    carimbo = alvo.stat().st_mtime + 5
    os.utime(alvo, (carimbo, carimbo))
    # Fase 3: a leitura seguinte já traz o valor novo, sem reiniciar nada.
    assert ler_parametros_email(alvo)["alerta"] == "depois@enbpar.gov.br"


def test_config_injetada_ignora_o_json(tmp_path):
    """Config passada explicitamente vence: é como os testes isolam o disco."""
    alvo = tmp_path / "email.json"
    alvo.write_text(json.dumps(_dados_json()), encoding="utf-8")
    falsa = _config_falsa()
    # Mesmo com um arquivo válido no caminho, a config injetada volta intacta.
    devolvida = obter_parametros_email(falsa, alvo)
    assert devolvida is falsa
    assert devolvida.smtp_host == "host-do-env"
