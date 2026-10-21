"""Bases territoriais georreferenciadas de `entrada/`: quilombolas (INCRA) e TIs (FUNAI).

Por que este módulo existe: duas regras de validação precisam responder "esta coordenada está
dentro de um território reconhecido?" — e essa pergunta exige geometria, que nada no projeto
tinha. O módulo isola três coisas que não cabem em `validacao.py`: ler shapefile, guardar
polígono em memória de forma econômica e medir distância sobre a superfície da Terra. Assim as
regras continuam **funções puras que recebem a base por parâmetro**, como já acontece com
`chaves_uc`, `odi_ref` e `vigente` — testáveis sem arquivo e sem servidor.

Por que **duas funções de carga separadas** (`carregar_quilombolas` / `carregar_indigenas`), e
não uma genérica com parâmetros: decisão do usuário em 2026-10-21, e ela tem razão técnica. As
duas bases vêm de órgãos diferentes e **os nomes de coluna não têm nada a ver um com o outro**
(`nm_comunid`/`cd_uf`/`fase` no INCRA, `terrai_nom`/`uf_sigla`/`fase_ti` na FUNAI); uma função
genérica esconderia esse mapeamento num dicionário de configuração, onde um nome errado só
aparece em produção. Separadas, cada mapeamento está escrito no código que o usa, e as duas
regras podem ser ligadas, testadas e implantadas **uma de cada vez**.

Entrada: os arquivos de shapefile em `entrada/areas_quilombolas/` e `entrada/areas_indigenas/`.
Fase 1: `carregar_*` lê o shapefile e devolve uma `BaseTerritorial` pronta.
Fase 2: `obter_*` mantém a base em memória, recarregando por mtime (como `referencia.py`).
Fase 3: `BaseTerritorial.localizar` responde "dentro de qual área?" em microssegundos.
Fase 4: `BaseTerritorial.mais_proxima` responde "a que distância está a área mais próxima?".
Saída: objetos `Area` com nome/UF/município/fase, consumidos pelas regras e pela mensagem.

⚠️ **A área em hectares é SEMPRE calculada da geometria, nunca lida da planilha de atributos**
(decisão do usuário, 2026-10-21). Medido na base do INCRA: `MONGE BELO` (MA) declara
`nr_area_ha` = 72.466.129 ha e a geometria dá 5.693 ha — razão de 12.729×, um erro de digitação
que sozinho responde por 96% da soma do campo. O próprio INCRA carrega um segundo campo,
`area_calc_`, que para esse registro vale 5.655 ha e confirma a geometria. Por isso nem
`nr_area_ha` nem `superficie` (FUNAI) são lidos aqui: `Area.hectares` vem da fórmula do sapateiro.
"""

from __future__ import annotations

# `array` guarda os vértices como float64 cru, sem um objeto Python por ponto: a base indígena
# cai de 160 MB (tuplas do pyshp) para a casa das dezenas, e a quilombola de 16,2 MB para 2,5 MB.
import array
# `math` para a trigonometria da projeção e para `hypot`/`sqrt` nas distâncias.
import math
# Log do processo: a indisponibilidade de uma base não pode ser silenciosa (ver `obter_*`).
import logging
# Caminhos independentes de sistema operacional e a leitura de mtime/tamanho.
from pathlib import Path

# pyshp: leitor de shapefile em Python puro, sem GDAL. É a única dependência nova do módulo.
import shapefile

# Logger do módulo, para avisar uma vez quando uma base não puder ser lida.
_LOG = logging.getLogger(__name__)

# Raiz do repositório: este arquivo mora em `backend/`, então a raiz é o diretório de cima.
_RAIZ = Path(__file__).resolve().parent.parent

# Caminhos das duas bases, SEM extensão — é assim que o pyshp recebe um shapefile (ele abre o
# `.shp`, o `.shx` e o `.dbf` com o mesmo nome base).
CAMINHO_QUILOMBOLAS = _RAIZ / "entrada" / "areas_quilombolas" / "areas_quilombolas"
CAMINHO_INDIGENAS = _RAIZ / "entrada" / "areas_indigenas" / "areas_indigenas"

# ⚠️ Codificação do `.dbf` passada à mão, nos dois casos. Os arquivos `.cpg`/`.cst` que
# acompanham os downloads vêm VAZIOS, e um arquivo de codificação vazio é pior que nenhum: o
# leitor acreditaria nele e os nomes sairiam como "PAREDÃO" em vez de "PAREDÃO".
_CODIFICACAO = "latin-1"

# Quilômetros por grau de latitude (meridiano médio). O grau de longitude encurta com o
# cosseno da latitude — ver `_projetar`.
_GRAU_KM = 111.32


class TerritorioIndisponivel(RuntimeError):
    """Erro de carga de uma base territorial (arquivo ausente, truncado ou ilegível).

    Por que é um tipo próprio: `obter_quilombolas`/`obter_indigenas` precisam distinguir
    "não consegui ler a base" de qualquer outro erro de programação, para tratar só o primeiro
    caso como ausência (regra desligada) e deixar o resto estourar.
    """


class Area:
    """Uma área territorial: atributos de identificação + geometria pronta para consulta.

    Por que é uma classe com `__slots__` e não um dicionário: são 390 + 665 instâncias vivas
    durante toda a vida do processo, e `__slots__` elimina o `__dict__` de cada uma. O ganho
    real, porém, está em `xy`: um `array('d')` achatado em vez de uma lista de tuplas.

    Entrada: os atributos lidos do `.dbf` e a geometria do `.shp`.
    Fase 1: guarda nome/UF/município/fase como texto limpo.
    Fase 2: guarda os vértices achatados (`xy`) e os cortes de anel (`partes`).
    Saída: objeto consultável por `contem` e por `distancia_km`.
    """

    # Campos fixos: sem `__dict__` por instância.
    __slots__ = ("nome", "uf", "municipio", "fase", "xy", "partes", "bbox")

    def __init__(self, nome, uf, municipio, fase, xy, partes, bbox):
        # Nome da comunidade (INCRA) ou da Terra Indígena (FUNAI).
        self.nome = nome
        # UF — pode vir composta na FUNAI ("AM, RR"), e é mostrada como veio.
        self.uf = uf
        # Município de referência do órgão (não é o município da UC).
        self.municipio = municipio
        # Fase do processo: "TITULADO", "RTID", "Regularizada", "Em Estudo"…
        self.fase = fase
        # Vértices achatados: [lon0, lat0, lon1, lat1, …] em float64.
        self.xy = xy
        # Índices de VÉRTICE onde cada anel começa, mais o total ao final (sentinela).
        self.partes = partes
        # Caixa envolvente (lon_min, lat_min, lon_max, lat_max) — prefiltro barato.
        self.bbox = bbox

    def __repr__(self):
        # Repr curto, útil em falha de teste e em log.
        return f"Area({self.nome!r}, {self.uf!r}, {self.fase!r})"

    def contem(self, lat, lon):
        """Diz se o ponto (lat, lon) está dentro desta área.

        Por que existe como método: é o coração das duas regras, e precisa ser rápido —
        chamado uma vez por linha de planilha, contra centenas de áreas.

        Entrada: `lat`/`lon` em graus decimais.
        Fase 1: descarta pela caixa envolvente (4 comparações) — elimina quase todas as áreas.
        Fase 2: conta em quantos anéis o ponto cai, por *ray casting*.
        Saída: True se o número de anéis for ÍMPAR (trata buraco dentro de polígono).
        """
        # Fase 1: fora da caixa, fora da área. Sem isto, cada consulta varreria 147 mil vértices.
        lon_min, lat_min, lon_max, lat_max = self.bbox
        if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
            return False
        # Fase 2: um shapefile de área pode ser multipolígono e pode ter anel de buraco.
        acertos = 0
        for i in range(len(self.partes) - 1):
            if _dentro_do_anel(self.xy, self.partes[i], self.partes[i + 1], lat, lon):
                acertos += 1
        # Saída: ímpar = dentro. Um ponto no buraco cai em 2 anéis (externo + buraco) = fora.
        return acertos % 2 == 1

    def distancia_km(self, lat, lon):
        """Menor distância, em km, do ponto até a BORDA desta área (0 se estiver dentro).

        Por que distância até o segmento, e não até o vértice mais próximo: a distância ao
        vértice superestima — num polígono com aresta longa, um ponto encostado no meio dela
        apareceria a quilômetros. A mensagem do painel diz um número ao operador; ele tem de
        ser o número certo.

        Entrada: `lat`/`lon` em graus decimais.
        Fase 1: se o ponto está dentro, a distância é zero.
        Fase 2: projeta os vértices em km ao redor do ponto (equirretangular local).
        Fase 3: mede ponto→segmento para cada aresta e guarda a menor.
        Saída: distância em km (float).
        """
        # Fase 1: dentro é zero — e evita percorrer a geometria à toa.
        if self.contem(lat, lon):
            return 0.0
        # Fator de encurtamento do grau de longitude na latitude do ponto consultado.
        cos_lat = math.cos(math.radians(lat))
        # Acumulador do menor quadrado de distância (poupa uma raiz por aresta).
        melhor = float("inf")
        xy = self.xy
        for p in range(len(self.partes) - 1):
            inicio, fim = self.partes[p], self.partes[p + 1]
            # Anel degenerado (menos de 2 vértices) não tem aresta para medir.
            if fim - inicio < 2:
                continue
            # Fase 2: primeiro vértice do anel, já projetado em km relativos ao ponto.
            ax = (xy[2 * inicio] - lon) * _GRAU_KM * cos_lat
            ay = (xy[2 * inicio + 1] - lat) * _GRAU_KM
            for i in range(inicio + 1, fim):
                # Vértice seguinte, também em km relativos.
                bx = (xy[2 * i] - lon) * _GRAU_KM * cos_lat
                by = (xy[2 * i + 1] - lat) * _GRAU_KM
                # Fase 3: distância da ORIGEM (o ponto consultado) ao segmento a→b.
                d = _dist2_origem_segmento(ax, ay, bx, by)
                if d < melhor:
                    melhor = d
                # O fim deste segmento é o começo do próximo: evita recalcular a projeção.
                ax, ay = bx, by
        # Saída: raiz só no final, uma vez por área.
        return math.sqrt(melhor)

    def hectares(self):
        """Área em hectares calculada DA GEOMETRIA (fórmula do sapateiro).

        Por que existe, e por que não lê o atributo: decisão do usuário em 2026-10-21 — a área
        vem do polígono, nunca da célula. Na base do INCRA o campo `nr_area_ha` tem um registro
        com 72.466.129 ha contra 5.693 ha de geometria (MONGE BELO/MA); o campo `area_calc_` do
        próprio órgão dá 5.655 ha e confirma a geometria, o que também confere esta conta.

        Entrada: a geometria da própria área.
        Fase 1: para cada anel, soma os produtos cruzados (sapateiro) em graus².
        Fase 2: converte graus² → km² corrigindo o grau de longitude pela latitude média do anel.
        Saída: hectares (1 km² = 100 ha).
        """
        total = 0.0
        xy = self.xy
        for p in range(len(self.partes) - 1):
            inicio, fim = self.partes[p], self.partes[p + 1]
            # Menos de 3 vértices não fecha polígono: área zero.
            if fim - inicio < 3:
                continue
            # Fase 1: produto cruzado acumulado e soma das latitudes (para a média do anel).
            soma = 0.0
            soma_lat = 0.0
            for i in range(inicio, fim):
                # Vértice atual e o seguinte, fechando no primeiro ao chegar ao fim do anel.
                j = inicio if i == fim - 1 else i + 1
                x1, y1 = xy[2 * i], xy[2 * i + 1]
                x2, y2 = xy[2 * j], xy[2 * j + 1]
                soma += x1 * y2 - x2 * y1
                soma_lat += y1
            # Latitude média do anel: o grau de longitude encurta conforme se afasta do equador.
            cos_lat = math.cos(math.radians(soma_lat / (fim - inicio)))
            # Fase 2: |soma|/2 em graus² → km² → hectares. Anéis de buraco somam positivo aqui;
            # a diferença é irrelevante para o uso (ordem de grandeza e conferência de dado).
            total += abs(soma) / 2 * (_GRAU_KM ** 2) * cos_lat * 100
        # Saída: hectares.
        return total


class BaseTerritorial:
    """Coleção de áreas de UMA base (INCRA ou FUNAI), com as duas consultas que as regras fazem.

    Por que é um objeto e não uma lista solta: a lista precisa viajar junto com o rótulo da base
    (que aparece na mensagem do operador), o caminho do arquivo (para o diagnóstico de saúde) e
    a assinatura de mtime (para a recarga). Passar quatro coisas separadas por quatro camadas
    seria convite a desencontro.

    Entrada: rótulo, lista de `Area` e o caminho de origem.
    Fase 1: guarda tudo e a assinatura do arquivo.
    Fase 2: `localizar` e `mais_proxima` respondem as perguntas das regras.
    Saída: objeto consultável, imutável na prática.
    """

    __slots__ = ("rotulo", "areas", "caminho", "assinatura")

    def __init__(self, rotulo, areas, caminho, assinatura=None):
        # Rótulo legível, usado na mensagem do painel ("território quilombola do INCRA").
        self.rotulo = rotulo
        # As áreas, na ordem do arquivo.
        self.areas = areas
        # Caminho base (sem extensão) de onde veio — None nos testes com base sintética.
        self.caminho = caminho
        # (mtime, tamanho) do `.shp` no momento da carga; é o gatilho de recarga.
        self.assinatura = assinatura

    def __len__(self):
        # Quantas áreas a base tem: usado em teste e no diagnóstico de saúde.
        return len(self.areas)

    def localizar(self, lat, lon):
        """Devolve a `Area` que contém o ponto, ou None.

        Entrada: `lat`/`lon` em graus decimais.
        Fase 1: percorre as áreas, cada uma descartando-se pela caixa envolvente.
        Saída: a primeira área que contém o ponto, ou None se nenhuma contiver.
        """
        for area in self.areas:
            # `contem` já faz o prefiltro de caixa: este laço custa ~0,02 ms por ponto.
            if area.contem(lat, lon):
                return area
        # Saída: nenhuma área contém o ponto.
        return None

    def mais_proxima(self, lat, lon):
        """Devolve `(area, km)` da área mais próxima do ponto, ou `(None, None)` se a base vazia.

        Por que não varre tudo: a varredura exaustiva dos vértices custou **9,9–12 ms por
        ponto** na medição de 2026-10-20 — numa planilha inteira de linhas quilombolas seriam
        ~6 s dentro de uma rota síncrona. Com o prefiltro abaixo, 0,32 ms.

        ⚠️ O prefiltro é EXATO, não heurístico, e isso é deliberado: a distância até a CAIXA
        envolvente é um limite inferior da distância até o polígono (sob a mesma projeção), então
        ao percorrer as áreas em ordem crescente de distância-até-a-caixa é lícito **parar** no
        momento em que a caixa seguinte já estiver mais longe que a melhor distância real achada.
        Nada além dela pode ser mais perto. (A versão "varrer só as 5 caixas mais próximas"
        acertou 30 de 30 pontos no teste, mas 30 acertos não são prova — e esta custa o mesmo.)

        Entrada: `lat`/`lon` em graus decimais.
        Fase 1: calcula o limite inferior por caixa para cada área e ordena por ele.
        Fase 2: percorre em ordem, medindo a distância real e parando quando o limite a supera.
        Saída: `(area, km)`.
        """
        # Base vazia não tem resposta — e dizer "a 0 km de nada" seria pior que dizer nada.
        if not self.areas:
            return None, None
        # Mesma projeção usada em `distancia_km`: é o que torna o limite inferior válido.
        cos_lat = math.cos(math.radians(lat))
        # Fase 1: (limite inferior, índice, área) — o índice desempata sem comparar `Area`.
        candidatas = sorted(
            ((_dist_km_ate_caixa(a.bbox, lat, lon, cos_lat), i, a) for i, a in enumerate(self.areas)),
            key=lambda t: t[0],
        )
        # Fase 2: melhor distância real encontrada até agora.
        melhor_km = float("inf")
        melhor_area = None
        for limite, _, area in candidatas:
            # Parada exata: o limite é crescente, então daqui para a frente ninguém melhora.
            if limite >= melhor_km:
                break
            km = area.distancia_km(lat, lon)
            if km < melhor_km:
                melhor_km, melhor_area = km, area
        # Saída: a área mais próxima e a distância em km.
        return melhor_area, melhor_km

    def resumo(self):
        """Resumo para o diagnóstico de saúde: rótulo, contagem e arquivo de origem.

        Por que existe: sem terminal na VM, a rota de diagnóstico de saúde é o único jeito de saber
        se a base chegou na imagem — o mesmo papel que `email.origem` cumpre para o SMTP.
        """
        # Só metadado: nenhuma coordenada e nenhum caminho absoluto de máquina de desenvolvimento.
        return {"rotulo": self.rotulo, "areas": len(self.areas),
                "arquivo": self.caminho.name if self.caminho else None}


def _dentro_do_anel(xy, inicio, fim, lat, lon):
    """*Ray casting* num anel do polígono: True se (lat, lon) está dentro de `xy[inicio:fim]`.

    Por que separada e não um método: é chamada uma vez por anel por consulta, e deixá-la como
    função de módulo evita a busca de atributo em cada chamada — o laço mais quente do módulo.

    Entrada: vetor achatado `xy`, limites de vértice do anel, e o ponto.
    Fase 1: para cada aresta, vê se ela cruza a semirreta horizontal que sai do ponto.
    Saída: True se o número de cruzamentos for ímpar.
    """
    dentro = False
    # `j` começa no último vértice: a primeira aresta avaliada é a de fechamento.
    j = fim - 1
    for i in range(inicio, fim):
        # Vértices da aresta atual (i) e do anterior (j), lidos do vetor achatado.
        xi, yi = xy[2 * i], xy[2 * i + 1]
        xj, yj = xy[2 * j], xy[2 * j + 1]
        # A aresta cruza a altura do ponto E o cruzamento fica à direita dele.
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    # Saída: paridade dos cruzamentos.
    return dentro


def _dist2_origem_segmento(ax, ay, bx, by):
    """Quadrado da distância da ORIGEM ao segmento a→b (coordenadas já projetadas em km).

    Por que a origem: `distancia_km` projeta os vértices *relativos ao ponto consultado*, então
    o ponto é sempre (0, 0) — uma subtração a menos por vértice, no laço mais executado.
    Por que o quadrado: a raiz sai uma vez por área, não uma vez por aresta.

    Entrada: extremos do segmento em km relativos.
    Fase 1: projeta a origem sobre a reta do segmento (parâmetro t).
    Fase 2: prende t em [0, 1] — fora disso o mais próximo é um dos extremos.
    Saída: distância², em km².
    """
    # Vetor do segmento.
    dx, dy = bx - ax, by - ay
    # Comprimento² do segmento.
    comprimento2 = dx * dx + dy * dy
    # Segmento degenerado (dois vértices iguais): a distância é até o próprio ponto.
    if comprimento2 == 0.0:
        return ax * ax + ay * ay
    # Fase 1 e 2: t = projeção escalar da origem sobre a→b, presa ao trecho do segmento.
    t = -(ax * dx + ay * dy) / comprimento2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    # Ponto do segmento mais próximo da origem.
    px, py = ax + t * dx, ay + t * dy
    # Saída: distância² da origem até esse ponto.
    return px * px + py * py


def _dist_km_ate_caixa(bbox, lat, lon, cos_lat):
    """Distância em km do ponto até a CAIXA envolvente (0 se dentro) — limite inferior exato.

    Por que existe: é o que permite a parada antecipada de `mais_proxima`. Como a caixa contém
    o polígono, nenhum ponto do polígono pode estar mais perto que a caixa.

    Entrada: `bbox` da área, o ponto e o cosseno da latitude dele.
    Fase 1: afastamento em graus em cada eixo (zero quando o ponto está entre os limites).
    Fase 2: converte para km com a mesma projeção usada nas distâncias reais.
    Saída: km.
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    # Fase 1: quanto o ponto está fora da faixa da caixa em cada eixo.
    dlon = max(lon_min - lon, 0.0, lon - lon_max)
    dlat = max(lat_min - lat, 0.0, lat - lat_max)
    # Fase 2: graus → km (longitude encurta pelo cosseno da latitude).
    return math.hypot(dlon * _GRAU_KM * cos_lat, dlat * _GRAU_KM)


def _ler_shapefile(caminho, rotulo, campo_nome, campo_uf, campo_municipio, campo_fase):
    """Lê um shapefile e monta a `BaseTerritorial` — motor comum das duas cargas.

    Por que existe, se o usuário pediu funções separadas: o que é *específico de cada base* são
    os nomes das colunas, e eles ficam escritos nas funções públicas, visíveis. O que é comum —
    abrir o arquivo, achatar vértices, calcular caixa, tratar ausência — é idêntico, e duplicar
    40 linhas de geometria em dois lugares criaria o risco de corrigir uma e esquecer a outra.

    Entrada: caminho base (sem extensão), rótulo e os quatro nomes de coluna do `.dbf`.
    Fase 1: abre o shapefile, com a codificação do `.dbf` passada à mão.
    Fase 2: percorre feição por feição (`iterShapeRecords`), sem materializar a base crua.
    Fase 3: achata os vértices em `array('d')` e calcula a caixa envolvente.
    Saída: `BaseTerritorial` com as áreas na ordem do arquivo.
    """
    caminho = Path(caminho)
    # Assinatura do `.shp`: (mtime, tamanho). É o gatilho de recarga em `obter_*`.
    try:
        st = caminho.with_suffix(".shp").stat()
        assinatura = (st.st_mtime, st.st_size)
    except OSError as erro:
        # ⚠️ Mensagem nomeia o caminho: sem terminal na VM, é o que permite diagnosticar.
        raise TerritorioIndisponivel(
            f"base territorial '{rotulo}' indisponível: não foi possível ler "
            f"{caminho.with_suffix('.shp')} ({erro.__class__.__name__})") from erro

    # Fase 1: pyshp aceita o caminho base e abre .shp/.shx/.dbf.
    try:
        leitor = shapefile.Reader(str(caminho), encoding=_CODIFICACAO)
    except Exception as erro:  # shapefile.ShapefileException e erros de I/O
        raise TerritorioIndisponivel(
            f"base territorial '{rotulo}' ilegível em {caminho} "
            f"({erro.__class__.__name__}: {erro})") from erro

    areas = []
    try:
        # Nomes das colunas do `.dbf`, menos o primeiro (flag de exclusão do formato).
        campos = [c[0] for c in leitor.fields[1:]]
        # Fase 2: uma feição por vez — a base indígena tem 1,82 milhão de vértices, e
        # materializar tudo como tupla do pyshp antes de converter custaria ordens de grandeza
        # mais memória do que o resultado final.
        for item in leitor.iterShapeRecords():
            atributos = dict(zip(campos, list(item.record)))
            pontos = item.shape.points
            # Feição sem geometria (acontece em base pública): não entra, e não quebra a carga.
            if not pontos:
                continue
            # Fase 3: vértices achatados — dois float64 por ponto, sem objeto intermediário.
            xy = array.array("d")
            for lon, lat in pontos:
                xy.append(lon)
                xy.append(lat)
            # Cortes de anel + sentinela com o total, para percorrer com `partes[i]:partes[i+1]`.
            partes = tuple(list(item.shape.parts) + [len(pontos)])
            # Caixa envolvente calculada da própria geometria (o `.shp` traz uma, mas calcular
            # aqui custa microssegundos e elimina a chance de confiar num cabeçalho errado).
            lons = xy[0::2]
            lats = xy[1::2]
            bbox = (min(lons), min(lats), max(lons), max(lats))
            areas.append(Area(
                nome=_limpo(atributos.get(campo_nome)),
                uf=_limpo(atributos.get(campo_uf)),
                municipio=_limpo(atributos.get(campo_municipio)),
                fase=_limpo(atributos.get(campo_fase)),
                xy=xy, partes=partes, bbox=bbox,
            ))
    finally:
        # Fecha os três descritores de arquivo mesmo se a leitura falhar no meio.
        leitor.close()

    # Base presente mas vazia é defeito de dado, não "nenhuma área": falha alto.
    if not areas:
        raise TerritorioIndisponivel(
            f"base territorial '{rotulo}' em {caminho} não tem nenhuma feição com geometria")

    # Saída: base pronta para consulta.
    return BaseTerritorial(rotulo, areas, caminho, assinatura)


def _limpo(valor):
    """Texto de atributo do `.dbf` sem bordas ('' quando ausente)."""
    # O `.dbf` é de largura fixa: todo texto vem preenchido com espaços à direita.
    return "" if valor is None else str(valor).strip()


def carregar_quilombolas(caminho=None):
    """Carrega a base de **áreas de quilombolas do INCRA** (`entrada/areas_quilombolas/`).

    Por que é uma função própria: os nomes de coluna são do INCRA e só valem aqui —
    `nm_comunid`, `cd_uf`, `nm_municip`, `fase`. Deixá-los escritos neste ponto é o que permite
    conferi-los contra o arquivo sem caçar um dicionário de configuração em outro módulo.

    ⚠️ **Todas as 390 áreas entram, qualquer que seja a `fase`.** Filtrar por "TITULADO"
    reduziria a base a 104 áreas e faria a regra reprovar território em processo — que é
    território reconhecido, só não concluído.

    Entrada: `caminho` base sem extensão (None usa `CAMINHO_QUILOMBOLAS`).
    Fase 1: delega a leitura ao motor comum, com o mapeamento de colunas do INCRA.
    Saída: `BaseTerritorial` (390 áreas na base de 2026-10-20).
    """
    return _ler_shapefile(
        caminho or CAMINHO_QUILOMBOLAS,
        rotulo="território quilombola do INCRA",
        campo_nome="nm_comunid", campo_uf="cd_uf",
        campo_municipio="nm_municip", campo_fase="fase",
    )


def carregar_indigenas(caminho=None):
    """Carrega a base de **Terras Indígenas da FUNAI** (`entrada/areas_indigenas/`).

    Por que é uma função própria: o esquema da FUNAI não tem uma coluna em comum com o do
    INCRA — `terrai_nom`, `uf_sigla`, `municipio_`, `fase_ti`. Além disso a `uf_sigla` pode vir
    **composta** ("AM, RR") quando a TI cruza divisa, e isso é mostrado como veio: inventar um
    desmembramento seria afirmar algo que o dado não diz.

    ⚠️ **Todas as 665 TIs entram, qualquer que seja a `fase_ti`** (Regularizada 494, Declarada
    73, Delimitada 45, Encaminhada RI 28, Homologada 17, Em Estudo 8).

    Entrada: `caminho` base sem extensão (None usa `CAMINHO_INDIGENAS`).
    Fase 1: delega a leitura ao motor comum, com o mapeamento de colunas da FUNAI.
    Saída: `BaseTerritorial` (665 áreas na base de 2026-10-20).
    """
    return _ler_shapefile(
        caminho or CAMINHO_INDIGENAS,
        rotulo="Terra Indígena da FUNAI",
        campo_nome="terrai_nom", campo_uf="uf_sigla",
        campo_municipio="municipio_", campo_fase="fase_ti",
    )


# Cache do processo: {rótulo interno: BaseTerritorial}. Mesma estratégia de `referencia.py` —
# a base é lida uma vez e revalidada por mtime, não a cada requisição.
_CACHE = {}
# Rótulos já reportados como indisponíveis, para não repetir a mesma linha de log a cada upload.
_AVISADOS = set()


def _obter(chave, carregar, caminho):
    """Devolve a base em memória, recarregando se o arquivo mudou; None se indisponível.

    ⚠️ **Por que falha ABERTA (None) e não estoura:** a ausência do arquivo desligaria a regra,
    mas estourar bloquearia **todo upload de Anexo V**, inclusive planilha correta, por causa de
    um arquivo de referência. Entre "a regra não roda" e "o sistema não recebe planilha", a
    primeira é a falha menos grave — e foi por isso que a regra do banco de identidade escolheu
    o contrário: lá o dado é do próprio sistema, aqui é base externa.
    ⚠️ **Mas não falha em SILÊNCIO** — e esse é o ponto que já custou caro neste projeto (o
    e-mail de identidade que não chegava por um remetente errado que ninguém via). A
    indisponibilidade sai no log do contêiner, uma vez por processo, e na rota de diagnóstico
    de saúde — `GET /api/health/detalhado` onde a rota foi dividida em 2026-10-01 (com token),
    `GET /api/health` onde ela ainda é uma só.

    Entrada: chave do cache, função de carga e caminho base.
    Fase 1: se a base está em cache e o `.shp` não mudou, devolve o que está em memória.
    Fase 2: (re)carrega; em `TerritorioIndisponivel`, loga uma vez e devolve None.
    Saída: `BaseTerritorial` ou None.
    """
    # Fase 1: assinatura atual do arquivo; None quando ele não existe.
    try:
        st = Path(caminho).with_suffix(".shp").stat()
        assinatura = (st.st_mtime, st.st_size)
    except OSError:
        assinatura = None
    base = _CACHE.get(chave)
    # Cache válido: mesma assinatura, nada a fazer.
    if base is not None and assinatura is not None and base.assinatura == assinatura:
        return base
    # Fase 2: (re)carrega.
    try:
        base = carregar(caminho)
    except TerritorioIndisponivel as erro:
        # Loga uma vez por processo e por chave — um log por upload seria ruído.
        if chave not in _AVISADOS:
            _AVISADOS.add(chave)
            _LOG.warning("regra territorial desligada: %s", erro)
        # Esquece o que havia em cache: a base sumiu, e responder com dado velho seria mentir.
        _CACHE.pop(chave, None)
        return None
    # Carga bem-sucedida: guarda e limpa a marca de aviso (a base voltou).
    _CACHE[chave] = base
    _AVISADOS.discard(chave)
    return base


def obter_quilombolas(caminho=None):
    """Base de quilombolas do processo (cache por mtime), ou None se indisponível."""
    # Delegação ao `_obter`: o `caminho` explícito existe para teste, como em `referencia.py`.
    return _obter("quilombolas", carregar_quilombolas, caminho or CAMINHO_QUILOMBOLAS)


def obter_indigenas(caminho=None):
    """Base de Terras Indígenas do processo (cache por mtime), ou None se indisponível."""
    return _obter("indigenas", carregar_indigenas, caminho or CAMINHO_INDIGENAS)


def limpar_cache():
    """Esvazia o cache do processo — existe para os testes não contaminarem um ao outro."""
    # Duas estruturas: as bases e as marcas de "já avisei no log".
    _CACHE.clear()
    _AVISADOS.clear()
