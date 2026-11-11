import asyncio

import pytest
from pydantic import BaseModel

from eventflow.core.nodes.base import Node
from eventflow.core.nodes.concurrent import ConcurrentNode
from eventflow.core.nodes.router import BaseRouter, RouterNode
from eventflow.core.schema import NodeConfig, WorkflowSchema
from eventflow.core.task import TaskContext
from eventflow.core.workflow import Workflow

cleaned: list[str] = []
order: list[str] = []


class Event(BaseModel):
    value: int


class Doubled(BaseModel):
    result: int


class DoubleNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        order.append(self.node_name)
        self.save_output(Doubled(result=task_context.event.value * 2))
        return task_context

    async def cleanup(self) -> None:
        cleaned.append(self.node_name)


class SlowChild(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        await asyncio.sleep(0.05)
        self.save_output(Doubled(result=1))
        return task_context

    async def cleanup(self) -> None:
        cleaned.append(self.node_name)


class OtherSlowChild(SlowChild):
    pass


class FailingChild(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        raise ValueError("boom")

    async def cleanup(self) -> None:
        cleaned.append(self.node_name)


class FanOutNode(ConcurrentNode):
    async def process(self, task_context: TaskContext) -> TaskContext:
        await self.execute_nodes_concurrently(task_context)
        return task_context


class BigNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        order.append(self.node_name)
        return task_context


class SmallNode(BigNode):
    pass


class StopNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        order.append(self.node_name)
        task_context.stop_workflow()
        return task_context


class IsBig(RouterNode):
    def determine_next_node(self, task_context: TaskContext) -> type[Node] | None:
        doubled: Doubled | None = self.get_output(DoubleNode)
        return BigNode if doubled and doubled.result > 10 else None


class SizeRouter(BaseRouter):
    def __init__(self, task_context: TaskContext | None = None):
        super().__init__(task_context=task_context)
        self.routes = [IsBig()]
        self.fallback = SmallNode


class RoutingWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        event_schema=Event,
        start=DoubleNode,
        nodes=[
            NodeConfig(node=DoubleNode, connections=[SizeRouter]),
            NodeConfig(node=SizeRouter, connections=[BigNode, SmallNode], is_router=True),
        ],
    )


class ConcurrentWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        event_schema=Event,
        start=FanOutNode,
        nodes=[NodeConfig(node=FanOutNode, concurrent_nodes=[SlowChild, OtherSlowChild])],
    )


class FailingConcurrentWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        event_schema=Event,
        start=FanOutNode,
        nodes=[NodeConfig(node=FanOutNode, concurrent_nodes=[FailingChild, SlowChild])],
    )


class StoppingWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        event_schema=Event,
        start=StopNode,
        nodes=[NodeConfig(node=StopNode, connections=[BigNode])],
    )


class ChildWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        event_schema=Event, start=BigNode, nodes=[NodeConfig(node=BigNode)]
    )


class DelegateNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        await ChildWorkflow().run_async(context=task_context)
        return task_context


class ParentWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        event_schema=Event,
        start=DoubleNode,
        nodes=[
            NodeConfig(node=DoubleNode, connections=[DelegateNode]),
            NodeConfig(node=DelegateNode, connections=[SmallNode]),
        ],
    )


@pytest.fixture(autouse=True)
def reset() -> None:
    cleaned.clear()
    order.clear()


def test_router_takes_matching_rule() -> None:
    context = RoutingWorkflow().run({"value": 6})
    assert order == ["DoubleNode", "BigNode"]
    assert context.nodes["SizeRouter"] == {"rule": "IsBig", "next_node": "BigNode"}


def test_router_uses_fallback() -> None:
    context = RoutingWorkflow().run({"value": 2})
    assert order == ["DoubleNode", "SmallNode"]
    assert context.nodes["SizeRouter"]["rule"] == "fallback"


def test_invalid_event_raises() -> None:
    with pytest.raises(Exception):
        RoutingWorkflow().run({"value": "not a number"})


def test_cleanup_runs_for_every_node() -> None:
    RoutingWorkflow().run({"value": 1})
    assert "DoubleNode" in cleaned


def test_concurrent_children_run_together_and_clean_up() -> None:
    loop_start = asyncio.new_event_loop()
    started = loop_start.time()
    context = loop_start.run_until_complete(ConcurrentWorkflow().run_async({"value": 1}))
    elapsed = loop_start.time() - started
    loop_start.close()
    assert set(context.nodes) == {"SlowChild", "OtherSlowChild"}
    assert elapsed < 0.09
    assert set(cleaned) == {"SlowChild", "OtherSlowChild"}


def test_concurrent_failure_cancels_and_cleans_siblings() -> None:
    with pytest.raises(ValueError, match="boom"):
        FailingConcurrentWorkflow().run({"value": 1})
    assert set(cleaned) == {"FailingChild", "SlowChild"}


def test_stop_workflow_halts_after_current_node() -> None:
    context = StoppingWorkflow().run({"value": 1})
    assert order == ["StopNode"]
    assert context.should_stop is True


def test_nested_workflow_shares_context_and_restores_registry() -> None:
    context = ParentWorkflow().run({"value": 3})
    assert order == ["DoubleNode", "BigNode", "SmallNode"]
    assert DoubleNode in context.metadata["nodes"]
    assert context.nodes["DoubleNode"].result == 6


def test_to_storage_drops_registry_and_dumps_models() -> None:
    context = RoutingWorkflow().run({"value": 6})
    stored = context.to_storage()
    assert "nodes" not in stored["metadata"]
    assert stored["nodes"]["DoubleNode"] == {"result": 12}
    assert stored["event"] == {"value": 6}


def test_update_node_merges() -> None:
    context = TaskContext(event={})
    context.update_node("X", a=1)
    context.update_node("X", b=2)
    assert context.nodes["X"] == {"a": 1, "b": 2}


def test_node_without_context_raises() -> None:
    with pytest.raises(RuntimeError, match="no task context"):
        DoubleNode().save_output(Doubled(result=1))
