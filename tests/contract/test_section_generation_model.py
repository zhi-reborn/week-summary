import json

import httpx

from app.domain.facts import Fact, FactKind, SourceRef
from app.domain.template import RecognitionMethod, TemplateLocator, TemplateSection
from app.infrastructure.llm.client import OpenAICompatibleClient


def test_section_model_returns_only_structured_content_and_ids() -> None:
    response = {
        "section_id": "risk",
        "body": "资源不足",
        "fact_ids": ["F1"],
        "source_ids": ["F1:S1"],
        "unused_important_fact_ids": [],
        "review_questions": [],
    }
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(response)}}]}
        )
    )
    client = OpenAICompatibleClient(
        base_url="http://model.local/v1",
        model="private-model",
        api_key=None,
        transport=transport,
    )
    section = TemplateSection(
        id="risk",
        name="风险与问题",
        method=RecognitionMethod.PLACEHOLDER,
        confidence=1,
        locator=TemplateLocator(part="word/document.xml", paragraph_index=0, token="{{风险}}"),
    )
    fact = Fact(
        id="F1",
        kind=FactKind.RISK,
        topic="资源",
        text="资源不足",
        sources=[SourceRef(person_id="P01", line_start=2, line_end=2, quote="资源不足")],
        confidence=0.9,
    )

    generated = client.generate_section(section, [fact], "")

    assert generated.fact_ids == ["F1"]
    assert generated.source_ids == ["F1:S1"]
