from typing import Dict
from agent.tool_base import Tool


class FileReadTool(Tool):
    name = "file_read"
    description = "Read the contents of a file at the given path."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The file path to read.",
            },
        },
        "required": ["path"],
    }

    async def execute(self, arguments: Dict) -> str:
        path = arguments["path"]
        try:
            with open(path, "r") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"
