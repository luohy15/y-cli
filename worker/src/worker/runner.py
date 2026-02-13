"""Run a single chat through the agent loop, writing events to DynamoDB cache."""

import json
from typing import Dict, List

from loguru import logger

from storage.cache import (
    append_event,
    save_chat_state,
    update_chat_status,
)
from storage.entity.dto import BotConfig, Message
from storage.service import bot_config as bot_service, chat as chat_service
from storage.util import generate_message_id, get_iso8601_timestamp, get_unix_timestamp

from agent.loop import ApprovalNeeded, run_agent_loop
from agent.provider import OpenAIFormatProvider, AnthropicFormatProvider
from agent.tools import get_tools_map, get_openai_tools
from agent.utils.message_utils import create_message


def _make_provider(bot_config: BotConfig):
    if bot_config.api_type == "anthropic":
        return AnthropicFormatProvider(bot_config)
    return OpenAIFormatProvider(bot_config)


def _make_permission_callback(chat_id: str):
    """Permission callback that raises ApprovalNeeded to pause the loop."""

    async def permission_callback(tool_name: str, tool_args: Dict) -> bool:
        raise ApprovalNeeded(
            tool_name=tool_name,
            tool_args=tool_args,
            tool_calls=[],
            tool_call_index=0,
        )

    return permission_callback


def _build_system_prompt() -> str:
    from agent.skills import discover_skills, skills_to_prompt
    skills_block = skills_to_prompt(discover_skills())
    return ("\n" + skills_block) if skills_block else ""


def _resolve_bot_config(chat: Dict) -> BotConfig:
    bot_name = chat.get("bot_name")
    bot_config = None
    if bot_name:
        bot_config = bot_service.get_config(bot_name)
    if not bot_config:
        bot_config = bot_service.get_config()
    return bot_config


async def run_chat(chat: Dict) -> None:
    """Execute a chat. Handles both fresh chats and resumed (approved) chats."""
    chat_id = chat["id"]
    prompt = chat.get("prompt", "")
    pending_approval = chat.get("pending_approval")

    logger.info("run_chat start chat_id={} has_pending_approval={}", chat_id, pending_approval is not None)

    bot_config = _resolve_bot_config(chat)
    logger.info("Resolved bot config: name={} api_type={} model={}", bot_config.name, bot_config.api_type, bot_config.model)
    provider = _make_provider(bot_config)

    tools_map = get_tools_map()
    openai_tools = get_openai_tools()
    system_prompt = _build_system_prompt()
    logger.info("Loaded {} tools, system_prompt length={}", len(tools_map), len(system_prompt) if system_prompt else 0)

    # Callback: write each message as an event to DynamoDB cache
    def display_callback(message: Message):
        logger.info("Event: role={} tool={} content_length={}", message.role, message.tool, len(message.content) if message.content else 0)
        append_event(chat_id, {"type": "message", "data": message.to_dict()})

    # --- Load messages ---
    saved_messages = chat.get("messages")
    if saved_messages:
        if isinstance(saved_messages, list) and saved_messages and isinstance(saved_messages[0], dict):
            messages = [Message.from_dict(m) for m in saved_messages]
        else:
            messages = saved_messages
        logger.info("Resumed with {} saved messages", len(messages))
    else:
        # Fresh chat: load from DB or start empty
        messages: List[Message] = []
        existing = await chat_service.get_chat(chat_id)
        if existing and existing.messages:
            messages = existing.messages
            logger.info("Loaded {} messages from chat {}", len(messages), chat_id)
        # Add user prompt (event already emitted by the API controller)
        if prompt:
            user_msg = create_message("user", prompt, id=generate_message_id())
            messages.append(user_msg)
        logger.info("Fresh chat with {} messages", len(messages))

    # --- Handle pending approval from a previous run ---
    if pending_approval and pending_approval.get("approved") is not None:
        approved = pending_approval["approved"]
        tool_name = pending_approval["tool_name"]
        tool_args = pending_approval["tool_args"]
        tool_calls = pending_approval.get("tool_calls", [])
        tc_index = int(pending_approval.get("tool_call_index", 0))
        logger.info("Processing approval: tool={} approved={} tc_index={}/{}", tool_name, approved, tc_index, len(tool_calls))

        assistant_msg_id = None
        for m in reversed(messages):
            if m.role == "assistant":
                assistant_msg_id = m.id
                break

        for i in range(tc_index, len(tool_calls)):
            tc = tool_calls[i]
            func = tc["function"]
            tn = func["name"]
            try:
                ta = json.loads(func["arguments"])
            except (json.JSONDecodeError, TypeError):
                ta = {}

            if i == tc_index:
                if approved:
                    tool = tools_map.get(tn)
                    result = await tool.execute(ta) if tool else f"Unknown tool: {tn}"
                else:
                    result = f"ERROR: User denied execution of {tn} with args {ta}. The command was NOT executed. Do NOT proceed as if it succeeded."
            else:
                tool = tools_map.get(tn)
                result = await tool.execute(ta) if tool else f"Unknown tool: {tn}"

            logger.info("Tool call [{}] {}  result_length={}", i, tn, len(result))

            if len(result) > 10000:
                result = result[:10000] + "\n... (truncated)"

            tool_msg = Message.from_dict({
                "role": "tool",
                "content": result,
                "timestamp": get_iso8601_timestamp(),
                "unix_timestamp": get_unix_timestamp(),
                "id": generate_message_id(),
                "parent_id": assistant_msg_id,
                "tool": tn,
            })
            tool_msg._tool_call_id = tc["id"]
            display_callback(tool_msg)
            messages.append(tool_msg)

    # --- Run agent loop ---
    try:
        logger.info("Starting agent loop with {} messages", len(messages))
        await run_agent_loop(
            provider=provider,
            messages=messages,
            system_prompt=system_prompt,
            tools_map=tools_map,
            openai_tools=openai_tools,
            display_callback=display_callback,
            permission_callback=_make_permission_callback(chat_id),
        )
        # Completed normally
        logger.info("Agent loop completed for chat {}", chat_id)
        update_chat_status(chat_id, "completed")
        append_event(chat_id, {"type": "done", "data": {}})

    except ApprovalNeeded as e:
        logger.info("Approval needed for chat {}: tool={}", chat_id, e.tool_name)
        last_assistant = None
        for m in reversed(messages):
            if m.role == "assistant" and hasattr(m, "_raw_tool_calls"):
                last_assistant = m
                break

        full_tool_calls = last_assistant._raw_tool_calls if last_assistant else []

        tc_index = 0
        for i, tc in enumerate(full_tool_calls):
            func = tc["function"]
            if func["name"] == e.tool_name:
                try:
                    args = json.loads(func["arguments"])
                except (json.JSONDecodeError, TypeError):
                    args = {}
                if args == e.tool_args:
                    tc_index = i
                    break

        pa = {
            "tool_name": e.tool_name,
            "tool_args": e.tool_args,
            "tool_calls": full_tool_calls,
            "tool_call_index": tc_index,
            "approved": None,
        }
        save_chat_state(
            chat_id,
            messages=[m.to_dict() for m in messages],
            pending_approval=pa,
        )
        update_chat_status(chat_id, "waiting_approval")
        append_event(chat_id, {
            "type": "ask",
            "data": {"tool_name": e.tool_name, "tool_args": e.tool_args},
        })
        return

    except Exception as e:
        logger.exception("Agent loop failed for chat {}", chat_id)
        update_chat_status(chat_id, "failed")
        append_event(chat_id, {"type": "error", "data": {"error": str(e)}})

    # Persist chat to DB
    await chat_service.update_chat_with_cache(chat_id, messages)
