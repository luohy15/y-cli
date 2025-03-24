from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional

@dataclass
class McpServerConfig:
    """
    Configuration class for MCP (Model Context Protocol) server settings.
    
    Attributes:
        name (str): The name of the MCP server
        command (str): The command to execute the server (e.g., 'node', 'python') - used for stdio
        args (list[str]): Command line arguments for the server - used for stdio
        env (dict[str, str]): Environment variables for the server process - used for stdio
        url (str, optional): The URL endpoint for SSE server connection
        token (str, optional): The authentication token for SSE server connection
        auto_confirm (list[str], optional): List of tool names that should be auto-confirmed without user prompt
    """
    
    name: str
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None
    token: Optional[str] = None
    auto_confirm: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'McpServerConfig':
        """
        Create a McpServerConfig instance from a dictionary
        
        Args:
            data (Dict): Dictionary containing McpServerConfig attributes
            
        Returns:
            McpServerConfig: A new McpServerConfig instance
        """
        return cls(**data)
        
    def to_dict(self) -> Dict:
        """
        Convert the McpServerConfig to a dictionary, excluding None values
        
        Returns:
            Dict: Dictionary representation of the McpServerConfig
        """
        return {k: v for k, v in asdict(self).items() if v is not None}
