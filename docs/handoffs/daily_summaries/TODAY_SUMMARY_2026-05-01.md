# TODAY SUMMARY — 2026-05-01

## Purpose / 用途

This Today Summary is for Qingchen start-of-work context only.

It is not a Codex change request.
It is not an implementation instruction by itself.
It is not a UI requirement list to execute automatically.

Before continuing Mini-MES work, Qingchen must read this summary first to avoid reopening completed modules, repeating already-pushed work, or drifting away from the latest active direction.

---

## Current Active Repository Context

Repository: mini-mes
Current UI mock file in active use:

docs/mockups/sales_order_local_overseas_mock.html

Important: This mock file currently contains both Sales Order Management mock work and Planning & Scheduling mock work.

Do not touch unrelated dirty files unless Ruichen explicitly selects them.

Known unrelated dirty files still present after latest confirmed push:

- tests/test_step47_fg_receive.py
- app/schemas/step46a_inventory_truth_semantic.py
- app/services/step46a_inventory_truth_semantic.py
- tests/test_step46a_inventory_truth_semantic.py

These must not be staged, committed, restored, reset, or pushed during UI mock work unless explicitly instructed.

---

## Latest Confirmed Push

Latest confirmed pushed commit:

35f76063c7b6a459f00008d4bbba106b42b0b730

GitHub commit URL:

https://github.com/richardsbh787/mini-mes/commit/35f76063c7b6a459f00008d4bbba106b42b0b730

Exact file included:

docs/mockups/sales_order_local_overseas_mock.html

Summary of pushed change:

Sales Order Management mock refinements were committed and pushed:
- compact Search/Create toolbars
- Create/Add opens directly to Order Summary
- flattened Sales Order workspace wrappers
- lighter Order Items layout
- separated Remove Item... danger action with helper text
- no unrelated dirty files were staged or pushed
- no PR was opened

Do not reopen or rework this pushed Sales Order Management refinement unless Ruichen explicitly asks.

---

## Sales Order Management Current Status

Sales Order Management is currently acceptable enough to leave and move on.

Important locked practical decision:

Remove Item / delete-style danger action must not sit beside Save, Undo, or Add in a way that causes accidental clicking.

Current design direction:
- + Add Order Item is a safe normal action
- Remove Item... is separated as a danger action
- helper text states that removal requires confirmation in a real system
- no real delete logic, backend, persistence, confirmation modal, or validation was added

Do not over-polish Sales Order Management now.

---

## Active Work Has Returned To Planning & Scheduling

After the Sales Order Management push, Ruichen confirmed:

“继续回到 Planning & Scheduling”

Current Planning & Scheduling surfaces visible in the mock:

1. LINE OVERVIEW
2. READINESS BOARD

Important business interpretation confirmed:

LINE OVERVIEW and READINESS BOARD are not two separate business analyses.

They are two views of the same planning readiness analysis:

- LINE OVERVIEW = line/item list view for supervisor search, selection, and drill-down
- READINESS BOARD = calendar/slot view for seeing whether runnable work can be placed across dates and lines

Therefore do not add duplicate logic, duplicate KPIs, or extra explanation that makes the customer feel Mini-MES is “adding water”.

The design must feel simple, serious, and necessary.

---

## Planning & Scheduling Current State

LINE OVERVIEW already exists and has been pushed previously.

Known pushed Planning-related commits from recent work include:

- LINE OVERVIEW / Planning Search-Find work was pushed previously.
- READINESS BOARD mock was pushed previously.
- LINE OVERVIEW compact toolbar refinement was pushed previously.

Do not assume Planning needs the same content rebuilt again.

Before asking Codex to edit Planning, Qingchen must first decide whether there is a real acceptance gap.

Current screen observation:

READINESS BOARD already shows:
- Search / Find toolbar
- LINE OVERVIEW tab
- READINESS BOARD tab
- Line filter
- Status filter
- 5-Day view filter
- date grid
- Line 1 / Line 2 rows
- Planning Gap cells
- Public Holiday cells
- runnable WO cell examples
- Cannot Plan / Replacement Advisory panel
- read-only static advisory note
- OT policy reference note marked as configurable by customer

LINE OVERVIEW already shows:
- Search / Find toolbar
- LINE OVERVIEW tab
- READINESS BOARD tab
- filters
- selected line band
- planning table
- Expand A / Expand B areas

Do not request edits that simply repeat this same structure.

---

## Current Product Principle

Ruichen’s latest direction:

Avoid “画蛇添足”.

Planning & Scheduling mock must not look like random extra features were added to make Mini-MES appear bigger.

The customer should feel:
- LINE OVERVIEW answers “which line/order is risky?”
- READINESS BOARD answers “where can we put runnable work?”
- both are needed, but they come from the same planning readiness thinking

Keep mock-stage language simple and practical.

---

## Next Correct Step

Next step should NOT be another automatic Codex modification.

Next step should be a short Qingchen review:

Check whether Planning & Scheduling LINE OVERVIEW + READINESS BOARD already passes current trial-mock acceptance.

Acceptance focus:

1. Is it clear that LINE OVERVIEW and READINESS BOARD are two views of the same planning readiness problem?
2. Can a supervisor understand in under 10 seconds:
   - which line has a planning gap
   - which WO is blocked
   - whether a replacement candidate exists
   - what action is required
3. Is there any duplicated or confusing wording that makes the UI feel overbuilt?
4. Are all disclaimers still mock-stage only?
5. Is there any real logic, backend, persistence, workflow engine, or auto-planning implied? There should not be.
6. Are Planning changes limited to the target HTML file only if another edit is needed?

Only if one of these acceptance points fails should Codex be asked to modify the HTML.

---

## Codex Discipline If Work Continues

If Codex is used next, the first instruction must be read-only:

1. Read AGENTS.md
2. Read docs/handoffs/current_main_handoff.md if governance context is needed
3. Read latest Today Summary under docs/handoffs/daily_summaries/ for context only
4. Run git status --short
5. Run git diff --stat
6. Confirm the current target file before editing

Codex must not treat Today Summary as a change request.

Codex must not stage or touch unrelated dirty files.

Allowed target file for current UI mock work, unless Ruichen changes scope:

docs/mockups/sales_order_local_overseas_mock.html

---

## Current Reminder For Qingchen

Do not rush to modify.

First judge whether the visible Planning & Scheduling mock already satisfies the agreed intent.

If it already passes, say so clearly and move to the next planning page or next module decision.

Do not create extra UI just because there is space.
Do not duplicate LINE OVERVIEW and READINESS BOARD.
Do not over-explain inside the customer-facing mock.

TS is Qingchen’s medicine, not Codex’s order.
