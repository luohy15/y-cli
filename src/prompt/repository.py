"""Prompt configuration repository."""

import json
import os
from typing import List, Optional
from .models import PromptConfig

class PromptRepository:
    """Repository for prompt configurations.
    
    Handles storage and retrieval of prompt configurations using JSONL file format.
    """
    
    def __init__(self, data_file: str):
        """Initialize the repository with a data file path.
        
        Args:
            data_file: Path to the JSONL file for storing prompt configurations
        """
        self.data_file = os.path.expanduser(data_file)
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensure the data file exists."""
        if not os.path.exists(self.data_file):
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'a', encoding="utf-8") as f:
                pass

    def _read_configs(self) -> List[PromptConfig]:
        """Read all prompt configs from the JSONL file."""
        configs = []
        if os.path.getsize(self.data_file) > 0:
            with open(self.data_file, 'r', encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        configs.append(PromptConfig.from_dict(data))
        return configs

    def _write_configs(self, configs: List[PromptConfig]) -> None:
        """Write all prompt configs to the JSONL file."""
        with open(self.data_file, 'w', encoding="utf-8") as f:
            for config in configs:
                json.dump(config.to_dict(), f, ensure_ascii=False)
                f.write('\n')

    def list_configs(self) -> List[PromptConfig]:
        """List all prompt configs.
        
        Returns:
            List of PromptConfig objects
        """
        return self._read_configs()

    def get_config(self, name: str) -> Optional[PromptConfig]:
        """Get a specific prompt config by name.
        
        Args:
            name: Name of the prompt configuration to retrieve
            
        Returns:
            PromptConfig if found, None otherwise
        """
        configs = self._read_configs()
        return next((config for config in configs if config.name == name), None)

    def add_config(self, config: PromptConfig) -> PromptConfig:
        """Add a new prompt config or update existing one.
        
        Args:
            config: PromptConfig object to add or update
            
        Returns:
            Added or updated PromptConfig
        """
        configs = self._read_configs()
        
        # Remove existing config with same name if exists
        configs = [c for c in configs if c.name != config.name]
        
        # Add new config
        configs.append(config)
        self._write_configs(configs)
        return config

    def delete_config(self, name: str) -> bool:
        """Delete a prompt config by name.
        
        Args:
            name: Name of the prompt configuration to delete
            
        Returns:
            True if deleted, False if not found
        """
        configs = self._read_configs()
        original_count = len(configs)
        configs = [c for c in configs if c.name != name]
        if len(configs) < original_count:
            self._write_configs(configs)
            return True
        return False
