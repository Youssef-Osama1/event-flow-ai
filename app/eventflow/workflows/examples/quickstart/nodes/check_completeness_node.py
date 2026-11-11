from pathlib import Path

from pydantic import Field

from eventflow.core.nodes.agent import AgentConfig, AgentNode
from eventflow.core.task import TaskContext
from eventflow.services.prompt_loader import PromptManager
from eventflow.workflows.examples.quickstart.schema import SupportTicketEventSchema

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class CheckCompletenessNode(AgentNode):
    class OutputType(AgentNode.OutputType):
        reasoning: str
        is_complete: bool
        missing_details: list[str] = Field(default_factory=list)

    def get_agent_config(self) -> AgentConfig:
        return AgentConfig(
            instructions=PromptManager.get_prompt("check_completeness", prompts_dir=PROMPTS_DIR),
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
