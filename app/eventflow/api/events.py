from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from eventflow.api.dependencies import verify_api_key
from eventflow.database.event import Event
from eventflow.database.repository import GenericRepository
from eventflow.database.session import db_session
from eventflow.worker.config import celery_app
from eventflow.workflows.workflow_registry import WorkflowRegistry

router = APIRouter(dependencies=[Depends(verify_api_key)])


class EventAccepted(BaseModel):
    event_id: UUID
    task_id: str
    workflow: str


class EventStatus(BaseModel):
    event_id: UUID
    workflow: str
    status: str
    error: str | None
    task_context: dict[str, Any] | None


def _get_workflow(workflow_name: str) -> WorkflowRegistry:
    try:
        return WorkflowRegistry[workflow_name.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown workflow: {workflow_name}"
        ) from None


@router.post(
    "/{workflow_name}", status_code=status.HTTP_202_ACCEPTED, response_model=EventAccepted
)
def handle_event(
    workflow_name: str,
    data: dict[str, Any] = Body(...),
    session: Session = Depends(db_session),
) -> EventAccepted:
    workflow = _get_workflow(workflow_name)
    event_schema = workflow.value.workflow_schema.event_schema
    try:
        parsed = event_schema.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(include_url=False, include_context=False),
        ) from None

    repository = GenericRepository(session=session, model=Event)
    event = repository.create(
        Event(workflow_type=workflow.name, data=parsed.model_dump(mode="json"))
    )
    task = celery_app.send_task("process_incoming_event", args=[str(event.id)])
    return EventAccepted(event_id=event.id, task_id=task.id, workflow=workflow.name)


@router.get("/{event_id}", response_model=EventStatus)
def get_event(event_id: UUID, session: Session = Depends(db_session)) -> EventStatus:
    event = GenericRepository(session=session, model=Event).get(event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventStatus(
        event_id=event.id,
        workflow=event.workflow_type,
        status=event.status,
        error=event.error,
        task_context=event.task_context,
    )
