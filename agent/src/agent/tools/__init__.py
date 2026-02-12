from typing import Dict, List
from agent.tool_base import Tool
from agent.tools.file_read import FileReadTool
from agent.tools.file_write import FileWriteTool
from agent.tools.file_edit import FileEditTool
from agent.tools.bash import BashTool


def get_tools() -> List[Tool]:
    return [FileReadTool(), FileWriteTool(), FileEditTool(), BashTool()]


def get_tools_map() -> Dict[str, Tool]:
    return {t.name: t for t in get_tools()}


def get_openai_tools() -> List[Dict]:
    return [t.to_openai_tool() for t in get_tools()]
