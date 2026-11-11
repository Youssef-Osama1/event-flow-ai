from eventflow.core.schema import NodeConfig, WorkflowSchema
from eventflow.core.workflow import Workflow
from eventflow.workflows.examples.quickstart.nodes.action_nodes import (
    CloseTicketNode,
    EscalateTicketNode,
    RequestInfoNode,
    SendInvoiceNode,
    SendReplyNode,
)
from eventflow.workflows.examples.quickstart.nodes.analyze_ticket_node import AnalyzeTicketNode
from eventflow.workflows.examples.quickstart.nodes.check_completeness_node import (
    CheckCompletenessNode,
)
from eventflow.workflows.examples.quickstart.nodes.classify_ticket_node import ClassifyTicketNode
from eventflow.workflows.examples.quickstart.nodes.detect_spam_node import DetectSpamNode
from eventflow.workflows.examples.quickstart.nodes.draft_reply_node import DraftReplyNode
from eventflow.workflows.examples.quickstart.nodes.ticket_router_node import TicketRouterNode
from eventflow.workflows.examples.quickstart.schema import SupportTicketEventSchema


class SupportTicketWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        description="Triage a Nordbike support ticket and take one action",
        event_schema=SupportTicketEventSchema,
        start=AnalyzeTicketNode,
        nodes=[
            NodeConfig(
                node=AnalyzeTicketNode,
                connections=[TicketRouterNode],
                description="Classify, spam-check, and completeness-check in parallel",
                concurrent_nodes=[ClassifyTicketNode, DetectSpamNode, CheckCompletenessNode],
            ),
            NodeConfig(
                node=TicketRouterNode,
                connections=[
                    CloseTicketNode,
                    EscalateTicketNode,
                    SendInvoiceNode,
                    RequestInfoNode,
                    DraftReplyNode,
                ],
                is_router=True,
                description="Pick exactly one action from the analysis",
            ),
            NodeConfig(
                node=DraftReplyNode,
                connections=[SendReplyNode],
                description="Draft a reply for routine questions",
            ),
        ],
    )
