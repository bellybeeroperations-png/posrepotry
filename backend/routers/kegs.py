"""Kegs router — 35+ tap tracker with volume + low-level alerts + prep-view aggregation."""
from datetime import datetime, timezone
from typing import Optional, Literal, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import db, _oid, serialize, sl
from auth import make_current_user_dep

get_current_user = make_current_user_dep(lambda: db)

router = APIRouter(prefix="/api", tags=["kegs"])


class KegIn(BaseModel):
    name: str
    product_id: str
    size_ml: int = 30000  # 30L standard HK keg
    ml_per_pour: int = 568  # UK pint
    threshold_pct: float = 10.0


@router.get("/kegs")
async def list_kegs(user: dict = Depends(get_current_user)):
    docs = await db.kegs.find().sort("name", 1).to_list(200)
    prods = {str(p["_id"]): p for p in await db.products.find().to_list(2000)}
    out = []
    for d in docs:
        s = serialize(d)
        s["product"] = serialize(prods.get(d.get("product_id"))) if prods.get(d.get("product_id")) else None
        pct = 0
        if s.get("size_ml"):
            pct = round(100 * (s.get("current_ml", 0) or 0) / s["size_ml"], 1)
        s["pct_remaining"] = pct
        s["alert"] = pct <= s.get("threshold_pct", 10) and s.get("status") == "on"
        out.append(s)
    return out


@router.post("/kegs")
async def create_keg(body: KegIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({
        "current_ml": body.size_ml,
        "status": "on",
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r = await db.kegs.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@router.patch("/kegs/{kid}")
async def update_keg(kid: str, body: KegIn, user: dict = Depends(get_current_user)):
    await db.kegs.update_one({"_id": _oid(kid)}, {"$set": body.model_dump()})
    return serialize(await db.kegs.find_one({"_id": _oid(kid)}))


@router.post("/kegs/{kid}/new")
async def install_new_keg(kid: str, user: dict = Depends(get_current_user)):
    """Mark a keg as freshly changed — reset volume and status."""
    k = await db.kegs.find_one({"_id": _oid(kid)})
    if not k:
        raise HTTPException(404, "Not found")
    await db.kegs.update_one(
        {"_id": _oid(kid)},
        {"$set": {
            "current_ml": k["size_ml"],
            "status": "on",
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return serialize(await db.kegs.find_one({"_id": _oid(kid)}))


@router.post("/kegs/{kid}/blown")
async def mark_blown(kid: str, user: dict = Depends(get_current_user)):
    await db.kegs.update_one({"_id": _oid(kid)}, {"$set": {"status": "blown", "current_ml": 0}})
    return serialize(await db.kegs.find_one({"_id": _oid(kid)}))


@router.delete("/kegs/{kid}")
async def delete_keg(kid: str, user: dict = Depends(get_current_user)):
    await db.kegs.delete_one({"_id": _oid(kid)})
    return {"ok": True}


async def decrement_kegs_for_order(order: dict):
    """Called by orders_pay — subtract ml per pour for every line matching an on-tap keg.
    When multiple on-tap kegs share the same product_id (main + backup), drain the
    lowest-current_ml keg first so the near-empty tap blows before the backup.
    Every pour is logged to keg_pours for the 7-day velocity analytics."""
    kegs = await db.kegs.find({"status": "on"}).to_list(200)
    kegs.sort(key=lambda k: (k.get("current_ml") or 0))
    by_pid = {}
    for k in kegs:
        by_pid.setdefault(k["product_id"], k)
    now_iso = datetime.now(timezone.utc).isoformat()
    pour_docs = []
    for l in order.get("lines", []):
        pid = l.get("product_id")
        if pid not in by_pid:
            continue
        k = by_pid[pid]
        qty = l.get("qty") or 1
        pour = (k.get("ml_per_pour") or 568) * qty
        new_ml = max(0, (k.get("current_ml") or 0) - pour)
        upd = {"current_ml": new_ml}
        if new_ml == 0:
            upd["status"] = "blown"
        await db.kegs.update_one({"_id": k["_id"]}, {"$set": upd})
        k["current_ml"] = new_ml
        pour_docs.append({
            "keg_id": str(k["_id"]),
            "product_id": pid,
            "ml": pour,
            "qty": qty,
            "at": now_iso,
        })
    if pour_docs:
        await db.keg_pours.insert_many(pour_docs)


@router.get("/kegs/{kid}/pours")
async def keg_pours(kid: str, days: int = 7, user: dict = Depends(get_current_user)):
    """Return per-day pour volume for the last N days (default 7)."""
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    docs = await db.keg_pours.find({"keg_id": kid, "at": {"$gte": since}}).to_list(5000)
    by_day: dict = {}
    for d in docs:
        day = d["at"][:10]  # YYYY-MM-DD
        by_day[day] = by_day.get(day, 0) + (d.get("ml") or 0)
    # Fill missing days with 0 so the chart line stays continuous
    out = []
    for i in range(days - 1, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat()
        out.append({"day": day, "ml": by_day.get(day, 0), "pints": round(by_day.get(day, 0) / 568, 1)})
    total_ml = sum(d["ml"] for d in out)
    return {"days": out, "total_ml": total_ml, "total_pints": round(total_ml / 568, 1)}


@router.post("/kds/prep/bump")
async def prep_bump_all(product_id: str, user: dict = Depends(get_current_user)):
    """Bump every fired-not-bumped line matching product_id across all open orders."""
    orders = await db.orders.find({"status": "open"}).to_list(500)
    bumped = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for o in orders:
        lines = o.get("lines", [])
        changed = False
        for l in lines:
            if l.get("product_id") == product_id and l.get("fired_at") and not l.get("bumped_at") and not l.get("held"):
                l["bumped_at"] = now_iso
                l["bumped_by"] = user["id"]
                bumped += 1
                changed = True
        if changed:
            await db.orders.update_one({"_id": o["_id"]}, {"$set": {"lines": lines}})
    return {"bumped": bumped}


# ---------- Prep view (consolidated kitchen batch) ----------
@router.get("/kds/prep")
async def prep_view(user: dict = Depends(get_current_user)):
    """Group fired items across open orders by product — kitchen bulk-cook view."""
    orders = await db.orders.find({"status": "open"}).to_list(500)
    tables = {str(t["_id"]): t for t in await db.tables.find().to_list(500)}
    prods = {str(p["_id"]): p for p in await db.products.find().to_list(2000)}
    prep: dict = {}
    for o in orders:
        raw_name = tables.get(o.get("table_id") or "", {}).get("name")
        tname = raw_name or (o.get("order_type", "") or "").upper() or "—"
        for l in o.get("lines", []):
            if l.get("held") or not l.get("fired_at") or l.get("bumped_at"):
                continue
            key = l.get("product_id") or l["name"]
            if key not in prep:
                p = prods.get(l.get("product_id") or "")
                prep[key] = {
                    "product_id": l.get("product_id"),
                    "name": (p or {}).get("name") or l["name"],
                    "kind": (p or {}).get("kind") or ("drink" if l.get("course") == "drink" else "food"),
                    "course": l.get("course"),
                    "total": 0,
                    "tables": {},
                }
            prep[key]["total"] += l.get("qty") or 1
            prep[key]["tables"][tname] = prep[key]["tables"].get(tname, 0) + (l.get("qty") or 1)
    out = []
    for v in prep.values():
        out.append({
            **v,
            "tables": [{"name": k, "qty": q} for k, q in sorted(v["tables"].items(), key=lambda x: -x[1])],
        })
    out.sort(key=lambda x: -x["total"])
    return out
