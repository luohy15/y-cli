import asyncio
import json
import os
import sys
from typing import Dict, List, Optional, Tuple, Any, Union, AsyncGenerator
from dataclasses import dataclass
from contextlib import asynccontextmanager

from loguru import logger
import os

@dataclass
class DaemonResponse:
    """Structured response from the MCP daemon server"""
    status: str  # 'success' or 'error'
    content: Optional[Any] = None
    error: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DaemonResponse':
        """
        Create a DaemonResponse instance from the raw dictionary returned by daemon server
        
        Args:
            data (Dict[str, Any]): Response dictionary from daemon server
            
        Returns:
            DaemonResponse: Structured response object
        """
        return cls(
            status=data.get("status", "error"),
            content=data.get("content"),
            error=data.get("error")
        )
        
    def is_success(self) -> bool:
        """
        Check if the response indicates success
        
        Returns:
            bool: True if status is 'success', False otherwise
        """
        return self.status == 'success'
        
    def get_parsed_content(self) -> Any:
        """
        Parse string content as JSON if possible
        
        Returns:
            Any: Parsed JSON content or original content if not JSON
        """
        if not self.content:
            return None
            
        if isinstance(self.content, str):
            try:
                return json.loads(self.content)
            except json.JSONDecodeError:
                return self.content
                
        return self.content
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert response to a dictionary (for backward compatibility)
        
        Returns:
            Dict[str, Any]: Dictionary representation of the response
        """
        result = {"status": self.status}
        if self.content is not None:
            result["content"] = self.content
        if self.error is not None:
            result["error"] = self.error
        return result