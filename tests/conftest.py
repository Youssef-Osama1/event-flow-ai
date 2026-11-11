import os

os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("ENABLE_TRACING", "false")
os.environ.setdefault("DATABASE_URL_OVERRIDE", "sqlite+pysqlite:///:memory:")

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from eventflow.core.nodes.agent import AgentNode

EXAMPLES_DIR = (
    Path(__file__).resolve().parents[1]
    / "app/eventflow/workflows/examples/quickstart/request_examples"
)


def load_example(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from eventflow.config import get_settings

    monkeypatch.setattr(get_settings(), "api_key", None)
    monkeypatch.setattr(get_settings(), "enable_tracing", False)


@pytest.fixture
def fake_llm() -> Iterator[Callable[[type[AgentNode], dict[str, Any]], None]]:
    applied: list[type[AgentNode]] = []

    def apply(node_class: type[AgentNode], payload: dict[str, Any]) -> None:
        def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            tool = info.output_tools[0]
            return ModelResponse(parts=[ToolCallPart(tool_name=tool.name, args=payload)])

        node_class.model_override = FunctionModel(respond)
        applied.append(node_class)

    yield apply
    for node_class in applied:
        node_class.model_override = None
