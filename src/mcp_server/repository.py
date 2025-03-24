from typing import List, Optional
from .models import McpServerConfig
import json
import os

class McpServerConfigRepository:
    """Repository for managing MCP configs in JSONL format"""
    
    def __init__(self, config_path: str):
        """
        Initialize the repository with a configuration file path
        
        Args:
            config_path (str): Path to the MCP configs JSONL file
        """
        self.config_path = config_path
        
    def load(self) -> List[McpServerConfig]:
        """
        Load MCP configs from the JSONL file
        
        Returns:
            List[McpServerConfig]: List of MCP configs
        """
        if not os.path.exists(self.config_path):
            return []
            
        configs = []
        try:
            with open(self.config_path, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        configs.append(McpServerConfig.from_dict(data))
            return configs
        except Exception as e:
            print(f"Error loading MCP configs: {str(e)}")
            return []
            
    def save(self, configs: List[McpServerConfig]) -> bool:
        """
        Save MCP configs to the JSONL file
        
        Args:
            configs (List[McpServerConfig]): List of MCP configs
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            # Write each config as a JSON line
            with open(self.config_path, 'w') as f:
                for config in configs:
                    line = json.dumps(config.to_dict())
                    f.write(line + '\n')
            return True
        except Exception as e:
            print(f"Error saving MCP configs: {str(e)}")
            return False
            
    def get_by_name(self, name: str) -> Optional[McpServerConfig]:
        """
        Get a specific MCP config by name
        
        Args:
            name (str): Name of the MCP server
            
        Returns:
            Optional[McpServerConfig]: The MCP config if found, None otherwise
        """
        for config in self.load():
            if config.name == name:
                return config
        return None
        
    def add_or_update(self, new_config: McpServerConfig) -> bool:
        """
        Add or update an MCP config
        
        Args:
            new_config (McpServerConfig): The MCP config to add or update
            
        Returns:
            bool: True if operation was successful, False otherwise
        """
        configs = self.load()
        # Remove existing config with same name if exists
        configs = [s for s in configs if s.name != new_config.name]
        # Add new config
        configs.append(new_config)
        return self.save(configs)
        
    def remove(self, name: str) -> bool:
        """
        Remove an MCP config by name
        
        Args:
            name (str): Name of the MCP server to remove
            
        Returns:
            bool: True if operation was successful, False otherwise
        """
        configs = self.load()
        filtered = [s for s in configs if s.name != name]
        if len(filtered) < len(configs):
            return self.save(filtered)
        return False
