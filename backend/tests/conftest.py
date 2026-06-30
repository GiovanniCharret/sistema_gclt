"""Fixtures compartilhadas dos testes do backend.

Por que existe: todo teste de API precisa de um cliente HTTP que exercite o app
FastAPI em memória (sem subir o uvicorn de verdade). Centralizar a criação desse
cliente aqui evita repetir o boilerplate em cada `test_*.py` e garante que todos
testem exatamente a mesma instância de `app`.
"""

# `pytest` fornece o decorador de fixtures.
import pytest
# `TestClient` exercita o app ASGI em processo, traduzindo chamadas Python em
# requisições HTTP reais contra as rotas registradas (sem rede/uvicorn).
from starlette.testclient import TestClient

# Importa a instância única do app FastAPI definida no módulo de produção.
from backend.app import app


@pytest.fixture
def client():
    """Entrega um TestClient pronto para fazer requisições ao app FastAPI.

    Entrada: nenhuma (usa o `app` importado no topo do módulo).
    Fase 1: instancia o TestClient envolvendo o `app` (dispara os eventos de
            startup/shutdown ao entrar/sair do contexto `with`).
    Saída: o objeto `client`, que os testes usam como `client.get(...)` etc.
    """
    # `with` garante o ciclo de vida (startup/shutdown) do app a cada teste.
    with TestClient(app) as test_client:
        # Disponibiliza o cliente para a função de teste que pedir a fixture.
        yield test_client
