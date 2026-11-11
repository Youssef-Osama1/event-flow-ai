import logging
from enum import Enum

from pydantic import BaseModel

from eventflow.core.nodes.base import Node
from eventflow.core.task import TaskContext
from eventflow.workflows.examples.quickstart.schema import SupportTicketEventSchema

logger = logging.getLogger(__name__)


class TicketAction(str, Enum):
    CLOSED_AS_SPAM = "closed_as_spam"
    ESCALATED = "escalated"
    INVOICE_SENT = "invoice_sent"
    INFO_REQUESTED = "info_requested"
    REPLIED = "replied"


class ActionResult(BaseModel):
    action: TicketAction
    ticket_id: str
    detail: str


class _ActionNode(Node):
    action: TicketAction
    detail: str

    async def process(self, task_context: TaskContext) -> TaskContext:
        event: SupportTicketEventSchema = task_context.event
        result = ActionResult(
            action=self.action, ticket_id=str(event.ticket_id), detail=self.describe(task_context)
        )
        logger.info("Ticket %s: %s", result.ticket_id, result.action.value)
        self.save_output(result)
        return task_context

    def describe(self, task_context: TaskContext) -> str:
        return self.detail


class CloseTicketNode(_ActionNode):
    action = TicketAction.CLOSED_AS_SPAM
    detail = "Closed without reply"

    async def process(self, task_context: TaskContext) -> TaskContext:
        await super().process(task_context)
        task_context.stop_workflow()
        return task_context


class EscalateTicketNode(_ActionNode):
    action = TicketAction.ESCALATED
    detail = "Assigned to the human support queue"


class SendInvoiceNode(_ActionNode):
    action = TicketAction.INVOICE_SENT
    detail = "Invoice lookup requested from the billing system"


class RequestInfoNode(_ActionNode):
    action = TicketAction.INFO_REQUESTED
    detail = "Asked the customer for missing details"

    def describe(self, task_context: TaskContext) -> str:
        from eventflow.workflows.examples.quickstart.nodes.check_completeness_node import (
            CheckCompletenessNode,
        )

        completeness: CheckCompletenessNode.OutputType | None = self.get_output(
            CheckCompletenessNode
        )
        if completeness and completeness.missing_details:
            return f"{self.detail}: {', '.join(completeness.missing_details)}"
        return self.detail


class SendReplyNode(_ActionNode):
    action = TicketAction.REPLIED

    def describe(self, task_context: TaskContext) -> str:
        from eventflow.workflows.examples.quickstart.nodes.draft_reply_node import DraftReplyNode

        draft: DraftReplyNode.OutputType | None = self.get_output(DraftReplyNode)
        return draft.reply if draft else "No draft available"
