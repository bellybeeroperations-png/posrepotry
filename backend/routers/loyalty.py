"""Loyalty & rewards — points, tiers, stamps, spin wheel, scratch tickets,
vouchers, birthday auto-issue. Auto-hooked from orders.pay_order."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import db, _oid, serialize, sl
from auth import make_current_user_dep

get_current_user = make_current_user_dep(lambda: db)
router = APIRouter(prefix="/api/loyalty", tags=["loyalty"])


# --------- Tier ladder ---------
TIERS = [
    {"name": "Bronze",   "min_spend": 0,     "point_multiplier": 1.0, "bday_pct": 5,  "perks": ["1× points", "Birthday −5%"]},
    {"name": "Silver",   "min_spend": 5000,  "point_multiplier": 1.25,"bday_pct": 10, "perks": ["1.25× points", "Priority seating", "Birthday −10%"]},
    {"name": "Gold",     "min_spend": 15000, "point_multiplier": 1.5, "bday_pct": 15, "perks": ["1.5× points", "Secret menu preview", "Free extra spins", "Birthday −15%"]},
    {"name": "Platinum", "min_spend": 50000, "point_multiplier": 2.0, "bday_pct": 25, "perks": ["2× points", "Chef's table invite", "VIP stamps 2×", "Birthday −25%"]},
]

STAMP_GOAL = 10


def tier_for(spend: float) -> dict:
    return next(t for t in reversed(TIERS) if spend >= t["min_spend"])


# --------- Voucher schema ---------
async def _issue_voucher(member_id: str, kind: str, title: str,
                         discount_type: str, discount_value: float,
                         source: str, ttl_days: int = 60) -> dict:
    now = datetime.now(timezone.utc)
    code = "V-" + secrets.token_hex(4).upper()
    doc = {
        "member_id": member_id,
        "code": code, "kind": kind, "title": title,
        "discount_type": discount_type, "discount_value": discount_value,
        "expires_at": (now + timedelta(days=ttl_days)).isoformat(),
        "redeemed_at": None, "redeemed_order_id": None,
        "source": source,
        "created_at": now.isoformat(),
    }
    r = await db.vouchers.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


# --------- Spin wheel prize pool (weighted) ---------
SPIN_PRIZES = [
    ("points_50",     40, {"kind": "points", "value": 50,  "title": "+50 points"}),
    ("points_100",    22, {"kind": "points", "value": 100, "title": "+100 points"}),
    ("stamp_bonus",   15, {"kind": "stamp",  "value": 1,   "title": "+1 stamp"}),
    ("voucher_20",    10, {"kind": "voucher","value": 20,  "title": "HK$20 off voucher"}),
    ("voucher_50",     8, {"kind": "voucher","value": 50,  "title": "HK$50 off voucher"}),
    ("free_drink",     4, {"kind": "voucher","value": 88,  "title": "Free house cocktail"}),
    ("jackpot_200",    1, {"kind": "voucher","value": 200, "title": "JACKPOT · HK$200 off"}),
]


def _pick_prize():
    total = sum(w for _, w, _ in SPIN_PRIZES)
    n = secrets.randbelow(total)
    running = 0
    for slug, w, prize in SPIN_PRIZES:
        running += w
        if n < running:
            return slug, prize
    return SPIN_PRIZES[0][0], SPIN_PRIZES[0][2]


# --------- Payloads ---------
class VoucherRedeemIn(BaseModel):
    order_id: str


# --------- Endpoints ---------
@router.get("/summary/{member_id}")
async def loyalty_summary(member_id: str, user: dict = Depends(get_current_user)):
    m = await db.members.find_one({"_id": _oid(member_id)})
    if not m:
        raise HTTPException(404, "Member not found")
    spend = m.get("lifetime_spend", 0.0)
    tier = tier_for(spend)
    idx = TIERS.index(tier)
    next_t = TIERS[idx + 1] if idx + 1 < len(TIERS) else None
    vouchers = await db.vouchers.find({"member_id": member_id, "redeemed_at": None}).to_list(50)
    # Live spin gate (one/day)
    last_spin = m.get("last_spin_at")
    can_spin = True
    if last_spin:
        try:
            can_spin = (datetime.now(timezone.utc) - datetime.fromisoformat(last_spin)).total_seconds() >= 86400
        except Exception:
            can_spin = True
    scratch = await db.scratch_tickets.find_one({"member_id": member_id, "claimed_at": None})
    return {
        "member": serialize(m),
        "tier": tier,
        "next_tier": next_t,
        "spend_to_next": max(0, (next_t["min_spend"] - spend)) if next_t else 0,
        "stamps": m.get("stamps", 0),
        "stamp_goal": STAMP_GOAL,
        "points": m.get("points", 0),
        "vouchers": sl(vouchers),
        "can_spin": can_spin,
        "pending_scratch": serialize(scratch) if scratch else None,
    }


@router.post("/spin/{member_id}")
async def spin_wheel(member_id: str, user: dict = Depends(get_current_user)):
    m = await db.members.find_one({"_id": _oid(member_id)})
    if not m:
        raise HTTPException(404, "Member not found")
    last = m.get("last_spin_at")
    if last:
        try:
            since = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
            if since < 86400:
                raise HTTPException(400, f"Next spin in {int((86400 - since) / 3600)}h")
        except HTTPException:
            raise
        except Exception:
            pass
    slug, prize = _pick_prize()
    voucher = None
    if prize["kind"] == "points":
        await db.members.update_one({"_id": _oid(member_id)}, {"$inc": {"points": prize["value"]}})
    elif prize["kind"] == "stamp":
        await db.members.update_one({"_id": _oid(member_id)}, {"$inc": {"stamps": prize["value"]}})
    elif prize["kind"] == "voucher":
        voucher = await _issue_voucher(
            member_id=member_id, kind="spin_wheel", title=prize["title"],
            discount_type="cash", discount_value=prize["value"], source="spin_wheel",
        )
    await db.members.update_one(
        {"_id": _oid(member_id)},
        {"$set": {"last_spin_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"prize_slug": slug, "prize": prize, "voucher": voucher}


@router.post("/scratch/{ticket_id}/claim")
async def claim_scratch(ticket_id: str, user: dict = Depends(get_current_user)):
    t = await db.scratch_tickets.find_one({"_id": _oid(ticket_id)})
    if not t:
        raise HTTPException(404, "Ticket not found")
    if t.get("claimed_at"):
        raise HTTPException(400, "Already claimed")
    slug, prize = _pick_prize()
    voucher = None
    mid = t["member_id"]
    if prize["kind"] == "points":
        await db.members.update_one({"_id": _oid(mid)}, {"$inc": {"points": prize["value"]}})
    elif prize["kind"] == "stamp":
        await db.members.update_one({"_id": _oid(mid)}, {"$inc": {"stamps": prize["value"]}})
    elif prize["kind"] == "voucher":
        voucher = await _issue_voucher(
            member_id=mid, kind="scratch_ticket", title=prize["title"],
            discount_type="cash", discount_value=prize["value"], source="scratch_ticket",
        )
    await db.scratch_tickets.update_one(
        {"_id": _oid(ticket_id)},
        {"$set": {"claimed_at": datetime.now(timezone.utc).isoformat(),
                  "prize_slug": slug, "prize": prize,
                  "voucher_id": voucher["id"] if voucher else None}},
    )
    return {"prize_slug": slug, "prize": prize, "voucher": voucher}


@router.get("/vouchers")
async def list_vouchers(member_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"redeemed_at": None}
    if member_id:
        q["member_id"] = member_id
    docs = await db.vouchers.find(q).sort("created_at", -1).to_list(200)
    return sl(docs)


@router.post("/vouchers/{vid}/redeem")
async def redeem_voucher(vid: str, body: VoucherRedeemIn, user: dict = Depends(get_current_user)):
    v = await db.vouchers.find_one({"_id": _oid(vid)})
    if not v:
        raise HTTPException(404, "Voucher not found")
    if v.get("redeemed_at"):
        raise HTTPException(400, "Already redeemed")
    o = await db.orders.find_one({"_id": _oid(body.order_id)})
    if not o:
        raise HTTPException(404, "Order not found")
    # Apply as manual cash discount stacked on existing (capped to un-locked subtotal by exclusivity engine)
    prev = o.get("discount_value", 0) or 0
    new_val = prev + v["discount_value"] if o.get("discount_type") == "cash" else v["discount_value"]
    await db.orders.update_one({"_id": _oid(body.order_id)},
        {"$set": {"discount_type": "cash", "discount_value": new_val}})
    await db.vouchers.update_one({"_id": _oid(vid)},
        {"$set": {"redeemed_at": datetime.now(timezone.utc).isoformat(),
                  "redeemed_order_id": body.order_id}})
    return {"ok": True, "applied": v["discount_value"], "voucher_code": v["code"]}


@router.get("/tiers")
async def get_tiers(user: dict = Depends(get_current_user)):
    return TIERS


# --------- Auto-hook invoked from orders.pay_order ---------
async def on_payment_earn(member_doc: dict, order_doc: dict):
    """Called after a paid order attaches to a member.
    - Adds tier-multiplied points (on top of the base int(total//10) from orders)
    - Increments stamps; issues stamp-card voucher every 10 visits
    - 20% chance issues a scratch ticket
    - Once/year birthday voucher if today's month matches member.birth_month
    Returns dict of things awarded (for the receipt / toast)."""
    awards = []
    spend = member_doc.get("lifetime_spend", 0)
    tier = tier_for(spend)
    mult = tier["point_multiplier"]
    # Bonus points on top of the base 10-per-HK$100 already applied by orders.pay_order
    base_pts = int(order_doc.get("total", 0) // 10)
    bonus_pts = int(base_pts * (mult - 1))
    if bonus_pts > 0:
        await db.members.update_one({"_id": member_doc["_id"]}, {"$inc": {"points": bonus_pts}})
        awards.append({"kind": "points", "value": bonus_pts, "title": f"+{bonus_pts} bonus pts ({tier['name']} ×{mult})"})

    # Stamps — Platinum earns 2× stamps
    stamp_delta = 2 if tier["name"] == "Platinum" else 1
    new_stamps = (member_doc.get("stamps", 0) or 0) + stamp_delta
    stamp_update = {"stamps": new_stamps}
    if new_stamps >= STAMP_GOAL:
        v = await _issue_voucher(
            member_id=str(member_doc["_id"]), kind="stamp_card",
            title="Free house cocktail — 10 visits!",
            discount_type="cash", discount_value=88.0, source="stamp_card",
        )
        awards.append({"kind": "voucher", "title": v["title"], "voucher": v})
        stamp_update["stamps"] = new_stamps - STAMP_GOAL  # reset with rollover
    await db.members.update_one({"_id": member_doc["_id"]}, {"$set": stamp_update})

    # Tier promotion notice
    new_spend = (spend or 0) + order_doc.get("total", 0)
    new_tier = tier_for(new_spend)
    if new_tier["name"] != tier["name"]:
        awards.append({"kind": "tier", "title": f"Promoted to {new_tier['name']}!", "value": new_tier["name"]})

    # Scratch ticket drop (~20%)
    if secrets.randbelow(5) == 0:
        r = await db.scratch_tickets.insert_one({
            "member_id": str(member_doc["_id"]),
            "order_id": str(order_doc.get("_id", "")),
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "claimed_at": None,
        })
        awards.append({"kind": "scratch", "title": "Surprise scratch ticket!", "ticket_id": str(r.inserted_id)})

    # Birthday voucher (once per year, on match month)
    bmonth = member_doc.get("birth_month")
    if bmonth and datetime.now(timezone.utc).month == int(bmonth):
        year = datetime.now(timezone.utc).year
        already = await db.vouchers.find_one({
            "member_id": str(member_doc["_id"]),
            "source": "birthday",
            "created_at": {"$gte": f"{year}-01-01"},
        })
        if not already:
            v = await _issue_voucher(
                member_id=str(member_doc["_id"]), kind="birthday",
                title=f"Happy Birthday — {new_tier['bday_pct']}% off",
                discount_type="percent", discount_value=new_tier["bday_pct"], source="birthday",
                ttl_days=30,
            )
            awards.append({"kind": "voucher", "title": v["title"], "voucher": v})

    return awards
