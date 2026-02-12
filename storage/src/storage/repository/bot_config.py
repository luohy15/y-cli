"""Function-based bot config repository using SQLAlchemy sessions."""

from typing import List, Optional
from sqlalchemy.orm import Session
from storage.entity.bot_config import BotConfigEntity
from storage.entity.dto import BotConfig
from storage.repository.user import get_current_user_db_id


def _entity_to_dto(entity: BotConfigEntity) -> BotConfig:
    return BotConfig(
        name=entity.name,
        base_url=entity.base_url,
        api_key=entity.api_key,
        api_type=entity.api_type,
        model=entity.model,
        description=entity.description,
        openrouter_config=entity.openrouter_config,
        prompts=entity.prompts,
        max_tokens=entity.max_tokens,
        custom_api_path=entity.custom_api_path,
    )


def _dto_to_entity_fields(config: BotConfig) -> dict:
    return dict(
        base_url=config.base_url,
        api_key=config.api_key,
        api_type=config.api_type,
        model=config.model,
        description=config.description,
        openrouter_config=config.openrouter_config,
        prompts=config.prompts,
        max_tokens=config.max_tokens,
        custom_api_path=config.custom_api_path,
    )


def list_configs(session: Session) -> List[BotConfig]:
    user_id = get_current_user_db_id(session)
    rows = session.query(BotConfigEntity).filter_by(user_id=user_id).all()
    return [_entity_to_dto(row) for row in rows]


def get_config(session: Session, name: str) -> Optional[BotConfig]:
    user_id = get_current_user_db_id(session)
    row = session.query(BotConfigEntity).filter_by(user_id=user_id, name=name).first()
    if row:
        return _entity_to_dto(row)
    return None


def add_config(session: Session, config: BotConfig) -> BotConfig:
    user_id = get_current_user_db_id(session)
    entity = session.query(BotConfigEntity).filter_by(user_id=user_id, name=config.name).first()
    fields = _dto_to_entity_fields(config)
    if entity:
        for k, v in fields.items():
            setattr(entity, k, v)
    else:
        entity = BotConfigEntity(user_id=user_id, name=config.name, **fields)
        session.add(entity)
    session.flush()
    return config


def delete_config(session: Session, name: str) -> bool:
    user_id = get_current_user_db_id(session)
    count = session.query(BotConfigEntity).filter_by(user_id=user_id, name=name).delete()
    session.flush()
    return count > 0


