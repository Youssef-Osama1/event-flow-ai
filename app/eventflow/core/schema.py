from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    node: type[Any]
    connections: list[type[Any]] = Field(default_factory=list)
    is_router: bool = False
    description: str | None = None
    concurrent_nodes: list[type[Any]] = Field(default_factory=list)


class WorkflowSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    description: str | None = None
    event_schema: type[BaseModel]
    start: type[Any]
    nodes: list[NodeConfig] = Field(default_factory=list)
