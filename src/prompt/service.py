"""Prompt configuration service."""

from typing import List, Optional
from .models import PromptConfig
from .repository import PromptRepository
from .mcp import mcp_prompt
from .preset import deep_research_prompt

class PromptService:
    """Service for managing prompt configurations.
    
    Provides business logic for prompt configuration management.
    """
    
    def __init__(self, repository: PromptRepository):
        """Initialize the prompt service with a repository.
        
        Args:
            repository: Repository for storing prompt configurations
        """
        self.repository = repository
        self._ensure_default_prompt()
    
    @property
    def _mcp_prompt(self) -> PromptConfig:
        """Get the mcp prompt configuration.
        
        Returns:
            PromptConfig
        """
        return PromptConfig(
            name="mcp",
            content=mcp_prompt,
            description="mcp prompt"
        )
    
    @property
    def _deep_research_prompt(self) -> PromptConfig:
        """Get the deep_research prompt configuration.
        
        Returns:
            PromptConfig
        """
        return PromptConfig(
            name="deep-research",
            content=deep_research_prompt,
            description="deep research prompt"
        )
    
    def _ensure_default_prompt(self) -> None:
        """Ensure default prompt exists."""
        if not self.get_prompt("mcp"):
            self.add_prompt(self._mcp_prompt)
        if not self.get_prompt("deep-research"):
            self.add_prompt(self._deep_research_prompt)
    
    def list_prompts(self) -> List[PromptConfig]:
        """List all prompt configurations.
        
        Returns:
            List of PromptConfig objects
        """
        return self.repository.list_configs()
    
    def get_prompt(self, name: str = "default") -> Optional[PromptConfig]:
        """Get a prompt configuration by name.
        
        Args:
            name: Name of the prompt to retrieve, defaults to "default"
            
        Returns:
            PromptConfig if found, None otherwise
        """
        return self.repository.get_config(name)
    
    def add_prompt(self, config: PromptConfig) -> PromptConfig:
        """Add a new prompt configuration or update existing one.
        
        Args:
            config: PromptConfig to add or update
            
        Returns:
            Added or updated PromptConfig
        """
        return self.repository.add_config(config)
    
    def delete_prompt(self, name: str) -> bool:
        """Delete a prompt configuration by name.
        
        Args:
            name: Name of the prompt to delete
            
        Returns:
            True if deleted, False if not found or cannot delete (default)
        """
        return self.repository.delete_config(name)
