from pathlib import Path

from pydantic import Field

from eventflow.core.nodes.agent import AgentConfig, AgentNode
from eventflow.core.task import TaskContext
from eventflow.services.prompt_loader import PromptManager
from eventflow.workflows.examples.quickstart.nodes.classify_ticket_node import ClassifyTicketNode
from eventflow.workflows.examples.quickstart.schema import SupportTicketEventSchema

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class DraftReplyNode(AgentNode):
    class OutputType(AgentNode.OutputType):
        reply: str = Field(description="Email reply to send to the customer")
        confidence: float = Field(ge=0, le=1)

    def get_agent_config(self) -> AgentConfig:
        return AgentConfig(
            instructions=PromptManager.get_prompt(
                "draft_reply", prompts_dir=PROMPTS_DIR, company="Nordbike"
            ),
            output_type=self.OutputType,
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        event: SupportTicketEventSchema = task_context.event
        classification: ClassifyTicketNode.OutputType | None = self.get_output(ClassifyTicketNode)
        result = await self.agent.run(
            user_prompt=PromptManager.get_prompt(
                "ticket_input",
                prompts_dir=PROMPTS_DIR,
                subject=event.subject,
                message=event.message,
                customer_name=event.customer_name,
                category=classification.category.value if classification else "other",
            )
        )
        self.save_output(result.output)
        return task_context
