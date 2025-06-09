from typing import Optional
from config import config
from . import ChatRepository
from .file import FileRepository
from .cloudflare_d1 import CloudflareD1Repository

def get_chat_repository() -> ChatRepository:
    """
    Factory function to get the appropriate chat repository implementation
    based on configuration.
    
    Returns:
        ChatRepository: An instance of the configured repository implementation
    """
    # Check storage type configuration
    storage_type = config.get('storage_type', 'file')
    
    if storage_type == 'cloudflare_d1':
        d1_config = config.get('cloudflare_d1', {})
        required_keys = ['database_id', 'api_token']
        
        if all(key in d1_config for key in required_keys):
            return CloudflareD1Repository()
        else:
            missing = [key for key in required_keys if key not in d1_config]
            print(f"Warning: Missing cloudflare_d1 configuration: {', '.join(missing)}")
            print("Falling back to file-based storage")
    
    # Default to file-based repository
    return FileRepository()
