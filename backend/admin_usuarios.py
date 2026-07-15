"""CLI de provisionamento de usuários (`python -m backend.admin_usuarios`) — Bloco B1.

Por que existe: não há tela web de admin (§2, YAGNI); o administrador cria e desativa
usuários por linha de comando. Ao **criar**, o sistema gera uma senha temporária e a
**imprime no terminal** (fallback temporário 2026-07-15: o login por e-mail — e portanto
o envio da senha por e-mail — foi adiado p/ V1/V2), para o admin repassá-la ao operador,
que deverá trocá-la no 1º acesso.

Uso:
    python -m backend.admin_usuarios add     equatorialenergia
    python -m backend.admin_usuarios disable equatorialenergia

Design testável: a lógica fica em `executar(argv, caminho)` (retorna o código de saída),
para os testes rodarem a CLI sem `sys.argv`/processo e apontando o store para um
diretório temporário.
"""

# `argparse` interpreta os subcomandos e argumentos da linha de comando.
import argparse
# `sys` fornece os argumentos reais e o código de saída no `main`.
import sys

# CRUD do store de usuários (criar com senha temporária, desativar).
from backend.auth import criar_usuario, desativar_usuario


def _montar_parser():
    """Monta o parser de argumentos com os subcomandos `add` e `disable`.

    Entrada: nenhuma.
    Fase 1: cria o parser e o grupo de subcomandos.
    Fase 2: registra `add <email>` e `disable <email>`.
    Saída: o `ArgumentParser` configurado.
    """
    # Fase 1: parser raiz + subcomandos obrigatórios.
    parser = argparse.ArgumentParser(prog="admin_usuarios",
                                     description="Provisionamento de usuários do sistema.")
    sub = parser.add_subparsers(dest="comando", required=True)
    # Fase 2: `add <operador>` — cria usuário e imprime a senha temporária.
    p_add = sub.add_parser("add", help="cria usuário e imprime a senha temporária")
    p_add.add_argument("operador", help="operador (login) do usuário")
    # `disable <operador>` — desativa usuário.
    p_dis = sub.add_parser("disable", help="desativa um usuário existente")
    p_dis.add_argument("operador", help="operador (login) do usuário")
    # Saída: parser pronto.
    return parser


def executar(argv, caminho=None):
    """Executa a CLI a partir de uma lista de argumentos (entrypoint testável).

    Entrada: `argv` (lista de args, ex.: `["add", "x@y.com"]`) e `caminho` (store
             opcional; None usa o `usuarios.json` real).
    Fase 1: interpreta os argumentos.
    Fase 2 (add): cria o usuário (senha temporária) e envia o e-mail de credenciais.
    Fase 2 (disable): desativa o usuário (erro se não existir).
    Saída: código de saída (0 sucesso, 1 falha).
    """
    # Fase 1: parseia os argumentos recebidos.
    args = _montar_parser().parse_args(argv)
    # Fase 2 (add): provisiona e imprime a senha temporária (sem e-mail no fallback).
    if args.comando == "add":
        # Cria o usuário; recebe o registro e a senha temporária em texto.
        registro, senha = criar_usuario(args.operador, caminho=caminho)
        # Imprime o operador CANÔNICO gravado + a senha, para o admin repassar.
        print(f"Operador criado: {registro['operador']} — senha temporária: {senha}")
        print("Repasse a senha ao operador; ele deverá trocá-la no 1º acesso.")
        # Sucesso.
        return 0
    # Fase 2 (disable): desativa; sinaliza se o usuário não existe.
    if args.comando == "disable":
        # Tenta desativar; retorna False se o operador não existir.
        ok = desativar_usuario(args.operador, caminho=caminho)
        if ok:
            print(f"Operador desativado: {args.operador}.")
            return 0
        # Usuário inexistente → erro.
        print(f"Operador não encontrado: {args.operador}.")
        return 1
    # Saída: comando desconhecido (não deve ocorrer — subcomando é obrigatório).
    return 1


def main():
    """Ponto de entrada real da CLI (usa `sys.argv` e encerra com o código de saída).

    Entrada: argumentos do processo.
    Fase 1: executa a CLI com os argumentos reais.
    Saída: encerra o processo com o código retornado.
    """
    # Fase 1/Saída: roda e propaga o código de saída ao SO.
    sys.exit(executar(sys.argv[1:]))


# Permite `python -m backend.admin_usuarios ...`.
if __name__ == "__main__":
    main()
