from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

from eventflow.core.task import TaskContext

NodeT = TypeVar("NodeT", bound="Node")


class Node(ABC):
    class OutputType(BaseModel):
        pass

    def __init__(self, task_context: TaskContext | None = None):
        self.task_context = task_context

    @property
    def node_name(self) -> str:
        return type(self).__name__

    def bind(self, task_context: TaskContext) -> None:
        self.task_context = task_context

    def save_output(self, output: BaseModel) -> None:
        self._require_context().nodes[self.node_name] = output

    def get_output(self, node_class: type["Node"]) -> Any:
        return self._require_context().nodes.get(node_class.__name__)

    @abstractmethod
    async def process(self, task_context: TaskContext) -> TaskContext:
        raise NotImplementedError

    async def cleanup(self) -> None:
        return None

    def _require_context(self) -> TaskContext:
        if self.task_context is None:
            raise RuntimeError(f"{self.node_name} has no task context bound")
        return self.task_context
