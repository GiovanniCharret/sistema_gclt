# ferramentas/

Ferramentas de diagnóstico **reutilizáveis**, versionadas de propósito: elas ganham histórico e
sobrevivem à máquina. Este repositório **não deploya nada** — a produção sai de
`enbpar/enbpar-sistema-gclt` —, então nada daqui alcança um servidor.

## Regras desta pasta

1. **Só entra o que se usa mais de uma vez.** Script de migração, de uso único, é descartável:
   roda, a mudança é commitada, e o script é apagado. O raciocínio dele fica na mensagem do
   commit e no `planning/PLAN.md`, que é onde alguém vai procurar.
2. **Nenhum segredo, nunca.** Senha se pede por `getpass`, no momento do uso, ou se lê de um
   arquivo gitignorado. Endereço, porta e nome de usuário podem ficar: não são credencial.
3. **Leitura por padrão.** Uma ferramenta que escreve precisa dizer isso no próprio docstring,
   na primeira linha.

## O que há aqui

| Arquivo | O que faz |
|---|---|
| `verificar_banco_identidade.py` | Inspeciona o MySQL `db_lpt` — tabelas, colunas, permissões, perfis e a cifra TLS negociada. **Só leitura**: nenhum `CREATE`, `INSERT`, `UPDATE` ou `DELETE`. Pede a senha no prompt. |
| `testar_smtp_enbpar.py` | Envia um e-mail de teste pelo mesmo caminho que o backend usa, para separar "o código não envia" de "o servidor não aceita". Pede a senha e o destino no prompt. |

Rodar da raiz do repositório, por exemplo:

```bash
uv run --no-project --python 3.12 --with pymysql python ferramentas\verificar_banco_identidade.py
```
