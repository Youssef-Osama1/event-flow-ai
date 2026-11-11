import asyncio
from abc import ABC, abstractmethod

from eventflow.core.nodes.base import Node
from eventflow.core.task import TaskContext


class ConcurrentNode(Node, ABC):
    async def execute_nodes_concurrently(self, task_context: TaskContext) -> None:
        node_config = task_context.metadata["nodes"][type(self)]
        try:
            async with asyncio.TaskGroup() as group:
                for node_class in node_config.concurrent_nodes:
                    group.create_task(self._run_child(node_class, task_context))
        except ExceptionGroup as group_error:
            if len(group_error.exceptions) == 1:
                raise group_error.exceptions[0] from group_error
            raise

    async def _run_child(self, node_class: type[Node], task_context: TaskContext) -> None:
        node = node_class(task_context=task_context)
        try:
            await node.process(task_context)
        finally:
            await node.cleanup()

    @abstractmethod
    async def process(self, task_context: TaskContext) -> TaskContext:
        raise NotImplementedError
