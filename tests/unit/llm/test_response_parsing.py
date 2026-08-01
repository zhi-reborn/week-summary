import json

import httpx
import pytest

from app.domain.people import PersonSegment
from app.infrastructure.llm.client import LLMConnectionError, OpenAICompatibleClient
from app.infrastructure.llm.schemas import (
    InvalidStructuredResponse,
    parse_person_extraction,
)


VALID_EXTRACTION = {
    "person_id": "P01",
    "person_name": "张三",
    "facts": [
        {
            "id": "P01-F01",
            "kind": "completed",
            "topic": "统一认证",
            "text": "完成统一认证上线",
            "metrics": [],
            "sources": [
                {"person_id": "P01", "line_start": 2, "line_end": 2, "quote": "完成统一认证上线"}
            ],
            "confidence": 0.95,
        }
    ],
}


def test_parses_person_extraction_with_source_lines() -> None:
    result = parse_person_extraction(json.dumps(VALID_EXTRACTION, ensure_ascii=False))

    assert result.person_id == "P01"
    assert result.facts[0].sources[0].line_start == 2


def test_accepts_fenced_json_without_guessing_fields() -> None:
    raw = f"```json\n{json.dumps(VALID_EXTRACTION, ensure_ascii=False)}\n```"

    assert parse_person_extraction(raw).person_name == "张三"


def test_rejects_fact_without_source() -> None:
    invalid = json.loads(json.dumps(VALID_EXTRACTION))
    invalid["facts"][0]["sources"] = []

    with pytest.raises(InvalidStructuredResponse, match="source"):
        parse_person_extraction(json.dumps(invalid))


def test_client_repairs_invalid_structured_response_once() -> None:
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        content = '{"person_id":"P01"}' if len(calls) == 1 else json.dumps(VALID_EXTRACTION)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        transport=httpx.MockTransport(handler),
    )
    person = PersonSegment(
        id="P01", name="张三", line_start=1, line_end=2, content="完成统一认证上线"
    )

    result = client.extract_person(person)

    assert result.facts[0].id == "P01-F01"
    assert len(calls) == 2
    assert "修复" in str(calls[1]["messages"])
    assert "P01" in str(calls[1]["messages"])
    assert "张三" in str(calls[1]["messages"])
    assert "完成统一认证上线" in str(calls[1]["messages"])


def test_client_stops_after_one_failed_repair() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200, json={"choices": [{"message": {"content": '{"person_id":"P01"}'}}]}
        )
    )
    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        transport=transport,
    )
    person = PersonSegment(id="P01", name="张三", line_start=1, line_end=2, content="完成A")

    with pytest.raises(InvalidStructuredResponse) as error:
        client.extract_person(person)

    assert error.value.code == "MODEL_SCHEMA_INVALID"


def test_extraction_falls_back_when_response_format_is_unsupported() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if "response_format" in payload:
            return httpx.Response(400, json={"error": {"message": "response_format unsupported"}})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(VALID_EXTRACTION)}}]},
        )

    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        transport=httpx.MockTransport(handler),
    )
    person = PersonSegment(id="P01", name="张三", line_start=1, line_end=2, content="完成A")

    assert client.extract_person(person).person_id == "P01"
    assert len(requests) == 2
    assert "response_format" not in requests[1]


def test_connection_test_accepts_markdown_fenced_json() -> None:
    # Some providers (e.g. GLM) wrap JSON responses in markdown code fences even
    # when response_format=json_object is set. test_connection must still report
    # json_mode=True so the service is usable with these models.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "```json\n{\"ok\": true}\n```"}}]},
        )

    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        transport=httpx.MockTransport(handler),
    )

    capabilities = client.test_connection()

    assert capabilities.reachable is True
    assert capabilities.json_mode is True


def test_complete_retries_on_timeout_then_succeeds() -> None:
    # Reasoning models behind cloud APIs occasionally time out on large inputs.
    # _complete must retry transient timeouts (MODEL_TIMEOUT) up to max_retries
    # times so the pipeline self-heals instead of failing the whole task.
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.TimeoutException("simulated timeout")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(VALID_EXTRACTION)}}]},
        )

    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        timeout_seconds=1,
        max_retries=2,
        transport=httpx.MockTransport(handler),
    )

    result = client.extract_person(
        PersonSegment(id="P01", name="张三", line_start=1, line_end=2, content="完成A")
    )

    assert attempts == 2
    assert result.person_id == "P01"


def test_complete_does_not_retry_auth_errors() -> None:
    # AUTH_FAILED is not transient; retrying wastes time and still fails.
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"error": "bad key"})

    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        max_retries=3,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMConnectionError) as error:
        client.extract_person(
            PersonSegment(id="P01", name="张三", line_start=1, line_end=2, content="完成A")
        )

    assert attempts == 1
    assert error.value.code == "AUTH_FAILED"
