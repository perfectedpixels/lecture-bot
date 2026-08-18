"""
Shareable Explore Canvas boards (DynamoDB-backed).

lecture-bot has no user accounts (anonymous students), so board "ownership"
uses a client-side bearer token instead of a real identity: on create, a
random secret is generated and returned exactly once; the caller must present
it again to update/delete. Only its SHA-256 hash is ever stored, so a table
read or log leak can't hand out a usable credential. Anyone without the token
can still read/list a board and "save a copy" (a fresh `create_board` call).

Single-tenant, single table, composite key so `list_boards` stays a cheap
Query instead of a Scan:

    pk = "BOARDS"
    sk = "BOARD#{board_id}"
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

PK = "BOARDS"
MAX_DATA_CHARS = 350_000  # headroom under DynamoDB's 400 KB item limit
MAX_TITLE = 200

_TABLE = None


def _table():
    global _TABLE
    if _TABLE is None:
        table_name = os.environ.get("BOARDS_TABLE_NAME", "lecture-bot-explore-boards")
        aws_region = (
            os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        _TABLE = boto3.resource("dynamodb", region_name=aws_region).Table(table_name)
    return _TABLE


def _sk(board_id: str) -> str:
    return f"BOARD#{board_id}"


def generate_owner_token() -> str:
    return secrets.token_hex(24)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _dump(data: Any) -> str:
    s = json.dumps(data, separators=(",", ":"), default=str)
    if len(s) > MAX_DATA_CHARS:
        raise ValueError(f"board too large ({len(s)} chars > {MAX_DATA_CHARS}); prune the canvas")
    return s


def create_board(*, title: str, data: Any) -> Dict[str, Any]:
    """Returns {"board": summary, "owner_token": <raw secret — only ever returned here>}."""
    title = (title or "Untitled board").strip()[:MAX_TITLE]
    board_id = uuid.uuid4().hex[:12]
    owner_token = generate_owner_token()
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "pk": PK,
        "sk": _sk(board_id),
        "board_id": board_id,
        "title": title,
        "owner_token_hash": _hash_token(owner_token),
        "data_json": _dump(data),
        "created_at": now,
        "updated_at": now,
    }
    _table().put_item(Item=item)
    return {"board": _summary(item), "owner_token": owner_token}


def update_board(
    board_id: str,
    *,
    owner_token: str,
    title: Optional[str] = None,
    data: Any = None,
) -> Optional[Dict[str, Any]]:
    """Token-gated update. Returns the summary, or None on mismatch/missing board."""
    sets = ["updated_at = :u"]
    values: Dict[str, Any] = {
        ":u": datetime.now(timezone.utc).isoformat(),
        ":h": _hash_token(owner_token),
    }
    if title is not None:
        sets.append("title = :t")
        values[":t"] = title.strip()[:MAX_TITLE]
    if data is not None:
        sets.append("data_json = :d")
        values[":d"] = _dump(data)
    try:
        resp = _table().update_item(
            Key={"pk": PK, "sk": _sk(board_id)},
            UpdateExpression="SET " + ", ".join(sets),
            ConditionExpression="attribute_exists(pk) AND owner_token_hash = :h",
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return None
        raise
    return _summary(resp["Attributes"])


def get_board(board_id: str) -> Optional[Dict[str, Any]]:
    resp = _table().get_item(Key={"pk": PK, "sk": _sk(board_id)})
    item = resp.get("Item")
    if not item:
        return None
    out = _summary(item)
    try:
        out["data"] = json.loads(item.get("data_json") or "null")
    except json.JSONDecodeError:
        out["data"] = None
    return out


def list_boards() -> List[Dict[str, Any]]:
    resp = _table().query(
        KeyConditionExpression="pk = :pk AND begins_with(sk, :p)",
        ExpressionAttributeValues={":pk": PK, ":p": "BOARD#"},
    )
    boards = [_summary(i) for i in resp.get("Items", [])]
    boards.sort(key=lambda b: b.get("updated_at") or "", reverse=True)
    return boards


def delete_board(board_id: str, *, owner_token: str) -> bool:
    try:
        _table().delete_item(
            Key={"pk": PK, "sk": _sk(board_id)},
            ConditionExpression="attribute_exists(pk) AND owner_token_hash = :h",
            ExpressionAttributeValues={":h": _hash_token(owner_token)},
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise
    return True


def _summary(item: Dict[str, Any]) -> Dict[str, Any]:
    # owner_token_hash is deliberately never included — it never leaves this module.
    return {
        "board_id": item.get("board_id"),
        "title": item.get("title"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
