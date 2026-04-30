from __future__ import annotations

from abc import ABC

from .models import WorkItemStatus


class TransitionError(ValueError):
    """Raised when a workflow transition is not allowed."""


class IncidentState(ABC):
    status: WorkItemStatus
    allowed_next: tuple[WorkItemStatus, ...] = ()

    def ensure_can_transition(
        self,
        target: WorkItemStatus,
        *,
        rca_complete: bool,
    ) -> None:
        if target not in self.allowed_next:
            raise TransitionError(f"{self.status.value} cannot transition to {target.value}.")
        if target is WorkItemStatus.CLOSED and not rca_complete:
            raise TransitionError("Work item cannot be CLOSED until a complete RCA is submitted.")


class OpenState(IncidentState):
    status = WorkItemStatus.OPEN
    allowed_next = (WorkItemStatus.INVESTIGATING,)


class InvestigatingState(IncidentState):
    status = WorkItemStatus.INVESTIGATING
    allowed_next = (WorkItemStatus.RESOLVED,)


class ResolvedState(IncidentState):
    status = WorkItemStatus.RESOLVED
    allowed_next = (WorkItemStatus.CLOSED,)


class ClosedState(IncidentState):
    status = WorkItemStatus.CLOSED
    allowed_next = ()


STATE_REGISTRY: dict[WorkItemStatus, IncidentState] = {
    WorkItemStatus.OPEN: OpenState(),
    WorkItemStatus.INVESTIGATING: InvestigatingState(),
    WorkItemStatus.RESOLVED: ResolvedState(),
    WorkItemStatus.CLOSED: ClosedState(),
}


class WorkflowStateMachine:
    @staticmethod
    def transition(
        current_status: WorkItemStatus,
        target_status: WorkItemStatus,
        *,
        rca_complete: bool,
    ) -> None:
        STATE_REGISTRY[current_status].ensure_can_transition(
            target_status,
            rca_complete=rca_complete,
        )
