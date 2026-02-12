from abc import ABC, abstractmethod
from typing import Dict


class Tool(ABC):
    name: str
    description: str
    parameters: Dict  # JSON schema

    def to_openai_tool(self) -> Dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    async def execute(self, arguments: Dict) -> str:
        pass
