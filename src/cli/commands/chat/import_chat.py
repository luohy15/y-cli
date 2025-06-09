import os
import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, List
import click

from chat.models import Chat
from chat.repository.file import FileRepository
from config import config

@click.command('import')
@click.argument('file_path', type=click.Path(exists=True, readable=True))
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def import_chats(file_path: str, verbose: bool = False):
    """Import chats from an external file.
    
    The import follows these rules:
    1. If chat ID doesn't exist, import it
    2. If chat ID exists, compare update times and use the more recent one
    3. Prints summary of new, existing, and replaced chats
    """
    if verbose:
        click.echo(f"Importing chats from: {file_path}")
        click.echo(f"Current chat file: {config['chat_file']}")
    
    # Setup temporary file repository for the source file
    source_repo = FileRepository()
    source_repo.data_file = os.path.expanduser(file_path)
    
    # Setup repository for the current chat file
    current_repo = FileRepository()
    
    # Read chats from both files
    source_chats = asyncio.run(source_repo._read_chats())
    current_chats = asyncio.run(current_repo._read_chats())
    
    if verbose:
        click.echo(f"Found {len(source_chats)} chats in source file")
        click.echo(f"Found {len(current_chats)} chats in current file")
    
    # Track statistics
    new_count = 0
    existing_count = 0
    replaced_count = 0
    
    # Create a map of current chats by ID for efficient lookup and update
    current_chats_map: Dict[str, Chat] = {chat.id: chat for chat in current_chats}
    
    # Process each source chat
    for source_chat in source_chats:
        if source_chat.id not in current_chats_map:
            # New chat - add it to the map
            current_chats_map[source_chat.id] = source_chat
            new_count += 1
            if verbose:
                click.echo(f"Importing new chat: {source_chat.id}")
        else:
            # Existing chat - check timestamps
            existing_count += 1
            current_chat = current_chats_map[source_chat.id]
            
            # Parse timestamps to datetime for comparison
            source_time = datetime.fromisoformat(source_chat.update_time.replace('Z', '+00:00'))
            current_time = datetime.fromisoformat(current_chat.update_time.replace('Z', '+00:00'))
            
            if source_time > current_time:
                # Source is newer - replace in the map
                current_chats_map[source_chat.id] = source_chat
                replaced_count += 1
                if verbose:
                    click.echo(f"Replacing chat with newer version: {source_chat.id}")
            else:
                if verbose:
                    click.echo(f"Keeping existing chat (newer): {current_chat.id}")
    
    # Convert the map back to a list for writing
    updated_chats = list(current_chats_map.values())
    
    # Write updated chats back to current file
    asyncio.run(current_repo._write_chats(updated_chats))
    
    # Print statistics
    click.echo(f"Import completed:")
    click.echo(f"  New chats: {new_count}")
    click.echo(f"  Existing chats: {existing_count}")
    click.echo(f"  Replaced chats: {replaced_count}")
