"""Config package - loads settings, initializes DB, and exposes global services."""

from .settings import load_config
from .database import init_db, get_db

config = load_config()
init_db(config['sqlite_file'])

# Initialize services
from service import bot_config as bot_service
from service import prompt_config as prompt_service

bot_service.init()
prompt_service.init()
