from pathlib import Path

import pytest
from jinja2 import UndefinedError

from eventflow.services.prompt_loader import PromptManager


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    (tmp_path / "greet.j2").write_text(
        "---\ndescription: Greets {{ who | default('people') }}\nauthor: tests\n---\n"
        "Hello {{ name }} from {{ team | default('support') }}",
        encoding="utf-8",
    )
    return tmp_path


def test_renders_with_variables_and_defaults(prompts_dir: Path) -> None:
    assert PromptManager.get_prompt("greet", prompts_dir=prompts_dir, name="Lena") == (
        "Hello Lena from support"
    )


def test_missing_required_variable_fails_loudly(prompts_dir: Path) -> None:
    with pytest.raises(UndefinedError):
        PromptManager.get_prompt("greet", prompts_dir=prompts_dir)


def test_frontmatter_is_not_part_of_prompt(prompts_dir: Path) -> None:
    prompt = PromptManager.get_prompt("greet", prompts_dir=prompts_dir, name="x")
    assert "description" not in prompt


def test_template_info(prompts_dir: Path) -> None:
    info = PromptManager.get_template_info("greet", prompts_dir=prompts_dir)
    assert info["description"] == "Greets people"
    assert info["author"] == "tests"
    assert info["variables"] == ["name", "team"]


def test_missing_template_raises(prompts_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        PromptManager.get_prompt("nope", prompts_dir=prompts_dir)


def test_quickstart_prompts_render() -> None:
    from eventflow.workflows.examples.quickstart.nodes.classify_ticket_node import PROMPTS_DIR

    for name in ["classify_ticket", "detect_spam", "check_completeness"]:
        assert PromptManager.get_prompt(name, prompts_dir=PROMPTS_DIR)
    assert "Nordbike Support" in PromptManager.get_prompt(
        "draft_reply", prompts_dir=PROMPTS_DIR, company="Nordbike"
    )
    ticket = PromptManager.get_prompt(
        "ticket_input", prompts_dir=PROMPTS_DIR, subject="S", message="M"
    )
    assert ticket.startswith("<ticket>")
