# Word Instruction Placeholder Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recognize every explicit `【填写……】`-style instruction in the user's Word template as an independently generated section, preserve existing template formats, and explain empty recognition results in the UI.

**Architecture:** Extend the existing OOXML parser with one narrowly scoped candidate source for Chinese instruction tokens. The parser derives hierarchical names from custom paragraph styles while the existing writer continues replacing exact tokens. Add a frontend empty state without changing task state or confirmation rules.

**Tech Stack:** Python 3.12, lxml, python-docx, pytest, FastAPI, React 18, TypeScript, Vitest.

---

## File map

- Modify `app/domain/template.py`: add the new recognition method value.
- Modify `app/infrastructure/docx/template_parser.py`: recognize instruction tokens, track custom-style context, derive unique names, and retain instructions.
- Modify `tests/unit/docx/test_template_parser.py`: exercise recognition, naming, filtering, and backward compatibility.
- Modify `tests/unit/docx/test_writer_body.py`: verify multiple tokens in one paragraph are independently replaced.
- Modify `frontend/src/pages/template-page.tsx`: render an actionable empty-state message.
- Modify `frontend/src/test/template-page.test.tsx`: verify empty and non-empty page behavior.

### Task 1: Add failing parser coverage

**Files:**
- Modify: `tests/unit/docx/test_template_parser.py`

- [ ] **Step 1: Add a test helper that creates the custom-style template**

```python
def _instruction_template(path: Path) -> None:
    document = Document()
    styles = document.styles
    styles.add_style("Weekly Section", WD_STYLE_TYPE.PARAGRAPH)
    styles.add_style("Weekly Group", WD_STYLE_TYPE.PARAGRAPH)
    document.add_paragraph("一、本周工作概述", style="Weekly Section")
    document.add_paragraph(
        "业务连续性：【概述本周成果。】 产品化建设：【概述产品进展。】"
    )
    document.add_paragraph("二、本周重点工作", style="Weekly Section")
    document.add_paragraph("业务连续性", style="Weekly Group")
    document.add_paragraph("系统/项目名称，【填写完成情况。】")
    document.add_paragraph("系统/项目名称，【填写后续安排。】")
    document.add_paragraph("三、问题及风险点", style="Weekly Section")
    document.add_paragraph("【无；如有，请填写风险及计划。】")
    document.add_paragraph("四、下周重点工作", style="Weekly Section")
    document.add_paragraph("1. 【填写下周计划一。】")
    document.save(path)
```

- [ ] **Step 2: Add the expected behavior test**

```python
def test_finds_instruction_placeholders_with_hierarchical_unique_names(
    tmp_path: Path,
) -> None:
    path = tmp_path / "instruction-template.docx"
    _instruction_template(path)

    sections = parse_template(path)

    assert [section.name for section in sections] == [
        "本周工作概述 / 业务连续性",
        "本周工作概述 / 产品化建设",
        "本周重点工作 / 业务连续性 / 系统/项目名称",
        "本周重点工作 / 业务连续性 / 系统/项目名称（2）",
        "问题及风险点",
        "下周重点工作 / 计划一",
    ]
    assert all(section.method.value == "instruction_placeholder" for section in sections)
    assert all(section.confidence == 0.95 for section in sections)
    assert sections[0].instruction == "概述本周成果。"
    assert sections[0].locator.token == "【概述本周成果。】"
```

- [ ] **Step 3: Add a filtering test**

```python
def test_ignores_non_instruction_square_brackets(tmp_path: Path) -> None:
    path = tmp_path / "ordinary-brackets.docx"
    document = Document()
    document.add_paragraph("变更结果【符合预期】")
    document.save(path)

    assert parse_template(path) == []
```

- [ ] **Step 4: Run the parser tests and verify RED**

Run: `.venv/bin/pytest tests/unit/docx/test_template_parser.py -q`

Expected: the new behavior test fails because no instruction placeholders are returned; existing tests remain valid.

### Task 2: Implement instruction placeholder parsing

**Files:**
- Modify: `app/domain/template.py`
- Modify: `app/infrastructure/docx/template_parser.py`

- [ ] **Step 1: Add the recognition method**

```python
class RecognitionMethod(StrEnum):
    PLACEHOLDER = "placeholder"
    INSTRUCTION_PLACEHOLDER = "instruction_placeholder"
    HEADING_STYLE = "heading_style"
    HEADING_TEXT = "heading_text"
    TABLE_LABEL = "table_label"
```

- [ ] **Step 2: Add narrowly scoped token patterns and naming helpers**

```python
_INSTRUCTION_PLACEHOLDER = re.compile(
    r"【(?P<instruction>(?:填写|概述|无[；;，, ]*如有[，, ]*请填写)[^【】]*)】"
)
_SECTION_PREFIX = re.compile(r"^[一二三四五六七八九十]+[、，,.．]\s*")
_ITEM_PREFIX = re.compile(r"^\d+[.、．]\s*")
```

Add helpers that:

1. strip section and item numbering;
2. find the field label between the previous token end and the current token start;
3. maintain `Weekly Section` and `Weekly Group` context;
4. create `section / group / field` names while omitting duplicate adjacent parts;
5. append `（2）` and higher suffixes for repeated names.

- [ ] **Step 3: Emit instruction candidates before heading fallback**

For each paragraph, emit one candidate per `_INSTRUCTION_PLACEHOLDER` match:

```python
candidates.append(
    (
        part,
        paragraph_index,
        unique_name,
        RecognitionMethod.INSTRUCTION_PLACEHOLDER,
        0.95,
        match.group(0),
        match.group("instruction").strip(),
    )
)
```

Extend the internal candidate tuple and final `TemplateSection` construction so existing candidate sources use an empty instruction and instruction candidates preserve their prompt text.

- [ ] **Step 4: Run parser tests and verify GREEN**

Run: `.venv/bin/pytest tests/unit/docx/test_template_parser.py -q`

Expected: all parser tests pass.

- [ ] **Step 5: Run static checks for modified Python files**

Run: `.venv/bin/ruff check app/domain/template.py app/infrastructure/docx/template_parser.py tests/unit/docx/test_template_parser.py`

Expected: no errors.

### Task 3: Prove exact multi-token writing

**Files:**
- Modify: `tests/unit/docx/test_writer_body.py`

- [ ] **Step 1: Add a multi-token writer test**

```python
def test_replaces_multiple_instruction_tokens_in_one_paragraph(tmp_path: Path) -> None:
    source = tmp_path / "instruction-template.docx"
    output = tmp_path / "out.docx"
    document = Document()
    document.add_paragraph(
        "业务连续性：【概述业务连续性。】 产品化建设：【概述产品化建设。】"
    )
    document.save(source)

    write_sections(
        source,
        output,
        {
            "业务连续性": "完成扩容",
            "产品化建设": "完成平台升级",
        },
    )

    assert Document(output).paragraphs[0].text == (
        "业务连续性：完成扩容 产品化建设：完成平台升级"
    )
```

- [ ] **Step 2: Run the writer test**

Run: `.venv/bin/pytest tests/unit/docx/test_writer_body.py::test_replaces_multiple_instruction_tokens_in_one_paragraph -q`

Expected before parser implementation: fail with `UNKNOWN_SECTION`; expected after Task 2: pass without writer changes.

- [ ] **Step 3: Run the complete DOCX test subset**

Run: `.venv/bin/pytest tests/unit/docx tests/integration/docx tests/integration/test_template_api.py -q`

Expected: all tests pass.

### Task 4: Add the template-page empty state

**Files:**
- Modify: `frontend/src/test/template-page.test.tsx`
- Modify: `frontend/src/pages/template-page.tsx`

- [ ] **Step 1: Add the failing UI test**

```tsx
it("explains when no template positions were recognized", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => [],
  }));

  render(<TemplatePage taskId="task-1" />);

  expect(await screen.findByText(/模板中没有可识别的填写位置/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "确认模板板块" })).toBeDisabled();
});
```

- [ ] **Step 2: Run the UI test and verify RED**

Run: `npm test -- --run src/test/template-page.test.tsx`

Working directory: `frontend`

Expected: the new empty-state assertion fails.

- [ ] **Step 3: Render the empty state**

Inside `section.template-grid`, render a message only after the successful request has completed and `sections.length === 0`. Track loading separately so the message does not flash before the response:

```tsx
const [loading, setLoading] = useState(true);

// in both success and error completion paths
setLoading(false);

{!loading && !error && sections.length === 0 ? (
  <p className="empty-state">
    模板中没有可识别的填写位置。请在 Word 中使用 {"{{板块名称}}"}，
    或使用“【填写……】”“【概述……】”标记需要生成的内容。
  </p>
) : null}
```

- [ ] **Step 4: Run UI tests and type checking**

Run: `npm test -- --run src/test/template-page.test.tsx && npm run typecheck`

Working directory: `frontend`

Expected: tests and type checking pass.

### Task 5: Verify the real template and recover the active task

**Files:**
- No tracked file changes.

- [ ] **Step 1: Run complete project verification**

Run:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy app
npm test -- --run
npm run build
```

Run the npm commands from `frontend`.

Expected: all commands exit zero.

- [ ] **Step 2: Parse the current uploaded template directly**

Run:

```bash
.venv/bin/python -c 'from pathlib import Path; from app.infrastructure.docx.template_parser import parse_template; p=Path("data/tasks/4c6b3d9a-0fb5-4179-97de-19a3f31bd4ef/input/template.docx"); s=parse_template(p); print(len(s)); print("\\n".join(x.name for x in s)); assert s and len({x.name for x in s}) == len(s) and len({x.locator.token for x in s}) == len(s)'
```

Expected: a non-zero section count followed by unique names.

- [ ] **Step 3: Restart the local service with the rebuilt frontend**

Build frontend assets, stop only the currently running weekly-report process, and start `app.bootstrap` with the existing `WRA_DATA_DIR` and `WRA_LOG_DIR`.

- [ ] **Step 4: Re-run template detection for the active task**

Run:

```bash
curl -sS -X POST \
  http://127.0.0.1:8765/api/tasks/4c6b3d9a-0fb5-4179-97de-19a3f31bd4ef/template/detect
```

Expected: a non-empty JSON array.

- [ ] **Step 5: Verify the live page**

Reload the current template page, confirm that section cards are visible, no empty-state message is shown, and the “确认模板板块” button is enabled.
