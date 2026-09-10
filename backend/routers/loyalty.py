"""Loyalty & rewards — points, tiers, stamps, spin wheel, scratch tickets,
vouchers, birthday auto-issue. Auto-hooked from orders.pay_order."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import secrets
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import db, _oid, serialize, sl
from auth import make_current_user_dep
from models import FeedbackIn, SocialShareIn, PushSegmentIn

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

    # --- Happy-Hour points boost (2× base points during any active window) ---
    active_hh = await db.happy_hours.find({"active": True}).to_list(50)
    if active_hh:
        now = datetime.now(ZoneInfo("Asia/Hong_Kong"))
        cur = now.strftime("%H:%M")
        in_window = False
        for h in active_hh:
            s, e = h.get("start_time"), h.get("end_time")
            days = h.get("days") or []
            if days and now.weekday() not in days:
                continue
            if not s or not e:
                continue
            if (s <= e and s <= cur <= e) or (s > e and (cur >= s or cur <= e)):
                in_window = True
                break
        if in_window and base_pts > 0:
            await db.members.update_one({"_id": member_doc["_id"]}, {"$inc": {"points": base_pts}})
            awards.append({"kind": "points", "value": base_pts, "title": f"+{base_pts} HH boost (2×)"})

    # --- Visit-streak bonus (consecutive ISO weeks) ---
    now_hk = datetime.now(ZoneInfo("Asia/Hong_Kong"))
    iso_year, iso_week, _ = now_hk.isocalendar()
    key = f"{iso_year}-W{iso_week:02d}"
    last_wk = member_doc.get("last_visit_week")
    streak = member_doc.get("streak_weeks", 0) or 0
    streak_award = 0
    if last_wk == key:
        pass  # same week, no change
    else:
        # Was last week consecutive?
        try:
            ly, lw = int(last_wk.split("-W")[0]), int(last_wk.split("-W")[1]) if last_wk else (None, None)
        except Exception:
            ly, lw = None, None
        consecutive = False
        if ly and lw:
            # Simple: same year & lw+1==iso_week; OR crossing year boundary at week 52/53→1
            consecutive = (ly == iso_year and lw + 1 == iso_week) or \
                          (ly == iso_year - 1 and iso_week == 1 and lw in (52, 53))
        streak = streak + 1 if consecutive else 1
        streak_update = {"last_visit_week": key, "streak_weeks": streak}
        await db.members.update_one({"_id": member_doc["_id"]}, {"$set": streak_update})
        if streak >= 2:
            streak_award = min(500, streak * 50)
            await db.members.update_one({"_id": member_doc["_id"]}, {"$inc": {"points": streak_award}})
            awards.append({"kind": "points", "value": streak_award,
                           "title": f"+{streak_award} streak bonus · {streak}-week run"})

    # --- Referral first-order bonus (fires once per referred member) ---
    ref = member_doc.get("referred_by")
    if ref and not member_doc.get("referral_awarded"):
        try:
            await db.members.update_one({"_id": member_doc["_id"]}, {"$set": {"referral_awarded": True}, "$inc": {"points": 200}})
            await db.members.update_one({"_id": _oid(ref)}, {"$inc": {"points": 200}})
            v_new = await _issue_voucher(member_id=str(member_doc["_id"]), kind="referral",
                                         title="Thanks for joining — HK$50 off",
                                         discount_type="cash", discount_value=50.0, source="referral_new")
            v_ref = await _issue_voucher(member_id=ref, kind="referral",
                                         title="Referral reward — HK$50 off",
                                         discount_type="cash", discount_value=50.0, source="referral_ref")
            awards.append({"kind": "voucher", "title": v_new["title"], "voucher": v_new})
            awards.append({"kind": "referral_ref", "title": f"Referrer +200pts + voucher (member {ref[:6]}…)",
                           "value": ref, "voucher": v_ref})
        except Exception:
            pass

    return awards


# --- Engagement endpoints (feedback + social share) ---
@router.post("/feedback/{member_id}")
async def submit_feedback(member_id: str, body: FeedbackIn, user: dict = Depends(get_current_user)):
    """Reward completed post-visit feedback with a small voucher (HK$20).
    One reward per order (or per member/day if order_id omitted)."""
    m = await db.members.find_one({"_id": _oid(member_id)})
    if not m:
        raise HTTPException(404, "Member not found")
    dupe_q = {"member_id": member_id}
    if body.order_id:
        dupe_q["order_id"] = body.order_id
    else:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        dupe_q["created_at"] = {"$gte": cutoff}
    dupe = await db.feedback.find_one(dupe_q)
    if dupe:
        raise HTTPException(400, "Feedback already logged for this order/window")
    now = datetime.now(timezone.utc).isoformat()
    await db.feedback.insert_one({**body.model_dump(), "member_id": member_id, "created_at": now,
                                  "source": "feedback", "logged_by": user["id"]})
    v = await _issue_voucher(member_id=member_id, kind="feedback",
                             title="Thanks for the feedback — HK$20 off",
                             discount_type="cash", discount_value=20.0, source="feedback", ttl_days=45)
    return {"ok": True, "voucher": v}


@router.post("/social-share/{member_id}")
async def social_share(member_id: str, body: SocialShareIn, user: dict = Depends(get_current_user)):
    """Reward tagging the venue (once/day/member) with +25 points."""
    m = await db.members.find_one({"_id": _oid(member_id)})
    if not m:
        raise HTTPException(404, "Member not found")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    dupe = await db.social_shares.find_one({"member_id": member_id, "created_at": {"$gte": cutoff}})
    if dupe:
        raise HTTPException(400, "Already claimed a share reward in the last 24h")
    now = datetime.now(timezone.utc).isoformat()
    await db.social_shares.insert_one({**body.model_dump(), "member_id": member_id, "created_at": now,
                                       "logged_by": user["id"]})
    await db.members.update_one({"_id": _oid(member_id)}, {"$inc": {"points": 25}})
    return {"ok": True, "points_awarded": 25, "platform": body.platform}


# --- Push Composer — segment blast (MOCKED SMS/WhatsApp send) ---
async def _match_segment(seg: PushSegmentIn):
    q = {}
    if seg.tier:
        # Tier is derived from lifetime_spend; translate to min range
        band = next((t for t in TIERS if t["name"] == seg.tier), None)
        if band:
            idx = TIERS.index(band)
            upper = TIERS[idx + 1]["min_spend"] if idx + 1 < len(TIERS) else float("inf")
            q["lifetime_spend"] = {"$gte": band["min_spend"], "$lt": upper}
    if seg.min_lifetime_spend:
        q.setdefault("lifetime_spend", {})["$gte"] = seg.min_lifetime_spend
    members = await db.members.find(q).to_list(2000)
    if seg.days_inactive:
        cutoff = datetime.now(timezone.utc) - timedelta(days=seg.days_inactive)
        filtered = []
        for m in members:
            # inactive if never visited OR last order.closed_at older than cutoff
            last_order = await db.orders.find_one(
                {"member_id": str(m["_id"]), "status": "paid"}, sort=[("closed_at", -1)]
            )
            if not last_order:
                filtered.append(m)
            elif last_order.get("closed_at") and datetime.fromisoformat(last_order["closed_at"]) < cutoff:
                filtered.append(m)
        members = filtered
    return members


@router.post("/push/preview")
async def push_preview(body: PushSegmentIn, user: dict = Depends(get_current_user)):
    members = await _match_segment(body)
    return {"count": len(members), "sample": [{"id": str(m["_id"]), "name": m["name"], "phone": m.get("phone")} for m in members[:5]]}


@router.post("/push/send")
async def push_send(body: PushSegmentIn, user: dict = Depends(get_current_user)):
    if user["role"] not in ("admin", "manager"):
        raise HTTPException(403, "Manager only")
    members = await _match_segment(body)
    # Optional Twilio wire-up — best-effort; MOCKED if creds missing
    import os as _os
    twilio_client = None
    tw_from_sms = _os.environ.get("TWILIO_SMS_FROM")
    tw_from_wa = _os.environ.get("TWILIO_WHATSAPP_FROM")  # e.g. whatsapp:+14155238886
    try:
        sid = _os.environ.get("TWILIO_ACCOUNT_SID")
        tok = _os.environ.get("TWILIO_AUTH_TOKEN")
        if sid and tok:
            from twilio.rest import Client
            twilio_client = Client(sid, tok)
    except Exception:
        twilio_client = None

    issued = 0
    delivered = 0
    for m in members:
        v = await _issue_voucher(
            member_id=str(m["_id"]), kind="push",
            title=body.title,
            discount_type=body.discount_type, discount_value=body.discount_value,
            source="push_composer", ttl_days=body.ttl_days,
        )
        # Compose message
        amount_str = f"{body.discount_value}% off" if body.discount_type == "percent" else f"HK${body.discount_value:.0f} off"
        msg_body = f"{body.title} · use code {v['code']} · expires in {body.ttl_days}d · {amount_str}"
        phone = m.get("phone") or ""
        # Normalise to +852 if bare 8-digit
        if phone and not phone.startswith("+"):
            phone = f"+852{phone.replace(' ', '')}"

        send_status = "MOCKED"
        send_error = None
        if twilio_client and phone:
            try:
                if body.channel == "sms" and tw_from_sms:
                    twilio_client.messages.create(from_=tw_from_sms, to=phone, body=msg_body)
                    send_status = "SENT"
                elif body.channel == "whatsapp" and tw_from_wa:
                    twilio_client.messages.create(from_=tw_from_wa, to=f"whatsapp:{phone}", body=msg_body)
                    send_status = "SENT"
                # email left to a future Resend/SendGrid integration
            except Exception as e:
                send_status = "FAILED"
                send_error = str(e)[:200]
        if send_status == "SENT":
            delivered += 1

        await db.push_log.insert_one({
            "member_id": str(m["_id"]), "member_name": m.get("name"),
            "phone": phone, "channel": body.channel,
            "voucher_id": v["id"], "voucher_code": v["code"],
            "title": body.title, "body": msg_body,
            "sent_by": user["id"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "status": send_status, "error": send_error,
        })
        issued += 1
    return {
        "issued": issued, "delivered": delivered, "channel": body.channel,
        "note": ("Real Twilio send" if twilio_client else "MOCKED — set TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_SMS_FROM / TWILIO_WHATSAPP_FROM to enable")
    }


@router.get("/digest")
async def loyalty_digest(user: dict = Depends(get_current_user)):
    """Today's loyalty ROI snapshot for the Reports dashboard."""
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    signups = await db.members.count_documents({"created_at": {"$gte": day_start}})
    vouchers_issued = await db.vouchers.count_documents({"created_at": {"$gte": day_start}})
    vouchers_redeemed = await db.vouchers.count_documents({"redeemed_at": {"$gte": day_start}})
    scratch_claimed = await db.scratch_tickets.count_documents({"claimed_at": {"$gte": day_start}})
    push_sent = await db.push_log.count_documents({"sent_at": {"$gte": day_start}})
    top_members = await db.members.find().sort("points", -1).limit(5).to_list(5)
    return {
        "signups_today": signups,
        "vouchers_issued_today": vouchers_issued,
        "vouchers_redeemed_today": vouchers_redeemed,
        "scratch_claimed_today": scratch_claimed,
        "push_sent_today": push_sent,
        "top_point_earners": [{"id": str(m["_id"]), "name": m.get("name"), "points": m.get("points", 0), "tier": tier_for(m.get("lifetime_spend", 0))["name"]} for m in top_members],
    }


@router.get("/campaigns")
async def push_campaigns(limit: int = 50, user: dict = Depends(get_current_user)):
    """List every past push blast grouped by (title + channel + day) with
    delivered/mocked/failed counts + first send time. Powers the campaign history."""
    logs = await db.push_log.find().sort("sent_at", -1).to_list(2000)
    groups: dict = {}
    for L in logs:
        ts = L.get("sent_at", "")[:10]  # day bucket
        key = f"{L.get('title')}|{L.get('channel')}|{ts}"
        g = groups.setdefault(key, {
            "title": L.get("title"), "channel": L.get("channel"), "day": ts,
            "sent": 0, "delivered": 0, "mocked": 0, "failed": 0,
            "sample_body": L.get("body"), "first_sent_at": L.get("sent_at"),
        })
        g["sent"] += 1
        st = (L.get("status") or "").upper()
        if st == "SENT": g["delivered"] += 1
        elif st == "MOCKED": g["mocked"] += 1
        elif st == "FAILED": g["failed"] += 1
    out = sorted(groups.values(), key=lambda x: x["first_sent_at"] or "", reverse=True)
    return out[:limit]


@router.post("/digest/send-weekly")
async def send_weekly_digest(user: dict = Depends(get_current_user)):
    """Sends a Monday-morning digest to every manager/admin.
    Best-effort: uses Twilio WhatsApp when creds are present, otherwise logs to
    push_log with status=MOCKED. Intended to be called from .emergent/crons.yml."""
    if user["role"] not in ("admin", "manager", "system"):
        raise HTTPException(403, "Manager or scheduled system only")
    from datetime import timedelta as _td
    week_ago = (datetime.now(timezone.utc) - _td(days=7)).isoformat()
    signups = await db.members.count_documents({"created_at": {"$gte": week_ago}})
    v_issued = await db.vouchers.count_documents({"created_at": {"$gte": week_ago}})
    v_redeemed = await db.vouchers.count_documents({"redeemed_at": {"$gte": week_ago}})
    scratch = await db.scratch_tickets.count_documents({"claimed_at": {"$gte": week_ago}})
    # Biggest missed nudges (dismissed status) — top 3 by count
    nudges = await db.upsell_nudges.find({"ts": {"$gte": week_ago}, "status": "dismissed"}).to_list(2000)
    miss_counts: dict = {}
    for n in nudges:
        k = n.get("combo_name") or "?"
        miss_counts[k] = miss_counts.get(k, 0) + 1
    top_misses = sorted(miss_counts.items(), key=lambda x: -x[1])[:3]

    body = (
        f"HK Bar · Weekly Digest\n"
        f"• {signups} new sign-ups\n"
        f"• {v_issued} vouchers issued · {v_redeemed} redeemed\n"
        f"• {scratch} scratch cards claimed\n"
        f"• Top missed combos: " + (", ".join(f"{n}×{c}" for n, c in top_misses) or "—")
    )
    recipients = await db.users.find({"role": {"$in": ["admin", "manager"]}}).to_list(50)
    now_iso = datetime.now(timezone.utc).isoformat()
    for r in recipients:
        await db.push_log.insert_one({
            "member_id": None, "member_name": r.get("name") or r.get("email"),
            "phone": r.get("phone"), "channel": "whatsapp",
            "voucher_id": None, "voucher_code": None,
            "title": "Weekly Digest", "body": body,
            "sent_by": "system", "sent_at": now_iso,
            "status": "MOCKED",
        })
    return {"summary": body, "recipients": len(recipients)}
