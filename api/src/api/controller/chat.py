import asyncio
import json
import os
import uuid
from decimal import Decimal
from typing import Optional

import boto3
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from storage.cache import cache_chat, get_cached_chat, list_cached_chats, resolve_approval
from storage.service import chat as chat_service
from storage.util import generate_message_id, get_iso8601_timestamp, get_unix_timestamp

router = APIRouter(prefix="/v1")


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)


def _get_sqs_client():
    region = os.environ.get("AWS_REGION", "us-east-1")
    endpoint_url = os.environ.get("SQS_ENDPOINT_URL")
    kwargs = {"region_name": region}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client("sqs", **kwargs)


def _send_chat_message(chat_id: str):
    """Send an SQS message to trigger the worker for a chat."""
    queue_url = os.environ.get("SQS_QUEUE_URL")
    if not queue_url:
        return
    client = _get_sqs_client()
    client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({"chat_id": chat_id}),
    )


class CreateChatRequest(BaseModel):
    prompt: str
    bot_name: Optional[str] = None
    chat_id: Optional[str] = None


class CreateChatResponse(BaseModel):
    chat_id: str


class ApproveRequest(BaseModel):
    approved: bool


def _get_user_id(request: Request) -> int:
    return request.state.user_id


@router.get("/chats")
async def get_chats():
    chats = list_cached_chats()
    return json.loads(json.dumps(chats, cls=_DecimalEncoder))


@router.post("/chats", response_model=CreateChatResponse)
async def post_create_chat(req: CreateChatRequest, request: Request):
    chat_id = req.chat_id or str(uuid.uuid4())
    user_id = _get_user_id(request)

    # Create in DB with status=pending
    chat = await chat_service.create_chat_with_cache(
        messages=[],
        chat_id=chat_id,
        status="pending",
        bot_name=req.bot_name,
        prompt=req.prompt,
        user_id=user_id,
    )

    # Build user message event so SSE clients see it immediately
    user_msg_data = {
        "role": "user",
        "content": req.prompt,
        "timestamp": get_iso8601_timestamp(),
        "unix_timestamp": get_unix_timestamp(),
        "id": generate_message_id(),
    }
    user_event = {"type": "message", "data": user_msg_data}

    # Ensure cache has the prompt, status, and user message event for SSE
    cache_chat(chat_id, {
        **chat.to_dict(),
        "prompt": req.prompt,
        "status": "pending",
        "events": [user_event],
    })

    _send_chat_message(chat_id)
    return CreateChatResponse(chat_id=chat_id)


@router.post("/chats/{chat_id}/approve")
async def post_approve(chat_id: str, req: ApproveRequest):
    cached = get_cached_chat(chat_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="chat not found")
    if cached.get("status") != "waiting_approval":
        raise HTTPException(status_code=400, detail="chat is not waiting for approval")
    resolve_approval(chat_id, req.approved)
    _send_chat_message(chat_id)
    return {"ok": True}


@router.get("/chats/{chat_id}/events")
async def get_chat_events(chat_id: str, last_index: int = Query(0, ge=0)):
    async def event_stream():
        idx = last_index
        while True:
            cached = get_cached_chat(chat_id)
            if cached is None:
                yield {"event": "error", "data": json.dumps({"error": "chat not found"})}
                return

            events = cached.get("events", [])
            while idx < len(events):
                evt = events[idx]
                idx_val = idx
                idx += 1
                yield {
                    "event": evt.get("type", "message"),
                    "data": json.dumps({"index": idx_val, **evt}, cls=_DecimalEncoder),
                }

            status = cached.get("status", "")
            if status in ("completed", "failed"):
                yield {"event": "done", "data": json.dumps({"status": status})}
                return

            await asyncio.sleep(1)

    return EventSourceResponse(event_stream())
