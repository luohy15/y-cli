import click
import shutil
from tabulate import tabulate
from typing import List, Optional

from mcp_server.models import McpServerConfig
from mcp_server.service import McpServerConfigService
from mcp_server.repository import McpServerConfigRepository

def truncate_text(text, max_length):
    """Truncate text to max_length with ellipsis if needed."""
    if not text or len(str(text)) <= max_length:
        return text
    return str(text)[:max_length-3] + "..."

def get_server_type(config: McpServerConfig) -> str:
    """Determine server type from configuration."""
    if config.url:
        return "sse"
    return "stdio"

@click.command('list')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def mcp_list(verbose: bool = False):
    """List all MCP server configurations."""
    from config import config
    
    if verbose:
        click.echo(f"{click.style('MCP config data will be stored in:', fg='green')}\n{click.style(config['mcp_config_file'], fg='cyan')}")

    # Initialize repository and service
    repository = McpServerConfigRepository(config['mcp_config_file'])
    service = McpServerConfigService(repository)
    
    # Get all configs
    configs = service.get_all_configs()
    
    if not configs:
        click.echo("No MCP server configurations found")
        return

    if verbose:
        click.echo(f"Found {len(configs)} MCP server configuration(s)")
    
    # Define column width ratios (total should be < 1 to leave space for separators)
    width_ratios = {
        "Name": 0.15,
        "Type": 0.1,
        "Command/URL": 0.2,
        "Arguments/Token": 0.2,
        "Environment": 0.15,
        "Auto-Confirm": 0.15
    }
    
    # Calculate actual column widths
    term_width = shutil.get_terminal_size().columns
    col_widths = {k: max(10, int(term_width * ratio)) for k, ratio in width_ratios.items()}
    
    # Prepare table data with truncated values
    table_data = []
    headers = ["Name", "Type", "Command/URL", "Arguments/Token", "Environment", "Auto-Confirm"]
    
    for config in configs:
        server_type = get_server_type(config)
        
        # Determine display values based on server type
        if server_type == "stdio":
            command_or_url = config.command or ""
            args_or_token = ' '.join(config.args) if config.args else ''
        else:  # sse
            command_or_url = config.url or ""
            args_or_token = config.token or ""
        
        # Format env dict for display
        env_str = ', '.join(f'{k}={v}' for k, v in config.env.items()) if config.env else ''
        
        # Format auto_confirm list for display
        auto_confirm_str = ', '.join(config.auto_confirm) if config.auto_confirm else ''
        
        table_data.append([
            truncate_text(config.name, col_widths["Name"]),
            server_type,
            truncate_text(command_or_url, col_widths["Command/URL"]),
            truncate_text(args_or_token, col_widths["Arguments/Token"]),
            truncate_text(env_str, col_widths["Environment"]),
            truncate_text(auto_confirm_str, col_widths["Auto-Confirm"])
        ])
    
    click.echo(tabulate(
        table_data,
        headers=headers,
        tablefmt="simple",
        numalign='left',
        stralign='left'
    ))
