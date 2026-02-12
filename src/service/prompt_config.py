"""Prompt configuration service."""

from typing import List, Optional
from entity.dto import PromptConfig
from entity.preset import deep_research_prompt
from config.database import get_db
from repository import prompt_config as prompt_repo


def init():
    _ensure_default_prompt()
    _auto_migrate()


def _auto_migrate():
    from config import config
    with get_db() as session:
        prompt_repo.auto_migrate_jsonl(session, config['sqlite_file'])


def _ensure_default_prompt() -> None:
    if not get_prompt("deep-research"):
        add_prompt(PromptConfig(
            name="deep-research",
            content=deep_research_prompt,
            description="deep research prompt"
        ))


def list_prompts() -> List[PromptConfig]:
    with get_db() as session:
        return prompt_repo.list_configs(session)


def get_prompt(name: str = "default") -> Optional[PromptConfig]:
    with get_db() as session:
        return prompt_repo.get_config(session, name)


def add_prompt(config: PromptConfig) -> PromptConfig:
    with get_db() as session:
        return prompt_repo.add_config(session, config)


def delete_prompt(name: str) -> bool:
    with get_db() as session:
        return prompt_repo.delete_config(session, name)
