import pytest

from app.domain.enums import TaskStatus
from app.infrastructure.jobs.state_machine import InvalidTransition, transition


def test_rejects_skipping_from_draft_to_analyzing() -> None:
    with pytest.raises(InvalidTransition):
        transition(TaskStatus.DRAFT, TaskStatus.ANALYZING)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TaskStatus.READY_FOR_ANALYSIS, TaskStatus.ANALYZING),
        (TaskStatus.ANALYZING, TaskStatus.REVIEW),
        (TaskStatus.ANALYZING, TaskStatus.FAILED),
        (TaskStatus.FAILED, TaskStatus.ANALYZING),
        (TaskStatus.REVIEW, TaskStatus.COMPLETED),
    ],
)
def test_allows_explicit_analysis_transitions(
    current: TaskStatus, target: TaskStatus
) -> None:
    assert transition(current, target) == target
