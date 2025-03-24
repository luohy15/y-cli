"""Prompt configuration models."""

from dataclasses import dataclass, asdict, field
from typing import Dict, Optional

@dataclass
class PromptConfig:
    """Prompt configuration model.
    
    Attributes:
        name: Unique identifier for the prompt
        content: The content of the prompt
        description: Optional description of the prompt's purpose
    """
    name: str
    content: str
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'PromptConfig':
        """Create a PromptConfig from a dictionary.
        
        Args:
            data: Dictionary containing prompt configuration
            
        Returns:
            PromptConfig instance
        """
        return cls(**data)

    def to_dict(self) -> Dict:
        """Convert the PromptConfig to a dictionary.
        
        Returns:
            Dictionary representation of the prompt configuration
        """
        return {k: v for k, v in asdict(self).items() if v is not None}
