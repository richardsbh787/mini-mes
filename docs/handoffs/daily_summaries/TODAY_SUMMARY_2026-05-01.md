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

Known unrelated dirty files still present and must not be staged, committed, restored, reset, or pushed unless Ruichen explicitly selects them:

- tests/test_step47_fg_receive.py
- app/schemas/step46a_inventory_truth_semantic.py
- app/services/step46a_inventory_truth_semantic.py
- tests/test_step46a_inventory_truth_semantic.py

---

## Sales Order Management Current Status

Sales Order Management mock refinement is complete enough and should not be reopened unless Ruichen explicitly asks.

Latest confirmed pushed Sales Order Management mock refinement:

- Commit: 35f76063c7b6a459f00008d4bbba106b42b0b730
- URL: https://github.com/richardsbh787/mini-mes/commit/35f76063c7b6a459f00008d4bbba106b42b0b730
- File: docs/mockups/sales_order_local_overseas_mock.html

Summary of pushed Sales Order Management state:

- compact Search / Create toolbars
- Create / Add opens directly to Order Summary
- Search / Find remains clickable from Create / Add and routes back to Search Order
- flattened Sales Order workspace wrappers
- lighter Order Items layout
- + Add Order Item remains a safe normal action
- Remove Item... is separated as a danger action with helper text
- no backend, persistence, confirmation modal, validation, or delete workflow was added

Do not over-polish Sales Order Management now.

---

## Active Direction: Planning & Scheduling

Current active direction is Planning & Scheduling.

Next development target:

Planning & Scheduling → Search / Find → Capacity / Load Check

Do not jump into Planning Create / Add or the Production module before the Capacity / Load Check task package is confirmed.

Before any HTML change, prepare a single-page task package for Qwen / Qianwen review first. Do not call Codex for a big UI change directly.

---

## Existing Planning Pages

LINE OVERVIEW remains completed.

READINESS BOARD was renamed to Production Schedule Grid.

- Rename commit: e52e8f7f4b77eae1ee01d6a4baa007eaa7c5ee2e
- Production Schedule Grid is the same existing schedule grid view, not a new third page.
- LINE OVERVIEW remains the other Planning Search / Find view.

Current practical meaning:

- LINE OVERVIEW answers: which line / order is risky?
- Production Schedule Grid answers: where can runnable work be placed?

They are two views of the same planning readiness problem, not two separate business analyses.

Do not add duplicate logic, duplicate KPIs, or extra explanation that makes the customer feel Mini-MES is adding water.

---

## Frozen Planning Schema / Architecture Baselines Now Active

Planning & Scheduling Master List Schemas v1

- File: docs/blueprints/planning_scheduling_master_list_schemas_v1.md
- Commit: 942a47462f52c662860bc6feb63e1a2d890399eb

Planning Capacity Constraint / Repair / Reject Impact Addendum v1.1

- File: docs/blueprints/planning_scheduling_capacity_constraint_repair_reject_addendum_v1_1.md
- Commit: a73cc1aa62083e57697e7c0de7ceb4f876c9c9b6

Dropdown Master List v1

- File: docs/blueprints/dropdown_master_list_v1.md
- Commit: 6ea543c77007122fe83ad6b10bff4345cc3f0ca0

Module Plug-and-Play Validation Principles v1

- File: docs/blueprints/module_plug_and_play_validation_principles_v1.md
- Commit: 02c3775909ae54d9b65515c938a8bf9fe24580c8

---

## Trial Objective — Module Plug-and-Play Validation

Mini-MES trial must validate that modules can be hidden, restored, reordered, enabled/disabled, and combined into future package structures without breaking core workflows.

Plug-and-play does not override frozen governance, schema, dropdown, handoff, legal truth, or module-boundary disciplines.

Cross-module references are read-only / reference-only by default.

Missing or disabled module data must display as Reference Unavailable / N/A and must not be treated as Passed, Ready, Approved, or Completed.

Future Planning & Scheduling Task Cards must include Module Dependency Declaration.

Module Dependency Declaration must be reviewed and approved by Qingchen before the corresponding Task Card can be frozen or passed to Codex.

---

## Planning Task Card Rule

Every future Planning & Scheduling Task Card must include:

- Schema Alignment
- Dropdown Master List Alignment
- Module Dependency Declaration
- Factory Usability Check / 工厂可用性小验证
- 📋 業務邏輯確認 / 對應工廠現場場景

This rule is active for the next Capacity / Load Check package.

---

## Capacity / Load Check Next-Step Reminder

Capacity / Load Check must align to:

- Master List Schemas v1
- Capacity Constraint / Repair / Reject Addendum v1.1
- Dropdown Master List v1
- Module Plug-and-Play Validation Principles v1

Capacity / Load Check must stay advisory/read-side unless a later governed record explicitly opens stronger behavior.

It must not imply:

- backend implementation
- database migration
- auto-planning
- auto-release
- auto-move-line
- auto-approve OT
- production execution
- inventory update
- WO release
- WO close
- Step 47 Phase B

Before Codex changes any HTML, Qingchen should prepare a one-page task package for Qwen / Qianwen review.

---

## Codex Discipline If Work Continues

If Codex is used next, the first instruction should be read-only:

1. Read AGENTS.md.
2. Read docs/handoffs/current_main_handoff.md if governance context is needed.
3. Read latest Today Summary under docs/handoffs/daily_summaries/ for context only.
4. Run git status --short.
5. Run git diff --stat.
6. Confirm the current target file before editing.

Codex must not treat Today Summary as a change request.

Codex must not stage or touch unrelated dirty files.

Allowed target file for current UI mock work, unless Ruichen changes scope:

docs/mockups/sales_order_local_overseas_mock.html

---

## Current Reminder For Qingchen

Do not rush to modify.

Planning & Scheduling should move next through a small reviewed Capacity / Load Check task package, not a large direct UI edit.

Do not create extra UI just because there is space.
Do not duplicate LINE OVERVIEW and Production Schedule Grid.
Do not over-explain inside the customer-facing mock.

TS is Qingchen’s medicine, not Codex’s order.
