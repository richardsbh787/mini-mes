Mini-MES Handoff v2.10

Updated after Step 47B freeze-record cleanup
Date: 2026-03-28

1. Frozen mainline snapshot

Current frozen mainline now includes:

Steps 1-44 frozen

Step 40A implementation frozen

Step 45 implementation frozen

Step 46A implementation frozen

Step 47 design-freeze baseline

Step 47A frozen admitted source event baseline

Step 47B frozen legal location evidence & accountability baseline

FG_RECEIVE Location Master Physical Schema Baseline frozen as design-layer schema baseline only

FG_RECEIVE Event Truth Surface Baseline frozen as design-layer event-truth baseline only

FG_RECEIVE Event Truth Physical Schema Baseline frozen as design-layer physical-schema baseline only

Step 40A is no longer design-only.
It has passed main review, Qinran final review, commit, and push.

Step 45 is implemented and frozen.

Step 46A is implemented and frozen.

Step 47 is design-freeze only.
Step 47 implementation remains BLOCKED.

Step 47A is frozen.
All four current candidate source-event types are NOT_ADMISSIBLE_YET.
Step 47 admitted source list remains effectively EMPTY.
location_code remains the main unblock key.
Any future repaired FG_RECEIVE source must still pass full Step 47A admissibility re-evaluation before any unblock decision.

Step 47B is frozen as Step 47B Task Card v2.1 = Design Freeze Baseline.

FG_RECEIVE Location Master Physical Schema Baseline is frozen as a design-layer schema baseline only.
It is not implementation authorization.

FG_RECEIVE Event Truth Surface Baseline is frozen as a design-layer event-truth baseline only.
It is not implementation authorization.

FG_RECEIVE Event Truth Physical Schema Baseline is frozen as a design-layer physical-schema baseline only.
It is not implementation authorization.

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
Step 47B - Legal Location Evidence & Accountability Baseline

Status: Design Freeze Baseline - formally frozen

Frozen task card baseline: Step 47B Task Card v2.1

Locked baseline statuses

Step 46A = Frozen
Inventory Truth Semantic Baseline

Step 47 = Design Freeze
Inventory Position Truth Baseline

Step 47A = Frozen
Admitted Source Event Baseline
Result: all 4 candidate sources are NOT_ADMISSIBLE_YET

Step 47B = Frozen
Legal Location Evidence & Accountability Baseline
Official frozen draft: Step 47B Task Card v2.1 = Design Freeze Baseline

Step 47 current status

Step 47 implementation remains BLOCKED.

Step 47 admitted source list remains effectively EMPTY.

location_code remains the main unblock key.

Any future source that adds evidence must still re-run the full Step 47A six-point admission evaluation.

Step 47B positioning

Step 47B is a pre-unblock design step for Step 47.

Step 47B is NOT Step 47 implementation.

Step 47B is NOT position truth write design.

Step 47B is NOT the discipline engine.

Step 47B is NOT a runtime accountability engine.

Step 47B is NOT config-table or persistence-object design.

Step 47B three iron laws

1. complete responsibility chain does NOT equal legal location evidence established

2. responsibility chain cannot replace any Step 47A admission requirement

3. Step 47B defines rules only and does not implement runtime objects

Hard boundaries

No new persistent table.

No new field.

No new truth surface.

No StockLedger column expansion.

No Step 46A semantic change.

Do not enter the discipline engine.

Do not enter Step 47 implementation.

Do not define any write action.

Do not use convenience inference for location_code.

Legal location evidence carry-forward

Legal Location Evidence still strictly follows the Step 47A six-point admission standard:

1. explicit location_code
2. resolvable item identity
3. explicit stock_bucket
4. explicit stock_uom
5. signed delta or unambiguous derivation rule
6. trace identity

Even if owner_role, duty_person, performed_by, and approved_by are complete, if explicit location_code is still missing, ambiguous, indirect, or inferred, legal location evidence is still NOT established and Step 47 remains BLOCKED.

Step 47B relationship to Step 47A

Step 47B does not modify the Step 47A six admission standards.

The accountability chain must not replace explicit evidence such as location_code, stock_bucket, stock_uom, delta rule, or trace identity.

Any future repaired source must still re-run the full Step 47A six-point admission evaluation.

FG_RECEIVE first frozen wording

FG_RECEIVE first is only a priority evaluation target.

FG_RECEIVE is NOT automatic admission.

FG_RECEIVE cannot board first and ticket later.

Any future location_code or other evidence repair must be handled in a separate future step.

Repair Gap frozen wording

If upstream frozen truth does not explicitly provide owner_role, duty_person, performed_by, or approved_by fields, Step 47B may only mark this as Repair Gap.

Do not backfill that gap in this step.

Step 47B acceptance criteria baseline

G01 - Step 47B Task Card v2.1 is the formally frozen Design Freeze Baseline.

G02 - Step 47 implementation remains BLOCKED; Step 47B does not authorize or start implementation.

G03 - Step 47B is frozen only as a legal-unblock prerequisite design step and not as Step 47 implementation, position truth write design, discipline engine, runtime accountability engine, or config-table / persistence-object design.

G04 - The three Step 47B core laws are frozen: accountability chain does not equal legal location evidence; accountability chain cannot replace any Step 47A admission standard; Step 47B defines rules only and materializes no runtime objects.

G05 - Step 47B hard boundaries are frozen: no new persistent table, no new field, no new truth surface, no StockLedger column expansion, no Step 46A semantic change, no discipline-engine entry, no Step 47 implementation entry, no write action, and no convenience inference for location_code.

G06 - Step 47B does not modify the Step 47A six admission standards, and any future repaired source must re-run the full Step 47A six-point admission evaluation before any unblock decision.

G07 - Legal location evidence still follows the Step 47A six-point admission standard only, and the accountability chain cannot replace explicit evidence requirements including location_code, stock_bucket, stock_uom, signed delta rule, and trace identity.

G08 - FG_RECEIVE-first wording is frozen as priority evaluation only and not automatic admission.

G09 - If upstream frozen truth lacks explicit owner_role, duty_person, performed_by, or approved_by fields, Step 47B may mark only a Repair Gap and must not patch or implement that gap in this step.

G10 - Any future evidence repair needed to satisfy Step 47A or Step 47 must be handled in a separate future step; Step 47B itself defines no write action and no runtime materialization path.

5. Newly frozen design-layer step
FG_RECEIVE Location Master Physical Schema Baseline

Status: Design-layer schema baseline - formally frozen

Boundary

This step is:

design baseline

physical schema baseline

This step is not:

migration authorization

ORM authorization

implementation authorization

Step 47 unblock authorization

admitted source activation

Admitted truth surfaces

Only these 3 physical truth surfaces are admitted:

physical_location

location_label

label_location_mapping

Minimum field skeleton

physical_location

id

location_code

location_name

status

created_at

updated_at

deactivated_at nullable

location_label

id

label_token

label_type

status

created_at

updated_at

retired_at nullable

label_location_mapping

id

location_label_id

physical_location_id

status

effective_from

effective_to nullable

created_at

updated_at

Core constraints

physical_location.location_code must be unique

location_label.label_token must be unique

mapping must reference real label and real location

effective_from required

if effective_to is not null, then effective_to > effective_from

same location_label_id must not have overlapping validity windows

remap must be non-destructive:

close old mapping

create new mapping

mapping history must remain readable

Future FG_RECEIVE runtime legal resolution boundary

Future FG_RECEIVE runtime may resolve location only through:

input location_label_token

unique matching location_label

location_label.status = ACTIVE

unique event-time valid label_location_mapping

label_location_mapping.status = ACTIVE

mapped physical_location.status = ACTIVE

return unique physical_location.location_code

Any of the following must fail hard with no fallback:

label not found

label inactive

mapping not found

multiple valid mappings at same time

mapping inactive

mapped location inactive

event-time outside validity window

Hard prohibitions

Do not derive or backfill location truth from:

board assignment

WO header metadata

BOM / routing metadata

station habit

last-used location

default location

operator memory

manual typing fallback

dropdown fallback

post-event repair

Locked status line

Step 47 implementation remains BLOCKED.

FG_RECEIVE is still not auto-admitted.

Any future repaired FG_RECEIVE source must still re-run full Step 47A admissibility evaluation.

6. Newly frozen design-layer step
FG_RECEIVE Event Truth Surface Baseline

Status: Design-layer event-truth baseline - formally frozen

Hard boundary

This step is design freeze only.

It is NOT implementation authorization.

Step 47 implementation remains BLOCKED.

FG_RECEIVE remains NOT auto-admitted.

Frozen core definition

A legally successful FG_RECEIVE event must atomically carry one and only one final location binding truth, with the minimum surface:

bound_location_code

bound_from_resolution_attempt_id

location_evidence_snapshot_ref

location_bound_at

Locked rules

1. A successful FG_RECEIVE event is not legally complete if any of the 4 fields above is missing.

2. One FG_RECEIVE event may carry only one final location binding truth.

3. Event truth may come only from this event's successful resolution attempt.

4. Failed attempts must remain only in failed-attempt / resolution-trace surfaces and must not enter final bound truth.

5. Later master remap / deactivate / retire must not rewrite old event truth.

6. Event success truth write and event commit must be atomic; no async backfill, no read-time side write.

Prior frozen boundaries preserved

location legality still comes only from event-time resolution

resolution failure still means FG_RECEIVE does not legally stand

trace != truth

maintenance audit != truth

correction still requires independent correction / reversal path

no re-resolve to silently change old bound events

Step 47 remains blocked

FG_RECEIVE remains not auto-admitted

Non-blocking note

The semantic boundary between bound_from_resolution_attempt_id and location_evidence_snapshot_ref is not yet further split at schema level; future schema baseline must explicitly decide whether these remain separate or can be structurally merged. This note must not weaken the frozen event-truth separation.

7. Newly frozen design-layer step
FG_RECEIVE Event Truth Physical Schema Baseline

Status: Design-layer physical-schema baseline - formally frozen

Boundary

This patch is handoff-only.

This step preserves the already-frozen FG_RECEIVE Event Truth Surface Baseline semantics and adds the physical-schema-layer minimum persistence skeleton only.

Minimum persisted object

FG_RECEIVE event truth is represented by one dedicated, minimum persisted final-truth object.

Semantic grain: one FG_RECEIVE event may have at most one final event-truth record.

Successful-resolution-only admission

Only successful resolution may enter final truth.

Failed / ambiguous / unresolved / candidate-level outcomes remain trace-only and must not occupy final-truth state.

Four frozen minimum fields

The minimum final-truth persistence skeleton must preserve:

bound_location_code

bound_from_resolution_attempt_id

location_evidence_snapshot_ref

location_bound_at

Attempt and evidence separation

bound_from_resolution_attempt_id and location_evidence_snapshot_ref must remain semantically distinct.

They may coexist in the same minimum persisted final-truth object.

They must not be merged into one mixed field, one ambiguous reference, or one combined JSON-like slot.

Boundary firewall

trace != truth

master != event truth

later master changes cannot rewrite old event truth

repair must use independent correction path

no silent re-resolve

One-final-binding rule

For one FG_RECEIVE event, final event truth is 0 or 1 only.

No multi-final-truth fan-out.

No second final bind may silently replace the first.

New frozen addendum A

Future correction path must not reuse, occupy, or masquerade as this final-truth object.

If correction is needed in the future, it must go through an independent correction path / independent correction surface, not by taking over this object and not by weakening the one-final-truth boundary.

New frozen addendum B

location_evidence_snapshot_ref must resolve to an immutable evidence snapshot body.

Future implementation must not treat it as a mutable live pointer and must not allow in-place overwrite that changes the historical evidence basis of an already-bound event truth.

Explicit non-scope

This step does NOT authorize:

implementation

table creation

migration

ORM model

service

router

tests

Step 47 admissibility release

admitted source activation

correction-path implementation

semantic changes to the already-frozen FG_RECEIVE Event Truth Surface Baseline

8. Governance baseline normalization now frozen

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

9. Review / control discipline remains locked

Still in force:

double-layer review system

Qingchen main review

Qinran final review

single-step advancement

no step jump before freeze / permission

Ontology + Guard V2 + GUARD MODE + Operator Minimal Action Rule

T-1 / T0 / T+1 truth audit

S-1 / S0 / S+1 step audit

10. Current locked status

Step 45 is implemented and frozen.

Step 46A is implemented and frozen.

Step 47 is design-frozen only.

Step 47A is frozen as the admitted source event baseline.

Step 47B is frozen as the legal location evidence & accountability baseline.

FG_RECEIVE Location Master Physical Schema Baseline is frozen as a design-layer schema baseline only.

FG_RECEIVE Event Truth Surface Baseline is frozen as a design-layer event-truth baseline only.

FG_RECEIVE Event Truth Physical Schema Baseline is frozen as a design-layer physical-schema baseline only.

Important

Do not auto-advance beyond the current locked task without explicit user authorization.

Do not auto-advance to Step 47 implementation without explicit user authorization.

Do not auto-advance to Step 48 without explicit user authorization.

Do not treat Step 47B freeze as Step 47 implementation authorization.

Step 47 implementation remains BLOCKED.

Step 47 admitted source list remains effectively EMPTY.

FG_RECEIVE is still not auto-admitted.

location_code remains the main unblock key.

Any future repaired FG_RECEIVE source must still pass full Step 47A admissibility re-evaluation before any unblock decision.

11. One-line summary

Step 40A, Step 45, and Step 46A remain formally implemented and frozen.
Step 47 remains design-frozen and BLOCKED, Step 47A remains frozen with all four current candidates still NOT_ADMISSIBLE_YET and the admitted source list effectively EMPTY, Step 47B remains frozen as the legal location evidence & accountability baseline under Task Card v2.1, and FG_RECEIVE now also has frozen design-layer baselines for the Location Master Physical Schema, the Event Truth Surface, and the Event Truth Physical Schema while remaining NOT auto-admitted.
