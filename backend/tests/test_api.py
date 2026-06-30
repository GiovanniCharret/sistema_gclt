"""Testes e2e das rotas da API (via TestClient).

Por que existe: a §13 da spec e o CLAUDE.md exigem testes e2e cobrindo os
caminhos importantes. Nesta sub-fase (A1) o único endpoint é o health-check, que
prova que o app FastAPI sobe e responde — base para todas as sub-fases seguintes.
"""


def test_health_retorna_200_e_status_ok(client):
    """Garante que `GET /api/health` responde 200 com `{"status": "ok"}`.

    Entrada: a fixture `client` (TestClient do app).
    Fase 1: faz `GET /api/health`.
    Fase 2: confere o código HTTP (200) — prova que a rota existe e o app subiu.
    Fase 3: confere o corpo JSON (`status == "ok"`) — prova o contrato mínimo
            do health esperado pela A1.
    Saída: asserções; o teste passa se todas forem verdadeiras.
    """
    # Fase 1: dispara a requisição ao endpoint de saúde.
    resposta = client.get("/api/health")
    # Fase 2: o health-check deve sempre responder 200 quando o serviço está de pé.
    assert resposta.status_code == 200
    # Fase 3: o corpo mínimo acordado para a A1 é {"status": "ok"}.
    assert resposta.json()["status"] == "ok"


def test_health_expoe_contagem_da_referencia(client):
    """Garante que `GET /api/health` expõe as contagens da referência (A2).

    Entrada: a fixture `client` (TestClient) — o app carrega o `entrada/` real.
    Fase 1: faz `GET /api/health`.
    Fase 2: lê o bloco `referencia` do corpo.
    Fase 3: confere que as 4 contagens existem e são positivas (o `entrada/`
            real tem dezenas de milhares de pares (odi, uc) e mapeamentos odi→loc).
    Saída: asserções.
    """
    # Fase 1: consulta o health.
    corpo = client.get("/api/health").json()
    # Fase 2: o bloco de contagens da referência deve estar presente.
    referencia = corpo["referencia"]
    # Fase 3: as 4 contagens devem ser positivas com os dados reais de `entrada/`.
    assert referencia["totalChavesUc"] > 0
    assert referencia["totalOdiRef"] > 0
    assert referencia["contratosComChavesUc"] > 0
    assert referencia["contratosComOdiRef"] > 0


def test_health_lista_integridade_22_sem_referencia(client):
    """Garante que `GET /api/health` expõe a integridade com os 22 sem UC (A3).

    Entrada: a fixture `client` (TestClient) — app com `entrada/` e `base_contratos.json` reais.
    Fase 1: faz `GET /api/health` e lê o bloco `integridade`.
    Fase 2: confere 19 com referência, 22 sem referência e 0 órfãos (estado atual da base).
    Fase 3: confere que os 3 LPT pendentes estão entre os sem-referência.
    Saída: asserções.
    """
    # Fase 1: lê a integridade do health.
    integridade = client.get("/api/health").json()["integridade"]
    # Fase 2: classificação esperada hoje (19 com UC; 22 sem — 19 MLA + 3 LPT; 0 órfãos).
    assert integridade["contratosComReferencia"] == 19
    assert len(integridade["contratosSemReferencia"]) == 22
    assert integridade["orfaos"] == []
    # Fase 3: os 3 contratos LPT ainda pendentes devem estar na lista de sem-referência.
    for contrato in ["ECO 034/2026", "ECO 039/2025", "ECO 042/2025"]:
        assert contrato in integridade["contratosSemReferencia"]
