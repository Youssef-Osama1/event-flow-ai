import logging
from uuid import UUID

from pydantic_ai.exceptions import ModelHTTPError
from sqlalchemy.orm import Session

from eventflow.config import get_settings
from eventflow.database.event import Event
from eventflow.database.repository import GenericRepository
from eventflow.database.session import get_session_factory
from eventflow.worker.config import celery_app
from eventflow.workflows.workflow_registry import WorkflowRegistry

logger = logging.getLogger(__name__)

class TransientWorkflowError(RuntimeError):
    pass


def is_transient(error: BaseException) -> bool:
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True
    if isinstance(error, ModelHTTPError):
        return error.status_code == 429 or error.status_code >= 500
    if isinstance(error, BaseExceptionGroup):
        return all(is_transient(inner) for inner in error.exceptions)
    return False


def run_event(session: Session, event_id: str) -> Event | None:
    repository = GenericRepository(session=session, model=Event)
    event = repository.get(UUID(event_id))
    if event is None:
        logger.error("Event %s not found", event_id)
        return None
    if event.status == "completed":
        logger.info("Event %s already completed, skipping", event_id)
        return event

    repository.update(event, status="running", error=None)
    workflow_class = WorkflowRegistry[event.workflow_type].value
    workflow = workflow_class(enable_tracing=get_settings().enable_tracing)
    try:
        task_context = workflow.run(event.data)
    except Exception as exc:
        if is_transient(exc):
            repository.update(event, status="queued", error=f"Retrying: {type(exc).__name__}")
            raise TransientWorkflowError(str(exc)) from exc
        logger.exception("Workflow failed for event %s", event_id)
        return repository.update(event, status="failed", error=f"{type(exc).__name__}: {exc}")
    return repository.update(event, status="completed", task_context=task_context.to_storage())


@celery_app.task(
    name="process_incoming_event",
    autoretry_for=(TransientWorkflowError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
)
def process_incoming_event(event_id: str) -> None:
    with get_session_factory()() as session:
        run_event(session, event_id)
