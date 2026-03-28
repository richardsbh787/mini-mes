Mini-MES Handoff v2.9

Updated after Step 47B legal location evidence & accountability baseline freeze
Date: 2026-03-28

1. Frozen mainline snapshot

Current frozen implementation line now includes:

Steps 1-44 frozen

Step 40A implementation frozen

Step 45 implementation frozen

Step 46 design-layer frozen

Step 47 design-layer frozen

Step 47A frozen admission baseline

Step 47B design-layer frozen

Step 40A is no longer design-only.
It has passed main review, Qinran final review, commit, and push.

Step 45 is implemented and frozen.

Step 46 is design-layer frozen only.
It is a semantic interpretation baseline and not an implementation freeze.

Step 46A is implemented and frozen.

Step 47 is design-frozen only.

Step 47A is frozen as the admitted source event baseline.

Step 47B is design-frozen only.

2. Newly frozen step
Step 40A - Daily Smart Stock Check / Movement Health Audit Baseline

Commit: 25d24e3e2090a132f92ffc16c96c066e356f121b
Final status: PASS - Frozen
Qinran final review date: 2026-03-22

Step 40A frozen scope

Step 40A implements the daily stock audit baseline so the system can:

run daily stock audit

select candidate high-frequency / high-risk items

evaluate movement-health rules

generate suspicious findings

create physical check tasks when thresholds are hit

Step 40A frozen write boundary

Step 40A may write only:

daily_stock_audit_run

daily_stock_audit_finding

physical_check_task

Step 40A must not mutate frozen truth surfaces including:

stock_ledger

work_order_wip_transfer

work_order_fg_receive

work_order_shipment

work_order_routing_snapshot_step

prebuild_authorization

shadow_batch_case

scan_execution_event

3. Newly frozen step
Step 45 - Prebuild Authorization Read Surface Completion Check

Commit: c6c704db344d08b1d57a7346629e767d5e2b49ab
Final status: PASS - Frozen
Qinran final review date: 2026-03-23

Step 45 frozen scope

Step 45 adds read-only endpoints:

GET /v2/prebuild-authorizations

GET /v2/prebuild-authorizations/detail

Step 45 reuses frozen Step 42 schema/service layer.

Step 45 adds no write path.

Step 45 changes no Step 42 / Step 43 / Step 44 semantics.

Step 45 touches no frozen truth write surfaces.

main.py only adds approved router import/include hunks.

Step 45 frozen test coverage

list filtering

detail VOID fields:

voided_by

voided_at

void_reason_code

void_note

Step 45 frozen risk

no new risk points

4. Newly frozen design-layer step
Step 46 - Inventory Truth Ontology Baseline

Final status: design-layer frozen
Review status: passed Qinran final review
Eligibility status: eligible to enter current_main_handoff

Step 46 positioning

Step 46 is the inventory semantic interpretation layer only.

Step 46 is not a replacement for any already-frozen status truth.

Step 46 must not pollute any write path.

Step 46 does not implement Step 46A.

Non-blocking note

The Step 46A Task Card must include an "Inventory State judgment rule table" as acceptance criteria.

5. Newly frozen step
Step 46A - Inventory Truth Semantic Baseline

Final status: PASS - Frozen
Review status: formal freeze recorded

Step 46A frozen base boundary

Step 46A is the first implementation slice under Step 46.

Step 46A scope is read-only semantic interpretation only.

Step 46A adds no write path.

Step 46A adds no new truth table.

Step 46A adds no posting-column expansion.

WIP must remain conservatively interpreted.

Shortage may appear only as risk hint, not as a formal shortage object or module.

Step 46A frozen implementation boundary

Step 46A reads frozen StockLedger evidence only.

Step 46A returns derived semantic meaning only.

Step 46A adds no truth table.

Step 46A adds no write path.

Step 46A adds no posting-column expansion.

Step 46A adds no API / router / bootstrap / main.py / models.py expansion.

Step 46A does not enter Step 47 stock position / bucket / location truth.

Step 46A Patch Pack A frozen lock points

P-A1 requested_qty shortage hint comparison is allowed only against CONFIRMED_AVAILABLE quantity.

OBSERVED_IN_TRANSFER must not contribute to available supply comparison.

OBSERVED_WIP_CONSERVATIVE must not contribute to available supply comparison.

CONFIRMED_RESTRICTED and CONFIRMED_SCRAP must not contribute to available supply comparison.

NO_EVIDENCE must not be silently converted into shortage truth.

P-A2 as_of is frozen as an evidence cutoff only.

as_of filters which frozen ledger evidence may be considered.

as_of does not create a time-window engine.

as_of does not create trend or period analytics.

as_of does not alter the response contract.

P-A3 evidence_refs ordering is frozen as deterministic newest-first by evidence timestamp, tie-break by ledger_id descending.

P-A4 conservative non-promotion is frozen.

WIP must never be promoted to AVAILABLE.

IN_TRANSFER must never be promoted to AVAILABLE.

risk_hints may coexist with conservative states without changing semantic_state or availability_class.

Step 46A focused verification counts

Initial Step 46A focused verification: 11 passed.

Patch Pack A focused verification: 16 passed.

Step 46A non-blocking note

RP-46A-P-1 - Step 46A evidence aggregation remains an interpretation read layer only.

Current implementation reads matching StockLedger evidence and interprets semantics in-process.
Accepted because this is a frozen read-only semantic baseline, not a performance or analytics step.

6. Newly frozen design-layer step
Step 47 - Inventory Position Truth Baseline

Status: Design Freeze

Main review result: PASS

Secondary review result: PASS

Step 47 frozen core boundary

Step 47 may introduce one new persisted truth surface only for inventory position truth.

Step 47 must not expand StockLedger columns.

Step 47 must not modify frozen Step 46A semantics.

Step 47 must not auto-start implementation.

Step 47 legal write principle

No legal location evidence = no legal position write

Only the system may write InventoryPositionTruth in Step 47.

No guessed / convenience-inferred location truth is allowed.

Step 47 admitted source-event policy

Admitted source-event list = EMPTY by default.

No existing source event type is automatically admitted.

Any unlisted source must hard-reject and must not write InventoryPositionTruth.

Future admission requirements:

1. explicit location_code
2. resolvable item_code or item_id
3. explicit stock_bucket
4. explicit stock_uom
5. signed quantity delta or unambiguous derivation rule
6. source-event trace identity

Step 47 zero-position rule

Retain zero-quantity position rows.

Do not prune zero rows in Step 47.

Zero rows remain readable as current-state truth.

Future prune/archive policy is out of scope for Step 47.

Step 47 non-goals / exclusions

Step 47 does not introduce physical count.

Step 47 does not introduce discrepancy / investigation flow.

Step 47 does not introduce recount.

Step 47 does not introduce relocate / reclassify / adjustment workflow.

Step 47 does not introduce 701/702 posting.

Step 47 does not introduce ATP / formal shortage engine.

Step 47 does not introduce warehouse hierarchy expansion.

Step 47 does not introduce Step 48 work.

Step 47 non-blocking notes

RP-47-D-1: item_id-only source resolution rule to be clarified at implementation stage.

RP-47-D-2: last_event_at timezone rule to be clarified at implementation stage; preferred UTC stored / KL display.

Step 47 stop rule

Step 47 is design-frozen only.

Implementation must not start automatically.

Any Step 47 implementation requires explicit user authorization.

7. Newly frozen design-layer step
Step 47A - Source Admission Evaluation Baseline

Status: Frozen

Step 47A positioning

Step 47A is the source-admission evaluation layer only.

Step 47A does not modify frozen Step 47 boundary.

Step 47A does not modify frozen Step 46A semantics.

Step 47A does not modify frozen StockLedger boundaries.

Step 47A does not start implementation.

Step 47A does not auto-admit any source.

Step 47A candidate source-event review scope

Review scope is limited to:

FG_RECEIVE

RM_ISSUE

SHIPMENT

WIP_TRANSFER

Step 47A legal admission standard

Each candidate source must be evaluated only against this six-point legal admission standard:

1. explicit location_code
2. resolvable item_code or item_id
3. explicit stock_bucket
4. explicit stock_uom
5. signed quantity delta or unambiguous derivation rule
6. source-event trace identity

Step 47A classification boundary

Classification is limited to:

ADMISSIBLE

NOT_ADMISSIBLE_YET

OUT_OF_SCOPE

Any missing, ambiguous, or convenience-inferred requirement must classify as NOT_ADMISSIBLE_YET.

Step 47A output contract fields

Output contract is limited to:

source_event_type

classification

evidence_1_location_code

evidence_2_item_identity

evidence_3_stock_bucket

evidence_4_stock_uom

evidence_5_signed_delta

evidence_6_trace_identity

admission_gap_summary

note

This is not runtime configuration.

This is not a persisted table.

This is not an implementation surface.

Step 47A non-blocking notes

RP-47A-D-1: the future activation path from ADMISSIBLE classification into the Step 47 admitted-source list must be clarified in the later admission-table phase

RP-47A-D-2: future non-starter source-event candidates may require a later Step 47B or equivalent path

Step 47A stop rule

Step 47A is frozen as the admitted source event baseline.

Step 47A does not yet produce final four-source admission results.

Step 47A does not start implementation.

Any Step 47A implementation or final four-source admission output requires explicit user authorization.

Step 47A admission evaluation output freeze

Step 47A Admission Evaluation Output = Frozen

Freeze date = 2026-03-27

All four candidate source-event types are NOT_ADMISSIBLE_YET.

FG_RECEIVE fails due to missing explicit location_code.

RM_ISSUE fails due to missing explicit location_code.

SHIPMENT fails due to missing explicit location_code.

WIP_TRANSFER fails due to missing explicit location_code, stock_bucket mismatch, and ambiguous delta direction.

Step 47 admitted-source list remains effectively EMPTY.

Step 47 implementation remains BLOCKED.

Unblock path requires at least one source to gain legal location_code in its frozen truth surface, then pass full Step 47A re-evaluation and final main review.

RP-47A-E-1: the location_code unblock path must be explicitly frozen in handoff to avoid implementation shortcuts

7A. Newly frozen design-layer step
Step 47B - Legal Location Evidence & Accountability Baseline

Status: Design Freeze Baseline - formally frozen

Frozen task card baseline: Step 47B Task Card v2.1

Step 47 current status

Step 47 implementation remains BLOCKED.

Step 47B positioning

Step 47B is a legal-unblock prerequisite design step for Step 47.

Step 47B is NOT Step 47 implementation.

Step 47B is NOT position truth write design.

Step 47B is NOT the discipline engine.

Step 47B is NOT a runtime accountability engine.

Step 47B is NOT config-table or persistence-object design.

Step 47B three core laws

A complete accountability chain does NOT equal valid legal location evidence.

The accountability chain cannot replace any of the Step 47A six admission standards.

Step 47B defines rules only and does not materialize runtime objects.

Step 47B hard boundaries

No new persistent tables.

No new fields.

No new truth surfaces.

No StockLedger column expansion.

No Step 46A semantic change.

Do not enter the discipline engine.

Do not enter Step 47 implementation.

Do not define any write action.

Do not use convenience inference to fill location_code.

Step 47B relationship to Step 47A

Step 47B does not modify the six Step 47A admission standards.

Any source repaired in the future must still re-run the full Step 47A six-point admission evaluation.

The accountability chain must not replace explicit evidence such as location_code, stock_bucket, stock_uom, delta rule, or trace identity.

Legal location evidence carry-forward

Legal location evidence still strictly follows the Step 47A six-point admission standard only:

1. explicit location_code
2. resolvable item_code or item_id
3. explicit stock_bucket
4. explicit stock_uom
5. signed quantity delta or unambiguous derivation rule
6. source-event trace identity

Even if owner_role, duty_person, performed_by, and approved_by are complete, if explicit location_code is still missing, ambiguous, indirect, or inferred, legal location evidence is still NOT established and Step 47 remains BLOCKED.

FG_RECEIVE first frozen wording

FG_RECEIVE is only the first priority evaluation candidate.

FG_RECEIVE is NOT automatic admission.

FG_RECEIVE cannot board first and ticket later.

If location_code or any other missing evidence must be added, that must be handled in a separate future step.

Repair Gap frozen wording

If upstream frozen truth does not explicitly provide required owner_role, duty_person, performed_by, or approved_by fields, Step 47B may only mark this as a Repair Gap.

Step 47B must not patch or implement that gap within this step.

Step 47B acceptance criteria baseline

G01 - Step 47B Task Card v2.1 is the formally frozen Design Freeze Baseline.

G02 - Step 47 implementation remains BLOCKED; Step 47B does not authorize or start implementation.

G03 - Step 47B is frozen only as a legal-unblock prerequisite design step and not as Step 47 implementation, position truth write design, discipline engine, runtime accountability engine, or config-table / persistence-object design.

G04 - The three Step 47B core laws are frozen: accountability chain does not equal legal location evidence; accountability chain cannot replace any Step 47A admission standard; Step 47B defines rules only and materializes no runtime objects.

G05 - Step 47B hard boundaries are frozen: no new persistent tables, no new fields, no new truth surfaces, no StockLedger column expansion, no Step 46A semantic change, no discipline-engine entry, no Step 47 implementation entry, no write action, and no convenience inference to fill location_code.

G06 - Step 47B does not modify the Step 47A six admission standards, and any future repaired source must re-run the full Step 47A six-point admission evaluation before any unblock decision.

G07 - Legal location evidence still follows the Step 47A six-point admission standard only, and the accountability chain cannot replace explicit evidence requirements including location_code, stock_bucket, stock_uom, signed delta rule, and trace identity.

G08 - FG_RECEIVE-first wording is frozen as first priority evaluation candidate only, not automatic admission, with no board-first-ticket-later shortcut.

G09 - If upstream frozen truth lacks explicit owner_role, duty_person, performed_by, or approved_by fields, Step 47B may mark only a Repair Gap and must not patch or implement that gap in this step.

G10 - Any future evidence repair needed to satisfy Step 47A or Step 47 must be handled in a separate future step; Step 47B itself defines no write action and no runtime materialization path.

8. Step 40A frozen guard chain

Guard chain confirmed frozen as:

G01 audit_date parse / fallback (KL timezone)

G02 duplicate successful run-date guard (409)

G03 ledger source availability guard (503)

G04 candidate item selection

G05 per-item rule evaluation (R01-R05)

G06 finding write

G07 physical-check-task decision

G08 run finalize + commit

9. Step 40A frozen rule baseline
Rules

R01_NEGATIVE_BALANCE -> 50

R02_HIGH_MOVEMENT_DENSITY -> 20

R03_SAME_DAY_IN_OUT_OSCILLATION -> 20

R04_EXCESSIVE_CORRECTION_ACTIVITY -> 30

R05_BUCKET_FLOW_ABNORMALITY -> 20

Risk levels

HIGH >= 50

MEDIUM >= 20

LOW < 20

Physical Check Task trigger

Create PCT when:

hit R01, or

risk level = HIGH

10. Step 40A frozen integration surface

Approved Step 40A implementation set includes:

app/api/v2/daily_stock_audit.py

app/bootstrap/step40a_daily_stock_audit_schema.py

app/models_step40a_daily_stock_audit.py

app/schemas/step40a_daily_stock_audit.py

app/services/step40a_daily_stock_audit.py

tests/test_step40a_daily_stock_audit.py

main.py Step 40A-only approved hunks

main.py approved hunks

import ensure_step40a_daily_stock_audit_schema

import daily_stock_audit_router

import register_daily_stock_audit_scheduler

app.include_router(daily_stock_audit_router)

ensure_step40a_daily_stock_audit_schema(engine)

register_daily_stock_audit_scheduler(app)

Confirmed excluded from Step 40A commit:

models.py

schemas.py

any Step 41 / 42 leftovers

.env.txt

AGENTS_final.md

AGENTS_updated.md

unrelated docs files

11. Step 40A known non-blocking risks
RP-1 - candidate selection scans full StockLedger

Current implementation loads StockLedger rows then filters in memory by date.
Accepted as Starter simplification. Performance risk only, not blocking freeze.

RP-2 - triggered_rule_codes stored as comma-separated string

rule_code filter uses LIKE.
Accepted because current rule-code naming set has no overlap collision.

RP-3 - _next_no uses millisecond timestamp + uuid hex

Accepted. Uniqueness risk considered sufficiently low for Starter.

12. Governance baseline normalization now frozen

Main handoff baseline normalization has been completed.

New rule

The only valid main handoff baseline is:

docs/handoffs/current_main_handoff.md

Hard rule

Do not guess latest handoff by:

filename

timestamp

patch file

patch_pack file

archive file

unless explicitly instructed.

AGENTS.md governance update

AGENTS.md now explicitly locks this rule.
Future Codex runs must read:

AGENTS.md

docs/handoffs/current_main_handoff.md

before any step work.

13. Corrected final blueprint now locked

Starter Final Blueprint

Step 46 Inventory Truth Ontology Baseline

Step 46A Inventory Truth Semantic Baseline

Step 47 Stock Position / Bucket / Location Truth

Step 48 Auth / Operator Identity Baseline

Step 49 Physical Observation / Count

Step 50 Discrepancy Case

Step 51 Post Inventory Adjustments 701 / 702

Step 52 Exception Inventory / Reclassify / Relocate

Step 53 Trusted Availability Engine

Step 54 Shortage Check

Step 55 Shortage Summary

Step 56 Inbound / Receiving

Step 57 Basic Shipment Completion

Step 58 WO VOID

Step 59 ECN / Revision Control

Step 60 WAIVER / Controlled Substitution

Step 61 Monthly Closing v1

Step 62 Frontend Trial Pages

Step 63 Integration / Stabilization / Trial Prep

Full Continuation Blueprint

Step 64 Planning Full Baseline

Step 64A HMLV Planning & Risk Appetite Engine

Step 65 Purchasing / Supply Chain Full Baseline

Optional / Phase 2+

Step 66 R&D / Engineering Support (Optional)

Quality / Complaint / CAPA

Step 67 Quality Management Baseline

Step 68 Complaint / Customer Claim Baseline

Step 69 CAPA Baseline

14. Step 64 / 64A / 65 / 66 / 67-69 frozen notes

Step 64 is Full-level core, not lightweight scheduling.

Step 64A is the core engine layer inside Step 64, not a separate mainline step.

Step 64A merges planning logic with risk appetite in HMLV context.

Step 64A output classes are:

Safe

Pushable

Unsafe

Step 64A user choice output must provide:

conservative

balanced

sprint

Step 65 should target near-full/full coverage because China sourcing lead time, shipping, customs, and inland transport materially affect delivery dates.

Step 65 must include Supplier Management / Comparison.

Step 66 is optional and must not block Step 64 or Step 65.

Step 67 / Step 68 / Step 69 must support direct Excel link / Google Drive link access.

15. Factory Control Overlay V1

Factory Control Overlay V1 is not a separate mainline.

Factory Control Overlay V1 is a horizontal embedded control layer inside the main blueprint.

Factory Control Overlay V1 covers:

Production Discipline Control V1

Shadow Batch / Discipline Breach Batch

Scan-Driven Traceability / Barcode + QR Code scan system

Output Truth / Unique Part Input Anchor + Tray/Pallet Completion Scan + Hourly Auto Rollup

Prebuild / Prep Control

Emergency Make / Commercial Pressure / Executive Override Control

Capacity Truth Control

Embedded blueprint effect

The overlay must be reflected horizontally across:

Inventory Truth / identity / labels

stock position buckets including PREBUILD_WIP / EMERGENCY_MAKE_WIP / FG_CONVERSION_HOLD / EXEC_RISK_BATCH

observation / discrepancy investigation chain

trusted availability / shortage / capacity reservation / warning / diversion

inbound rule linkage

WIP / QC / FG read-surface expansion

shipment override chain

WO VOID / Auth / ECN / WAIVER traceability

frontend visibility

integration test additions

16. Shortage Check Activation Gate

Accountability Engine V1 and 厂库库存真相控制 V1 are memory-only before Step 54.

They must not be implemented or allowed to pollute upstream steps before Step 54.

They become active prerequisite design packages only when the project formally enters Step 54 Shortage Check.

17. Review / control discipline remains locked

Still in force:

double-layer review system

Qingchen main review

Qinran final review

single-step advancement

no step jump before freeze / permission

Ontology + Guard V2 + GUARD MODE + Operator Minimal Action Rule

T-1 / T0 / T+1 truth audit

S-1 / S0 / S+1 step audit

18. Current locked status

Step 45 is implemented and frozen.

Step 46 is design-layer frozen.

Step 46A is implemented and frozen.

Step 47 is design-frozen only.

Step 47A is frozen as the admitted source event baseline.

Step 47B is design-frozen only.

Important

Do not auto-advance beyond the current locked task without explicit user authorization.

Do not auto-advance to Step 47 without explicit user authorization.

Do not start Step 47 implementation without explicit user authorization.

Do not auto-advance to Step 48 without explicit user authorization.

Do not enter the Step 47A final four-source admission evaluation output phase without explicit user authorization.

Do not treat Step 47B freeze as Step 47 implementation authorization.

Step 47 implementation remains BLOCKED until the Step 47A unblock path is satisfied and explicitly authorized.

19. One-line summary

Step 40A, Step 45, and Step 46A are formally implemented and frozen.
Step 46 remains design-layer frozen, Step 46A remains formally frozen, Step 47, Step 47A, and Step 47B are design-frozen only, Step 47A admission evaluation output remains frozen with all four current candidates remaining NOT_ADMISSIBLE_YET, Step 47B is now frozen as the legal location evidence and accountability baseline, Step 47 implementation remains BLOCKED, and no auto-advance to Step 48 is allowed without explicit user authorization.
