import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_ai.exceptions import ModelHTTPError

from eventflow.workflows.workflow_registry import WorkflowRegistry

MAX_ATTEMPTS = 4
RATE_LIMIT_WAIT_SECONDS = 20
PAUSE_BETWEEN_CASES_SECONDS = 3

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = Path(__file__).with_name("cases.json")
EXAMPLES_DIR = ROOT / "app/eventflow/workflows/examples/quickstart/request_examples"
RESULTS_DIR = Path(__file__).with_name("results")


def load_event(case: dict[str, Any]) -> dict[str, Any]:
    if "event" in case:
        return case["event"]
    return json.loads((EXAMPLES_DIR / f"{case['example']}.json").read_text(encoding="utf-8"))


def run_workflow(event: dict[str, Any]) -> str | None:
    for attempt in range(MAX_ATTEMPTS):
        try:
            context = WorkflowRegistry.QUICKSTART.value().run(event)
            return context.nodes.get("TicketRouterNode", {}).get("next_node")
        except ModelHTTPError as exc:
            if exc.status_code != 429 or attempt == MAX_ATTEMPTS - 1:
                raise
            wait = exc.retry_after or RATE_LIMIT_WAIT_SECONDS * (attempt + 1)
            print(f"      rate limited, waiting {wait:.0f}s")
            time.sleep(wait)
    return None


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        route, error = run_workflow(load_event(case)), None
    except Exception as exc:
        route, error = None, f"{type(exc).__name__}: {str(exc)[:200]}"
    return {
        "id": case["id"],
        "expected": case["expected_route"],
        "actual": route,
        "passed": route == case["expected_route"],
        "seconds": round(time.perf_counter() - started, 2),
        "error": error,
    }


def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    results = []
    for index, case in enumerate(cases):
        if index:
            time.sleep(PAUSE_BETWEEN_CASES_SECONDS)
        result = run_case(case)
        results.append(result)
        mark = "PASS" if result["passed"] else "FAIL"
        detail = result["error"] or f"expected {result['expected']}, got {result['actual']}"
        print(f"{mark}  {result['id']:<24} {detail}", flush=True)
    passed = sum(result["passed"] for result in results)
    print(f"\nRoute accuracy: {passed}/{len(results)} ({passed / len(results):.0%})")

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (RESULTS_DIR / f"quickstart_{stamp}.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
