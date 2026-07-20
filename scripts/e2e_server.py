import json
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.application.analysis_pipeline import AnalysisPipeline  # noqa: E402
from app.config import Settings  # noqa: E402
from app.infrastructure.files.task_storage import TaskStorage  # noqa: E402
from app.infrastructure.jobs.runner import AnalysisRunner  # noqa: E402
from app.infrastructure.llm.client import OpenAICompatibleClient  # noqa: E402
from app.main import create_app  # noqa: E402
from app.migrations import run_migrations  # noqa: E402


def _handler() -> type[BaseHTTPRequestHandler]:
    class FixedModelHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            payload = json.loads(self.rfile.read(length))
            request = payload["messages"][-1]["content"]
            content = (
                _person_response(request)
                if "<weekly_report_data" in request
                else _section_response(request)
            )
            body = json.dumps(
                {"choices": [{"message": {"content": content}}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            del format, args

    return FixedModelHandler


def _person_response(request: str) -> str:
    identity = re.search(r'person_id="(P\d+)" person_name="([^"]+)"', request)
    source_lines = re.findall(r"\n(\d+): ([^\n<]+)", request)
    if identity is None or not source_lines:
        raise ValueError("测试模型无法解析人员提炼请求")
    person_id, person_name = identity.groups()
    line_number, quote = source_lines[-1]
    return json.dumps(
        {
            "person_id": person_id,
            "person_name": person_name,
            "facts": [
                {
                    "id": f"{person_id}-F01",
                    "kind": "completed",
                    "topic": "本周交付",
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
            "body": f"{'；'.join(fact['text'] for fact in facts)}；覆盖率达到95%",
            "fact_ids": [fact["id"] for fact in facts],
            "source_ids": [fact["source_ids"][0] for fact in facts],
            "unused_important_fact_ids": [],
            "review_questions": [],
        },
        ensure_ascii=False,
    )


def main() -> None:
    model_server = ThreadingHTTPServer(("127.0.0.1", 0), _handler())
    model_thread = threading.Thread(target=model_server.serve_forever, daemon=True)
    model_thread.start()
    host, port = model_server.server_address

    with tempfile.TemporaryDirectory(prefix="weekly-report-e2e-") as data_dir:
        settings = Settings(data_dir=Path(data_dir), host="127.0.0.1", port=8787)
        run_migrations(settings)
        application = create_app(settings)

        def create_llm() -> OpenAICompatibleClient:
            return OpenAICompatibleClient(
                base_url=f"http://{host}:{port}/v1",
                model="fixed-e2e-model",
                api_key=None,
                timeout_seconds=5,
            )

        pipeline = AnalysisPipeline(
            application.state.session_factory,
            TaskStorage(settings.data_dir),
            create_llm,
        )
        runner = AnalysisRunner(application.state.session_factory, pipeline, poll_seconds=0.05)
        application.state.llm_factory = create_llm
        application.state.runner = runner
        runner.start()
        try:
            uvicorn.run(application, host=settings.host, port=settings.port, log_level="warning")
        finally:
            runner.stop()
            model_server.shutdown()
            model_server.server_close()
            model_thread.join(timeout=2)


if __name__ == "__main__":
    main()
