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

## What's Implemented (v5 · Feb 2026 iteration)
- **XSS hardening**: replaced `document.write` in Shift/Receipt/QR print with blob-URL `openPrintableWindow`
- **Defensive var inits** in backend (`_compute_totals`, `pay_order`, `public_menu`)
- **React hook deps stabilised** via `useCallback` in KDS/Waitlist/Floorplan
- 17/17 backend regression + full frontend blob-URL flows verified

## What's Implemented (v4 · Feb 2026 iteration)
- **Dark Menu QR**: public `/m/:tableId` mobile menu (no auth) with search, category chips, happy-hour banner, discounted pricing. QRCode modal from any Floorplan table with copy-link and printable QR card.
- **Live Waitlist** (`/waitlist`): add form (name/phone/party/quote), stat KPIs (waiting/notified/covers/avg wait), per-row Text (mocked SMS with actual message string in toast), Seat, Cancel. Overdue rows turn rose; notified rows turn cyan.
- **Combo Deals**: `/api/combos` CRUD + auto-apply engine. ComboEditor picks 2+ required products and discount type/value. Register live-detects combos and adds a cyan `Combo · <name>` line to totals; backend also applies on order create/update.
- **Manager Voids**: intercepts line-delete on saved orders for non-manager users → ManagerPin modal with keypad (PIN verified via `/api/auth/pin-verify` with role check).
- **Bonus — Repeat Round**: `btn-repeat-round` duplicates every current line for regulars ordering the same round again.
- Backend + frontend testing agent 100% pass on iteration 4.

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

## What's Implemented (v16 · Feb 2026 — Iter 23)
- **Peak-Rush Auto-Flash**: `RegisterUpsellStrip` starts a 90s timer whenever the top hint appears. If not accepted, the top chip flashes amber (ring + pulse animation) and a sonner toast fires: `Push this now: +1 <Product> → <Combo>`. Timer resets whenever the top hint changes or is accepted.
- **Nudges on QuickBar tiles**: Every tile with a `+1 → -X%` hint POSTs `shown` (deduped via ref map). Tapping the tile POSTs `accepted`. Clearing the tab or completing Send & Pay flushes remaining un-accepted hints as `dismissed`.
- **Nudges on Floorplan glow**: The 8s combo-hints poll now diffs against a `fpShownRef` — new hints POST `shown` with `source: "floorplan"`, hints that disappear from the feed POST `dismissed`. Every table-glow ping now feeds the leaderboard.
- **Leaderboard covers 3 touchpoints**: `register`, `quickbar`, `floorplan` (stored in `source` field; leaderboard aggregates all sources per server).

## What's Implemented (v15 · Feb 2026 — Iter 22)
- **Dismiss Tracking**: `RegisterUpsellStrip` now remembers every shown nudge in a `pendingRef` map (keyed by `order|combo|product`). On accept the entry is deleted (no dismiss). When the order transitions to `paid` or `voided`, every remaining pending nudge is flushed as `POST /api/upsell/log {status: "dismissed"}`. Leaderboard conversion % now reflects reality.

## What's Implemented (v14 · Feb 2026 — Iter 21)
- **Combo Heat-Map on Register**: new `RegisterUpsellStrip` component renders a cyan pulse-dot strip above the ProductGrid with the top-3 combos exactly one product-tap away from firing. Chips read `+1 <Product> → -X% (Combo)` with a net-gain badge; tapping a chip adds the product and logs an `accepted` nudge.
- **Live Upsell Nudge Log**: new backend collection `upsell_nudges` + three endpoints:
  - `POST /api/upsell/log` — record `shown | accepted | dismissed` (auto-dedupes `shown` within 60s per server+combo+product+order).
  - `GET  /api/upsell/leaderboard?window_hours=168` — per-server rollup: shown, accepted, conversion %, revenue_lifted.
  - `GET  /api/upsell/feed?limit=50` — reverse-chronological live event stream.
- **/upsell page + nav "Nudges"**: KPIs (Shown / Accepted / Conversion % / Revenue Lifted), a 7-day server leaderboard, and a live feed that refreshes every 12s. RegisterUpsellStrip now fires `shown` on hint render + `accepted` on chip tap.
- **Component Split Sprint** (targeted):
  - `TableCard` extracted from Floorplan.jsx → `/app/frontend/src/components/pos/floorplan/TableCard.jsx`
  - `ResCountdown` extracted → `/app/frontend/src/components/pos/floorplan/ResCountdown.jsx`
  - `ComboScheduleFields` extracted from ComboEditor.jsx → `/app/frontend/src/components/pos/combo/ComboScheduleFields.jsx`
  - `RegisterUpsellStrip` new self-contained component with hint calc + logging
  - Deferred (too risky mid-session, tracked in ROADMAP): CartTicket into 4 further sub-components + Register/Floorplan hook extraction.
- **Security**: moved test admin credentials out of `tests/test_iter17_features.py` into env vars (`TEST_ADMIN_EMAIL`, `TEST_ADMIN_PASSWORD`) with sane defaults for local dev.
- **Error visibility**: replaced 3 silent empty-catch blocks with `console.error/warn` — `AuthContext` /me refresh, `AuthContext` logout, `printable.js` print-blocked branch.
- **State correctness**: swapped React `key={i}` index-as-key anti-patterns for stable keys in `Receipt.jsx` (line items + split rows), `editors.jsx` (variant/modifier rows + HH day chips), `PaymentModal.jsx` (split rows), `ComboEditor.jsx` (slots).
- **Skipped as false positives**: 37 flagged `is <literal>` cases were all `is None` / `is True` / `is False` — correct Python for singleton comparison; grep for `is <int>` returned 0 hits, so no changes were needed.
- **Deferred to a dedicated refactor iteration**: component splits for `Floorplan.jsx` / `Register.jsx` / `ComboEditor.jsx` / `CartTicket.jsx` (large surface), complexity refactors of `_compute_totals`, `combo_hints`, `reports_summary`, `prep_view` (all functionally correct; splitting mid-flight risks regressions before a full test pass).
- **Test coverage**: 12/12 combined pytest still green after all string-key changes.

## What's Implemented (v12 · Feb 2026 — Iter 19)
- **Combo Heat-Map on QuickBar**: each drink tile shows a cyan "+1 → -X%" badge when tapping it would complete an active combo. Pure client-side calc using the cached `/api/combos` list, no extra endpoint.
- **Delivery Fee Split**: `/api/reports/summary` now returns `net_revenue`, `delivery_fees`, `delivery_gross`, `by_delivery_platform` (gross/fee/net per platform). Reports page shows a "Net Revenue" KPI and a per-platform breakdown card (foodpanda/deliveroo/keeta tinted rows).
- **Preauth Stripe SetupIntent** (real): `POST /api/tabs/preauth/setup-intent` creates a real Stripe SetupIntent (`usage=off_session`, test-key `sk_test_emergent`) and returns `client_secret`+`publishable_key`. `POST /api/tabs/preauth/complete` retrieves the SetupIntent post-confirmation, extracts card brand/last4/exp, and attaches them onto the preauth order. PreauthModal now has a "Create Card Hold" button; wire-up of Stripe Elements confirmation UI is scaffolded for the next iter (backend endpoints are live).
- **Combo Heat-Map on Floorplan**: new `GET /api/floorplan/combo-hints` returns per-occupied-table hints ("+1 <product> → -<value>%/HK$"); Floorplan renders a cyan glow ring + neon badge above each hinted table.
- **Substitution Pop**: new `GET /api/products/{pid}/substitutes` returns the 3 closest-in-price alternatives (same category, in-stock, kegs not all-blown). Register/QuickBar toasts "**<name>** is out. Try **<alt>** · HK$X" with an "Add substitute" action.
- **Delivery Ingest** (MOCKED): `POST /api/delivery/ingest`, `POST /api/delivery/simulate`, `GET /api/delivery/inbox`. New `/delivery` page shows platform-tinted cards (foodpanda/deliveroo/keeta) with a Simulate button. Ingested orders auto-fire so they land on KDS.
- **Bar Preauth Tab**: `POST /api/tabs/preauth` records `{customer_name, card_last4, hold_amount}` on an open order. Floorplan header "Preauth Tab" button opens the modal, then navigates to the Register.
- **Register layout fix**: `ProductGrid.jsx` now uses `col-span-6` for the products grid so tiles have breathing room; 86'd tiles clickable (needed for Substitution Pop).
- **Deal-Of-The-Night Rotator**: combos now carry an optional `schedule: {days, start_time, end_time}` (HK time, cross-midnight aware). `_active_combos` filters by the current window so a scheduled combo only auto-applies inside its slot. ComboEditor exposes a "Scheduled ↔ Always-on" toggle plus day chips and HH:MM inputs.
- **Auto-Close Tabs**: `POST /api/orders/auto-close` — manager/admin only. One click batch-settles every open tab, records `payment.method` (default card) + `note`, frees tables to dirty, decrements kegs. Floorplan header ships a red `Last Call · Auto-Close` button that confirms first.
- **Quick Bar Mode**: new `/bar` route + nav pill. Giant drink tiles show HH-discounted pricing with a `-X%` neon badge. One tap adds to a running tab; **Send & Pay Cash / Card** creates the order → auto-fires (so it lands on KDS instantly) → pays → shows the receipt modal.
- **Split & Merge Seats**:
  - Every `OrderLineIn` gains a `seat` field. CartTicket line rows show a `S1/S2…` chip that cycles through the party's guests (`data-testid=line-seat-<i>`).
  - `POST /api/orders/{oid}/move-line` moves a line to another seat *or* another order; totals recompute with the exclusivity engine on both sides.
  - `POST /api/orders/merge` (source→target) appends lines into target, voids source, frees the source table. Floorplan `TableActionModal` has `Merge Into Another Tab…`.
- **Bug fix (iter14→iter16 retest)**: TicketLines updaters (`qtyChange`, `toggleHold`, `cycleSeat`) rewritten with immutable `.map()` so React StrictMode's double-invoke no longer doubles the mutation. Verified guests=4 seat cycle S1→S2→S3→S4→S1, qty+ increments by exactly 1 per click, hold toggles cleanly.

## What's Implemented (v9 · Feb 2026 — Iter 13)
- **Orders router extracted**: all `/api/orders*` endpoints (list, get, create, patch, fire, pay, void, bump) moved into `/app/backend/routers/orders.py`. The exclusivity totals engine lives beside them. `server.py` is now ~530 lines.
- **Promo / Combo / Discount Mutual Exclusivity**: a product that already receives one promotion cannot receive another. Precedence HH → Combo → order-level discount. Backend `_compute_totals` returns `hh_locked_product_ids` + `combo_locked_product_ids`; frontend `Register.jsx` mirrors the same math and paints per-line "HH -X%" or "COMBO · <name>" lock badges plus an exclusivity note so staff see why a discount button is inert.
- **`hh_pct` line field** added to `OrderLineIn` — the register stamps it when it applies happy-hour pricing so the backend can enforce exclusivity on save/pay.
- **Advanced combo seed** — `_seed_combos` now seeds 3 slot-based demo combos on fresh installs: "Cocktail Duo" (2 slots, AND-style), "Beer & Bites" (2 slots, min/max qty), "Steak Night" (1 slot, any-2 mains).
- **Tests**: 5/5 `tests/test_iter13_exclusivity.py` unit + 8/8 `tests/test_iter13_orders_router.py` HTTP integration = 13/13 green. Frontend E2E (HH banner + lock badges + combo banner + payment + receipt) verified by testing agent.


- **Tables router extracted**: every `/api/tables*` endpoint moved to `/app/backend/routers/tables.py`; `server.py` shows a `NOTE` comment where they lived. Orders extraction remains next-up (staged rollout).
- **Keg Analytics**: every paid pour is now logged to `db.keg_pours`; new `GET /api/kegs/{id}/pours?days=7` returns per-day pour volume + `total_ml` / `total_pints` (with 0-fill for missing days). Frontend `keg-chart-<name>` button per card opens a modal with 3 KPIs (Total / Daily avg / Peak day) and a Recharts LineChart of the 7-day velocity.
- **Prep Bump All**: `POST /api/kds/prep/bump?product_id=…` bumps every fired-not-bumped line matching that product across all open orders. Frontend KDS Prep View gets a `prep-bump-all-<name>` button on every row → toast "Bumped N tickets" and the row disappears in one tap.
- Backend + frontend testing agent 100% pass on iter 11 (10/10) — 3 test-authoring bugs fixed inside the test file (schema `seats` naming, `rect` shape enum, `held=True` for fire to work).

## What's Implemented (v7 · Feb 2026 iteration)
- **Server.py split (pattern demo)**: extracted `/app/backend/routers/kegs.py` as its own APIRouter with shared helpers in `/app/backend/deps.py`.
- **Keg Watch**: `/api/kegs` CRUD + auto-decrement on payment; drains the lowest-volume keg per product first so alerts and 'blown' fire on the near-empty tap not the backup. Seed 6 kegs with Tap 01 at 8% for alert demo. `/kegs` page with KPIs and per-tap progress bars.
- **Consolidated Prep View**: `GET /api/kds/prep` groups fired items by product; KDS gets a Prep View tab with giant `×N` counts and per-table pill chips.
- Testing agent 100% pass — iter10 (8/8) + iter8+9 regression (8/8).

## Prioritized Backlog (from user's expanded HK Bar spec)

### P0 · Fast Bar Ops (next up)
- 1.01 One-Tap Quick Bar Mode — dedicated bartender screen with big-tile drinks + auto-fire
- 1.02 Pre-Authorized Bar Tabs — swipe card to open, prevents walk-outs
- 1.03 Move/split/merge items between seats (extends split payments)
- 1.05 Named Tab Search — find open tabs by name / description / seat
- 1.06 Auto-Close Tabs at Last Call — batch-settle to preauth cards at 03:00
- 1.09 already done (PIN quick-switch)
- 1.10 Multi-tier Happy Hours (3 windows) — extends current single-window engine

### P0 · KDS/BDS enhancements
- 3.01 Isolated Station Routing (kitchen/service-bar/food) — extend current KDS station filter
- 3.03 Consolidated Prep Views ("7 burgers total")
- 3.04 Dine-in vs Take-Away color borders
- 3.05 Allergen / Modification flashing
- 3.06 One-Touch 86ing (product-level "out of stock")
- 3.08 Zone-based printer routing

### P0 · HK Payments
- 4.01 Octopus Card hardware integration
- 4.02 FPS QR generation
- 4.03 AlipayHK / WeChat Pay HK / PayMe / UnionPay
- 4.04 Foodpanda / Deliveroo / KeeTa order ingestion
- 4.06 Dual-language receipts (Traditional Chinese + English)
- 4.07 already done (mixed payment via split)
- 4.08 already done (10% service + separate tips)

### P1 · Draught & Inventory
- 2.01 Tap-level volume tracking (35+ taps)
- 2.03 Keg threshold alerts (<10%)
- 2.04 Digital tap-list push to QR menu on keg-blown
- 2.05 Cocktail ml-level modifiers
- 2.06 Substitution triggers ("this IPA is out, try Hazy Pale?")
- 2.09 Keg deposit / return ledger
- 2.10 Keg life curve (days-open vs pour velocity)

### P2
- 1.04 Offline Processing Mode
- 2.08 Batch cocktail recipe depletion
- 3.02 (already covered by KDS colour timers)
- 3.07 Delayed cook sync (marked overkill by user)

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
