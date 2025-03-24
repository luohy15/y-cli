import os
import sys
import toml
from bot import BotService, BotRepository
from mcp_server import McpServerConfigService, McpServerConfigRepository
from prompt import PromptService, PromptRepository

def get_default_config():
    """Get default configuration"""
    app_name = "y-cli"
    if sys.platform == "darwin":  # macOS
        base_dir = os.path.expanduser(f"~/Library/Application Support/{app_name}")
        cache_dir = os.path.expanduser(f"~/Library/Caches/{app_name}")
    else:  # Linux and others
        base_dir = os.path.expanduser(f"~/.local/share/{app_name}")
        cache_dir = base_dir
        
    return {
        # Storage configuration
        "storage_type": "file",  # Options: "file" or "cloudflare"
        
        # File storage paths
        "chat_file": f"{base_dir}/chat.jsonl",
        "bot_config_file": f"{base_dir}/bot_config.jsonl",
        "mcp_config_file": f"{base_dir}/mcp_config.jsonl",
        "prompt_config_file": f"{base_dir}/prompt_config.jsonl",
        "openrouter_import_dir": f"{base_dir}/openrouter_import",
        "openrouter_import_history": f"{base_dir}/openrouter_import_history.jsonl",
        "tmp_dir": f"{cache_dir}/tmp",
        
        # Cloudflare configuration
        "cloudflare": {
            "account_id": "",
            "api_token": "",
            "kv_namespace_id": "",
            "r2_bucket_name": ""
        },
        
        # Other settings
        "s3_bucket": "",
        "cloudfront_distribution_id": "",
        "proxy_host": "",
        "proxy_port": ""
    }

def load_config():
    """Load configuration from TOML file or create with defaults if it doesn't exist"""
    app_name = "y-cli"
    # toml config file - use Preferences dir on macOS
    if sys.platform == "darwin":
        CONFIG_FILE = os.path.expanduser(f"~/Library/Preferences/{app_name}/config.toml")
    else:
        CONFIG_FILE = os.path.expanduser(f"~/.config/{app_name}/config.toml")
    # ensure the directory exists
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

    # Create default config if file doesn't exist
    if not os.path.exists(CONFIG_FILE):
        config = get_default_config()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            toml.dump(config, f)
    else:
        # read existing config file
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = toml.load(f)
            # Merge with defaults to ensure all required fields exist
            defaults = get_default_config()
            for key, value in defaults.items():
                if key not in config:
                    config[key] = value

    # Set up data files
    for file_key in ["chat_file", "bot_config_file", "mcp_config_file", "prompt_config_file", "tmp_dir"]:
        config[file_key] = os.path.expanduser(config[file_key])
        os.makedirs(os.path.dirname(config[file_key]), exist_ok=True)

    # Set up proxy settings if configured
    PROXY_HOST = config.get("proxy_host")
    PROXY_PORT = config.get("proxy_port")
    if PROXY_HOST and PROXY_PORT:
        os.environ["http_proxy"] = f"http://{PROXY_HOST}:{PROXY_PORT}"
        os.environ["https_proxy"] = f"http://{PROXY_HOST}:{PROXY_PORT}"

    return CONFIG_FILE, config

CONFIG_FILE, config = load_config()

# Initialize global services
bot_service = BotService(BotRepository(config['bot_config_file']))
mcp_service = McpServerConfigService(McpServerConfigRepository(config['mcp_config_file']))
prompt_service = PromptService(PromptRepository(config['prompt_config_file']))
