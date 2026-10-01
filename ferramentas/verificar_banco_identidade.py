# -*- coding: utf-8 -*-
"""Inspeciona, SÓ LEITURA, o MySQL `db_lpt` antes do merge do login por e-mail.

Por que este arquivo existe: o subsistema de identidade vai passar a usar o
`db_lpt`, que é um banco **compartilhado** ("geral"), e três perguntas precisam
de resposta ANTES de qualquer rota de identidade ser chamada em produção —
porque `obter_engine` hoje cria tabela sozinho na primeira chamada, e não há
terminal na VM para desfazer:

  1. As tabelas `usuario`, `convite` e `evento` já existem? Com QUAIS colunas?
     (Se existirem de OUTRO sistema, `create_all(checkfirst=True)` não cria, não
     avisa, e os repositórios passam a gravar na tabela alheia.)
  2. O usuário `usr_lpt` tem permissão de criar tabela? (Se não tiver, as rotas
     de identidade respondem 500 sem explicação na tela.)
  3. Já existe alguém com perfil `gerente`? (Sem gerente, ninguém promove
     ninguém: só esse perfil tem a ação `alterar_perfil`.)

E uma quarta, que o Azure impõe: a conexão sai cifrada de verdade? O servidor
está com `ssl-mode=require`, e este script mostra a cifra negociada, medindo o
mesmo caminho que o app usa (PyMySQL em modo PREFERRED).

⚠️ **Este script não escreve nada.** Não há CREATE, INSERT, UPDATE nem DELETE, e
ele nunca imprime a senha, nem hash de senha de ninguém.

Entrada: a senha de `usr_lpt`, digitada no prompt (não fica no histórico).
Fase 1: conecta, cifrado, e prova a cifra.
Fase 2: lista as tabelas do banco e separa as três nossas das alheias.
Fase 3: compara coluna por coluna o que existe com o que o código declara.
Fase 4: lê as permissões do usuário.
Fase 5: se `usuario` existir, lista quem está lá e com que perfil.
Saída: um veredito por pergunta, no terminal.

Como rodar, da raiz deste repositório (não precisa instalar nada):
    uv run --no-project --python 3.12 --with pymysql python minhas_notas\verificar_banco_identidade.py
"""

# `getpass` lê a senha sem ecoar na tela nem gravar no histórico do PowerShell.
import getpass
# `sys` só para sair com código de erro quando a conexão não acontece.
import sys

# `pymysql` é o MESMO driver que o container usa (o SQLAlchemy só monta o SQL).
import pymysql

# --- dados do servidor, informados pela TI em 28/09/2026 (não são segredo) ---
# Endereço do MySQL gerenciado do Azure.
HOST = "lpt-mysql-geral-prd-brs.mysql.database.azure.com"
# Porta padrão do MySQL.
PORTA = 3306
# Banco (schema) onde o subsistema de identidade vai viver.
BANCO = "db_lpt"
# Usuário da aplicação.
USUARIO = "usr_lpt"

# --- o que o código declara em backend/identidade/infra/tabelas.py ---
# Fonte da verdade do schema esperado; divergência aqui é sinal de tabela alheia.
ESPERADO = {
    "usuario": ["id", "email", "perfil", "siglas", "senha_hash", "salt",
                "ativo", "criado_em", "atualizado_em"],
    "convite": ["id", "email", "token_hash", "perfil", "expira_em",
                "usado_em", "criado_em"],
    "evento": ["id", "quando", "ator", "tipo", "alvo", "detalhe"],
}


def main():
    """Roda a inspeção inteira e imprime o veredito.

    Por que é uma função só: o script é linear por natureza — cada fase depende
    da conexão aberta na anterior —, e quebrá-lo em funções que apenas passam o
    cursor adiante acrescentaria indireção sem tornar nada testável.

    Entrada: nenhuma (a senha vem do prompt).
    Fase 1: conecta e prova a cifra.
    Fase 2: lista tabelas.
    Fase 3: compara colunas.
    Fase 4: lê permissões.
    Fase 5: lista usuários e perfis.
    Saída: None (imprime).
    """

    # Fase 1: pede a senha e conecta.
    # `ssl={}` é exatamente o que `bd.opcoes_de` passa: em PyMySQL isso cai no
    # modo PREFERRED — tenta TLS e só aceitaria texto claro se o servidor não
    # oferecesse cifra. O Azure oferece e exige, então a sessão sai cifrada.
    senha = getpass.getpass("Senha de %s (nao aparece na tela): " % USUARIO)
    # Tenta abrir a conexão; erro de rede/firewall morre aqui com mensagem própria.
    try:
        conexao = pymysql.connect(host=HOST, port=PORTA, user=USUARIO,
                                  password=senha, database=BANCO, ssl={})
    # Qualquer falha de conexão: relata e sai, sem stack trace ilegível.
    except Exception as erro:
        print("\n[FALHOU A CONEXAO] %s: %s" % (type(erro).__name__, erro))
        print("  Se for 2003/timeout, o firewall do MySQL nao libera o SEU IP —")
        print("  peca a TI uma regra para o seu endereco, ou rode de dentro da VM.")
        print("  Se for 1045, a senha ou o usuario estao errados.")
        sys.exit(1)

    # A partir daqui há conexão; o `finally` garante que ela feche.
    try:
        # Cursor único para todas as consultas (todas de leitura).
        cursor = conexao.cursor()

        # Prova da cifra: `Ssl_cipher` vazio significaria sessão em texto claro.
        cursor.execute("SHOW STATUS LIKE 'Ssl_cipher'")
        cifra = (cursor.fetchone() or ("", ""))[1]
        print("\n=== 1. Conexao")
        print("  servidor: %s:%s  banco: %s  usuario: %s" % (HOST, PORTA, BANCO, USUARIO))
        # Mostra a cifra negociada, ou avisa alto se não houver nenhuma.
        print("  cifra TLS: %s" % (cifra or "*** NENHUMA — sessao em texto claro! ***"))

        # Fase 2: todas as tabelas do banco, para ver o que mais mora aqui.
        cursor.execute("SHOW TABLES")
        # Cada linha vem como tupla de um elemento.
        tabelas = sorted(linha[0] for linha in cursor.fetchall())
        # Separa as nossas três das demais.
        nossas = [t for t in tabelas if t in ESPERADO]
        alheias = [t for t in tabelas if t not in ESPERADO]
        print("\n=== 2. Tabelas em %s (%d no total)" % (BANCO, len(tabelas)))
        print("  nossas presentes: %s" % (nossas or "nenhuma"))
        print("  outras: %s" % (", ".join(alheias) if alheias else "nenhuma"))
        # Diz explicitamente quais das três faltam.
        faltando = [t for t in ESPERADO if t not in tabelas]
        print("  nossas AUSENTES: %s" % (faltando or "nenhuma — as tres existem"))

        # Fase 3: compara coluna por coluna o que existe.
        print("\n=== 3. Colunas (o que existe x o que o codigo declara)")
        # Percorre só as que existem; as ausentes já foram relatadas.
        for tabela in nossas:
            # `DESCRIBE` devolve uma linha por coluna; o nome é o primeiro campo.
            cursor.execute("DESCRIBE `%s`" % tabela)
            reais = [linha[0] for linha in cursor.fetchall()]
            # Colunas que o código espera e o banco não tem: quebra na primeira query.
            sem = [c for c in ESPERADO[tabela] if c not in reais]
            # Colunas a mais: sinal forte de tabela de outro sistema.
            extra = [c for c in reais if c not in ESPERADO[tabela]]
            # Contagem de linhas, para saber se a tabela já tem dado de gente.
            cursor.execute("SELECT COUNT(*) FROM `%s`" % tabela)
            quantas = cursor.fetchone()[0]
            print("  %-8s %d linha(s) | faltando: %s | a mais: %s"
                  % (tabela, quantas, sem or "-", extra or "-"))

        # Fase 4: permissões — decide se o `create_all` conseguiria criar tabela.
        print("\n=== 4. Permissoes de %s" % USUARIO)
        cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
        # Junta as linhas de GRANT como vieram.
        concessoes = [linha[0] for linha in cursor.fetchall()]
        # Imprime cada uma.
        for linha in concessoes:
            print("  %s" % linha)
        # Resposta direta à pergunta que importa.
        tem_create = any("ALL PRIVILEGES" in c or "CREATE" in c for c in concessoes)
        print("  -> pode criar tabela: %s" % ("SIM" if tem_create else "NAO"))

        # Fase 5: quem já está cadastrado, e com que perfil.
        print("\n=== 5. Usuarios ja cadastrados")
        # Só faz sentido se a tabela existir.
        if "usuario" in nossas:
            # ⚠️ Nunca seleciona senha_hash nem salt.
            cursor.execute("SELECT email, perfil, ativo, criado_em FROM usuario "
                           "ORDER BY criado_em")
            linhas = cursor.fetchall()
            # Sem ninguém, o impasse do primeiro gerente está de pé.
            if not linhas:
                print("  (vazia)")
            # Com gente, lista cada um.
            for email, perfil, ativo, criado in linhas:
                print("  %-40s %-16s ativo=%s  %s" % (email, perfil, ativo, criado))
            # Destaca a resposta da pergunta 3.
            gerentes = [l[0] for l in linhas if l[1] == "gerente"]
            print("  -> gerente(s): %s" % (gerentes or "NENHUM — ninguem promove ninguem"))
        # Tabela ausente: a pergunta fica sem resposta, e isso é a resposta.
        else:
            print("  tabela `usuario` nao existe — nada cadastrado ainda")

    # Fecha a conexão em qualquer desfecho.
    finally:
        conexao.close()

    # Fecha o relatório lembrando o que este script NÃO fez.
    print("\n(nada foi escrito: sem CREATE, INSERT, UPDATE ou DELETE)")


# Executa só quando chamado como script.
if __name__ == "__main__":
    main()
