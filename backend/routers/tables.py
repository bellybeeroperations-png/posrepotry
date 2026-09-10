"""Orders + Tables router — extracted from server.py so payments live beside orders.
Uses shared deps and delegates to server.py-level helpers for compute_totals/keg
decrement to avoid circular imports."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import db, _oid, serialize, sl
from auth import make_current_user_dep
from models import TableIn, TablePosIn

get_current_user = make_current_user_dep(lambda: db)

router = APIRouter(prefix="/api", tags=["tables"])


@router.get("/tables")
async def list_tables(area_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"area_id": area_id} if area_id else {}
    tables = sl(await db.tables.find(q).to_list(500))
    for t in tables:
        if t.get("current_order_id"):
            o = await db.orders.find_one({"_id": _oid(t["current_order_id"])})
            if o:
                t["current_order"] = {
                    "id": str(o["_id"]),
                    "total": o.get("total", 0),
                    "guests": o.get("guests", 1),
                    "opened_at": o.get("opened_at"),
                }
        if t.get("reservation_id"):
            r = await db.reservations.find_one({"_id": _oid(t["reservation_id"])})
            if r:
                t["reservation"] = {
                    "id": str(r["_id"]),
                    "guest_name": r["guest_name"],
                    "phone": r["phone"],
                    "party_size": r["party_size"],
                    "reserved_for": r["reserved_for"],
                }
    return tables


@router.post("/tables")
async def create_table(body: TableIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["status"] = "available"
    doc["current_order_id"] = None
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.tables.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@router.patch("/tables/{table_id}")
async def update_table(table_id: str, body: TablePosIn, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.tables.update_one({"_id": _oid(table_id)}, {"$set": update})
    return serialize(await db.tables.find_one({"_id": _oid(table_id)}))


@router.delete("/tables/{table_id}")
async def delete_table(table_id: str, user: dict = Depends(get_current_user)):
    await db.tables.delete_one({"_id": _oid(table_id)})
    return {"ok": True}


@router.post("/tables/{tid}/clear")
async def clear_table(tid: str, user: dict = Depends(get_current_user)):
    await db.tables.update_one({"_id": _oid(tid)}, {"$set": {"status": "available", "current_order_id": None}})
    return {"ok": True}


@router.post("/tables/{tid}/status")
async def set_status(tid: str, status: str, user: dict = Depends(get_current_user)):
    await db.tables.update_one({"_id": _oid(tid)}, {"$set": {"status": status}})
    return {"ok": True}
