"""LLM-client (0002-ai-suggest): verzoekvorm en netwerkinperking."""

import pytest

from tools.ai_suggest.llm import LLMClient, LLMError, normalize_zekerheid

SCHEMA = {"type": "object"}
ALLOWED = ["Boodschappen"]
MESSAGES = [{"role": "user", "content": "Tegenpartij: Test Bakker"}]


def ok(body):
    return 200, {"categorie": "Boodschappen", "zoekterm": "test bakker", "zekerheid": 0.5}


def test_request_body_shape(stub):
    stub.responder = ok
    client = LLMClient(stub.url, "Qwen3-14B-Q4_K_M", api_key="sleutel")
    result = client.suggest(MESSAGES, SCHEMA, ALLOWED)
    assert result["categorie"] == "Boodschappen"
    req = stub.requests[0]
    assert req["path"] == "/v1/chat/completions"
    body = req["body"]
    assert body["model"] == "Qwen3-14B-Q4_K_M"
    assert body["temperature"] == 0
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    assert req["headers"]["Authorization"] == "Bearer sleutel"


def test_ignores_proxy_env(stub, monkeypatch):
    # R1: proxyvariabelen naar een dode poort mogen het verzoek niet omleiden
    stub.responder = ok
    for var in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.setenv(var, "http://127.0.0.1:9")
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    client = LLMClient(stub.url, "m")
    assert client.suggest(MESSAGES, SCHEMA, ALLOWED)["categorie"] == "Boodschappen"
    assert len(stub.requests) == 1


def test_redirect_refused(stub):
    stub.responder = lambda body: (302, "http://example.com/v1/chat/completions")
    client = LLMClient(stub.url, "m")
    with pytest.raises(LLMError, match="redirect"):
        client.suggest(MESSAGES, SCHEMA, ALLOWED)


def test_http_error_is_llm_error(stub):
    stub.responder = lambda body: (500, "kapot")
    with pytest.raises(LLMError):
        LLMClient(stub.url, "m").suggest(MESSAGES, SCHEMA, ALLOWED)


def test_unreachable_is_llm_error():
    with pytest.raises(LLMError):
        LLMClient("http://127.0.0.1:9", "m", timeout=2).suggest(MESSAGES, SCHEMA, ALLOWED)


@pytest.mark.parametrize(
    "value,expected,flagged",
    [(0.5, 0.5, False), (95, 0.95, False), (1, 1.0, False), (-0.2, 0.0, True),
     (250, 1.0, True), ("hoog", 0.0, True), (None, 0.0, True), (float("nan"), 0.0, True)],
)
def test_normalize_zekerheid(value, expected, flagged):
    v, flags = normalize_zekerheid(value)
    assert v == pytest.approx(expected)
    assert bool(flags) is flagged
