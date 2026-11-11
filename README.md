# event-flow-ai

Event-driven framework for AI workflows. Events arrive over HTTP, are stored in Postgres, queued with Celery,
and processed by a workflow: a graph of small nodes that share one task context.

```
POST /events/{workflow} -> Postgres -> Redis -> Celery worker -> Workflow -> result saved on the event
```

## Stack

FastAPI, Celery + Redis, Postgres (pgvector), SQLAlchemy + Alembic, pydantic-ai (Groq by default), Jinja2
prompts, optional Langfuse tracing, Docker Compose.

## Example

`workflows/examples/quickstart` triages a support ticket: three LLM checks run in parallel, a Python router
picks one action (close spam, escalate, send invoice, ask for details, or draft a reply).

## Run

```bash
uv sync
cp .env.example .env                        # add GROQ_API_KEY
uv run pytest
uv run playground/quickstart.py invoice
uv run evals/quickstart_eval.py
```

Full stack:

```bash
cp docker/.env.example docker/.env
cd docker && ./start.sh
curl -X POST localhost:8080/events/quickstart -H "Content-Type: application/json" \
  -d @../app/eventflow/workflows/examples/quickstart/request_examples/invoice.json
```

## Add a workflow

Create `app/eventflow/workflows/<name>/` with `schema.py`, `workflow.py`, `nodes/`, `prompts/`, and
`request_examples/`, then register it in `workflows/workflow_registry.py`.
