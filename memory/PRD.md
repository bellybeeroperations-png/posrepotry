# HK Bar POS — Product Requirements

## Original Problem Statement
Advanced restaurant POS for a Hong Kong bar/restaurant running 11am–6am, 7 days a week. Dine-in / pick-up / delivery. Happy hours, cash & % discounts, automatic 10% service charge. Two areas (Backroom, Main+Terrace) with a full floorplan. Staff with different roles/permissions, member CRM with spend/duration/item tracking, product categories/sub-categories, variants & modifiers, hold-and-fire courses. Must feel like Lightspeed Restaurant POS but better.

## User Choices (Feb 2026)
- Auth: JWT-based custom auth + 4-digit staff PIN quick-switch
- Payments: Mocked (cash/card/octopus/wallet buttons, no real processor)
- First build scope: Full core POS + Floorplan + Members/Loyalty
- Currency/Language: HKD / English
- Seed data: Yes (realistic bar/restaurant menu, dual-area tables, sample staff & members)

## Architecture
- Frontend: React 19 + TailwindCSS + shadcn/ui + Framer-Motion + Recharts + sonner
- Backend: FastAPI + Motor (MongoDB async), JWT (PyJWT) + bcrypt password hashing
- DB: MongoDB `hkbar_pos` — collections `users`, `areas`, `tables`, `categories`, `products`, `orders`, `members`, `happy_hours`
- Theme: Hong Kong neon cyberpunk dark mode (`#0B0E14` bg, `#00F2FE` cyan, `#FFB800` amber, distinct table-state colors)

## What's Implemented (v3 · Feb 2026 iteration)
- **Kitchen Display System (/kds)**: fired-but-not-bumped items grouped with station filter (All/Kitchen/Bar), age-coloured cards (green <5m, amber <10m, red >10m pulsing), tap-to-bump with instant removal, KPI cards for total/food/drink/late
- **Shift Reports (/shift)**: clock-in / clock-out per staff, live shift KPIs (revenue, orders, covers, tips, avg ticket, payment mix), printable X-report mid-shift and Z-report on close (opens a formatted receipt-style popup for the printer), history of past shifts with per-row print button
- **Reservations**: click any table → TableActionModal (Open Order / Reserve / Cancel Reservation depending on state) → ReservationModal collects guest name, phone, party size, reserved-for datetime, notes; table becomes reserved-purple with the guest name and a live countdown (in Xm / now / X m late)
- **Print / Email Receipts**: after every payment a printable Receipt modal opens (subtotal, discount, service, total, payment breakdown including per-split rows, tip, change). Receipt can also be opened for any historic order from the CRM member profile. Print opens a windowed thermal-style receipt; email is MOCKED (toast).
- All four features tested end-to-end: iteration_3.json backend + frontend 100% pass

## What's Implemented (v2 · Feb 2026 iteration)
- **Menu Matrix Editor**: rich Product editor with variant + modifier grids (add/edit/delete rows, price deltas), Category editor with color swatches, Happy Hour editor with time inputs, day toggles, and category multi-select
- **Live Happy Hour**: `/api/happy-hours/active` returns rules whose HK weekday + time window matches now (cross-midnight aware). Register shows a live HH banner and applies discounted prices with -X% badge + strikethrough automatically on eligible products. Variant modal also discounts.
- **Split Payments**: PaymentModal with Single vs Split modes. Split supports Equal Parts, By Seat (uses guest count), and Custom (add/remove rows, per-row method dropdown, per-row amount). Live sum indicator with under/over feedback. Backend validates split total ≥ order total.
- **Floorplan enhancements**: KPI header bar (Covers · Open Tables · $ Due · Free Tables · >30m Sessions · Day OPEN/CLOSED — auto based on 11:00–06:00 HK window), live sports ticker with 6 games, right-side Active Promotions / Items to Push / Announcements sidebar cards
- All new features tested end-to-end: iteration_2.json backend + frontend 100% pass

## What's Implemented (v1 · Feb 2026)
- Email + password login and PIN quick-switch login (5 seeded users, roles: admin/manager/bartender/server/cashier)
- Dual-area floorplan (Main+Terrace 12 tables, Backroom 6 tables) with drag-to-reposition edit mode, add/delete tables, live status pills (available/occupied/bill/dirty/reserved), guest counts, current bill overlay, 5-second polling
- Order-taking register: order types (dine-in/pick-up/delivery), category grid, variant modal (e.g. Beer Pint/Tower/Bucket, Steak temperatures), modifier chips, hold-and-fire courses per line, member attach with live search, guest counter
- Discount engine: none / percent / cash, automatic 10% service charge, live totals
- Payment modal: cash / card / octopus / wallet, tip capture, cash change calculation
- Menu manager: browse products / categories / happy-hour cards (create/delete via prompt-based flow)
- Members CRM: list with tier badges, live search, profile drawer with lifetime spend, visits, avg duration, points, favorite items, recent orders
- Staff management (create/delete with role guard: manager+admin only)
- Events dashboard (live sports / darts queue / trivia — read-only overview)
- Reports & Insights: revenue, orders, avg ticket, top staff KPIs; hourly bar chart, category pie chart, payment mix, staff leaderboard
- Idempotent seed on server startup

## Test Coverage
- Backend: 100% pass — 18 tables, 9 categories, 23 products, 5 members seeded; order create/patch/fire/pay math verified; discount percent & cash math; void role-gating (bartender 403, manager 200); staff CRUD gating; reports summary shape
- Frontend E2E: 100% pass — full login → floorplan → open table → add product with variant → discount 20% → save → pay cash → back to floorplan with table dirty

## Prioritized Backlog

### P0 (next iteration)
- Kitchen Display System (KDS) view for fired lines with bump/timer
- Split payments UI (by seat / by equal parts / by custom amount) — backend accepts `splits: []` already
- Menu manager: inline forms + variant/modifier matrix editor (currently prompts)
- Happy-hour price auto-apply during order taking (backend rule exists, apply live in Register)

### P1
- Full events module: trivia team registration, darts scoring machine hook, TV channel schedule CRUD
- Reservations & waitlist
- Inventory / stock deduction per line
- Digital receipts (email/SMS via Resend/Twilio)
- Shift reports & X/Z reports, cash-drawer float open/close

### P2
- Multi-venue, multi-terminal sync via websockets
- Offline mode with local cache
- Loyalty campaigns, targeted push notifications
- Delivery driver dispatch

## Personas
- **Owner (polymuze111@gmail.com)**: full admin, reviews reports, manages staff
- **Manager**: discount overrides, voids, staff CRUD, all POS actions
- **Head Bartender**: takes drink orders, fires bar course; cannot void
- **Server**: takes dine-in orders, fires kitchen; cannot void or manage staff
- **Cashier**: closes bills, processes payments
