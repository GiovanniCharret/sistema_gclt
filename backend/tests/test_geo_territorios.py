"""Testes do leitor de bases territoriais (`backend/geo_territorios.py`) — 2026-10-21.

Por que existe: as duas regras territoriais confiam neste módulo para responder "a coordenada
está dentro?" — e um erro de geometria aqui não aparece como exceção, aparece como **planilha
correta reprovada** (a severidade é erro, por decisão do usuário). Então a geometria é testada
contra retângulos de limites conhecidos, onde "dentro" e "fora" não admitem interpretação, e só
depois contra os arquivos reais.

⚠️ Divisão deliberada: a maior parte usa geometria **sintética** (independente do dado externo);
os quatro testes que leem `entrada/areas_*` estão marcados no nome e são o único ponto onde uma
atualização do INCRA ou da FUNAI pode alterar o resultado. Eles existem porque caminho e
codificação só se provam no arquivo de verdade — a mesma razão dos três testes que leem os
arquivos reais de `backend/parametros/`.
"""

# `array` monta a geometria do caso de buraco, que não cabe na fábrica de retângulos.
import array
# `logging` para conferir que a indisponibilidade da base é registrada (e não engolida).
import logging

# `pytest` para o `raises` e o `caplog`.
import pytest

# Módulo sob teste.
from backend import geo_territorios as geo
# Fábrica compartilhada com a suíte de regras: garante que as duas montem a base do mesmo jeito.
from backend.tests.fixtures import area_retangular, base_sintetica


# Retângulo de referência: 1° de latitude por 1° de longitude no Amazonas.
# Limites redondos para que qualquer conta de distância seja verificável de cabeça.
LAT_MIN, LAT_MAX = -4.0, -3.0
LON_MIN, LON_MAX = -60.5, -59.5


def _area():
    """Área retangular de referência usada pela maioria dos testes."""
    return area_retangular("QUILOMBO DE TESTE", LAT_MIN, LAT_MAX, LON_MIN, LON_MAX)


# ───────────────────────────────── geometria sintética ─────────────────────────────────

def test_ponto_interno_esta_dentro():
    """O centro do retângulo está dentro dele."""
    # Centro exato: nenhuma ambiguidade de borda.
    assert _area().contem(-3.5, -60.0) is True


def test_ponto_externo_esta_fora():
    """Um ponto 1° ao sul do retângulo está fora."""
    assert _area().contem(-5.0, -60.0) is False


def test_ponto_fora_da_caixa_sai_pelo_prefiltro():
    """Ponto em outro hemisfério nem chega ao *ray casting* — e continua fora."""
    # Serve para fixar que o prefiltro de caixa não produz falso positivo.
    assert _area().contem(10.0, 10.0) is False


def test_distancia_de_ponto_interno_e_zero():
    """Dentro da área, a distância é zero (e a mensagem do painel nunca é emitida)."""
    assert _area().distancia_km(-3.5, -60.0) == 0.0


def test_distancia_e_medida_ate_o_segmento_nao_ate_o_vertice():
    """A distância usa a ARESTA, não o vértice mais próximo — diferença de 50× aqui.

    Por que este teste importa: a mensagem do painel diz um número ao operador. Um ponto a
    1,1 km do MEIO da borda norte está a ~55 km do canto mais próximo. Medir até o vértice
    faria o sistema afirmar "a 55 km" para quem está a pouco mais de um quilômetro — e a
    pessoa concluiria que a coordenada está muito errada quando está quase certa.
    """
    # 0,01° ao norte da borda superior, na metade do lado (longitude central).
    km = _area().distancia_km(LAT_MAX + 0.01, (LON_MIN + LON_MAX) / 2)
    # 0,01° de latitude ≈ 1,11 km. Tolerância de 1% cobre a aproximação da projeção.
    assert 1.10 <= km <= 1.13, km


def test_buraco_no_poligono_conta_como_fora():
    """Ponto dentro de um buraco (anel interno) está FORA da área.

    Por que existe: shapefile de território usa anel interno para enclave, e a regra de
    paridade (ímpar = dentro) é o que trata isso. Sem este teste, um enclave passaria a ser
    "dentro" e a regra aprovaria UC em terra que não é do território.
    """
    # Anel externo: o retângulo de referência. Anel interno: um quadrado central menor.
    externo = [(LON_MIN, LAT_MIN), (LON_MAX, LAT_MIN), (LON_MAX, LAT_MAX),
               (LON_MIN, LAT_MAX), (LON_MIN, LAT_MIN)]
    buraco = [(-60.1, -3.6), (-59.9, -3.6), (-59.9, -3.4), (-60.1, -3.4), (-60.1, -3.6)]
    xy = array.array("d")
    for lon, lat in externo + buraco:
        xy.append(lon)
        xy.append(lat)
    area = geo.Area(nome="COM BURACO", uf="AM", municipio="X", fase="TITULADO", xy=xy,
                    partes=(0, len(externo), len(externo) + len(buraco)),
                    bbox=(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX))
    # Centro do buraco: cai em dois anéis → paridade par → fora.
    assert area.contem(-3.5, -60.0) is False
    # Ponto do retângulo fora do buraco: um anel só → dentro.
    assert area.contem(-3.9, -60.4) is True


def test_localizar_devolve_a_area_que_contem_o_ponto():
    """Entre duas áreas distantes, `localizar` devolve a certa."""
    perto = _area()
    longe = area_retangular("OUTRA", -10.0, -9.0, -50.5, -49.5, uf="BA")
    base = base_sintetica(longe, perto)
    # A ordem na base é irrelevante: o ponto só está dentro de uma delas.
    assert base.localizar(-3.5, -60.0) is perto


def test_localizar_devolve_none_quando_nenhuma_area_contem():
    """Fora de todas as áreas, `localizar` devolve None — é o gatilho da regra."""
    assert base_sintetica(_area()).localizar(-20.0, -45.0) is None


def test_mais_proxima_escolhe_a_area_mais_perto_e_a_distancia():
    """Com duas áreas, devolve a mais próxima e a distância em km."""
    perto = _area()
    longe = area_retangular("OUTRA", -10.0, -9.0, -50.5, -49.5, uf="BA")
    area, km = base_sintetica(longe, perto).mais_proxima(LAT_MIN - 1.0, -60.0)
    assert area is perto
    # 1° de latitude ao sul da borda inferior ≈ 111,3 km.
    assert 110.0 <= km <= 112.5, km


def test_mais_proxima_em_base_vazia_nao_invent_a_distancia():
    """Base sem área nenhuma devolve (None, None) — nunca "a 0 km de nada"."""
    assert base_sintetica().mais_proxima(-3.5, -60.0) == (None, None)


def test_resumo_nao_vaza_caminho_de_disco():
    """`resumo()` publica rótulo, contagem e nome do arquivo — nada além.

    Por que: o resumo vai para a resposta HTTP de `/api/health`. Caminho absoluto de máquina
    de desenvolvimento e coordenada não têm o que fazer num corpo de resposta.
    """
    resumo = base_sintetica(_area(), rotulo="base de teste").resumo()
    assert resumo == {"rotulo": "base de teste", "areas": 1, "arquivo": None}


# ───────────────────────────── carga, cache e indisponibilidade ─────────────────────────────

def test_arquivo_ausente_estoura_territorio_indisponivel(tmp_path):
    """Carga direta de um caminho inexistente falha ALTO, nomeando o arquivo.

    Por que falhar alto aqui e abrir em `obter_*`: são dois públicos diferentes. Quem chama
    `carregar_*` está pedindo a base explicitamente (um teste, um script de conferência) e tem
    de saber que ela não existe; a rota de upload não pode cair por causa disso.
    """
    with pytest.raises(geo.TerritorioIndisponivel) as erro:
        geo.carregar_quilombolas(tmp_path / "nao_existe")
    # A mensagem nomeia o `.shp` procurado — sem terminal na VM, é o que permite diagnosticar.
    assert "nao_existe.shp" in str(erro.value)


def test_obter_devolve_none_e_registra_no_log_quando_a_base_falta(tmp_path, caplog):
    """`obter_*` falha ABERTA (None) mas deixa rastro no log — nunca em silêncio.

    Por que este teste: a falha silenciosa é o defeito que já custou caro neste projeto (o
    e-mail de identidade que não chegava por um remetente errado que ninguém via). Se alguém
    "simplificar" o `except` e tirar o log, este teste cai.
    """
    geo.limpar_cache()
    with caplog.at_level(logging.WARNING):
        assert geo.obter_quilombolas(tmp_path / "vazio") is None
    # `getMessage()` aplica os argumentos do log (a mensagem é montada com `%s` preguiçoso).
    assert any("desligada" in r.getMessage() for r in caplog.records)
    geo.limpar_cache()


def test_obter_avisa_uma_vez_so(tmp_path, caplog):
    """A segunda chamada não repete o log: um aviso por processo, não um por upload."""
    geo.limpar_cache()
    with caplog.at_level(logging.WARNING):
        geo.obter_indigenas(tmp_path / "vazio")
        n_primeiro = len(caplog.records)
        geo.obter_indigenas(tmp_path / "vazio")
        n_segundo = len(caplog.records)
    assert n_primeiro == 1
    assert n_segundo == 1
    geo.limpar_cache()




# ⚠️ As bases de `entrada/` podem NÃO estar no repositório — e isso é um estado legítimo, não um
# defeito: a implantação em produção foi desenhada em etapas (primeiro o código, inerte, porque sem
# base a regra não roda; depois cada base, uma de cada vez). Os testes abaixo que leem o dado real
# **pulam** nessa situação, dizendo qual pasta falta. O que NÃO pula é o teste de caminho, logo
# abaixo: ele pega um caminho escrito errado mesmo sem nenhum shapefile instalado.
_TEM_QUILOMBOLAS = geo.CAMINHO_QUILOMBOLAS.with_suffix(".shp").exists()
_TEM_INDIGENAS = geo.CAMINHO_INDIGENAS.with_suffix(".shp").exists()
_so_com_quilombolas = pytest.mark.skipif(
    not _TEM_QUILOMBOLAS, reason="base do INCRA ausente (entrada/areas_quilombolas/)")
_so_com_indigenas = pytest.mark.skipif(
    not _TEM_INDIGENAS, reason="base da FUNAI ausente (entrada/areas_indigenas/)")


def test_os_caminhos_apontam_para_dentro_de_entrada():
    """Os dois caminhos padrão ficam em `entrada/`, com o nome canônico — roda sempre.

    Por que existe: os testes que leem o dado real pulam quando a pasta não está instalada. Sem
    este, um caminho digitado errado (`entrada/area_quilombolas`, singular) atravessaria a suíte
    inteira verde, e a regra chegaria à produção desligada em silêncio.
    """
    assert geo.CAMINHO_QUILOMBOLAS.parent.name == "areas_quilombolas"
    assert geo.CAMINHO_QUILOMBOLAS.parent.parent.name == "entrada"
    assert geo.CAMINHO_QUILOMBOLAS.name == "areas_quilombolas"
    assert geo.CAMINHO_INDIGENAS.parent.name == "areas_indigenas"
    assert geo.CAMINHO_INDIGENAS.parent.parent.name == "entrada"
    assert geo.CAMINHO_INDIGENAS.name == "areas_indigenas"


# ─────────────────────────── os arquivos REAIS de `entrada/` ───────────────────────────
# ⚠️ Daqui para baixo os testes leem os shapefiles de verdade. É o único acoplamento da suíte
# com dado externo, e é intencional: caminho e codificação não se provam de outra forma.

@_so_com_quilombolas
def test_base_real_de_quilombolas_carrega_as_areas_do_incra():
    """A base do INCRA carrega de `entrada/areas_quilombolas/` com as 390 áreas de 20/10/2026.

    Por que a contagem exata: se o arquivo for trocado por uma atualização do órgão, este teste
    cai — e isso é o comportamento desejado. A troca da base é uma decisão, não um detalhe: ela
    muda quais UCs passam a ser reprovadas.
    """
    base = geo.carregar_quilombolas()
    assert len(base) == 390
    assert base.rotulo == "território quilombola do INCRA"


@_so_com_indigenas
def test_base_real_de_indigenas_carrega_as_tis_da_funai():
    """A base da FUNAI carrega de `entrada/areas_indigenas/` com as 665 TIs de 20/10/2026."""
    base = geo.carregar_indigenas()
    assert len(base) == 665
    assert base.rotulo == "Terra Indígena da FUNAI"


@_so_com_quilombolas
@_so_com_indigenas
def test_nomes_das_bases_reais_vem_com_acento_correto():
    """A codificação latin-1 do `.dbf` é passada à mão, e isto prova que está certa.

    Por que: os `.cpg`/`.cst` dos dois downloads vêm VAZIOS. Sem a codificação explícita, os
    nomes chegariam como "PAREDÃO" — e a mensagem do painel mostraria isso ao operador.
    """
    nomes = {a.nome for a in geo.carregar_quilombolas().areas}
    assert "PAREDÃO" in nomes
    # Na FUNAI o acento aparece em nome composto, com maiúscula e minúscula.
    nomes_ti = {a.nome for a in geo.carregar_indigenas().areas}
    assert "Água Preta/Inari" in nomes_ti


@_so_com_quilombolas
def test_hectares_vem_da_geometria_e_nao_do_campo_da_base():
    """⚠️ Fixa a decisão do usuário de 2026-10-21: a área vem do polígono, nunca da célula.

    `MONGE BELO` (MA) declara `nr_area_ha` = 72.466.129 ha — 96% da soma do campo na base
    inteira — contra 5.693 ha de geometria; o próprio INCRA traz `area_calc_` = 5.655 ha, que
    confirma a geometria. Se algum dia alguém trocar `hectares()` por uma leitura do atributo,
    este teste cai.
    """
    base = geo.carregar_quilombolas()
    monge = next(a for a in base.areas if a.nome == "MONGE BELO")
    # Ordem de grandeza: milhares de hectares, não dezenas de milhões.
    assert 5_000 < monge.hectares() < 6_500, monge.hectares()


@_so_com_quilombolas
def test_prefiltro_de_mais_proxima_da_a_mesma_resposta_da_forca_bruta():
    """A parada antecipada de `mais_proxima` é EXATA, não heurística — provado por comparação.

    Por que existe: `mais_proxima` ordena as áreas pela distância até a caixa envolvente e para
    quando a caixa seguinte já está mais longe que a melhor distância real. O argumento é que a
    caixa é limite inferior do polígono; este teste confere o argumento contra a varredura de
    todas as 390 áreas, em pontos espalhados pelo país.
    """
    base = geo.carregar_quilombolas()
    # Pontos escolhidos à mão em regiões diferentes (SP, DF, PA, BA, RS) — nenhum dentro de área.
    for lat, lon in ((-23.5614, -46.6554), (-15.8030, -47.8610), (-1.4558, -48.5044),
                     (-12.9777, -38.5016), (-30.0346, -51.2177)):
        area, km = base.mais_proxima(lat, lon)
        # Força bruta: mede TODAS as áreas, sem prefiltro e sem parada.
        melhor = min(((a.distancia_km(lat, lon), a.nome) for a in base.areas))
        assert area.nome == melhor[1], (lat, lon, area.nome, melhor)
        assert abs(km - melhor[0]) < 1e-9


@_so_com_quilombolas
def test_cache_do_processo_devolve_o_mesmo_objeto():
    """A base é lida uma vez por processo: a segunda chamada devolve o MESMO objeto.

    ⚠️ Marcado para pular sem a base: `obter_*` devolveria `None` nas duas chamadas e o
    `is` passaria comparando `None` com `None` — verde sem medir nada.

    Por que importa: a base indígena ocupa ~29 MB e leva ~0,4 s para carregar. Recarregar a cada
    upload seria pagar isso por requisição, e é exatamente o que `referencia.py` já evita com
    recarga por mtime.
    """
    geo.limpar_cache()
    primeira = geo.obter_quilombolas()
    segunda = geo.obter_quilombolas()
    assert primeira is segunda
    geo.limpar_cache()
