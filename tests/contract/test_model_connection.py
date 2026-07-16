import json

import httpx
import pytest

from app.infrastructure.llm.client import LLMConnectionError, OpenAICompatibleClient


def _request_content(request: httpx.Request) -> dict[str, object]:
    return json.loads(request.content)


def test_connection_detects_json_mode() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert _request_content(request)["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        transport=httpx.MockTransport(handler),
    )

    result = client.test_connection()

    assert result.reachable is True
    assert result.model_callable is True
    assert result.json_mode is True


def test_connection_falls_back_when_json_mode_is_rejected() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if "response_format" in _request_content(request):
            return httpx.Response(400, json={"error": {"message": "response_format unsupported"}})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    result = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        transport=httpx.MockTransport(handler),
    ).test_connection()

    assert calls == 2
    assert result.model_callable is True
    assert result.json_mode is False


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [(401, "AUTH_FAILED"), (404, "MODEL_NOT_FOUND")],
)
def test_connection_maps_model_http_errors(status_code: int, expected_code: str) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(status_code, json={"error": {"message": "failed"}})
    )
    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key="secret",
        transport=transport,
    )

    with pytest.raises(LLMConnectionError) as caught:
        client.test_connection()

    assert caught.value.code == expected_code


def test_connection_maps_timeout() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow model", request=request)

    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        transport=httpx.MockTransport(timeout),
    )

    with pytest.raises(LLMConnectionError) as caught:
        client.test_connection()

    assert caught.value.code == "MODEL_TIMEOUT"


def test_connection_rejects_non_json_response() -> None:
    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text="not-json")),
    )

    with pytest.raises(LLMConnectionError) as caught:
        client.test_connection()

    assert caught.value.code == "INVALID_MODEL_RESPONSE"
