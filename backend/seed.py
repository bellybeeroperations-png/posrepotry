"""Idempotent seed data for HK Bar POS."""
import os
from datetime import datetime, timezone
from auth import hash_password, verify_password


async def seed_all(db):
    await _seed_users(db)
    await _seed_areas_and_tables(db)
    await _seed_menu(db)
    await _seed_members(db)
    await _seed_happy_hours(db)
    await _seed_kegs(db)


async def _seed_kegs(db):
    if await db.kegs.count_documents({}) > 0:
        return
    from datetime import datetime, timezone
    # link kegs to beer products by name
    beer_names = ["Tsingtao", "Craft IPA", "San Miguel"]
    prods = {p["name"]: p async for p in db.products.find({"name": {"$in": beer_names}})}
    kegs = []
    tap = 1
    for beer_name, size, pour in [
        ("Tsingtao", 30000, 568),
        ("Craft IPA", 30000, 568),
        ("San Miguel", 30000, 500),
    ]:
        p = prods.get(beer_name)
        if not p:
            continue
        # Two kegs per beer (main + backup) to demonstrate 35+ taps at scale
        for backup in [False, True]:
            kegs.append({
                "name": f"Tap {tap:02d} · {beer_name}{' (backup)' if backup else ''}",
                "product_id": str(p["_id"]),
                "size_ml": size,
                "current_ml": int(size * (0.08 if (tap == 1) else 1.0)),  # tap 1 low for demo
                "ml_per_pour": pour,
                "threshold_pct": 10.0,
                "status": "on",
                "opened_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            tap += 1
    if kegs:
        await db.kegs.insert_many(kegs)


async def _seed_users(db):
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
    admin_pin = os.environ.get("ADMIN_PIN", "9999")

    users = [
        (admin_email, admin_pass, "Owner", "admin", admin_pin),
        ("manager@hkbar.com", "manager123", "Alex Chan", "manager", "1111"),
        ("bartender@hkbar.com", "bartender123", "Mei Wong", "bartender", "2222"),
        ("server@hkbar.com", "server123", "Ravi Kumar", "server", "3333"),
        ("cashier@hkbar.com", "cashier123", "Ivy Lo", "cashier", "4444"),
    ]
    for email, pwd, name, role, pin in users:
        existing = await db.users.find_one({"email": email})
        if not existing:
            await db.users.insert_one({
                "email": email,
                "password_hash": hash_password(pwd),
                "name": name,
                "role": role,
                "pin": pin,
                "active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            update = {"role": role, "pin": pin, "name": name}
            if not verify_password(pwd, existing["password_hash"]):
                update["password_hash"] = hash_password(pwd)
            await db.users.update_one({"_id": existing["_id"]}, {"$set": update})


async def _seed_areas_and_tables(db):
    areas = {}
    for name in ["Main+Terrace", "Backroom"]:
        existing = await db.areas.find_one({"name": name})
        if existing:
            areas[name] = existing["_id"]
        else:
            r = await db.areas.insert_one({"name": name, "created_at": datetime.now(timezone.utc).isoformat()})
            areas[name] = r.inserted_id

    if await db.tables.count_documents({}) > 0:
        return

    layout = [
        # Main+Terrace
        ("Main+Terrace", "T1", 4, 60, 60, 100, 100, "rect"),
        ("Main+Terrace", "T2", 4, 200, 60, 100, 100, "rect"),
        ("Main+Terrace", "T3", 4, 340, 60, 100, 100, "rect"),
        ("Main+Terrace", "T4", 2, 60, 200, 80, 80, "circle"),
        ("Main+Terrace", "T5", 2, 180, 200, 80, 80, "circle"),
        ("Main+Terrace", "T6", 6, 300, 200, 160, 90, "rect"),
        ("Main+Terrace", "Bar1", 1, 500, 60, 60, 60, "circle"),
        ("Main+Terrace", "Bar2", 1, 500, 140, 60, 60, "circle"),
        ("Main+Terrace", "Bar3", 1, 500, 220, 60, 60, "circle"),
        ("Main+Terrace", "Terr1", 4, 60, 340, 100, 100, "rect"),
        ("Main+Terrace", "Terr2", 4, 200, 340, 100, 100, "rect"),
        ("Main+Terrace", "Terr3", 6, 340, 340, 160, 100, "rect"),
        # Backroom
        ("Backroom", "B1", 4, 60, 60, 110, 90, "rect"),
        ("Backroom", "B2", 4, 200, 60, 110, 90, "rect"),
        ("Backroom", "B3", 8, 60, 200, 250, 100, "rect"),
        ("Backroom", "Dart1", 2, 360, 60, 90, 90, "circle"),
        ("Backroom", "Dart2", 2, 360, 180, 90, 90, "circle"),
        ("Backroom", "VIP", 8, 60, 340, 400, 110, "rect"),
    ]
    docs = []
    for area_name, tname, seats, x, y, w, h, shape in layout:
        docs.append({
            "area_id": str(areas[area_name]),
            "name": tname,
            "seats": seats,
            "x": x, "y": y, "width": w, "height": h, "shape": shape,
            "status": "available",
            "current_order_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    if docs:
        await db.tables.insert_many(docs)


async def _seed_menu(db):
    if await db.categories.count_documents({}) > 0:
        return
    cats = [
        ("Cocktails", "drink", "#00F2FE"),
        ("Beer", "drink", "#FFB800"),
        ("Wine", "drink", "#A855F7"),
        ("Spirits", "drink", "#F43F5E"),
        ("Soft Drinks", "drink", "#10B981"),
        ("Starters", "food", "#F59E0B"),
        ("Mains", "food", "#06B6D4"),
        ("Sides", "food", "#94A3B8"),
        ("Desserts", "food", "#EC4899"),
    ]
    cat_ids = {}
    for name, kind, color in cats:
        r = await db.categories.insert_one({
            "name": name, "kind": kind, "color": color, "parent_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cat_ids[name] = str(r.inserted_id)

    products = [
        # Cocktails
        ("Hong Kong Sour", "Cocktails", 118, "drink", True,
            [{"name": "Single", "price_delta": 0}, {"name": "Double", "price_delta": 40}],
            [{"name": "No Ice", "price_delta": 0}, {"name": "Extra Lime", "price_delta": 5}]),
        ("Neon Negroni", "Cocktails", 128, "drink", True,
            [{"name": "Single", "price_delta": 0}, {"name": "Double", "price_delta": 45}],
            [{"name": "Orange Peel", "price_delta": 0}]),
        ("Lychee Martini", "Cocktails", 122, "drink", True, [], []),
        ("Old Fashioned", "Cocktails", 138, "drink", True, [], [{"name": "Extra Cherry", "price_delta": 5}]),
        # Beer
        ("Tsingtao", "Beer", 55, "drink", True,
            [{"name": "Pint", "price_delta": 0}, {"name": "Tower", "price_delta": 220}, {"name": "Bucket x6", "price_delta": 250}],
            []),
        ("Craft IPA", "Beer", 75, "drink", True,
            [{"name": "Pint", "price_delta": 0}, {"name": "Half", "price_delta": -30}], []),
        ("San Miguel", "Beer", 50, "drink", True,
            [{"name": "Bottle", "price_delta": 0}, {"name": "Bucket x6", "price_delta": 220}], []),
        # Wine
        ("House Red Glass", "Wine", 78, "drink", True, [{"name": "Glass", "price_delta": 0}, {"name": "Bottle", "price_delta": 220}], []),
        ("House White Glass", "Wine", 78, "drink", True, [{"name": "Glass", "price_delta": 0}, {"name": "Bottle", "price_delta": 220}], []),
        # Spirits
        ("Johnnie Walker Black", "Spirits", 95, "drink", True,
            [{"name": "Single", "price_delta": 0}, {"name": "Double", "price_delta": 60}],
            [{"name": "Neat", "price_delta": 0}, {"name": "On Rocks", "price_delta": 0}, {"name": "With Coke", "price_delta": 10}]),
        ("Jose Cuervo", "Spirits", 85, "drink", True, [{"name": "Shot", "price_delta": 0}, {"name": "Double Shot", "price_delta": 50}], []),
        # Soft
        ("Coke", "Soft Drinks", 35, "drink", False, [], [{"name": "No Ice", "price_delta": 0}]),
        ("Sparkling Water", "Soft Drinks", 40, "drink", False, [], []),
        # Food
        ("Truffle Fries", "Starters", 88, "food", False, [], [{"name": "Extra Parmesan", "price_delta": 10}]),
        ("Chicken Wings", "Starters", 98, "food", False,
            [{"name": "Original", "price_delta": 0}, {"name": "Hot", "price_delta": 0}, {"name": "BBQ", "price_delta": 0}], []),
        ("Salt & Pepper Squid", "Starters", 118, "food", False, [], []),
        ("Wagyu Burger", "Mains", 168, "food", False,
            [{"name": "Medium Rare", "price_delta": 0}, {"name": "Medium", "price_delta": 0}, {"name": "Well Done", "price_delta": 0}],
            [{"name": "Add Bacon", "price_delta": 20}, {"name": "Add Cheese", "price_delta": 15}]),
        ("Ribeye Steak 250g", "Mains", 288, "food", False,
            [{"name": "Rare", "price_delta": 0}, {"name": "Medium Rare", "price_delta": 0}, {"name": "Medium", "price_delta": 0}, {"name": "Well Done", "price_delta": 0}],
            [{"name": "Peppercorn Sauce", "price_delta": 25}, {"name": "Mushroom Sauce", "price_delta": 25}]),
        ("Fish & Chips", "Mains", 148, "food", False, [], []),
        ("Pad Thai", "Mains", 118, "food", False, [{"name": "Chicken", "price_delta": 0}, {"name": "Prawn", "price_delta": 25}, {"name": "Veg", "price_delta": -10}], []),
        ("Coleslaw", "Sides", 38, "food", False, [], []),
        ("Onion Rings", "Sides", 48, "food", False, [], []),
        ("Chocolate Lava", "Desserts", 78, "food", False, [], [{"name": "Ice Cream", "price_delta": 15}]),
    ]
    docs = []
    course_map = {"Starters": "starter", "Mains": "main", "Sides": "side", "Desserts": "dessert"}
    for name, cat, price, kind, hh, variants, mods in products:
        docs.append({
            "name": name,
            "category_id": cat_ids[cat],
            "price": price,
            "kind": kind,
            "course": course_map.get(cat, "drink"),
            "variants": variants,
            "modifiers": mods,
            "happy_hour_eligible": hh,
            "description": "",
            "image": None,
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    if docs:
        await db.products.insert_many(docs)


async def _seed_members(db):
    if await db.members.count_documents({}) > 0:
        return
    members = [
        ("Jason Lee", "+852 9123 4567", "jason@hk.com", "VIP"),
        ("Priya Sharma", "+852 9876 5432", "priya@hk.com", "Gold"),
        ("Marco Rossi", "+852 9111 2222", "marco@hk.com", "Silver"),
        ("Karen Chow", "+852 9333 4444", "karen@hk.com", "Regular"),
        ("Daniel Kim", "+852 9555 6666", "daniel@hk.com", "Gold"),
    ]
    docs = []
    for n, p, e, t in members:
        docs.append({
            "name": n, "phone": p, "email": e, "tier": t, "notes": "",
            "lifetime_spend": 0.0, "visits": 0, "points": 0,
            "favorite_items": [],
            "avg_duration_min": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    if docs:
        await db.members.insert_many(docs)


async def _seed_happy_hours(db):
    if await db.happy_hours.count_documents({}) > 0:
        return
    cocktails = await db.categories.find_one({"name": "Cocktails"})
    beer = await db.categories.find_one({"name": "Beer"})
    cat_ids = [str(c["_id"]) for c in [cocktails, beer] if c]
    await db.happy_hours.insert_one({
        "name": "Daily Happy Hour",
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start_time": "16:00",
        "end_time": "21:00",
        "percent_off": 20.0,
        "category_ids": cat_ids,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
