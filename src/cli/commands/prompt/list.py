import click
import shutil
from tabulate import tabulate
from config import config, prompt_service

def truncate_text(text, max_length):
    """Truncate text to max_length with ellipsis if needed."""
    if not text or len(str(text)) <= max_length:
        return text
    return str(text)[:max_length-3] + "..."

@click.command('list')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def prompt_list(verbose: bool = False):
    """List all prompt configurations."""
    if verbose:
        click.echo(f"{click.style('Prompt config data will be stored in:', fg='green')}\n{click.style(config['prompt_config_file'], fg='cyan')}")

    prompts = prompt_service.list_prompts()
    
    if not prompts:
        click.echo("No prompt configurations found")
        return

    if verbose:
        click.echo(f"Found {len(prompts)} prompt configuration(s)")
    
    # Define column width ratios (total should be < 1 to leave space for separators)
    width_ratios = {
        "Name": 0.2,
        "Content": 0.6,
        "Description": 0.2
    }
    
    # Calculate actual column widths
    term_width = shutil.get_terminal_size().columns
    col_widths = {k: max(10, int(term_width * ratio)) for k, ratio in width_ratios.items()}
    
    # Prepare table data with truncated values
    table_data = []
    headers = ["Name", "Content", "Description"]
    
    for prompt in prompts:
        table_data.append([
            truncate_text(prompt.name, col_widths["Name"]),
            truncate_text(prompt.content, col_widths["Content"]),
            truncate_text(prompt.description or "N/A", col_widths["Description"])
        ])
    click.echo(tabulate(
        table_data,
        headers=headers,
        tablefmt="simple",
        numalign='left',
        stralign='left'
    ))
