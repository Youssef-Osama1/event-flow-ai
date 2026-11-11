import asyncio
import logging
from abc import ABC
from collections.abc import AsyncIterator
from typing import Any, ClassVar

from pydantic import BaseModel

from eventflow.core import tracing
from eventflow.core.nodes.agent_streaming_node import AgentStreamingNode
from eventflow.core.nodes.base import Node
from eventflow.core.nodes.router import BaseRouter
from eventflow.core.schema import NodeConfig, WorkflowSchema
from eventflow.core.task import TaskContext
from eventflow.core.validate import WorkflowValidator

logger = logging.getLogger(__name__)


class Workflow(ABC):
    workflow_schema: ClassVar[WorkflowSchema]

    def __init__(self, enable_tracing: bool = False):
        WorkflowValidator(self.workflow_schema).validate()
        self.enable_tracing = enable_tracing
        self.node_registry: dict[type, NodeConfig] = {
            config.node: config for config in self.workflow_schema.nodes
        }
        self.langfuse = tracing.get_langfuse() if enable_tracing else None

    @property
    def name(self) -> str:
        return type(self).__name__

    def run(
        self, event: dict[str, Any] | BaseModel | None = None, *, context: TaskContext | None = None
    ) -> TaskContext:
        return asyncio.run(self.run_async(event, context=context))

    async def run_async(
        self, event: dict[str, Any] | BaseModel | None = None, *, context: TaskContext | None = None
    ) -> TaskContext:
        task_context, parent_registry = self._enter(event, context)
        try:
            with tracing.span(self.langfuse, self.name, input=self._trace_input(task_context)):
                task_context.trace_id = task_context.trace_id or tracing.current_trace_id(
                    self.langfuse
                )
                current = self.workflow_schema.start
                while current is not None and not task_context.should_stop:
                    node = current(task_context=task_context)
                    logger.info("%s: running %s", self.name, node.node_name)
                    with tracing.span(self.langfuse, node.node_name):
                        try:
                            if isinstance(node, AgentStreamingNode):
                                async for _ in node.process(task_context):
                                    pass
                            else:
                                await node.process(task_context)
                        finally:
                            await node.cleanup()
                    current = self._next_node(node, task_context)
            return task_context
        finally:
            self._exit(task_context, parent_registry)
            tracing.flush(self.langfuse)

    async def run_stream_async(
        self, event: dict[str, Any] | BaseModel | None = None, *, context: TaskContext | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        task_context, parent_registry = self._enter(event, context)
        try:
            with tracing.span(self.langfuse, self.name, input=self._trace_input(task_context)):
                current = self.workflow_schema.start
                while current is not None and not task_context.should_stop:
                    node = current(task_context=task_context)
                    with tracing.span(self.langfuse, node.node_name):
                        try:
                            if isinstance(node, AgentStreamingNode):
                                async for chunk in node.process(task_context):
                                    yield chunk
                            else:
                                await node.process(task_context)
                        finally:
                            await node.cleanup()
                    current = self._next_node(node, task_context)
        finally:
            self._exit(task_context, parent_registry)
            tracing.flush(self.langfuse)

    def _enter(
        self, event: dict[str, Any] | BaseModel | None, context: TaskContext | None
    ) -> tuple[TaskContext, Any]:
        if context is not None:
            parent_registry = context.metadata.get("nodes")
            context.should_stop = False
        else:
            if event is None:
                raise ValueError("Either event or context is required")
            parsed = self._parse_event(event)
            context = TaskContext(event=parsed)
            parent_registry = None
        context.metadata["nodes"] = self.node_registry
        context.metadata.setdefault("workflow", self.name)
        return context, parent_registry

    def _exit(self, task_context: TaskContext, parent_registry: Any) -> None:
        if parent_registry is not None:
            task_context.metadata["nodes"] = parent_registry

    def _parse_event(self, event: dict[str, Any] | BaseModel) -> BaseModel:
        event_schema = self.workflow_schema.event_schema
        if isinstance(event, event_schema):
            return event
        if isinstance(event, BaseModel):
            event = event.model_dump()
        return event_schema.model_validate(event)

    def _next_node(self, node: Node, task_context: TaskContext) -> type[Node] | None:
        config = self.node_registry.get(type(node))
        if isinstance(node, BaseRouter):
            next_node = node.route(task_context)
            if next_node is not None and config and next_node not in config.connections:
                raise RuntimeError(
                    f"{node.node_name} routed to {next_node.__name__}, "
                    "which is not listed in its connections"
                )
            return next_node
        if config is None or not config.connections:
            return None
        return config.connections[0]

    def _trace_input(self, task_context: TaskContext) -> Any:
        event = task_context.event
        return event.model_dump(mode="json") if isinstance(event, BaseModel) else event
