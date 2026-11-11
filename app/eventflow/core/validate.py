from eventflow.core.schema import WorkflowSchema


class WorkflowValidationError(ValueError):
    pass


class WorkflowValidator:
    def __init__(self, workflow_schema: WorkflowSchema):
        self.workflow_schema = workflow_schema
        self.graph = {
            config.node: list(config.connections) for config in workflow_schema.nodes
        }

    def validate(self) -> None:
        self._validate_start()
        self._validate_unique_nodes()
        self._validate_routers()
        self._validate_acyclic()
        self._validate_reachability()

    def _validate_start(self) -> None:
        if self.workflow_schema.start not in self.graph:
            name = self.workflow_schema.start.__name__
            raise WorkflowValidationError(f"Start node {name} has no NodeConfig")

    def _validate_unique_nodes(self) -> None:
        seen = set()
        for config in self.workflow_schema.nodes:
            if config.node in seen:
                raise WorkflowValidationError(
                    f"Node {config.node.__name__} is configured more than once"
                )
            seen.add(config.node)

    def _validate_routers(self) -> None:
        for config in self.workflow_schema.nodes:
            if len(config.connections) > 1 and not config.is_router:
                raise WorkflowValidationError(
                    f"Node {config.node.__name__} has {len(config.connections)} connections "
                    "but is not a router"
                )

    def _validate_acyclic(self) -> None:
        visiting: set[type] = set()
        done: set[type] = set()

        def visit(node: type) -> None:
            if node in done:
                return
            if node in visiting:
                raise WorkflowValidationError(f"Cycle detected at node {node.__name__}")
            visiting.add(node)
            for child in self.graph.get(node, []):
                visit(child)
            visiting.remove(node)
            done.add(node)

        for node in self.graph:
            visit(node)

    def _validate_reachability(self) -> None:
        reachable: set[type] = set()
        stack = [self.workflow_schema.start]
        while stack:
            node = stack.pop()
            if node in reachable:
                continue
            reachable.add(node)
            stack.extend(self.graph.get(node, []))
        unreachable = [node.__name__ for node in self.graph if node not in reachable]
        if unreachable:
            raise WorkflowValidationError(
                f"Nodes not reachable from start: {', '.join(sorted(unreachable))}"
            )
