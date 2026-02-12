import asyncio
from typing import Dict
from agent.tool_base import Tool


class BashTool(Tool):
    name = "bash"
    description = "Run a shell command and return stdout and stderr."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
        },
        "required": ["command"],
    }

    async def execute(self, arguments: Dict) -> str:
        command = arguments["command"]
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = ""
            if stdout:
                output += stdout.decode()
            if stderr:
                output += stderr.decode()
            return output or "(no output)"
        except asyncio.TimeoutError:
            proc.kill()
            return "Error: command timed out after 30 seconds"
        except Exception as e:
            return f"Error running command: {e}"
