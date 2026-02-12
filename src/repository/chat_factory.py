from types import SimpleNamespace
from config import config


def get_chat_repository() -> SimpleNamespace:
    """Factory function to get the appropriate chat repository implementation."""
    d1_config = config.get('cloudflare_d1', {})
    required_keys = ['database_id', 'api_token']

    if all(d1_config.get(key) for key in required_keys):
        from repository import chat_d1 as repo
    else:
        from repository import chat_sqlite as repo

    return SimpleNamespace(
        list_chats=repo.list_chats,
        get_chat=repo.get_chat,
        add_chat=repo.add_chat,
        update_chat=repo.update_chat,
        delete_chat=repo.delete_chat,
    )
