import json
from typing import Callable, Dict, List, Optional

from storage.entity.dto import Message
from storage.util import generate_message_id, get_iso8601_timestamp, get_unix_timestamp
from agent.permissions import PermissionManager


def _default_display(message: Message):
    """Fallback plain-text display."""
    if message.role == "assistant":
        print(message.content)
    elif message.role == "tool" and message.tool:
        result = message.content
        print(f"[tool_result] {message.tool}: {result[:200]}{'...' if len(result) > 200 else ''}")


async def run_agent_loop(
    provider,
    messages: List[Message],
    system_prompt: Optional[str],
    tools_map: Dict,
    openai_tools: List[Dict],
    max_iterations: int = 50,
    permission_manager: Optional[PermissionManager] = None,
    display_callback: Optional[Callable[[Message], None]] = None,
) -> List[Message]:
    """Run the agent loop: call LLM, execute tool calls, repeat until plain text."""
    if permission_manager is None:
        permission_manager = PermissionManager()
    if display_callback is None:
        display_callback = _default_display
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

            for tc in tool_calls:
                func = tc["function"]
                tool_name = func["name"]
                try:
                    tool_args = json.loads(func["arguments"])
                except (json.JSONDecodeError, TypeError):
                    tool_args = {}

                tool = tools_map.get(tool_name)
                if not tool:
                    result = f"Unknown tool: {tool_name}"
                elif not permission_manager.is_allowed(tool_name, tool_args):
                    try:
                        args_str = json.dumps(tool_args, ensure_ascii=False)
                        if len(args_str) > 80:
                            args_str = args_str[:80] + "..."
                        answer = input(f"Allow {tool_name}({args_str})? [y/N] ").strip().lower()
                    except EOFError:
                        answer = "n"
                    if answer == "y":
                        result = await tool.execute(tool_args)
                    else:
                        result = f"ERROR: User denied execution of {tool_name} with args {tool_args}. The command was NOT executed. Do NOT proceed as if it succeeded."
                else:
                    result = await tool.execute(tool_args)

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
    except KeyboardInterrupt:
        print("\n[agent] Interrupted")
        return new_messages

    print("[agent] Max iterations reached")
    return new_messages
