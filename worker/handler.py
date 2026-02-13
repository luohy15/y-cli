"""Worker Lambda handler — triggered by SQS to run chats."""

import asyncio
import json

from storage.cache import get_cached_chat, update_chat_status
from worker.runner import run_chat


def lambda_handler(event, context):
    """Handle SQS trigger.

    Each SQS record contains a JSON body with {"chat_id": "..."}.
    BatchSize is 1, so we process one chat per invocation.
    """
    records = event.get("Records", [])
    if not records:
        return {"status": "ok", "message": "no records"}

    record = records[0]
    body = json.loads(record["body"])
    chat_id = body["chat_id"]

    print(f"[worker] SQS trigger for chat {chat_id}")

    chat = get_cached_chat(chat_id)
    if not chat:
        print(f"[worker] chat {chat_id} not found, skipping")
        return {"status": "error", "message": f"chat {chat_id} not found"}

    status = chat.get("status")
    if status not in ("pending",):
        print(f"[worker] chat {chat_id} status={status}, skipping")
        return {"status": "ok", "message": f"chat {chat_id} already {status}"}

    # Atomically claim the chat
    update_chat_status(chat_id, "running")
    print(f"[worker] claimed chat {chat_id}")

    asyncio.run(run_chat(chat))
    return {"status": "ok", "chat_id": chat_id}
