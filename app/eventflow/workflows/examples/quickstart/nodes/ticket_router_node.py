from eventflow.core.nodes.base import Node
from eventflow.core.nodes.router import BaseRouter, RouterNode
from eventflow.core.task import TaskContext
from eventflow.workflows.examples.quickstart.nodes.action_nodes import (
    CloseTicketNode,
    EscalateTicketNode,
    RequestInfoNode,
    SendInvoiceNode,
)
from eventflow.workflows.examples.quickstart.nodes.check_completeness_node import (
    CheckCompletenessNode,
)
from eventflow.workflows.examples.quickstart.nodes.classify_ticket_node import (
    ClassifyTicketNode,
    TicketCategory,
)
from eventflow.workflows.examples.quickstart.nodes.detect_spam_node import DetectSpamNode
from eventflow.workflows.examples.quickstart.nodes.draft_reply_node import DraftReplyNode

SPAM_CONFIDENCE_THRESHOLD = 0.8


class SpamRouter(RouterNode):
    def determine_next_node(self, task_context: TaskContext) -> type[Node] | None:
        spam: DetectSpamNode.OutputType | None = self.get_output(DetectSpamNode)
        if spam and spam.is_spam and spam.confidence > SPAM_CONFIDENCE_THRESHOLD:
            return CloseTicketNode
        return None


class EscalationRouter(RouterNode):
    def determine_next_node(self, task_context: TaskContext) -> type[Node] | None:
        classification: ClassifyTicketNode.OutputType | None = self.get_output(ClassifyTicketNode)
        if classification is None:
            return EscalateTicketNode
        if classification.category.needs_human or classification.flag_for_human:
            return EscalateTicketNode
        return None


class InvoiceRouter(RouterNode):
    def determine_next_node(self, task_context: TaskContext) -> type[Node] | None:
        classification: ClassifyTicketNode.OutputType | None = self.get_output(ClassifyTicketNode)
        if classification and classification.category is TicketCategory.INVOICE_REQUEST:
            return SendInvoiceNode
        return None


class MissingInfoRouter(RouterNode):
    def determine_next_node(self, task_context: TaskContext) -> type[Node] | None:
        completeness: CheckCompletenessNode.OutputType | None = self.get_output(
            CheckCompletenessNode
        )
        if completeness and not completeness.is_complete:
            return RequestInfoNode
        return None


class TicketRouterNode(BaseRouter):
    def __init__(self, task_context: TaskContext | None = None):
        super().__init__(task_context=task_context)
        self.routes = [SpamRouter(), EscalationRouter(), InvoiceRouter(), MissingInfoRouter()]
        self.fallback = DraftReplyNode
