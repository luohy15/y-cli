import json
from typing import Callable, Dict, List, Optional

from storage.entity.dto import Message
from storage.util import generate_message_id, get_iso8601_timestamp, get_unix_timestamp
from agent.permissions import PermissionManager


class ClientError(Exception):
    """Raised when the LLM API returns a 4xx client error (non-retryable)."""
    pass


class ApprovalNeeded(Exception):
    """Raised by permission_callback to pause the agent loop.

    The caller should save state (messages already include the assistant
    message with tool calls) and resume later once approval is granted.
    """
    def __init__(self, tool_name: str, tool_args: Dict, tool_calls: List[Dict], tool_call_index: int):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.tool_calls = tool_calls           # full tool_calls list from the LLM response
        self.tool_call_index = tool_call_index  # index into tool_calls where we stopped
        super().__init__(f"Approval needed for {tool_name}")


def _default_display(message: Message):
    """Fallback plain-text display."""
    if message.role == "assistant":
        print(message.content)
    elif message.role == "tool" and message.tool:
        result = message.content
        print(f"[tool_result] {message.tool}: {result[:200]}{'...' if len(result) > 200 else ''}")


async def _default_permission_callback(tool_name: str, tool_args: Dict) -> bool:
    """Default interactive permission prompt via stdin."""
    try:
        args_str = json.dumps(tool_args, ensure_ascii=False)
        if len(args_str) > 80:
            args_str = args_str[:80] + "..."
        answer = input(f"Allow {tool_name}({args_str})? [y/N] ").strip().lower()
    except EOFError:
        answer = "n"
    return answer == "y"


async def run_agent_loop(
    provider,
    messages: List[Message],
    system_prompt: Optional[str],
    tools_map: Dict,
    openai_tools: List[Dict],
    max_iterations: int = 50,
    permission_manager: Optional[PermissionManager] = None,
    display_callback: Optional[Callable[[Message], None]] = None,
    permission_callback: Optional[Callable[[str, Dict], bool]] = None,
) -> List[Message]:
    """Run the agent loop: call LLM, execute tool calls, repeat until plain text.

    Args:
        permission_callback: Async callable(tool_name, tool_args) -> bool.
            Called when a tool is not auto-allowed by the permission_manager.
            Return True to approve, False to deny.
            May raise ApprovalNeeded to pause the loop (worker use-case).
            Defaults to an interactive stdin prompt.
    """
    if permission_manager is None:
        permission_manager = PermissionManager()
    if display_callback is None:
        display_callback = _default_display
    if permission_callback is None:
        permission_callback = _default_permission_callback
    new_messages: List[Message] = []

    try:
        for _ in range(max_iterations):
            raw = await provider.call_chat_completions_non_stream(
                messages, system_prompt, tools=openai_tools
            )

            tool_calls = raw.get("tool_calls")
            content = raw.get("content", "")
            provider_name = raw.get("provider")
            model = raw.get("model")

            assistant_msg_id = generate_message_id()
            parent_id = messages[-1].id if messages and messages[-1].id else None

            if not tool_calls:
                assistant_message = Message.from_dict({
                    "role": "assistant",
                    "content": content or "",
                    "timestamp": get_iso8601_timestamp(),
                    "unix_timestamp": get_unix_timestamp(),
                    "id": assistant_msg_id,
                    "parent_id": parent_id,
                    "provider": provider_name,
                    "model": model,
                })
                display_callback(assistant_message)
                messages.append(assistant_message)
                new_messages.append(assistant_message)
                return new_messages

            # Has tool calls
            first_tc = tool_calls[0]
            func = first_tc["function"]
            try:
                args = json.loads(func["arguments"])
            except (json.JSONDecodeError, TypeError):
                args = {"raw": func["arguments"]}

            assistant_message = Message.from_dict({
                "role": "assistant",
                "content": content or "",
                "timestamp": get_iso8601_timestamp(),
                "unix_timestamp": get_unix_timestamp(),
                "id": assistant_msg_id,
                "parent_id": parent_id,
                "provider": provider_name,
                "model": model,
                "tool": func["name"],
                "arguments": args,
            })
            assistant_message._raw_tool_calls = tool_calls
            display_callback(assistant_message)
            messages.append(assistant_message)
            new_messages.append(assistant_message)

            for tc_index, tc in enumerate(tool_calls):
                func = tc["function"]
                tool_name = func["name"]
                try:
                    tool_args = json.loads(func["arguments"])
                except (json.JSONDecodeError, TypeError):
                    tool_args = {}

                tool = tools_map.get(tool_name)
                if not tool:
                    result = f"Unknown tool: {tool_name}"
                elif permission_manager.is_allowed(tool_name, tool_args):
                    result = await tool.execute(tool_args)
                elif await permission_callback(tool_name, tool_args):
                    # permission_callback may raise ApprovalNeeded to pause
                    result = await tool.execute(tool_args)
                else:
                    result = f"ERROR: User denied execution of {tool_name} with args {tool_args}. The command was NOT executed. Do NOT proceed as if it succeeded."

                if len(result) > 10000:
                    result = result[:10000] + "\n... (truncated)"

                tool_msg_id = generate_message_id()
                tool_message = Message.from_dict({
                    "role": "tool",
                    "content": result,
                    "timestamp": get_iso8601_timestamp(),
                    "unix_timestamp": get_unix_timestamp(),
                    "id": tool_msg_id,
                    "parent_id": assistant_msg_id,
                    "tool": tool_name,
                })
                tool_message._tool_call_id = tc["id"]
                display_callback(tool_message)
                messages.append(tool_message)
                new_messages.append(tool_message)
    except ClientError as e:
        error_message = Message.from_dict({
            "role": "assistant",
            "content": f"[agent] API client error (not retrying): {e}",
            "timestamp": get_iso8601_timestamp(),
            "unix_timestamp": get_unix_timestamp(),
            "id": generate_message_id(),
            "parent_id": messages[-1].id if messages and messages[-1].id else None,
        })
        display_callback(error_message)
        messages.append(error_message)
        new_messages.append(error_message)
        return new_messages
    except KeyboardInterrupt:
        print("\n[agent] Interrupted")
        return new_messages

    print("[agent] Max iterations reached")
    return new_messages
