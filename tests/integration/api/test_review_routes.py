from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.domain.enums import TaskStatus
from app.domain.facts import Fact, FactKind, PersonExtraction, SourceRef
from app.domain.people import PersonSegment
from app.domain.review import GeneratedSection
from app.domain.template import RecognitionMethod, TemplateLocator, TemplateSection
from app.infrastructure.db.repositories import (
    FactRepository,
    PeopleRepository,
    SectionVersionRepository,
    TaskRepository,
)
from app.infrastructure.files.task_storage import TaskStorage


def _review_task(client: TestClient, *, status: TaskStatus = TaskStatus.REVIEW) -> str:
    storage = TaskStorage(client.app.state.settings.data_dir)
    with client.app.state.session_factory() as session:
        task = TaskRepository(session).create("第29周")
        TaskRepository(session).set_status(task.id, status)
        person = PersonSegment(
            id="P01", name="张三", line_start=1, line_end=2, content="完成项目 A"
        )
        PeopleRepository(session).replace_confirmed(task.id, [person])
        fact = Fact(
            id="F01",
            kind=FactKind.COMPLETED,
            topic="项目 A",
            text="完成项目 A",
            sources=[
                SourceRef(person_id="P01", line_start=2, line_end=2, quote="完成项目 A")
            ],
            confidence=0.95,
        )
        FactRepository(session).replace_person_facts(
            task.id,
            PersonExtraction(person_id="P01", person_name="张三", facts=[fact]),
        )
        SectionVersionRepository(session).save(
            task.id,
            GeneratedSection(
                section_id="progress",
                body="张三完成项目 A",
                fact_ids=["F01"],
                source_ids=["F01:S1"],
            ),
            status="pass",
            instruction="",
        )
        session.commit()
    section = TemplateSection(
        id="progress",
        name="本周进展",
        method=RecognitionMethod.PLACEHOLDER,
        confidence=1,
        locator=TemplateLocator(
            part="document", paragraph_index=0, token="{{本周进展}}"
        ),
    )
    storage.write_result(
        task.id,
        "template_sections.json",
        TypeAdapter(list[TemplateSection]).dump_json([section]),
    )
    return task.id


def test_updates_section_and_creates_revision(client: TestClient) -> None:
    task_id = _review_task(client)

    initial = client.get(f"/api/tasks/{task_id}/sections/progress")
    response = client.put(
        f"/api/tasks/{task_id}/sections/progress",
        json={"content": "调整后的本周进展"},
    )

    assert initial.status_code == 200
    assert initial.json()["revision"] == 1
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert response.json()["content"] == "调整后的本周进展"
    versions = client.get(f"/api/tasks/{task_id}/sections/progress/versions")
    assert [item["revision"] for item in versions.json()] == [2, 1]


def test_section_sources_include_original_excerpt(client: TestClient) -> None:
    task_id = _review_task(client)

    response = client.get(f"/api/tasks/{task_id}/sections/progress/sources")

    assert response.status_code == 200
    assert response.json()[0]["person"] == "张三"
    assert response.json()[0]["excerpt"] == "完成项目 A"
    assert response.json()[0]["line_start"] == 2


def test_confirms_and_restores_as_new_revisions(client: TestClient) -> None:
    task_id = _review_task(client)
    client.get(f"/api/tasks/{task_id}/sections")
    confirmed = client.post(f"/api/tasks/{task_id}/sections/progress/confirm")
    restored = client.post(f"/api/tasks/{task_id}/sections/progress/restore/1")

    assert confirmed.json()["revision"] == 2
    assert confirmed.json()["confirmed"] is True
    assert restored.json()["revision"] == 3
    assert restored.json()["confirmed"] is False


def test_review_route_error_contracts(client: TestClient) -> None:
    task_id = _review_task(client)
    draft_id = _review_task(client, status=TaskStatus.DRAFT)

    assert client.get("/api/tasks/missing/sections").status_code == 404
    assert client.get(f"/api/tasks/{task_id}/sections/missing").status_code == 404
    assert client.put(
        f"/api/tasks/{task_id}/sections/progress", json={"content": "   "}
    ).status_code == 422
    assert client.post(
        f"/api/tasks/{task_id}/sections/progress/restore/99"
    ).status_code == 404
    not_ready = client.put(
        f"/api/tasks/{draft_id}/sections/progress", json={"content": "不能编辑"}
    )
    assert not_ready.status_code == 409
    assert not_ready.json()["code"] == "REVIEW_NOT_READY"
