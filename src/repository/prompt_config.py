"""Function-based prompt config repository using SQLAlchemy sessions."""

import json
import os
from typing import List, Optional
from sqlalchemy.orm import Session
from entity.prompt_config import PromptConfigEntity
from entity.dto import PromptConfig


def list_configs(session: Session) -> List[PromptConfig]:
    rows = session.query(PromptConfigEntity).all()
    return [PromptConfig.from_dict(json.loads(row.json_content)) for row in rows]


def get_config(session: Session, name: str) -> Optional[PromptConfig]:
    row = session.query(PromptConfigEntity).filter_by(name=name).first()
    if row:
        return PromptConfig.from_dict(json.loads(row.json_content))
    return None


def add_config(session: Session, config: PromptConfig) -> PromptConfig:
    entity = session.query(PromptConfigEntity).filter_by(name=config.name).first()
    content = json.dumps(config.to_dict(), ensure_ascii=False)
    if entity:
        entity.json_content = content
    else:
        entity = PromptConfigEntity(name=config.name, json_content=content)
        session.add(entity)
    session.flush()
    return config


def delete_config(session: Session, name: str) -> bool:
    count = session.query(PromptConfigEntity).filter_by(name=name).delete()
    session.flush()
    return count > 0


def auto_migrate_jsonl(session: Session, db_path: str) -> None:
    """Import from prompt_config.jsonl if it exists next to the db."""
    jsonl_path = os.path.join(os.path.dirname(db_path), "prompt_config.jsonl")
    if not os.path.exists(jsonl_path):
        return
    configs = []
    if os.path.getsize(jsonl_path) > 0:
        with open(jsonl_path, 'r', encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    configs.append(PromptConfig.from_dict(json.loads(line)))
    if configs:
        for config in configs:
            existing = session.query(PromptConfigEntity).filter_by(name=config.name).first()
            if not existing:
                entity = PromptConfigEntity(
                    name=config.name,
                    json_content=json.dumps(config.to_dict(), ensure_ascii=False)
                )
                session.add(entity)
        session.flush()
    os.remove(jsonl_path)
