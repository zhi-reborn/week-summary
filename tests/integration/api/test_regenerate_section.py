from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from app.domain.facts import Fact
from app.domain.review import GeneratedSection
from app.domain.template import TemplateSection
from app.infrastructure.llm.client import LLMConnectionError
from tests.integration.api.test_review_routes import _review_task


@dataclass
class SectionModelSpy:
    section_keys: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)

    def generate_section(
        self, section: TemplateSection, facts: list[Fact], instruction: str
    ) -> GeneratedSection:
        self.section_keys.append(section.id)
        self.instructions.append(instruction)
        return GeneratedSection(
            section_id=section.id,
            body="重新生成：" + "；".join(fact.text for fact in facts),
            fact_ids=[fact.id for fact in facts],
            source_ids=[f"{fact.id}:S1" for fact in facts],
        )


def test_regenerate_only_calls_requested_section(client: TestClient) -> None:
    task_id = _review_task(client)
    model = SectionModelSpy()
    client.app.state.llm_factory = lambda: model
    client.get(f"/api/tasks/{task_id}/sections/progress")

    response = client.post(
        f"/api/tasks/{task_id}/sections/progress/regenerate",
        json={"instruction": "突出关键结果，控制在三条以内"},
    )

    assert response.status_code == 202
    assert response.json()["revision"] == 2
    assert response.json()["content"].startswith("重新生成：")
    assert model.section_keys == ["progress"]
    assert model.instructions == ["突出关键结果，控制在三条以内"]
    history = client.get(f"/api/tasks/{task_id}/sections/progress/versions").json()
    assert [item["revision"] for item in history] == [2, 1]


def test_regenerate_requires_configured_model_factory(client: TestClient) -> None:
    task_id = _review_task(client)

    response = client.post(
        f"/api/tasks/{task_id}/sections/progress/regenerate",
        json={"instruction": "更精炼"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "MODEL_NOT_CONFIGURED"


def test_regenerate_handles_missing_saved_model_settings(client: TestClient) -> None:
    task_id = _review_task(client)

    def missing_settings() -> SectionModelSpy:
        raise FileNotFoundError("model_settings.json")

    client.app.state.llm_factory = missing_settings

    response = client.post(
        f"/api/tasks/{task_id}/sections/progress/regenerate",
        json={"instruction": "更精炼"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "MODEL_NOT_CONFIGURED"


class FailingSectionModel(SectionModelSpy):
    def generate_section(
        self, section: TemplateSection, facts: list[Fact], instruction: str
    ) -> GeneratedSection:
        raise LLMConnectionError("MODEL_TIMEOUT", "模型连接超时")


def test_regenerate_keeps_current_review_when_model_fails(client: TestClient) -> None:
    task_id = _review_task(client)
    client.app.state.llm_factory = FailingSectionModel
    before = client.get(f"/api/tasks/{task_id}/sections/progress").json()

    response = client.post(
        f"/api/tasks/{task_id}/sections/progress/regenerate",
        json={"instruction": "更精炼"},
    )

    assert response.status_code == 502
    assert response.json()["code"] == "MODEL_TIMEOUT"
    after = client.get(f"/api/tasks/{task_id}/sections/progress").json()
    assert after["revision"] == before["revision"] == 1
