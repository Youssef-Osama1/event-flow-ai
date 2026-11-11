from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from eventflow.core.nodes.agent import AgentNode
from eventflow.core.task import TaskContext


class AgentStreamingNode(AgentNode, ABC):
    @abstractmethod
    def process(self, task_context: TaskContext) -> AsyncIterator[dict[str, Any]]:
        raise NotImplementedError

    async def stream_text_deltas(
        self, stream_result: Any, debounce_by: float | None = 0.01
    ) -> AsyncIterator[dict[str, Any]]:
        async for delta in stream_result.stream_text(delta=True, debounce_by=debounce_by):
            if delta:
                yield self.completion_chunk(delta)

    async def stream_structured_deltas(
        self, stream_result: Any, debounce_by: float | None = 0.01
    ) -> AsyncIterator[dict[str, Any]]:
        async for partial in stream_result.stream_output(debounce_by=debounce_by):
            snapshot = partial.model_dump() if isinstance(partial, BaseModel) else partial
            if snapshot:
                yield self.completion_chunk(snapshot)

    def completion_chunk(self, content: Any, finish_reason: str | None = None) -> dict[str, Any]:
        return {
            "object": "chat.completion.chunk",
            "model": self.node_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": content},
                    "finish_reason": finish_reason,
                }
            ],
        }

    def final_chunk(self) -> dict[str, Any]:
        chunk = self.completion_chunk("", finish_reason="stop")
        chunk["choices"][0]["delta"] = {}
        return chunk
