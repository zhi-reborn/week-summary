from app.domain.enums import TaskStatus


class InvalidTransition(ValueError):
    pass


_ALLOWED = {
    TaskStatus.READY_FOR_ANALYSIS: {TaskStatus.ANALYZING},
    TaskStatus.ANALYZING: {
        TaskStatus.REVIEW,
        TaskStatus.EXPORTING,
        TaskStatus.FAILED,
    },
    TaskStatus.FAILED: {TaskStatus.ANALYZING},
    TaskStatus.REVIEW: {
        TaskStatus.EXPORTING,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    },
    TaskStatus.EXPORTING: {TaskStatus.COMPLETED, TaskStatus.EXPORT_FAILED},
    TaskStatus.EXPORT_FAILED: {TaskStatus.EXPORTING},
}


def transition(current: TaskStatus, target: TaskStatus) -> TaskStatus:
    if target not in _ALLOWED.get(current, set()):
        raise InvalidTransition(f"invalid task transition: {current.value} -> {target.value}")
    return target
