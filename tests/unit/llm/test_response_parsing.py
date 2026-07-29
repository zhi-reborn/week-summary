import json

import httpx
import pytest

from app.domain.people import PersonSegment
from app.infrastructure.llm.client import OpenAICompatibleClient
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
