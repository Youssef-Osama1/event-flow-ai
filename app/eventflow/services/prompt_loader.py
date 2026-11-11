from pathlib import Path
from typing import Any

import frontmatter
from jinja2 import Environment, FileSystemLoader, StrictUndefined, meta

SHARED_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
TEMPLATE_SUFFIX = ".j2"


class PromptManager:
    @staticmethod
    def _environment(prompts_dir: Path) -> Environment:
        return Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )

    @staticmethod
    def _load(name: str, prompts_dir: Path | None) -> tuple[Path, frontmatter.Post]:
        directory = Path(prompts_dir) if prompts_dir else SHARED_PROMPTS_DIR
        path = directory / f"{name}{TEMPLATE_SUFFIX}"
        if not path.is_file():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return directory, frontmatter.load(path)

    @classmethod
    def get_prompt(
        cls, template_name: str, /, prompts_dir: Path | None = None, **variables: Any
    ) -> str:
        directory, post = cls._load(template_name, prompts_dir)
        template = cls._environment(directory).from_string(post.content)
        return template.render(**variables).strip()

    @classmethod
    def get_template_info(cls, name: str, prompts_dir: Path | None = None) -> dict[str, Any]:
        directory, post = cls._load(name, prompts_dir)
        environment = cls._environment(directory)
        variables = meta.find_undeclared_variables(environment.parse(post.content))
        rendered_metadata = {
            key: environment.from_string(value).render() if isinstance(value, str) else value
            for key, value in post.metadata.items()
        }
        return {
            "name": name,
            "description": rendered_metadata.get("description"),
            "author": rendered_metadata.get("author"),
            "variables": sorted(variables),
            "frontmatter": rendered_metadata,
        }
