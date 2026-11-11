from enum import Enum
from pathlib import Path

from pydantic import Field

from eventflow.core.nodes.agent import AgentConfig, AgentNode
from eventflow.core.task import TaskContext
from eventflow.services.prompt_loader import PromptManager
from eventflow.workflows.examples.quickstart.schema import SupportTicketEventSchema

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class TicketCategory(str, Enum):
    ORDER_STATUS = "order_status"
    PRODUCT_QUESTION = "product_question"
    INVOICE_REQUEST = "invoice_request"
    RETURN_REQUEST = "return_request"
    WARRANTY_CLAIM = "warranty_claim"
    OTHER = "other"

    @property
    def needs_human(self) -> bool:
        return self in {TicketCategory.RETURN_REQUEST, TicketCategory.WARRANTY_CLAIM}


class ClassifyTicketNode(AgentNode):
    class OutputType(AgentNode.OutputType):
        reasoning: str = Field(description="Short explanation of the chosen category")
        category: TicketCategory
        confidence: float = Field(ge=0, le=1)
        flag_for_human: bool = Field(
            description="True for angry, legal, safety, or manipulative messages"
        )

    def get_agent_config(self) -> AgentConfig:
        return AgentConfig(
            instructions=PromptManager.get_prompt("classify_ticket", prompts_dir=PROMPTS_DIR),
            output_type=self.OutputType,
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        event: SupportTicketEventSchema = task_context.event
        result = await self.agent.run(
            user_prompt=PromptManager.get_prompt(
                "ticket_input",
                prompts_dir=PROMPTS_DIR,
                subject=event.subject,
                message=event.message,
            )
        )
        self.save_output(result.output)
        return task_context
