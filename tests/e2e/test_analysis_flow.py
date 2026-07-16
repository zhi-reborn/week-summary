import json
import re
import threading
import time
from collections import Counter
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

from fastapi.testclient import TestClient

from app.application.analysis_pipeline import AnalysisPipeline
from app.config import Settings
from app.infrastructure.files.task_storage import TaskStorage
from app.infrastructure.jobs.runner import AnalysisRunner
from app.infrastructure.llm.client import OpenAICompatibleClient
from app.main import create_app
from tests.conftest import migrate_database


class ModelState:
    def __init__(self) -> None:
        self.people_attempts: Counter[str] = Counter()
        self.extraction_requests: list[str] = []


def _handler(state: ModelState) -> type[BaseHTTPRequestHandler]:
    class MockModelHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            payload = json.loads(self.rfile.read(length))
            user_content = payload["messages"][-1]["content"]
            if "<weekly_report_data" in user_content:
                content = _person_response(state, user_content)
            else:
                content = _section_response(user_content)
            body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        def log_message(self, format: str, *args: Any) -> None:
            del format, args

    return MockModelHandler


def _person_response(state: ModelState, request: str) -> str:
    state.extraction_requests.append(request)
    identity = re.search(r'person_id="(P\d+)" person_name="([^"]+)"', request)
    source_line = re.search(r"\n(\d+): ([^\n<]+)", request)
    assert identity is not None and source_line is not None
    person_id, person_name = identity.groups()
    line_number, quote = source_line.groups()
    state.people_attempts[person_id] += 1
    if person_id == "P07" and state.people_attempts[person_id] == 1:
        time.sleep(0.15)
    return json.dumps(
        {
            "person_id": person_id,
            "person_name": person_name,
            "facts": [
                {
                    "id": f"{person_id}-F01",
                    "kind": "completed",
                    "topic": "共同交付",
                    "text": quote,
                    "metrics": [],
                    "sources": [
                        {
                            "person_id": person_id,
                            "line_start": int(line_number),
                            "line_end": int(line_number),
                            "quote": quote,
                        }
                    ],
                    "confidence": 0.95,
                }
            ],
        },
        ensure_ascii=False,
    )


def _section_response(request: str) -> str:
    payload = json.loads(request)
    facts = payload["candidate_facts"]
    return json.dumps(
        {
            "section_id": payload["section"]["id"],
            "body": "；".join(fact["text"] for fact in facts),
            "fact_ids": [fact["id"] for fact in facts],
            "source_ids": [fact["source_ids"][0] for fact in facts],
            "unused_important_fact_ids": [],
            "review_questions": [],
        },
        ensure_ascii=False,
    )


@contextmanager
def _mock_model() -> Iterator[tuple[str, ModelState]]:
    state = ModelState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/v1", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_twenty_people_analysis_resumes_after_one_timeout(
    tmp_path: Path, valid_docx_bytes: bytes
) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    settings.data_dir.mkdir(parents=True)
    migrate_database(settings.database_url)
    reports = "\n\n".join(
        f"成员{index:02d}周报\n完成共同交付" for index in range(1, 21)
    ).encode()

    with _mock_model() as (base_url, model_state), TestClient(create_app(settings)) as client:
        pipeline = AnalysisPipeline(
            client.app.state.session_factory,
            TaskStorage(settings.data_dir),
            lambda: OpenAICompatibleClient(
                base_url=base_url,
                model="private-model",
                api_key=None,
                timeout_seconds=0.05,  # type: ignore[arg-type]
            ),
        )
        runner = AnalysisRunner(client.app.state.session_factory, pipeline)
        client.app.state.runner = runner
        task = client.post("/api/tasks", json={"name": "第29周"}).json()
        task_id = task["id"]
        client.post(
            f"/api/tasks/{task_id}/inputs",
            files={
                "reports": ("reports.txt", reports, "text/plain"),
                "template": ("template.docx", valid_docx_bytes, "application/octet-stream"),
            },
        )
        assert client.post(f"/api/tasks/{task_id}/people/detect").json()["people"][-1]["id"] == "P20"
        assert client.post(f"/api/tasks/{task_id}/people/confirm").status_code == 200
        assert client.post(f"/api/tasks/{task_id}/template/detect").status_code == 200
        assert client.post(f"/api/tasks/{task_id}/template/confirm").status_code == 200
        assert client.post(f"/api/tasks/{task_id}/analysis/start").status_code == 202

        runner.run_once()
        failed = client.get(f"/api/tasks/{task_id}/analysis/status").json()
        assert failed["task_status"] == "failed"
        assert failed["current_step"] == "extract_person:P07", (
            failed,
            model_state.people_attempts,
            model_state.extraction_requests[:1],
        )

        assert client.post(f"/api/tasks/{task_id}/analysis/retry").status_code == 202
        runner.run_once()
        completed = client.get(f"/api/tasks/{task_id}/analysis/status").json()

    assert completed["task_status"] == "review"
    assert set(model_state.people_attempts) == {f"P{index:02d}" for index in range(1, 21)}
    assert model_state.people_attempts["P07"] == 2
    assert all(model_state.people_attempts[f"P{index:02d}"] == 1 for index in range(1, 7))
    assert all(request.count("<weekly_report_data") == 1 for request in model_state.extraction_requests)
