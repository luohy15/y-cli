"""Config module - loads settings, initializes DB, and exposes global services."""

from yagent.settings import load_config
from storage.database.base import init_db

config = load_config()
init_db(config['database_url'])
