"""Config module - loads settings, initializes DB, and exposes global services."""

from ycli.settings import load_config
from storage.database.base import init_db, init_tables

config = load_config()
init_db(config['database_url'])
init_tables()

# Initialize services
from storage.service import bot_config as bot_service

bot_service.init()
