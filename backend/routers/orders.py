"""Orders router — extracted from server.py.

Owns all /api/orders* endpoints plus the exclusivity-aware totals engine.

Exclusivity rule (per user, Iter 13):
    A product line that already received ONE promotion cannot receive another.
    Promotions include:
      • Live Happy-Hour pricing (`hh_pct > 0` on the line)
      • Matched Combo/Deal
      • Order-level manual discount (percent or cash)
    Precedence when there's a conflict is: HH  ->  Combo  ->  Order-level discount.
"""
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

from deps import db, _oid, serialize, sl
from auth import make_current_user_dep
from models import OrderIn, OrderUpdate, PaymentIn, AutoCloseIn, MoveLineIn, MergeOrdersIn
from routers.kegs import decrement_kegs_for_order

HK_TZ = ZoneInfo("Asia/Hong_Kong")

get_current_user = make_current_user_dep(lambda: db)

router = APIRouter(prefix="/api", tags=["orders"])


# ---------- Exclusivity engine ----------
def _combo_matches(c, line_qtys):
    """Slots satisfied by line_qtys={pid: qty}. Callers must zero out any pid
    already locked by a higher-priority promotion (HH or an earlier combo)."""
    slots = c.get("slots") or []
    if not slots:
        required = set(c.get("product_ids") or [])
        return bool(required) and all(line_qtys.get(pid, 0) >= 1 for pid in required)
    for slot in slots:
        pids = slot.get("product_ids") or []
        if not pids:
            return False
        counts = {pid: line_qtys.get(pid, 0) for pid in pids}
        total = sum(counts.values())
        min_q = slot.get("min_qty", 1) or 1
        max_q = slot.get("max_qty", 99) or 99
        if slot.get("operator", "or") == "and":
            if not all(c_ >= 1 for c_ in counts.values()):
                return False
            if any(c_ > max_q for c_ in counts.values()):
                return False
        else:
            if total < min_q or total > max_q:
                return False
    return True


def _combo_involved_pids(c):
    if c.get("slots"):
        pids = set()
        for s in c["slots"]:
            pids |= set(s.get("product_ids") or [])
        return pids
    return set(c.get("product_ids") or [])


def _compute_totals(lines, discount_type, discount_value, service_charge_pct, combos=None):
    """See module docstring for the exclusivity rule."""
    subtotal = sum(l["price"] * l["qty"] for l in lines)
    discount = 0.0
    combo_discount = 0.0
    combos_applied = []

    # 1) HH lock — any line whose register already applied happy-hour pricing
    hh_locked = {
        l.get("product_id")
        for l in lines
        if (l.get("hh_pct") or 0) > 0 and l.get("product_id")
    }

    # 2) Build combo-eligible qty map (skip HH-locked pids entirely)
    line_qtys: dict = {}
    for l in lines:
        pid = l.get("product_id")
        if pid and pid not in hh_locked and (l.get("qty") or 0) > 0:
            line_qtys[pid] = line_qtys.get(pid, 0) + l["qty"]

    combo_locked: set = set()
    if combos:
        def _potential(c):
            return (
                subtotal * (c.get("discount_value", 0) / 100)
                if c.get("discount_type") == "percent"
                else c.get("discount_value", 0)
            )

        # Greedy best-first — biggest discount wins; downstream combos with any
        # overlapping product are skipped (mutual exclusivity).
        for c in sorted(
            [c for c in combos if c.get("active", True)],
            key=_potential,
            reverse=True,
        ):
            involved = _combo_involved_pids(c)
            if involved & combo_locked:
                continue
            if not _combo_matches(c, line_qtys):
                continue
            d = _potential(c)
            combo_discount += d
            combos_applied.append({
                "name": c.get("name"),
                "discount_type": c.get("discount_type"),
                "discount_value": c.get("discount_value"),
                "applied_discount": round(d, 2),
                "locked_product_ids": list(involved),
            })
            combo_locked |= involved
            for pid in involved:
                line_qtys.pop(pid, None)

    # 3) Order-level discount only against lines NOT locked by HH or a combo
    promo_locked = hh_locked | combo_locked
    disc_base = sum(
        l["price"] * l["qty"] for l in lines if l.get("product_id") not in promo_locked
    )
    if discount_type == "percent":
        discount = disc_base * (discount_value / 100.0)
    elif discount_type == "cash":
        discount = min(discount_value, disc_base)

    net = max(0.0, subtotal - discount - combo_discount)
    service = round(net * (service_charge_pct / 100.0), 2)
    total = round(net + service, 2)
    return {
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "combo_discount": round(combo_discount, 2),
        "combos_applied": combos_applied,
        "hh_locked_product_ids": list(hh_locked),
        "combo_locked_product_ids": list(combo_locked),
        "service_charge": service,
        "total": total,
    }


async def _active_combos():
    """Deal-Of-The-Night — only return combos whose schedule window matches
    the current Hong Kong time (or combos with no schedule, i.e. always-on)."""
    docs = await db.combos.find({"active": True}).to_list(200)
    now = datetime.now(HK_TZ)
    return [c for c in docs if _combo_in_window(c, now)]


def _combo_in_window(c: dict, now_hk: datetime) -> bool:
    sch = c.get("schedule") or {}
    if not sch:
        return True
    days = sch.get("days") or []
    if days and now_hk.weekday() not in days:
        return False
    start, end = sch.get("start_time"), sch.get("end_time")
    if not start or not end:
        return True
    cur = now_hk.strftime("%H:%M")
    if start <= end:
        return start <= cur <= end
    return cur >= start or cur <= end


# ---------- Endpoints ----------
@router.get("/orders")
async def list_orders(status: Optional[str] = None, limit: int = 100, user: dict = Depends(get_current_user)):
    q = {"status": status} if status else {}
    return sl(await db.orders.find(q).sort("opened_at", -1).to_list(limit))


@router.get("/orders/{oid}")
async def get_order(oid: str, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    return serialize(o)


@router.post("/orders")
async def create_order(body: OrderIn, user: dict = Depends(get_current_user)):
    lines = [l.model_dump() for l in body.lines]
    combos = await _active_combos()
    totals = _compute_totals(lines, body.discount_type, body.discount_value, body.service_charge_pct, combos)
    doc = body.model_dump()
    doc["lines"] = lines
    doc.update(totals)
    doc["status"] = "open"
    doc["server_id"] = body.server_id or user["id"]
    doc["opened_at"] = datetime.now(timezone.utc).isoformat()
    doc["closed_at"] = None
    r = await db.orders.insert_one(doc)
    order_id = str(r.inserted_id)
    if body.table_id:
        await db.tables.update_one(
            {"_id": _oid(body.table_id)},
            {"$set": {"status": "occupied", "current_order_id": order_id}},
        )
    doc["_id"] = r.inserted_id
    return serialize(doc)


@router.patch("/orders/{oid}")
async def update_order(oid: str, body: OrderUpdate, user: dict = Depends(get_current_user)):
    existing = await db.orders.find_one({"_id": _oid(oid)})
    if not existing:
        raise HTTPException(404, "Not found")
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    combos = await _active_combos()
    if "lines" in update:
        totals = _compute_totals(
            update["lines"],
            update.get("discount_type", existing.get("discount_type", "none")),
            update.get("discount_value", existing.get("discount_value", 0)),
            existing.get("service_charge_pct", 10),
            combos,
        )
        update.update(totals)
    elif "discount_type" in update or "discount_value" in update:
        totals = _compute_totals(
            existing["lines"],
            update.get("discount_type", existing.get("discount_type", "none")),
            update.get("discount_value", existing.get("discount_value", 0)),
            existing.get("service_charge_pct", 10),
            combos,
        )
        update.update(totals)
    await db.orders.update_one({"_id": _oid(oid)}, {"$set": update})
    return serialize(await db.orders.find_one({"_id": _oid(oid)}))


@router.post("/orders/{oid}/fire")
async def fire_order(oid: str, course: Optional[str] = None, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    lines = o.get("lines", [])
    fired = 0
    for l in lines:
        if l.get("held") and (course is None or l.get("course") == course):
            l["held"] = False
            l["fired_at"] = datetime.now(timezone.utc).isoformat()
            fired += 1
    await db.orders.update_one({"_id": _oid(oid)}, {"$set": {"lines": lines}})
    return {"fired": fired}


@router.post("/orders/{oid}/pay")
async def pay_order(oid: str, body: PaymentIn, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    change = 0.0
    if body.method == "split":
        paid = sum((s.get("amount") or 0) for s in body.splits)
        if paid + 0.01 < o["total"]:
            raise HTTPException(400, f"Split total HK${paid:.2f} is less than order total HK${o['total']:.2f}")
        change = round(paid - o["total"], 2)
    elif body.method == "cash":
        change = round(body.amount - o["total"], 2)
    payment = {
        "method": body.method, "amount": body.amount, "tip": body.tip,
        "splits": body.splits, "change": max(change, 0),
        "paid_at": datetime.now(timezone.utc).isoformat(),
        "cashier_id": user["id"],
    }
    await db.orders.update_one(
        {"_id": _oid(oid)},
        {"$set": {"status": "paid", "payment": payment,
                  "closed_at": datetime.now(timezone.utc).isoformat()}},
    )
    if o.get("table_id"):
        await db.tables.update_one(
            {"_id": _oid(o["table_id"])},
            {"$set": {"status": "dirty", "current_order_id": None}},
        )
    try:
        await decrement_kegs_for_order(o)
    except Exception:
        pass
    if o.get("member_id"):
        opened = o.get("opened_at")
        dur_min = 0
        if opened:
            try:
                d = datetime.now(timezone.utc) - datetime.fromisoformat(opened)
                dur_min = int(d.total_seconds() / 60)
            except Exception:
                dur_min = 0
        item_names = [l["name"] for l in o.get("lines", [])]
        member = await db.members.find_one({"_id": _oid(o["member_id"])})
        if member:
            visits = member.get("visits", 0) + 1
            lifetime = member.get("lifetime_spend", 0.0) + o["total"]
            points = member.get("points", 0) + int(o["total"] // 10)
            fav = list(set((member.get("favorite_items") or []) + item_names))[:20]
            avg_prev = member.get("avg_duration_min", 0) or 0
            avg_new = int(((avg_prev * (visits - 1)) + dur_min) / max(visits, 1))
            await db.members.update_one(
                {"_id": _oid(o["member_id"])},
                {"$set": {
                    "visits": visits, "lifetime_spend": lifetime,
                    "points": points, "favorite_items": fav,
                    "avg_duration_min": avg_new,
                }},
            )
    return serialize(await db.orders.find_one({"_id": _oid(oid)}))


@router.delete("/orders/{oid}")
async def void_order(oid: str, user: dict = Depends(get_current_user)):
    if user["role"] not in ("admin", "manager"):
        raise HTTPException(403, "Manager override required to void")
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    await db.orders.update_one({"_id": _oid(oid)}, {"$set": {"status": "voided"}})
    if o.get("table_id"):
        await db.tables.update_one(
            {"_id": _oid(o["table_id"])},
            {"$set": {"status": "available", "current_order_id": None}},
        )
    return {"ok": True}


@router.post("/orders/{oid}/bump/{index}")
async def bump_line(oid: str, index: int, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    lines = o.get("lines", [])
    if index < 0 or index >= len(lines):
        raise HTTPException(400, "Bad line index")
    lines[index]["bumped_at"] = datetime.now(timezone.utc).isoformat()
    lines[index]["bumped_by"] = user["id"]
    await db.orders.update_one({"_id": _oid(oid)}, {"$set": {"lines": lines}})
    return {"ok": True, "bumped_at": lines[index]["bumped_at"]}


# ---------- Auto-Close Tabs (manager only) ----------
@router.post("/orders/auto-close")
async def auto_close_tabs(body: AutoCloseIn, user: dict = Depends(get_current_user)):
    """Batch-settle every open tab at last call. Used at 03:00 HK / closing time.
    Manager/admin only. Records payment.method=body.method + note; frees tables."""
    if user["role"] not in ("admin", "manager"):
        raise HTTPException(403, "Manager override required")
    orders = await db.orders.find({"status": "open"}).to_list(1000)
    now_iso = datetime.now(timezone.utc).isoformat()
    closed = 0
    revenue = 0.0
    for o in orders:
        payment = {
            "method": body.method,
            "amount": o.get("total", 0),
            "tip": 0.0,
            "splits": [],
            "change": 0,
            "paid_at": now_iso,
            "cashier_id": user["id"],
            "auto_closed": True,
            "note": body.note,
        }
        await db.orders.update_one(
            {"_id": o["_id"]},
            {"$set": {"status": "paid", "payment": payment, "closed_at": now_iso}},
        )
        if o.get("table_id"):
            await db.tables.update_one(
                {"_id": _oid(o["table_id"])},
                {"$set": {"status": "dirty", "current_order_id": None}},
            )
        try:
            await decrement_kegs_for_order(o)
        except Exception:
            pass
        closed += 1
        revenue += o.get("total", 0)
    return {"closed": closed, "revenue": round(revenue, 2), "method": body.method}


# ---------- Split / Merge seats ----------
@router.post("/orders/{oid}/move-line")
async def move_line(oid: str, body: MoveLineIn, user: dict = Depends(get_current_user)):
    """Move a line to another seat (same order) or to another order entirely."""
    src = await db.orders.find_one({"_id": _oid(oid)})
    if not src:
        raise HTTPException(404, "Source order not found")
    lines = src.get("lines", [])
    if body.line_index < 0 or body.line_index >= len(lines):
        raise HTTPException(400, "Bad line index")

    combos = await _active_combos()

    if body.target_order_id and body.target_order_id != oid:
        tgt = await db.orders.find_one({"_id": _oid(body.target_order_id)})
        if not tgt:
            raise HTTPException(404, "Target order not found")
        moved = lines.pop(body.line_index)
        if body.target_seat is not None:
            moved["seat"] = int(body.target_seat)
        tgt_lines = list(tgt.get("lines", [])) + [moved]
        src_totals = _compute_totals(lines, src.get("discount_type", "none"), src.get("discount_value", 0), src.get("service_charge_pct", 10), combos)
        tgt_totals = _compute_totals(tgt_lines, tgt.get("discount_type", "none"), tgt.get("discount_value", 0), tgt.get("service_charge_pct", 10), combos)
        await db.orders.update_one({"_id": src["_id"]}, {"$set": {"lines": lines, **src_totals}})
        await db.orders.update_one({"_id": tgt["_id"]}, {"$set": {"lines": tgt_lines, **tgt_totals}})
        return {"ok": True, "moved_to": str(tgt["_id"])}

    # Same-order reseat
    if body.target_seat is None:
        raise HTTPException(400, "target_seat required for same-order move")
    lines[body.line_index]["seat"] = int(body.target_seat)
    await db.orders.update_one({"_id": src["_id"]}, {"$set": {"lines": lines}})
    return {"ok": True, "seat": body.target_seat}


@router.post("/orders/merge")
async def merge_orders(body: MergeOrdersIn, user: dict = Depends(get_current_user)):
    """Merge source tab into target tab. Source order voided, source table freed."""
    if body.source_id == body.target_id:
        raise HTTPException(400, "Source and target must differ")
    src = await db.orders.find_one({"_id": _oid(body.source_id)})
    tgt = await db.orders.find_one({"_id": _oid(body.target_id)})
    if not src or not tgt:
        raise HTTPException(404, "Order not found")
    if src.get("status") != "open" or tgt.get("status") != "open":
        raise HTTPException(400, "Both orders must be open")
    combos = await _active_combos()
    merged_lines = list(tgt.get("lines", [])) + list(src.get("lines", []))
    totals = _compute_totals(merged_lines, tgt.get("discount_type", "none"), tgt.get("discount_value", 0), tgt.get("service_charge_pct", 10), combos)
    await db.orders.update_one({"_id": tgt["_id"]}, {"$set": {"lines": merged_lines, **totals}})
    await db.orders.update_one(
        {"_id": src["_id"]},
        {"$set": {"status": "voided", "voided_reason": "merged", "merged_into": body.target_id,
                  "closed_at": datetime.now(timezone.utc).isoformat()}},
    )
    if src.get("table_id"):
        await db.tables.update_one(
            {"_id": _oid(src["table_id"])},
            {"$set": {"status": "available", "current_order_id": None}},
        )
    return {"ok": True, "merged_into": body.target_id, "line_count": len(merged_lines), "total": totals["total"]}
