from abc import ABC, abstractmethod
from typing import Any

from eventflow.core.nodes.base import Node
from eventflow.core.task import TaskContext


class RouterNode(ABC):
    def __init__(self) -> None:
        self.task_context: TaskContext | None = None

    @property
    def node_name(self) -> str:
        return type(self).__name__

    def get_output(self, node_class: type[Node]) -> Any:
        if self.task_context is None:
            raise RuntimeError(f"{self.node_name} has no task context bound")
        return self.task_context.nodes.get(node_class.__name__)

    @abstractmethod
    def determine_next_node(self, task_context: TaskContext) -> type[Node] | None:
        raise NotImplementedError


class BaseRouter(Node):
    routes: list[RouterNode]
    fallback: type[Node] | None = None

    async def process(self, task_context: TaskContext) -> TaskContext:
        return task_context

    def route(self, task_context: TaskContext) -> type[Node] | None:
        for rule in self.routes:
            rule.task_context = task_context
            next_node = rule.determine_next_node(task_context)
            if next_node is not None:
                task_context.nodes[self.node_name] = {
                    "rule": rule.node_name,
                    "next_node": next_node.__name__,
                }
                return next_node
        task_context.nodes[self.node_name] = {
            "rule": "fallback",
            "next_node": self.fallback.__name__ if self.fallback else None,
        }
        return self.fallback
