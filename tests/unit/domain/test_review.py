from app.domain.review import SectionReview


def test_new_review_version_increments_revision() -> None:
    current = SectionReview(section_key="progress", revision=2, content="旧内容")

    updated = current.revise("新内容", editor="local-user")

    assert updated.revision == 3
    assert updated.content == "新内容"
    assert updated.confirmed is False
    assert current.revision == 2
    assert current.content == "旧内容"


def test_confirm_does_not_mutate_previous_revision() -> None:
    current = SectionReview(section_key="risk", revision=1, content="风险 A")

    confirmed = current.confirm(editor="local-user")

    assert current.confirmed is False
    assert confirmed.revision == 2
    assert confirmed.confirmed is True
