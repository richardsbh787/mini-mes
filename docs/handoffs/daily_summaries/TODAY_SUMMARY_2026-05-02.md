# TODAY SUMMARY — 2026-05-02

## Active baseline

* Current main handoff reached v2.67.
* Planner Decision Matrix is now the primary Planning & Scheduling → Search / Find read view.
* LINE OVERVIEW, Production Schedule Grid, and Capacity / Load Check are now Supporting Checks, not equal primary read-view pills.

## Completed today

* Frozen and inserted supporting governance / boundary records for:

  * Planner Decision Matrix HTML Mock Implementation Boundary
  * Planner Decision Matrix Primary View & Supporting Checks Boundary
  * Supporting Checks Read-only Link Correction
* Implemented and pushed the approved static HTML mock changes.

## Latest pushed implementation commit

* Commit: `5d2122529f8c8bb44301fd42db89c8d056b351c7`
* File: `docs/mockups/sales_order_local_overseas_mock.html`
* Summary: Planner Decision Matrix is the primary Planning Search / Find read view. The primary toolbar keeps `+ Create / Add`, `Search / Find`, and `Planner Decision Matrix`. Supporting Checks links are visually secondary and clickable, reusing existing static mock view switching.

## Important UI decisions now locked for this stage

* Planner Decision Matrix is the default Search / Find read view for Planning.
* Supporting Checks must remain visible but secondary:

  * Line Overview
  * Production Schedule Grid
  * Capacity / Load Check
* Supporting Checks are for deeper investigation only, not equal first-level views.
* Static HTML mock only. No backend, database, workflow, approval, real route, localStorage, schema, service, test, AGENTS, or handoff logic changes were part of the HTML implementation.

## Do not reopen unless explicitly requested

* Do not reopen the completed Planner Decision Matrix primary/supporting-check hierarchy.
* Do not restore the old equal-pill layout for LINE OVERVIEW / Production Schedule Grid / Capacity / Load Check.
* Do not treat Supporting Checks as main pills again.

## Known unrelated dirty files to preserve untouched

* `tests/test_step47_fg_receive.py`
* `app/schemas/step46a_inventory_truth_semantic.py`
* `app/services/step46a_inventory_truth_semantic.py`
* `tests/test_step46a_inventory_truth_semantic.py`

## Next clean step

* After TS rotation is pushed, return only:

  * commit hash
  * GitHub commit URL
  * exact files changed/deleted
  * confirmation that only the daily summary rotation files were touched
  * final `git status --short`
