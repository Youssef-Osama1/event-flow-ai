from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    event: Any
    nodes: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    should_stop: bool = False
    trace_id: str | None = None

    def update_node(self, node_name: str, **kwargs: Any) -> None:
        current = self.nodes.get(node_name)
        merged = dict(current) if isinstance(current, dict) else {}
        merged.update(kwargs)
        self.nodes[node_name] = merged

    def stop_workflow(self) -> None:
        self.should_stop = True

    def to_storage(self) -> dict[str, Any]:
        return {
            "event": _dump(self.event),
            "nodes": {name: _dump(value) for name, value in self.nodes.items()},
            "metadata": {
                key: _dump(value) for key, value in self.metadata.items() if key != "nodes"
            },
            "should_stop": self.should_stop,
            "trace_id": self.trace_id,
        }


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _dump(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dump(item) for item in value]
    return value
