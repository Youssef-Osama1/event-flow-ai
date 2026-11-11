from enum import Enum

from eventflow.workflows.examples.quickstart.workflow import SupportTicketWorkflow


class WorkflowRegistry(Enum):
    QUICKSTART = SupportTicketWorkflow
