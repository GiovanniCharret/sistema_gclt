# -*- coding: utf-8 -*-
"""Confere o `historico.json` e gera o `HISTORICO.md` a partir dele.

Por que este arquivo existe: o `historico.json` é a fonte única da história do projeto, e é
editado à mão. Três coisas precisam acontecer depois de cada edição, e nenhuma delas pode
depender de memória: (1) conferir se o arquivo continua válido — datas no formato certo, id
sem repetição, tipo conhecido; (2) recalcular os campos derivados, que são os que o rodapé
do site lê (`ultima_atualizacao`, `versao_app`, `contadores`); (3) reescrever a versão
legível por gente (`HISTORICO.md`), para não existirem duas histórias divergindo.

A alternativa — manter o `.md` à mão ao lado do `.json` — garante divergência: alguém
atualiza um e esquece o outro. Aqui o `.md` é **gerado**, nunca editado.

Como usar, da raiz do repositório (ou de dentro de `controle_versao/`):

    python controle_versao/atualizar.py            # confere, recalcula e gera o .md
    python controle_versao/atualizar.py --conferir # só confere, não grava nada

Entrada: `controle_versao/historico.json`.
Fase 1: lê o JSON e acusa erro de estrutura, sem gravar nada.
Fase 2: recalcula `ultima_atualizacao`, `versao_app` e `contadores` a partir das sub-fases.
Fase 3: regrava o JSON (só se algo derivado mudou) e escreve o `HISTORICO.md`.
Saída: relatório no terminal, dizendo o que mudou.
"""

# `io` grava sem o Python traduzir quebra de linha; `json` lê e escreve o arquivo de dados.
import io
import json
# `os` monta caminhos independentes de sistema operacional; `sys` dá o código de saída.
import os
import sys

# A pasta deste script é a pasta do controle de versão — assim ele funciona de qualquer lugar.
PASTA = os.path.dirname(os.path.abspath(__file__))
# Os dois arquivos que importam: a fonte e o documento gerado.
JSON = os.path.join(PASTA, "historico.json")
MARKDOWN = os.path.join(PASTA, "HISTORICO.md")

# Tipos aceitos numa sub-fase. Qualquer outro valor é erro, para o vocabulário não inflar
# sozinho com sinônimos ("bugfix", "fix", "correção"...) que depois ninguém sabe filtrar.
TIPOS = ("entrega", "decisao", "correcao", "incidente", "seguranca", "infra", "dados")
# Estados aceitos numa fase.
ESTADOS = ("concluida", "em_andamento", "planejada")
# Rótulos que vão para o `.md` — o JSON guarda o código, o documento mostra a palavra.
ROTULO = {
    "entrega": "Entrega", "decisao": "Decisão", "correcao": "Correção",
    "incidente": "Incidente", "seguranca": "Segurança", "infra": "Infraestrutura",
    "dados": "Dados",
}
# Mesma ideia para o estado da fase.
ROTULO_ESTADO = {
    "concluida": "concluída", "em_andamento": "em andamento", "planejada": "planejada",
}


def ler():
    """Lê o JSON e devolve o documento, ou morre explicando.

    Por que separada: é o único ponto que toca o disco para leitura, e um JSON quebrado tem
    de produzir uma frase útil em vez de um rastro de pilha.

    Entrada: nenhuma (usa a constante `JSON`).
    Fase 1: confere que o arquivo existe.
    Fase 2: tenta interpretar o JSON.
    Saída: o dicionário do documento.
    """
    # Fase 1: sem arquivo não há o que conferir.
    if not os.path.isfile(JSON):
        print("ERRO: não encontrei %s" % JSON)
        sys.exit(1)
    # Fase 2/Saída: vírgula sobrando é o erro mais comum ao editar à mão — diga a linha.
    try:
        with io.open(JSON, encoding="utf-8") as arq:
            return json.load(arq)
    except ValueError as erro:
        print("ERRO: o historico.json não é um JSON válido — %s" % erro)
        sys.exit(1)


def conferir(doc):
    """Valida a estrutura e devolve a lista de problemas (vazia = tudo certo).

    Por que existe: o arquivo é editado à mão, e um erro de digitação silencioso aqui vira
    data errada no rodapé do site. É mais barato recusar agora do que descobrir depois.

    Entrada: o documento já lido.
    Fase 1: confere as chaves de topo.
    Fase 2: percorre fases e sub-fases, acumulando problemas (não para no primeiro).
    Saída: lista de strings descrevendo cada problema.
    """
    # Fase 1: o mínimo que o resto do código pressupõe.
    problemas = []
    for chave in ("esquema", "produto", "fases"):
        if chave not in doc:
            problemas.append("falta a chave de topo '%s'" % chave)
    if problemas:
        return problemas

    # Fase 2: cada fase e cada sub-fase, acumulando tudo o que estiver torto.
    vistos = set()
    for fase in doc["fases"]:
        onde = "fase %s" % fase.get("id", "(sem id)")
        for chave in ("id", "nome", "estado", "subfases"):
            if chave not in fase:
                problemas.append("%s: falta '%s'" % (onde, chave))
        if fase.get("estado") not in ESTADOS:
            problemas.append("%s: estado '%s' não é um de %s"
                             % (onde, fase.get("estado"), ", ".join(ESTADOS)))
        for sub in fase.get("subfases", []):
            alvo = "sub-fase %s" % sub.get("id", "(sem id)")
            for chave in ("id", "data", "tipo", "titulo", "resumo"):
                if chave not in sub:
                    problemas.append("%s: falta '%s'" % (alvo, chave))
            # Id repetido estraga qualquer referência cruzada e a ordenação.
            if sub.get("id") in vistos:
                problemas.append("%s: id repetido" % alvo)
            vistos.add(sub.get("id"))
            # Data: só o formato AAAA-MM-DD ordena corretamente como texto.
            data = sub.get("data", "")
            if len(data) != 10 or data[4] != "-" or data[7] != "-":
                problemas.append("%s: data '%s' fora do formato AAAA-MM-DD" % (alvo, data))
            if sub.get("tipo") not in TIPOS:
                problemas.append("%s: tipo '%s' não é um de %s"
                                 % (alvo, sub.get("tipo"), ", ".join(TIPOS)))
    # Saída: a lista (vazia se nada estiver errado).
    return problemas


def derivar(doc):
    """Recalcula os campos que o rodapé do site lê, e diz se algo mudou.

    Por que existe: `ultima_atualizacao`, `versao_app` e `contadores` são **consequência**
    das sub-fases. Mantidos à mão, envelhecem calados — e o rodapé passaria a exibir uma
    data que não corresponde à última entrada, que é exatamente o erro que este controle
    de versão existe para não cometer.

    Entrada: o documento.
    Fase 1: junta todas as sub-fases e ordena por data (e por id, no empate do mesmo dia).
    Fase 2: monta os três blocos derivados.
    Fase 3: compara com o que estava escrito.
    Saída: (documento atualizado, lista de campos que mudaram).
    """
    # Fase 1: todas as sub-fases, com a fase de origem ao lado.
    todas = [(s["data"], f["id"], s) for f in doc["fases"] for s in f["subfases"]]
    if not todas:
        return doc, []
    # Ordenação textual funciona porque a data está em AAAA-MM-DD.
    todas.sort(key=lambda t: (t[0], t[2]["id"]))
    data_ult, fase_ult, sub_ult = todas[-1]

    # Fase 2: a versão exibida segue o padrão já usado no site: V<produto>.<marco>.<MMDD>.
    # Os dois primeiros números são decisão humana (marco de produto) e são preservados;
    # só o sufixo de data é recalculado.
    anterior = doc.get("versao_app", "V0.0.0000")
    prefixo = ".".join(anterior.split(".")[:2]) if anterior.count(".") >= 2 else "V0.0"
    novos = {
        "versao_app": "%s.%s%s" % (prefixo, data_ult[5:7], data_ult[8:10]),
        "ultima_atualizacao": {
            "data": data_ult,
            "fase": fase_ult,
            "subfase": sub_ult["id"],
            "titulo": sub_ult["titulo"],
            "resumo": sub_ult["resumo"],
        },
        "contadores": {
            "fases": len(doc["fases"]),
            "subfases": len(todas),
            "primeira_data": todas[0][0],
            "ultima_data": data_ult,
        },
    }

    # Fase 3/Saída: o que mudou, para o relatório dizer e para não regravar sem motivo.
    mudou = [chave for chave, valor in novos.items() if doc.get(chave) != valor]
    doc.update(novos)
    return doc, mudou


def escrever_markdown(doc):
    """Gera o HISTORICO.md: a mesma história, para ler sem abrir JSON.

    Por que existe: o JSON é para a máquina (o rodapé e, no futuro, a página de evolução);
    uma pessoa que queira entender o projeto não deve precisar ler chaves e colchetes.
    Como é **gerado**, nunca divergirá da fonte.

    Entrada: o documento já conferido e com os derivados em dia.
    Fase 1: escreve o cabeçalho com o estado atual.
    Fase 2: escreve uma seção por fase, com uma tabela de sub-fases.
    Fase 3: grava em UTF-8 com LF.
    Saída: o número de linhas escritas.
    """
    # Fase 1: cabeçalho — o que alguém quer saber nos primeiros cinco segundos.
    p, u, c = doc["produto"], doc["ultima_atualizacao"], doc["contadores"]
    linhas = [
        "# Histórico do projeto — %s" % p["nome"],
        "",
        "> ⚠️ **Arquivo gerado.** Não edite este `.md`: edite o `historico.json` e rode",
        "> `python controle_versao/atualizar.py`. O que estiver escrito aqui à mão será perdido.",
        "",
        "%s · %s" % (p["subtitulo"], p["orgao"]),
        "",
        "| | |",
        "|---|---|",
        "| Versão exibida no rodapé | **%s** |" % doc["versao_app"],
        "| Última atualização | **%s** — %s (%s) |" % (u["data"], u["titulo"], u["subfase"]),
        "| Período coberto | %s a %s |" % (c["primeira_data"], c["ultima_data"]),
        "| Tamanho | %d fases, %d sub-fases |" % (c["fases"], c["subfases"]),
        "| Produção | %s |" % p["producao"],
        "",
        "## Como ler",
        "",
        "Cada **fase** é um trecho da história com um tema próprio; cada **sub-fase** é um fato",
        "datado dentro dela. O rótulo diz de que tipo é o fato:",
        "",
    ]
    # Legenda dos tipos, na ordem fixa de `TIPOS` (não na ordem do dicionário).
    for tipo in TIPOS:
        if tipo in doc.get("legenda_tipos", {}):
            linhas.append("- **%s** — %s" % (ROTULO[tipo], doc["legenda_tipos"][tipo]))
    linhas.append("")

    # Fase 2: uma seção por fase, da mais antiga para a mais nova.
    for fase in doc["fases"]:
        periodo = fase.get("periodo") or {}
        inicio, fim = periodo.get("inicio", "?"), periodo.get("fim")
        # Fase sem fim é fase aberta — dizer "em aberto" é mais honesto que repetir a data.
        janela = "%s a %s" % (inicio, fim) if fim else "%s — em aberto" % inicio
        linhas += [
            "## %s — %s" % (fase["id"], fase["nome"]),
            "",
            "*%s · %s*" % (janela, ROTULO_ESTADO.get(fase["estado"], fase["estado"])),
            "",
            fase.get("resumo", ""),
            "",
            "| Data | Tipo | O que aconteceu |",
            "|---|---|---|",
        ]
        for sub in fase["subfases"]:
            # O impacto, quando existe, entra na mesma célula em itálico: é a consequência
            # prática do fato, e separá-lo em coluna própria deixaria a tabela quase vazia.
            texto = "**%s** — %s" % (sub["titulo"], sub["resumo"])
            if sub.get("impacto"):
                texto += " *%s*" % sub["impacto"]
            # A barra vertical quebraria a tabela do Markdown.
            texto = texto.replace("|", "\\|")
            linhas.append("| %s | %s | %s |" % (sub["data"], ROTULO.get(sub["tipo"], sub["tipo"]), texto))
        linhas.append("")

    # Fase 3/Saída: grava com LF, como todo texto deste repositório.
    with io.open(MARKDOWN, "w", encoding="utf-8", newline="\n") as arq:
        arq.write("\n".join(linhas))
    return len(linhas)


def main():
    """Encadeia conferir → derivar → gravar, respeitando `--conferir`."""
    # Modo somente-leitura: útil para rodar antes de um commit sem alterar arquivo.
    so_conferir = "--conferir" in sys.argv
    doc = ler()

    # Fase 1: estrutura. Problema aqui aborta antes de qualquer gravação.
    problemas = conferir(doc)
    if problemas:
        print("historico.json INVÁLIDO — nada foi gravado:")
        for item in problemas:
            print("  - %s" % item)
        sys.exit(1)
    print("historico.json válido: %d fases, %d sub-fases"
          % (len(doc["fases"]), sum(len(f["subfases"]) for f in doc["fases"])))

    # Fase 2: derivados.
    doc, mudou = derivar(doc)
    if mudou:
        print("campos derivados recalculados: %s" % ", ".join(sorted(mudou)))
    else:
        print("campos derivados já estavam em dia")

    if so_conferir:
        print("(--conferir: nada gravado)")
        return

    # Fase 3: grava o JSON só se algo mudou, e sempre regera o .md.
    if mudou:
        with io.open(JSON, "w", encoding="utf-8", newline="\n") as arq:
            json.dump(doc, arq, ensure_ascii=False, indent=2)
            arq.write("\n")
        print("ok  historico.json regravado")
    print("ok  HISTORICO.md gerado (%d linhas)" % escrever_markdown(doc))
    print("    rodapé deve exibir: %s (última: %s)"
          % (doc["versao_app"], doc["ultima_atualizacao"]["data"]))


# Só roda quando chamado direto — assim o arquivo pode ser importado por um teste.
if __name__ == "__main__":
    main()
