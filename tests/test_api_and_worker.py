from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from eventflow.api import events as events_module
from eventflow.api.main import app
from eventflow.config import get_settings
from eventflow.database.event import Event
from eventflow.database.session import Base, db_session
from eventflow.worker import tasks
from tests.conftest import load_example


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def sent_tasks(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[Any]]]:
    sent: list[tuple[str, list[Any]]] = []

    def fake_send_task(name: str, args: list[Any]) -> SimpleNamespace:
        sent.append((name, args))
        return SimpleNamespace(id="task-123")

    monkeypatch.setattr(events_module.celery_app, "send_task", fake_send_task)
    return sent


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[db_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_valid_event_is_stored_and_queued(
    client: TestClient, sent_tasks: list, session_factory: sessionmaker[Session]
) -> None:
    response = client.post("/events/quickstart", json=load_example("invoice"))
    assert response.status_code == 202
    body = response.json()
    assert body["workflow"] == "QUICKSTART"
    assert sent_tasks == [("process_incoming_event", [body["event_id"]])]
    with session_factory() as session:
        event = session.get(Event, UUID(body["event_id"]))
        assert event.status == "queued"
        assert event.data["customer_email"] == "lena.vogel@example.com"
        assert "ticket_id" in event.data


def test_invalid_event_is_rejected_before_queueing(client: TestClient, sent_tasks: list) -> None:
    response = client.post("/events/quickstart", json={"customer_email": "not-an-email"})
    assert response.status_code == 422
    assert sent_tasks == []


def test_unknown_workflow_is_404(client: TestClient, sent_tasks: list) -> None:
    response = client.post("/events/does_not_exist", json=load_example("invoice"))
    assert response.status_code == 404
    assert sent_tasks == []


def test_api_key_is_enforced_when_configured(
    client: TestClient, sent_tasks: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "api_key", SecretStr("secret"))
    assert client.post("/events/quickstart", json=load_example("invoice")).status_code == 401
    ok = client.post(
        "/events/quickstart", json=load_example("invoice"), headers={"X-API-Key": "secret"}
    )
    assert ok.status_code == 202


def test_get_event_status(client: TestClient, sent_tasks: list) -> None:
    event_id = client.post("/events/quickstart", json=load_example("product")).json()["event_id"]
    response = client.get(f"/events/{event_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"


class FakeContext:
    def to_storage(self) -> dict[str, Any]:
        return {"nodes": {"X": {"ok": True}}}


class FakeWorkflow:
    calls = 0
    error: Exception | None = None

    def __init__(self, enable_tracing: bool = False):
        pass

    def run(self, data: dict[str, Any]) -> FakeContext:
        FakeWorkflow.calls += 1
        if FakeWorkflow.error:
            raise FakeWorkflow.error
        return FakeContext()


@pytest.fixture
def stored_event(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> tuple[Session, str]:
    FakeWorkflow.calls = 0
    FakeWorkflow.error = None
    fake_registry = {"QUICKSTART": SimpleNamespace(value=FakeWorkflow)}
    monkeypatch.setattr(tasks, "WorkflowRegistry", fake_registry)
    session = session_factory()
    event = Event(workflow_type="QUICKSTART", data={"a": 1})
    session.add(event)
    session.commit()
    return session, str(event.id)


def test_worker_completes_event(stored_event: tuple[Session, str]) -> None:
    session, event_id = stored_event
    event = tasks.run_event(session, event_id)
    assert event.status == "completed"
    assert event.task_context == {"nodes": {"X": {"ok": True}}}


def test_worker_skips_completed_event(stored_event: tuple[Session, str]) -> None:
    session, event_id = stored_event
    tasks.run_event(session, event_id)
    tasks.run_event(session, event_id)
    assert FakeWorkflow.calls == 1


def test_worker_marks_failure(stored_event: tuple[Session, str]) -> None:
    session, event_id = stored_event
    FakeWorkflow.error = ValueError("bad output")
    event = tasks.run_event(session, event_id)
    assert event.status == "failed"
    assert "bad output" in event.error


def test_worker_reraises_transient_errors_for_retry(stored_event: tuple[Session, str]) -> None:
    session, event_id = stored_event
    FakeWorkflow.error = TimeoutError("provider slow")
    with pytest.raises(tasks.TransientWorkflowError):
        tasks.run_event(session, event_id)
    assert session.get(Event, UUID(event_id)).status == "queued"


def test_rate_limit_is_transient_and_bad_request_is_not() -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    assert tasks.is_transient(ModelHTTPError(429, "m"))
    assert tasks.is_transient(ModelHTTPError(503, "m"))
    assert not tasks.is_transient(ModelHTTPError(400, "m"))
    assert not tasks.is_transient(ValueError("x"))


def test_worker_missing_event_returns_none(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        assert tasks.run_event(session, "00000000-0000-0000-0000-000000000000") is None
