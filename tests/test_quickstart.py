from collections.abc import Callable
from typing import Any

import pytest

from eventflow.core.nodes.agent import AgentNode
from eventflow.workflows.examples.quickstart.nodes.check_completeness_node import (
    CheckCompletenessNode,
)
from eventflow.workflows.examples.quickstart.nodes.classify_ticket_node import ClassifyTicketNode
from eventflow.workflows.examples.quickstart.nodes.detect_spam_node import DetectSpamNode
from eventflow.workflows.examples.quickstart.nodes.draft_reply_node import DraftReplyNode
from eventflow.workflows.workflow_registry import WorkflowRegistry
from tests.conftest import load_example

FakeLLM = Callable[[type[AgentNode], dict[str, Any]], None]


def classify(category: str, flag: bool = False, confidence: float = 0.9) -> dict[str, Any]:
    return {
        "reasoning": "test",
        "category": category,
        "confidence": confidence,
        "flag_for_human": flag,
    }


def spam(is_spam: bool, confidence: float = 0.95) -> dict[str, Any]:
    return {"reasoning": "test", "is_spam": is_spam, "confidence": confidence}


def complete(is_complete: bool = True, missing: list[str] | None = None) -> dict[str, Any]:
    return {"reasoning": "test", "is_complete": is_complete, "missing_details": missing or []}


def run(
    fake_llm: FakeLLM,
    example: str,
    classification: dict[str, Any],
    spam_result: dict[str, Any],
    completeness: dict[str, Any],
) -> Any:
    fake_llm(ClassifyTicketNode, classification)
    fake_llm(DetectSpamNode, spam_result)
    fake_llm(CheckCompletenessNode, completeness)
    fake_llm(DraftReplyNode, {"reply": "Hi Sara, size S fits you. Nordbike Support", "confidence": 0.8})
    return WorkflowRegistry.QUICKSTART.value().run(load_example(example))


def test_spam_is_closed_and_workflow_stops(fake_llm: FakeLLM) -> None:
    context = run(fake_llm, "spam", classify("other"), spam(True), complete())
    assert context.nodes["TicketRouterNode"]["next_node"] == "CloseTicketNode"
    assert context.should_stop is True


def test_low_confidence_spam_is_not_closed(fake_llm: FakeLLM) -> None:
    context = run(fake_llm, "product", classify("product_question"), spam(True, 0.6), complete())
    assert context.nodes["TicketRouterNode"]["next_node"] == "DraftReplyNode"


def test_refund_always_escalates_even_if_llm_does_not_flag(fake_llm: FakeLLM) -> None:
    context = run(fake_llm, "refund", classify("return_request", flag=False), spam(False), complete())
    assert context.nodes["TicketRouterNode"]["next_node"] == "EscalateTicketNode"


def test_llm_flag_escalates_routine_category(fake_llm: FakeLLM) -> None:
    context = run(
        fake_llm, "prompt_injection", classify("product_question", flag=True), spam(False), complete()
    )
    assert context.nodes["TicketRouterNode"]["next_node"] == "EscalateTicketNode"


def test_invoice_goes_to_invoice_node(fake_llm: FakeLLM) -> None:
    context = run(fake_llm, "invoice", classify("invoice_request"), spam(False), complete())
    assert context.nodes["TicketRouterNode"]["next_node"] == "SendInvoiceNode"
    assert context.nodes["SendInvoiceNode"].action.value == "invoice_sent"


def test_incomplete_ticket_requests_info(fake_llm: FakeLLM) -> None:
    context = run(
        fake_llm, "vague", classify("order_status"), spam(False), complete(False, ["order number"])
    )
    assert context.nodes["TicketRouterNode"]["next_node"] == "RequestInfoNode"
    assert "order number" in context.nodes["RequestInfoNode"].detail


def test_routine_question_gets_reply(fake_llm: FakeLLM) -> None:
    context = run(fake_llm, "product", classify("product_question"), spam(False), complete())
    assert context.nodes["TicketRouterNode"]["next_node"] == "DraftReplyNode"
    assert context.nodes["SendReplyNode"].action.value == "replied"
    assert "size S" in context.nodes["SendReplyNode"].detail


def test_ticket_id_comes_from_event_not_llm(fake_llm: FakeLLM) -> None:
    context = run(fake_llm, "invoice", classify("invoice_request"), spam(False), complete())
    assert context.nodes["SendInvoiceNode"].ticket_id == str(context.event.ticket_id)


@pytest.mark.parametrize(
    "name", ["invoice", "refund", "spam", "product", "vague", "prompt_injection"]
)
def test_all_examples_match_event_schema(name: str) -> None:
    schema = WorkflowRegistry.QUICKSTART.value.workflow_schema.event_schema
    schema.model_validate(load_example(name))
