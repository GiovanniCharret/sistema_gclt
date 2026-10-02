# -*- coding: utf-8 -*-
"""Leitura do histórico de versões do produto (`controle_versao/historico.json`).

Por que este módulo existe: o rodapé do site precisa mostrar a versão e a data da última
atualização, e até 02/10/2026 esse dado era uma **constante escrita no código do front**
(`VERSAO_APP` em `App.jsx`). Isso significava que a versão exibida só mudava se alguém
lembrasse de editar a constante — e ela ficou quase dois meses parada em `V0.0.0804`,
exatamente o problema que o rodapé existia para resolver. Aqui o dado passa a vir do
arquivo que já é a fonte única da história do projeto, lido do disco **a cada pedido**:
editar o JSON e publicar vale na requisição seguinte, sem reconstruir o site.

Por que separado do `app.py`: o `app.py` orquestra rotas; ler e recortar arquivo é camada,
e camada se testa sem subir servidor — é a mesma divisão que `planilha.py` e `referencia.py`
já seguem.

⚠️ **Dois recortes do mesmo arquivo, de propósito.** O histórico completo narra incidentes
de produção e traz uma entrada que **descreve um risco aceito** (o "esqueci minha senha"
antigo, que reinicia a senha de um operador sem autenticação). Isso é material interno: numa
rota pública seria um roteiro pronto para quem quisesse abusar. Então:

- `resumo_publico` devolve **só** a versão, a data e o esquema — o que o rodapé precisa, e
  nada que descreva o sistema por dentro;
- o documento inteiro só sai por rota protegida, para a futura página de evolução.

Lógica (Entrada → Saída):
    Entrada: o caminho do JSON (ou o padrão do repositório).
    Fase 1: `ler_historico` lê o arquivo e recusa o que não serve, com motivo.
    Fase 2: `resumo_publico` recorta o mínimo exibível.
    Saída: dicionários prontos para virar JSON de resposta.
"""

# `io` abre o arquivo declarando a codificação, sem depender da do sistema.
import io
# `json` interpreta o conteúdo.
import json
# `pathlib` monta o caminho padrão de forma independente de sistema operacional.
import pathlib

# Caminho padrão, relativo à raiz do repositório — o backend sempre roda a partir dela
# (`uvicorn backend.app:app` na raiz), mesma premissa de `config.py` e `planilha.py`.
CAMINHO_PADRAO = "controle_versao/historico.json"


class HistoricoIndisponivel(Exception):
    """Levantada quando o histórico não pode ser lido, com o motivo na mensagem.

    Por que uma exceção própria: quem chama (o `app.py`) precisa distinguir "o arquivo não
    está lá" de um erro de programação, para responder um status honesto em vez de 500. A
    mensagem é escrita para aparecer na tela de quem opera o sistema.
    """


def ler_historico(caminho=None):
    """Lê o `historico.json` do disco e devolve o documento inteiro.

    Por que existe: concentra num lugar só a leitura e as três maneiras de o arquivo não
    servir — ausente, ilegível e com JSON quebrado. Sem isso, cada rota repetiria o
    tratamento e alguma esqueceria uma delas.

    ⚠️ **Lê a cada chamada, sem cache.** É decisão deliberada: o arquivo tem poucas dezenas
    de quilobytes e esta rota é chamada uma vez por carregamento de tela, então guardar em
    memória economizaria quase nada e criaria a pergunta "por que a tela não atualizou?".
    Ler sempre garante que publicar um JSON novo vale na requisição seguinte.

    Entrada: `caminho` (str/Path; `None` usa `CAMINHO_PADRAO`).
    Fase 1: resolve o caminho e confere que existe um arquivo ali.
    Fase 2: lê e interpreta o JSON, traduzindo falha em `HistoricoIndisponivel`.
    Fase 3: confere o mínimo que as duas rotas pressupõem.
    Saída: o dicionário do documento.
    """
    # Fase 1: sem arquivo não há o que responder — e dizer qual caminho foi procurado
    # economiza uma investigação inteira em produção, onde não há terminal.
    alvo = pathlib.Path(caminho or CAMINHO_PADRAO)
    if not alvo.is_file():
        raise HistoricoIndisponivel(
            "histórico de versões não encontrado no servidor (%s)" % alvo.as_posix())

    # Fase 2: leitura. JSON quebrado é erro de edição à mão, não defeito do sistema:
    # a mensagem tem de dizer isso, em vez de estourar como falha interna.
    try:
        with io.open(alvo, encoding="utf-8") as arquivo:
            documento = json.load(arquivo)
    except ValueError as erro:
        raise HistoricoIndisponivel(
            "histórico de versões com JSON inválido (%s)" % erro)
    except OSError as erro:
        raise HistoricoIndisponivel(
            "histórico de versões ilegível (%s)" % type(erro).__name__)

    # Fase 3: o contrato mínimo. Um arquivo válido como JSON mas sem estes campos
    # faria a rota devolver `null` para o rodapé, que é pior do que recusar com motivo.
    if not isinstance(documento, dict) or "versao_app" not in documento:
        raise HistoricoIndisponivel(
            "histórico de versões sem o campo 'versao_app'")

    # Saída: o documento como está no disco.
    return documento


def resumo_publico(documento):
    """Recorta do documento só o que pode aparecer sem autenticação.

    Por que existe: é a fronteira entre o que o rodapé precisa e o que o histórico conta. O
    documento inteiro narra incidentes e riscos aceitos — material que descreve o sistema
    por dentro. O rodapé precisa de duas informações: **qual versão** está no ar e **de
    quando** ela é.

    ⚠️ Nada de `titulo`, `resumo` ou `fases` sai aqui, e isso é a regra, não economia de
    bytes: o rodapé aparece **na tela de login**, antes de qualquer autenticação, então tudo
    o que ele mostra é público para a internet inteira.

    Entrada: o documento já lido por `ler_historico`.
    Fase 1: pega a versão exibível.
    Fase 2: pega a data da última atualização, tolerando documento sem esse bloco.
    Saída: dicionário com `versao`, `data` e `esquema`.
    """
    # Fase 1: a versão que o rodapé escreve (ex.: "V0.0.1002").
    versao = documento.get("versao_app")
    # Fase 2: a data da última entrada. O bloco é derivado e sempre existe em arquivo
    # gerado pela ferramenta, mas um arquivo editado à mão pode não tê-lo — daí o `or {}`.
    ultima = documento.get("ultima_atualizacao") or {}
    # Saída: o `esquema` acompanha para o front saber se entende o formato que recebeu.
    return {
        "versao": versao,
        "data": ultima.get("data"),
        "esquema": documento.get("esquema"),
    }
