"""Configuration loading from environment variables."""

import os


def load_config():
    """Load configuration from environment variables."""
    home = os.path.expanduser(os.environ.get("Y_CLI_HOME", "~/.y-cli"))
    os.makedirs(home, exist_ok=True)

    cfg = {
        # Storage
        "sqlite_file": os.path.join(home, "chat.db"),
        "openrouter_import_dir": os.path.join(home, "openrouter_import"),
        "openrouter_import_history": os.path.join(home, "openrouter_import_history.jsonl"),
        "tmp_dir": os.path.join(home, "tmp"),

        # Cloudflare configuration
        "cloudflare_d1": {
            "account_id": os.environ.get("Y_CLI_D1_ACCOUNT_ID", ""),
            "database_id": os.environ.get("Y_CLI_D1_DATABASE_ID", ""),
            "database_name": os.environ.get("Y_CLI_D1_DATABASE_NAME", ""),
            "api_token": os.environ.get("Y_CLI_D1_API_TOKEN", ""),
            "user_prefix": os.environ.get("Y_CLI_D1_USER_PREFIX", "default"),
        },

        # Other settings
        "s3_bucket": os.environ.get("Y_CLI_S3_BUCKET", ""),
        "cloudfront_distribution_id": os.environ.get("Y_CLI_CLOUDFRONT_DISTRIBUTION_ID", ""),
        "proxy_host": os.environ.get("Y_CLI_PROXY_HOST", ""),
        "proxy_port": os.environ.get("Y_CLI_PROXY_PORT", ""),
        "print_speed": int(os.environ.get("Y_CLI_PRINT_SPEED", "1000")),
    }

    # Ensure directories exist
    for file_key in ["sqlite_file", "tmp_dir"]:
        os.makedirs(os.path.dirname(cfg[file_key]), exist_ok=True)

    # Set up proxy settings if configured
    proxy_host = cfg.get("proxy_host")
    proxy_port = cfg.get("proxy_port")
    if proxy_host and proxy_port:
        os.environ["http_proxy"] = f"http://{proxy_host}:{proxy_port}"
        os.environ["https_proxy"] = f"http://{proxy_host}:{proxy_port}"

    return cfg
