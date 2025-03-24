import click
from typing import List, Optional

from mcp_server.models import McpServerConfig
from mcp_server.service import McpServerConfigService
from mcp_server.repository import McpServerConfigRepository

@click.command('add')
def mcp_add():
    """Add a new MCP server configuration."""
    from config import config
    # Tip about direct file editing
    click.echo(f"TIP: For efficiency, you can directly edit the MCP server configuration file at: {config['mcp_config_file']}")
    # Initialize repository and service
    repository = McpServerConfigRepository(config['mcp_config_file'])
    service = McpServerConfigService(repository)
    
    # Get server name
    name = click.prompt("Server name")
    
    # Check if server already exists
    existing_config = service.get_config(name)
    if existing_config:
        if not click.confirm(f"MCP server '{name}' already exists. Do you want to overwrite it?"):
            click.echo("Operation cancelled")
            return
    
    # Choose server type
    server_type = click.prompt(
        "Server type",
        type=click.Choice(["stdio", "sse"], case_sensitive=False)
    )
    
    command: Optional[str] = None
    args: List[str] = []
    env: dict[str, str] = {}
    url: Optional[str] = None
    token: Optional[str] = None
    
    # Collect type-specific configuration
    if server_type == "stdio":
        # Get command
        command = click.prompt("Command (e.g., 'node', 'python')")
        
        # Get arguments as a space-separated string and convert to list
        args_str = click.prompt("Arguments (space-separated)", default="")
        args = args_str.split() if args_str else []
        
        # Get environment variables
        while True:
            if not click.confirm("Add environment variable?", default=False):
                break
            key = click.prompt("Environment variable name")
            value = click.prompt("Environment variable value")
            env[key] = value
    else:  # sse type
        # Get URL and token
        url = click.prompt("Server URL")
        token = click.prompt("Authentication token", default="")
        if not token:
            token = None
    
    # Configure auto-confirm tools
    auto_confirm: List[str] = []
    if click.confirm("Configure auto-confirm tools?", default=False):
        click.echo("Enter tool names one at a time (empty line to finish):")
        while True:
            tool = click.prompt("Tool name", default="")
            if not tool:
                break
            auto_confirm.append(tool)
    
    # Save the config
    if service.create_config(
        name=name,
        command=command,
        args=args,
        env=env,
        url=url,
        token=token,
        auto_confirm=auto_confirm
    ):
        click.echo(f"MCP server '{name}' added successfully")
    else:
        click.echo(f"Failed to add MCP server '{name}'")
