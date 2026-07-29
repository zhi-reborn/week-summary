# Person Extraction Contract Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent local-model schema mistakes and identity drift from failing or contaminating per-person weekly-report extraction.

**Architecture:** Keep the model responsible only for semantic facts. Give the one repair request the original person context, then bind person metadata and deterministic fact IDs in `AnalysisService` before persistence. Preserve privacy by logging only a specific error code and person entity ID.

**Tech Stack:** Python 3.12, Pydantic 2, httpx, SQLAlchemy, pytest, ruff, mypy.

---

## File map

- Modify `app/infrastructure/llm/prompts.py`: build repair prompts with the expected person and original numbered report.
- Modify `app/infrastructure/llm/client.py`: pass the person to the repair prompt.
- Modify `app/infrastructure/llm/schemas.py`: give final schema failures a stable application error code.
- Modify `app/application/analysis_service.py`: bind server-owned identity and fact IDs, then emit a safe failure event.
- Modify `app/core/redaction.py`: permit the non-sensitive `entity_id` field in structured logs.
- Modify `tests/unit/llm/test_response_parsing.py`: cover person-aware repair and schema error codes.
- Modify `tests/unit/llm/test_prompt_boundaries.py`: cover the repair prompt's original-data boundary.
- Modify `tests/unit/application/test_person_extraction.py`: cover identity, source-person and fact-ID binding.
- Modify `tests/unit/core/test_redaction.py`: prove the new log field is allowed while private fields remain excluded.
- Modify `tests/integration/test_person_extraction_persistence.py`: prove the specific failure code is persisted.

### Task 1: Make schema repair person-aware and diagnosable

**Files:**
- Modify: `tests/unit/llm/test_response_parsing.py`
- Modify: `tests/unit/llm/test_prompt_boundaries.py`
- Modify: `app/infrastructure/llm/prompts.py`
- Modify: `app/infrastructure/llm/client.py`
- Modify: `app/infrastructure/llm/schemas.py`

- [ ] **Step 1: Add failing repair-context assertions**

Extend `test_client_repairs_invalid_structured_response_once` to inspect the second request:

```python
repair_messages = calls[1]["messages"]
assert "P01" in str(repair_messages)
assert "张三" in str(repair_messages)
assert "完成统一认证上线" in str(repair_messages)
```

Add a prompt-boundary test:

```python
def test_repair_prompt_repeats_expected_person_and_numbered_source() -> None:
    person = PersonSegment(
        id="P01",
        name="张三",
        line_start=4,
        line_end=5,
        content="完成统一认证上线",
    )

    messages = build_repair_messages(person, '{"person_id":"P02"}')

    assert 'person_id="P01"' in messages[1]["content"]
    assert 'person_name="张三"' in messages[1]["content"]
    assert "5: 完成统一认证上线" in messages[1]["content"]
    assert '{"person_id":"P02"}' in messages[1]["content"]
```

- [ ] **Step 2: Add a failing schema-error-code assertion**

Extend `test_client_stops_after_one_failed_repair`:

```python
with pytest.raises(InvalidStructuredResponse) as error:
    client.extract_person(person)

assert error.value.code == "MODEL_SCHEMA_INVALID"
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/pytest \
  tests/unit/llm/test_response_parsing.py::test_client_repairs_invalid_structured_response_once \
  tests/unit/llm/test_response_parsing.py::test_client_stops_after_one_failed_repair \
  tests/unit/llm/test_prompt_boundaries.py::test_repair_prompt_repeats_expected_person_and_numbered_source \
  -q
```

Expected: failures because `build_repair_messages` does not accept a person, repair messages lack source context, and `InvalidStructuredResponse` has no `code`.

- [ ] **Step 4: Implement the minimal repair contract**

In `app/infrastructure/llm/prompts.py`, share the existing numbered and escaped report payload between initial and repair prompts:

```python
def _weekly_report_data(person: PersonSegment) -> str:
    numbered_lines = "\n".join(
        f"{person.line_start + index + 1}: {line}"
        for index, line in enumerate(person.content.splitlines())
    )
    return (
        f'<weekly_report_data person_id="{html.escape(person.id, quote=True)}" '
        f'person_name="{html.escape(person.name, quote=True)}">\n'
        f"{html.escape(numbered_lines)}\n"
        "</weekly_report_data>"
    )
```

Change the repair signature and content:

```python
def build_repair_messages(person: PersonSegment, raw: str) -> list[dict[str, str]]:
    schema = json.dumps(PersonExtraction.model_json_schema(), ensure_ascii=False)
    return [
        {
            "role": "system",
            "content": (
                "修复给定响应，使其严格符合 JSON Schema。"
                "person_id、person_name 和所有来源 person_id 必须与 weekly_report_data 一致。"
                "不得添加原文中不存在的事实。只返回 JSON。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"JSON Schema:\n{schema}\n\n"
                f"原始周报：\n{_weekly_report_data(person)}\n\n"
                f"待修复响应：\n{raw}"
            ),
        },
    ]
```

Use `_weekly_report_data(person)` in `build_person_extraction_messages`, and update `OpenAICompatibleClient.extract_person`:

```python
repaired = self._complete(build_repair_messages(person, raw))
```

Give the parse exception a stable code:

```python
class InvalidStructuredResponse(ValueError):
    code = "MODEL_SCHEMA_INVALID"
```

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run:

```bash
.venv/bin/pytest tests/unit/llm/test_response_parsing.py tests/unit/llm/test_prompt_boundaries.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add \
  app/infrastructure/llm/prompts.py \
  app/infrastructure/llm/client.py \
  app/infrastructure/llm/schemas.py \
  tests/unit/llm/test_response_parsing.py \
  tests/unit/llm/test_prompt_boundaries.py
git commit -m "fix: preserve person context during model repair"
```

### Task 2: Bind model metadata at the application boundary

**Files:**
- Modify: `tests/unit/application/test_person_extraction.py`
- Modify: `app/application/analysis_service.py`

- [ ] **Step 1: Add a failing identity-binding test**

Add an LLM stub that returns structurally valid but incorrect metadata:

```python
@dataclass
class DriftingLLM:
    def extract_person(self, person: PersonSegment) -> PersonExtraction:
        return PersonExtraction(
            person_id="P99",
            person_name="错误姓名",
            facts=[
                Fact(
                    id="F1",
                    kind=FactKind.COMPLETED,
                    topic="交付",
                    text=person.content,
                    sources=[
                        SourceRef(
                            person_id="P99",
                            line_start=person.line_start + 1,
                            line_end=person.line_end,
                            quote=person.content,
                        )
                    ],
                    confidence=0.9,
                ),
                Fact(
                    id="F2",
                    kind=FactKind.NEXT_PLAN,
                    topic="计划",
                    text="继续推进",
                    sources=[
                        SourceRef(
                            person_id="P99",
                            line_start=person.line_start + 1,
                            line_end=person.line_end,
                            quote=person.content,
                        )
                    ],
                    confidence=0.8,
                ),
            ],
        )
```

The test invokes `AnalysisService.extract_people` for one person and asserts:

```python
facts = FactRepository(db_session).list_by_person(task_id, "P01")
assert [fact.id for fact in facts] == ["P01-F01", "P01-F02"]
assert {source.person_id for fact in facts for source in fact.sources} == {"P01"}
assert JobStepRepository(db_session).get(
    task_id, "extract_person", "P01"
).status == "succeeded"
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
.venv/bin/pytest tests/unit/application/test_person_extraction.py::test_binds_model_metadata_to_current_person -q
```

Expected: failure with `模型返回的人员身份与请求不一致`.

- [ ] **Step 3: Implement server-owned metadata binding**

In `AnalysisService`, bind the model result before validation:

```python
@staticmethod
def _bind_person(person: PersonSegment, extraction: PersonExtraction) -> PersonExtraction:
    facts = [
        fact.model_copy(
            update={
                "id": f"{person.id}-F{index:02d}",
                "sources": [
                    source.model_copy(update={"person_id": person.id})
                    for source in fact.sources
                ],
            }
        )
        for index, fact in enumerate(extraction.facts, start=1)
    ]
    return PersonExtraction(
        person_id=person.id,
        person_name=person.name,
        facts=facts,
    )
```

Call it immediately after the LLM returns:

```python
extraction = self._bind_person(person, self._llm.extract_person(person))
```

Keep `_validate_person` as defense in depth.

- [ ] **Step 4: Run the application tests and verify GREEN**

Run:

```bash
.venv/bin/pytest tests/unit/application/test_person_extraction.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add app/application/analysis_service.py tests/unit/application/test_person_extraction.py
git commit -m "fix: bind extracted facts to the requested person"
```

### Task 3: Persist specific safe diagnostics

**Files:**
- Modify: `tests/unit/core/test_redaction.py`
- Modify: `tests/integration/test_person_extraction_persistence.py`
- Modify: `app/core/redaction.py`
- Modify: `app/application/analysis_service.py`

- [ ] **Step 1: Add failing log-whitelist coverage**

Add `entity_id` to the input and expected result in `test_structured_log_event_only_keeps_whitelisted_fields`:

```python
"entity_id": "P01",
```

The test must continue proving that `report_text` and `response_body` are excluded.

- [ ] **Step 2: Add a failing persisted-error test**

Define a failure with a code:

```python
class SchemaFailure(ValueError):
    code = "MODEL_SCHEMA_INVALID"
```

Use an LLM stub that raises it, then assert:

```python
with pytest.raises(SchemaFailure):
    AnalysisService(db_session, SchemaFailingLLM()).extract_people(task.id)

step = JobStepRepository(db_session).get(task.id, "extract_person", "P01")
assert step is not None
assert step.error_code == "MODEL_SCHEMA_INVALID"
```

Monkeypatch `app.application.analysis_service.log_event` and assert the emitted event is exactly:

```python
{
    "task_id": task.id,
    "stage": "person_extraction",
    "entity_id": "P01",
    "error_code": "MODEL_SCHEMA_INVALID",
}
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/pytest \
  tests/unit/core/test_redaction.py::test_structured_log_event_only_keeps_whitelisted_fields \
  tests/integration/test_person_extraction_persistence.py::test_persists_specific_person_extraction_error \
  -q
```

Expected: redaction test drops `entity_id`, and the persistence test observes no failure event.

- [ ] **Step 4: Implement safe event logging**

Add `"entity_id"` to `_LOG_FIELDS` in `app/core/redaction.py`.

In the `AnalysisService.extract_people` exception handler, calculate and use one error code:

```python
error_code = getattr(exc, "code", "PERSON_EXTRACTION_FAILED")
log_event(
    {
        "task_id": task_id,
        "stage": "person_extraction",
        "entity_id": person.id,
        "error_code": error_code,
    }
)
JobStepRepository(self._session).mark_failed(current.id, error_code)
```

Do not log `str(exc)`, person name, report text or model response.

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run:

```bash
.venv/bin/pytest \
  tests/unit/core/test_redaction.py \
  tests/integration/test_person_extraction_persistence.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add \
  app/core/redaction.py \
  app/application/analysis_service.py \
  tests/unit/core/test_redaction.py \
  tests/integration/test_person_extraction_persistence.py
git commit -m "fix: record safe person extraction diagnostics"
```

### Task 4: Verify the release and recover the current task

**Files:**
- No production files expected.

- [ ] **Step 1: Run backend tests**

Run:

```bash
.venv/bin/pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 2: Run Python static checks**

Run:

```bash
.venv/bin/ruff check .
.venv/bin/mypy app
git diff --check
```

Expected: all commands exit successfully with no errors.

- [ ] **Step 3: Run frontend regression checks**

Run:

```bash
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

Expected: all frontend tests pass and the production build succeeds.

- [ ] **Step 4: Run a read-only current-P01 model probe**

Use the configured local model and current P01 data without writing to `data/app.db`. Assert in the diagnostic output:

```text
person_id=P01
person_name=周五
fact_ids=P01-F01,...
source_person_ids=P01
```

- [ ] **Step 5: Restart the application service**

Stop only the existing weekly-report application process, start it from this repository with the existing data directory and configuration, then verify:

```bash
curl -sS http://127.0.0.1:8765/health
curl -sS http://127.0.0.1:8765/api/settings/model
```

Expected: health is successful and model settings still point to the local Ollama endpoint.

- [ ] **Step 6: Retry the failed analysis step and monitor to a terminal state**

Call the existing retry endpoint once:

```bash
curl -sS -X POST \
  http://127.0.0.1:8765/api/tasks/4c6b3d9a-0fb5-4179-97de-19a3f31bd4ef/analysis/retry
```

Poll the analysis status without issuing additional retries. Acceptance criteria:

- `extract_person:P01` no longer fails because of identity drift.
- All nine confirmed people receive successful extraction steps.
- The task either reaches review/export successfully or exposes a new, specific downstream error code.
- No uploaded TXT, DOCX, confirmed people or template sections are modified.

- [ ] **Step 7: Commit any plan checkbox updates**

If plan checkboxes are updated during execution, commit only this plan:

```bash
git add docs/superpowers/plans/2026-07-29-person-extraction-contract-hardening.md
git commit -m "docs: record person extraction hardening verification"
```
