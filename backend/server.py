"""HK Bar POS — FastAPI server."""
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Response, Request
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from auth import (
    hash_password, verify_password, create_access_token,
    make_current_user_dep, _oid,
)
from models import (
    LoginIn, PinLoginIn, CategoryIn, ProductIn, AreaIn, TableIn, TablePosIn,
    MemberIn, HappyHourIn, OrderIn, OrderUpdate, PaymentIn, StaffIn,
)
from seed import seed_all

# ----- DB -----
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="HK Bar POS")
api = APIRouter(prefix="/api")

get_current_user = make_current_user_dep(lambda: db)


def serialize(doc: dict) -> dict:
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def sl(docs: list) -> list:
    return [serialize(d) for d in docs]


# ===================== AUTH =====================
@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(user["_id"]), email, user["role"])
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )
    return {"token": token, "user": {
        "id": str(user["_id"]), "email": user["email"], "name": user["name"],
        "role": user["role"], "pin": user.get("pin"),
    }}


@api.post("/auth/pin-login")
async def pin_login(body: PinLoginIn, response: Response):
    user = await db.users.find_one({"pin": body.pin, "active": True})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    token = create_access_token(str(user["_id"]), user["email"], user["role"])
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )
    return {"token": token, "user": {
        "id": str(user["_id"]), "email": user["email"], "name": user["name"],
        "role": user["role"], "pin": user.get("pin"),
    }}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


# ===================== AREAS & TABLES =====================
@api.get("/areas")
async def list_areas(user: dict = Depends(get_current_user)):
    return sl(await db.areas.find().to_list(100))


@api.post("/areas")
async def create_area(body: AreaIn, user: dict = Depends(get_current_user)):
    doc = {"name": body.name, "created_at": datetime.now(timezone.utc).isoformat()}
    r = await db.areas.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.get("/tables")
async def list_tables(area_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"area_id": area_id} if area_id else {}
    tables = sl(await db.tables.find(q).to_list(500))
    # attach current order summary
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
    return tables


@api.post("/tables")
async def create_table(body: TableIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["status"] = "available"
    doc["current_order_id"] = None
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.tables.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.patch("/tables/{table_id}")
async def update_table(table_id: str, body: TablePosIn, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.tables.update_one({"_id": _oid(table_id)}, {"$set": update})
    t = await db.tables.find_one({"_id": _oid(table_id)})
    return serialize(t)


@api.delete("/tables/{table_id}")
async def delete_table(table_id: str, user: dict = Depends(get_current_user)):
    await db.tables.delete_one({"_id": _oid(table_id)})
    return {"ok": True}


# ===================== MENU: CATEGORIES + PRODUCTS =====================
@api.get("/categories")
async def list_categories(user: dict = Depends(get_current_user)):
    return sl(await db.categories.find().to_list(500))


@api.post("/categories")
async def create_category(body: CategoryIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.categories.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.delete("/categories/{cid}")
async def delete_category(cid: str, user: dict = Depends(get_current_user)):
    await db.categories.delete_one({"_id": _oid(cid)})
    return {"ok": True}


@api.get("/products")
async def list_products(category_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"category_id": category_id} if category_id else {}
    return sl(await db.products.find(q).to_list(1000))


@api.post("/products")
async def create_product(body: ProductIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["active"] = True
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.products.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.patch("/products/{pid}")
async def update_product(pid: str, body: ProductIn, user: dict = Depends(get_current_user)):
    await db.products.update_one({"_id": _oid(pid)}, {"$set": body.model_dump()})
    return serialize(await db.products.find_one({"_id": _oid(pid)}))


@api.delete("/products/{pid}")
async def delete_product(pid: str, user: dict = Depends(get_current_user)):
    await db.products.delete_one({"_id": _oid(pid)})
    return {"ok": True}


# ===================== HAPPY HOUR =====================
@api.get("/happy-hours")
async def list_hh(user: dict = Depends(get_current_user)):
    return sl(await db.happy_hours.find().to_list(50))


@api.post("/happy-hours")
async def create_hh(body: HappyHourIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["active"] = True
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.happy_hours.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.delete("/happy-hours/{hid}")
async def delete_hh(hid: str, user: dict = Depends(get_current_user)):
    await db.happy_hours.delete_one({"_id": _oid(hid)})
    return {"ok": True}


# ===================== MEMBERS =====================
@api.get("/members")
async def list_members(q: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if q:
        query = {"$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"phone": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]}
    return sl(await db.members.find(query).sort("lifetime_spend", -1).to_list(500))


@api.post("/members")
async def create_member(body: MemberIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc.update({
        "lifetime_spend": 0.0, "visits": 0, "points": 0,
        "favorite_items": [], "avg_duration_min": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r = await db.members.insert_one(doc)
    doc["_id"] = r.inserted_id
    return serialize(doc)


@api.get("/members/{mid}")
async def get_member(mid: str, user: dict = Depends(get_current_user)):
    m = await db.members.find_one({"_id": _oid(mid)})
    if not m:
        raise HTTPException(404, "Not found")
    orders = sl(await db.orders.find({"member_id": mid, "status": "paid"}).sort("closed_at", -1).to_list(50))
    return {"member": serialize(m), "orders": orders}


@api.delete("/members/{mid}")
async def delete_member(mid: str, user: dict = Depends(get_current_user)):
    await db.members.delete_one({"_id": _oid(mid)})
    return {"ok": True}


# ===================== ORDERS =====================
def _compute_totals(lines, discount_type, discount_value, service_charge_pct):
    subtotal = sum(l["price"] * l["qty"] for l in lines)
    if discount_type == "percent":
        discount = subtotal * (discount_value / 100.0)
    elif discount_type == "cash":
        discount = min(discount_value, subtotal)
    else:
        discount = 0.0
    net = subtotal - discount
    service = round(net * (service_charge_pct / 100.0), 2)
    total = round(net + service, 2)
    return {
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "service_charge": service,
        "total": total,
    }


@api.get("/orders")
async def list_orders(status: Optional[str] = None, limit: int = 100, user: dict = Depends(get_current_user)):
    q = {"status": status} if status else {}
    return sl(await db.orders.find(q).sort("opened_at", -1).to_list(limit))


@api.get("/orders/{oid}")
async def get_order(oid: str, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    return serialize(o)


@api.post("/orders")
async def create_order(body: OrderIn, user: dict = Depends(get_current_user)):
    lines = [l.model_dump() for l in body.lines]
    totals = _compute_totals(lines, body.discount_type, body.discount_value, body.service_charge_pct)
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


@api.patch("/orders/{oid}")
async def update_order(oid: str, body: OrderUpdate, user: dict = Depends(get_current_user)):
    existing = await db.orders.find_one({"_id": _oid(oid)})
    if not existing:
        raise HTTPException(404, "Not found")
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if "lines" in update:
        lines = update["lines"]
        totals = _compute_totals(
            lines,
            update.get("discount_type", existing.get("discount_type", "none")),
            update.get("discount_value", existing.get("discount_value", 0)),
            existing.get("service_charge_pct", 10),
        )
        update.update(totals)
    elif "discount_type" in update or "discount_value" in update:
        totals = _compute_totals(
            existing["lines"],
            update.get("discount_type", existing.get("discount_type", "none")),
            update.get("discount_value", existing.get("discount_value", 0)),
            existing.get("service_charge_pct", 10),
        )
        update.update(totals)
    await db.orders.update_one({"_id": _oid(oid)}, {"$set": update})
    return serialize(await db.orders.find_one({"_id": _oid(oid)}))


@api.post("/orders/{oid}/fire")
async def fire_order(oid: str, course: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Un-hold items — mark them as fired for kitchen/bar."""
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


@api.post("/orders/{oid}/pay")
async def pay_order(oid: str, body: PaymentIn, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": _oid(oid)})
    if not o:
        raise HTTPException(404, "Not found")
    change = round(body.amount - o["total"], 2) if body.method == "cash" else 0.0
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


@api.delete("/orders/{oid}")
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


# ===================== TABLE ACTIONS =====================
@api.post("/tables/{tid}/clear")
async def clear_table(tid: str, user: dict = Depends(get_current_user)):
    await db.tables.update_one({"_id": _oid(tid)}, {"$set": {"status": "available", "current_order_id": None}})
    return {"ok": True}


@api.post("/tables/{tid}/status")
async def set_status(tid: str, status: str, user: dict = Depends(get_current_user)):
    await db.tables.update_one({"_id": _oid(tid)}, {"$set": {"status": status}})
    return {"ok": True}


# ===================== STAFF =====================
@api.get("/staff")
async def list_staff(user: dict = Depends(get_current_user)):
    users = await db.users.find({}, {"password_hash": 0}).to_list(200)
    return sl(users)


@api.post("/staff")
async def create_staff(body: StaffIn, user: dict = Depends(get_current_user)):
    if user["role"] not in ("admin", "manager"):
        raise HTTPException(403, "Manager only")
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(400, "Email exists")
    doc = {
        "email": body.email.lower(), "password_hash": hash_password(body.password),
        "name": body.name, "role": body.role, "pin": body.pin, "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await db.users.insert_one(doc)
    doc["_id"] = r.inserted_id
    doc.pop("password_hash")
    return serialize(doc)


@api.delete("/staff/{uid}")
async def delete_staff(uid: str, user: dict = Depends(get_current_user)):
    if user["role"] not in ("admin", "manager"):
        raise HTTPException(403, "Manager only")
    await db.users.delete_one({"_id": _oid(uid)})
    return {"ok": True}


# ===================== REPORTS =====================
@api.get("/reports/summary")
async def reports_summary(user: dict = Depends(get_current_user)):
    paid = await db.orders.find({"status": "paid"}).to_list(2000)
    total_revenue = sum(o.get("total", 0) for o in paid)
    total_orders = len(paid)
    avg_ticket = total_revenue / total_orders if total_orders else 0

    by_hour = {}
    by_cat = {}
    by_pay = {}
    by_staff = {}
    cats = {str(c["_id"]): c["name"] for c in await db.categories.find().to_list(500)}
    prods = {str(p["_id"]): p for p in await db.products.find().to_list(2000)}
    staff = {str(u["_id"]): u.get("name") for u in await db.users.find().to_list(200)}

    for o in paid:
        # hour
        try:
            h = datetime.fromisoformat(o["closed_at"]).astimezone(timezone.utc).hour
        except Exception:
            h = 0
        by_hour[h] = by_hour.get(h, 0) + o.get("total", 0)
        # category
        for l in o.get("lines", []):
            p = prods.get(l["product_id"])
            if p:
                cn = cats.get(p["category_id"], "Other")
                by_cat[cn] = by_cat.get(cn, 0) + l["price"] * l["qty"]
        # payment
        pay = (o.get("payment") or {}).get("method", "cash")
        by_pay[pay] = by_pay.get(pay, 0) + o.get("total", 0)
        # staff
        sid = o.get("server_id")
        sname = staff.get(sid, "—")
        by_staff[sname] = by_staff.get(sname, 0) + o.get("total", 0)

    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "avg_ticket": round(avg_ticket, 2),
        "by_hour": [{"hour": h, "revenue": round(v, 2)} for h, v in sorted(by_hour.items())],
        "by_category": [{"name": k, "revenue": round(v, 2)} for k, v in sorted(by_cat.items(), key=lambda x: -x[1])],
        "by_payment": [{"name": k, "revenue": round(v, 2)} for k, v in by_pay.items()],
        "by_staff": [{"name": k, "revenue": round(v, 2)} for k, v in sorted(by_staff.items(), key=lambda x: -x[1])],
    }


# ===================== BOOTSTRAP =====================
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hkbar")


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("pin")
    await db.tables.create_index("area_id")
    await db.products.create_index("category_id")
    await db.orders.create_index("status")
    await db.orders.create_index("member_id")
    await seed_all(db)
    logger.info("HK Bar POS ready.")


@app.on_event("shutdown")
async def shutdown():
    client.close()
