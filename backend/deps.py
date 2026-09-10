"""Shared FastAPI dependencies (splits server.py into routers)."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from bson import ObjectId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

HK_TZ = ZoneInfo("Asia/Hong_Kong")

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = _client[os.environ["DB_NAME"]]


def _oid(x: str) -> ObjectId:
    try:
        return ObjectId(x)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def serialize(doc: dict) -> dict:
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def sl(docs: list) -> list:
    return [serialize(d) for d in docs]


def now_iso() -> str:
    return datetime.now(HK_TZ).isoformat()
