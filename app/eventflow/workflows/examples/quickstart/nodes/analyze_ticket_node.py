from eventflow.core.nodes.concurrent import ConcurrentNode
from eventflow.core.task import TaskContext


class AnalyzeTicketNode(ConcurrentNode):
    async def process(self, task_context: TaskContext) -> TaskContext:
        await self.execute_nodes_concurrently(task_context)
        return task_context
