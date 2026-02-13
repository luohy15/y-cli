"""Bot configuration service."""

from typing import List, Optional
from storage.entity.dto import BotConfig, DEFAULT_OPENROUTER_CONFIG
from storage.database.base import get_db
from storage.repository import bot_config as bot_repo


def list_configs() -> List[BotConfig]:
    with get_db() as session:
        return bot_repo.list_configs(session)


def get_config(name: str = "default") -> Optional[BotConfig]:
    with get_db() as session:
        return bot_repo.get_config(session, name)


def add_config(config: BotConfig) -> BotConfig:
    if config.name == "default":
        if config.openrouter_config is None:
            config.openrouter_config = DEFAULT_OPENROUTER_CONFIG.copy()
    with get_db() as session:
        return bot_repo.add_config(session, config)


def delete_config(name: str) -> bool:
    if name == "default":
        return False
    with get_db() as session:
        return bot_repo.delete_config(session, name)
