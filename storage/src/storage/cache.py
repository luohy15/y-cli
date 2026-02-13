"""DynamoDB cache layer for active chats.

Single-table design: one item per chat.
Schema:
    id (S)              - chat UUID (partition key)
    status (S)          - pending | running | waiting_approval | completed | failed
    bot_name (S)        - which bot config to use (optional)
    prompt (S)          - user's initial query
    messages (L)        - conversation messages (list of dicts)
    events (L)          - transient SSE events (list of {type, data} dicts)
    pending_approval (M)- transient approval state (optional)
    created_at (S)      - ISO8601 timestamp
    updated_at (S)      - ISO8601 timestamp
    ttl (N)             - Unix epoch for DynamoDB TTL
"""

import os
import time
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

from storage.util import get_iso8601_timestamp


def _get_table_name() -> str:
    return os.environ.get("DYNAMODB_TABLE", "y-agent-jobs")


def _get_dynamodb_client():
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    region = os.environ.get("AWS_REGION", "us-east-1")
    kwargs: Dict[str, Any] = {"region_name": region}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client("dynamodb", **kwargs)


_serializer = TypeSerializer()
_deserializer = TypeDeserializer()


def _serialize(value: Any) -> Any:
    return _serializer.serialize(value)


def _deserialize_item(item: Dict) -> Dict:
    return {k: _deserializer.deserialize(v) for k, v in item.items()}


# ---------------------------------------------------------------------------
# Chat cache CRUD
# ---------------------------------------------------------------------------

def cache_chat(
    chat_id: str,
    data: Dict,
    ttl_seconds: int = 86400,
) -> None:
    """Write a chat dict (+ transient fields) to DynamoDB cache."""
    now = get_iso8601_timestamp()
    item: Dict[str, Any] = {
        **data,
        "id": chat_id,
        "updated_at": now,
        "ttl": int(time.time()) + ttl_seconds,
    }
    item.setdefault("events", [])
    item.setdefault("created_at", now)

    dynamo_item = {k: _serialize(v) for k, v in item.items()}

    client = _get_dynamodb_client()
    client.put_item(TableName=_get_table_name(), Item=dynamo_item)


def get_cached_chat(chat_id: str) -> Optional[Dict]:
    """Fetch a chat from cache by ID. Returns None on miss."""
    client = _get_dynamodb_client()
    resp = client.get_item(
        TableName=_get_table_name(),
        Key={"id": _serialize(chat_id)},
    )
    raw = resp.get("Item")
    if not raw:
        return None
    return _deserialize_item(raw)


def update_chat_status(chat_id: str, status: str) -> None:
    """Set chat status in cache."""
    client = _get_dynamodb_client()
    client.update_item(
        TableName=_get_table_name(),
        Key={"id": _serialize(chat_id)},
        UpdateExpression="SET #s = :s, updated_at = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": _serialize(status),
            ":u": _serialize(get_iso8601_timestamp()),
        },
    )


def append_event(chat_id: str, event: Dict) -> None:
    """Append an event to the chat's events list in cache."""
    client = _get_dynamodb_client()
    client.update_item(
        TableName=_get_table_name(),
        Key={"id": _serialize(chat_id)},
        UpdateExpression="SET events = list_append(events, :e), updated_at = :u",
        ExpressionAttributeValues={
            ":e": _serialize([event]),
            ":u": _serialize(get_iso8601_timestamp()),
        },
    )


def save_chat_state(
    chat_id: str,
    messages: List[Dict],
    pending_approval: Optional[Dict] = None,
) -> None:
    """Save conversation messages and optional pending approval to cache.

    Called by worker before exiting (either on completion or waiting_approval).
    """
    expr = "SET messages = :m, updated_at = :u"
    vals: Dict[str, Any] = {
        ":m": _serialize(messages),
        ":u": _serialize(get_iso8601_timestamp()),
    }
    if pending_approval is not None:
        expr += ", pending_approval = :pa"
        vals[":pa"] = _serialize(pending_approval)

    client = _get_dynamodb_client()
    client.update_item(
        TableName=_get_table_name(),
        Key={"id": _serialize(chat_id)},
        UpdateExpression=expr,
        ExpressionAttributeValues=vals,
    )


def claim_pending_chat() -> Optional[Dict]:
    """Scan for a pending chat and atomically claim it (set status=running).

    Returns the chat dict if one was claimed, None otherwise.
    """
    client = _get_dynamodb_client()
    scan_kwargs = {
        "TableName": _get_table_name(),
        "FilterExpression": "#s = :s",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":s": _serialize("pending")},
    }
    items = []
    while not items:
        resp = client.scan(**scan_kwargs)
        items = resp.get("Items", [])
        if items:
            break
        if "LastEvaluatedKey" not in resp:
            return None
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    chat = _deserialize_item(items[0])
    chat_id = chat["id"]

    try:
        client.update_item(
            TableName=_get_table_name(),
            Key={"id": _serialize(chat_id)},
            UpdateExpression="SET #s = :running, updated_at = :u",
            ConditionExpression="#s = :pending",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":running": _serialize("running"),
                ":pending": _serialize("pending"),
                ":u": _serialize(get_iso8601_timestamp()),
            },
        )
    except client.exceptions.ConditionalCheckFailedException:
        return None

    chat["status"] = "running"
    return chat


def resolve_approval(chat_id: str, approved: bool) -> None:
    """Client approves/denies, sets approved flag and moves chat back to pending."""
    client = _get_dynamodb_client()
    client.update_item(
        TableName=_get_table_name(),
        Key={"id": _serialize(chat_id)},
        UpdateExpression="SET pending_approval.approved = :a, #s = :p, updated_at = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":a": _serialize(approved),
            ":p": _serialize("pending"),
            ":u": _serialize(get_iso8601_timestamp()),
        },
    )


def list_cached_chats() -> List[Dict]:
    """Scan all cached chats and return summaries sorted by created_at desc."""
    client = _get_dynamodb_client()
    scan_kwargs = {
        "TableName": _get_table_name(),
        "ProjectionExpression": "id, #s, prompt, created_at, updated_at",
        "ExpressionAttributeNames": {"#s": "status"},
    }
    items = []
    while True:
        resp = client.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    chats = [_deserialize_item(item) for item in items]
    chats.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return chats
