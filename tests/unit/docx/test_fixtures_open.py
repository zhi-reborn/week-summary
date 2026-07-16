from pathlib import Path

import pytest
from docx import Document

FIXTURE_NAMES = [
    "plain_placeholder.docx",
    "table_placeholder.docx",
    "header_footer_placeholder.docx",
    "split_runs_placeholder.docx",
    "image_numbering_template.docx",
]


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_fixture_opens_with_python_docx(fixture_name: str) -> None:
    path = Path("tests/fixtures/docx") / fixture_name

    document = Document(path)

    assert document.sections

