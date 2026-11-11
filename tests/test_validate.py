import pytest
from pydantic import BaseModel

from eventflow.core.nodes.base import Node
from eventflow.core.schema import NodeConfig, WorkflowSchema
from eventflow.core.task import TaskContext
from eventflow.core.validate import WorkflowValidationError, WorkflowValidator


class Event(BaseModel):
    text: str


class A(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        return task_context


class B(A):
    pass


class C(A):
    pass


def schema(nodes: list[NodeConfig], start: type = A) -> WorkflowSchema:
    return WorkflowSchema(event_schema=Event, start=start, nodes=nodes)


def test_valid_linear_workflow_passes() -> None:
    WorkflowValidator(
        schema([NodeConfig(node=A, connections=[B]), NodeConfig(node=B, connections=[C])])
    ).validate()


def test_start_without_config_fails() -> None:
    with pytest.raises(WorkflowValidationError, match="Start node"):
        WorkflowValidator(schema([NodeConfig(node=B)], start=A)).validate()


def test_cycle_fails() -> None:
    nodes = [NodeConfig(node=A, connections=[B]), NodeConfig(node=B, connections=[A])]
    with pytest.raises(WorkflowValidationError, match="Cycle"):
        WorkflowValidator(schema(nodes)).validate()


def test_non_router_with_two_connections_fails() -> None:
    with pytest.raises(WorkflowValidationError, match="not a router"):
        WorkflowValidator(schema([NodeConfig(node=A, connections=[B, C])])).validate()


def test_router_with_two_connections_passes() -> None:
    WorkflowValidator(schema([NodeConfig(node=A, connections=[B, C], is_router=True)])).validate()


def test_unreachable_node_fails() -> None:
    nodes = [NodeConfig(node=A), NodeConfig(node=B, connections=[C])]
    with pytest.raises(WorkflowValidationError, match="not reachable"):
        WorkflowValidator(schema(nodes)).validate()


def test_duplicate_node_fails() -> None:
    with pytest.raises(WorkflowValidationError, match="more than once"):
        WorkflowValidator(schema([NodeConfig(node=A), NodeConfig(node=A)])).validate()
