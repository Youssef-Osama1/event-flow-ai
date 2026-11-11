import json
import logging
import sys
from pathlib import Path

from eventflow.workflows.workflow_registry import WorkflowRegistry

EXAMPLES_DIR = (
    Path(__file__).resolve().parents[1]
    / "app/eventflow/workflows/examples/quickstart/request_examples"
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

example = sys.argv[1] if len(sys.argv) > 1 else "invoice"
event = json.loads((EXAMPLES_DIR / f"{example}.json").read_text(encoding="utf-8"))

workflow = WorkflowRegistry.QUICKSTART.value(enable_tracing=False)
task_context = workflow.run(event)

print(json.dumps(task_context.to_storage(), indent=2, default=str))
