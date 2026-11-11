import asyncio
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel
from pydantic_ai.models.test import TestModel

from eventflow.core.nodes.agent import AgentConfig
from eventflow.core.nodes.agent_streaming_node import AgentStreamingNode
from eventflow.core.schema import NodeConfig, WorkflowSchema
from eventflow.core.task import TaskContext
from eventflow.core.workflow import Workflow


class ChatEvent(BaseModel):
    message: str


class Reply(BaseModel):
    text: str


class EchoStreamingNode(AgentStreamingNode):
    def get_agent_config(self) -> AgentConfig:
        return AgentConfig(output_type=str, model=TestModel(custom_output_text="hello there friend"))

    async def process(self, task_context: TaskContext) -> AsyncIterator[dict[str, Any]]:
        text = ""
        async with self.agent.run_stream(user_prompt=task_context.event.message) as result:
            async for chunk in self.stream_text_deltas(result, debounce_by=None):
                text += chunk["choices"][0]["delta"]["content"]
                yield chunk
        self.save_output(Reply(text=text))
        yield self.final_chunk()


class ChatWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        event_schema=ChatEvent,
        start=EchoStreamingNode,
        nodes=[NodeConfig(node=EchoStreamingNode)],
    )


async def collect() -> list[dict[str, Any]]:
    return [chunk async for chunk in ChatWorkflow().run_stream_async({"message": "hi"})]


def test_stream_yields_deltas_and_final_chunk() -> None:
    chunks = asyncio.run(collect())
    text = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
    assert text == "hello there friend"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert all(c["object"] == "chat.completion.chunk" for c in chunks)


def test_streaming_node_saves_output_when_run_normally() -> None:
    context = ChatWorkflow().run({"message": "hi"})
    assert context.nodes["EchoStreamingNode"].text == "hello there friend"
