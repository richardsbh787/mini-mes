# Planning & Scheduling — Capacity Constraint / Repair / Reject Impact Addendum v1.1

Status: FROZEN TRIAL ADDENDUM / extends Planning & Scheduling Master List Schemas v1

Parent baseline:

docs/blueprints/planning_scheduling_master_list_schemas_v1.md

## Purpose

This addendum extends Capacity / Load Check read-side visibility. It adds lightweight reference fields for capacity constraint, downtime reason, repair station impact, incoming reject impact, and material scrap impact.

It does not replace or rewrite the parent Master List Schemas v1.

## Core Boundary

Planning only reads the impact.

Planning does not own the source event.

Source ownership remains:

- Production owns actual downtime / line issue records.
- Repair Station owns repair / rework return records.
- QA / IQC owns incoming reject decisions.
- Store / Production / QA owns material scrap records depending on where scrap occurs.
- Planning only displays schedule and capacity impact.

In v1 trial mock, these impact records are manually logged by respective PICs or auto-generated from sample logs for visibility. Planning treats them as read-side advisory inputs only.

## Capacity Constraint Reference

Used by:

Planning & Scheduling -> Search / Find -> Capacity / Load Check

Fields:

- capacity_constraint_id
- schedule_entry_no
- plan_date
- line_code
- line_name
- wo_no
- constraint_reason
- constraint_source
- impact_to_plan
- impact_level
- estimated_lost_hours
- affected_qty
- owner_pic
- expected_recovery_time
- remark

constraint_reason dropdown:

- Manpower Shortage
- Model Changeover
- Jig / Fixture Breakdown
- Rack Not Enough
- Waiting Rework Return
- Store Kitting Delay
- Material Short
- IQC Hold
- QA Hold
- Machine / Tooling Issue
- Line Balance Issue
- Incoming Reject Impact
- Material Scrap Impact
- Other

constraint_source dropdown:

- Planning Observation
- Production Line
- Store / Warehouse
- QA / IQC
- Repair Station
- Engineering / IE
- Supervisor Judgment

impact_to_plan dropdown:

- No Impact
- Watch Only
- Delay Risk
- Capacity Reduced
- Line Stop Risk
- Cannot Run

impact_level dropdown:

- Low
- Watch
- High
- Line Stop

Boundary:

Capacity Constraint Reference explains why capacity is reduced. It cannot approve OT, release WO, move line, close WO, or update inventory.

## Repair Station Impact Reference

Used by Planning only as read-side visibility.

Fields:

- repair_impact_id
- wo_no
- model_no
- model_description
- repair_station_ref
- sent_to_repair_qty
- repaired_qty
- waiting_repair_qty
- scrap_qty_from_repair
- expected_return_date
- repair_reason
- repair_status
- impact_to_plan
- owner_pic
- remark

repair_status dropdown:

- Not Sent
- Waiting Repair
- Under Repair
- Partial Returned
- Returned
- Scrap Confirmed
- Hold

repair_reason dropdown:

- Function Fail
- Cosmetic Defect
- Assembly Defect
- Missing Part
- Wrong Part
- Customer Requirement
- QA Hold
- Other

impact_to_plan dropdown:

- No Impact
- Watch Only
- Delay Risk
- Capacity Reduced
- Line Stop Risk
- Cannot Run

Boundary:

Repair Station Impact Reference does not manage repair work. It only tells Planning whether missing repaired parts may affect schedule, WO completion, or Pending Stock-In.

## Incoming Reject / Scrap Impact Reference

Used by Planning only as read-side visibility.

Fields:

- reject_scrap_impact_id
- wo_no
- model_no
- model_description
- material_item_code
- material_item_name
- source_stage
- rejected_qty
- scrap_qty
- usable_qty
- replacement_needed_flag
- expected_replacement_date
- reject_or_scrap_reason
- impact_to_plan
- owner_pic
- remark

source_stage dropdown:

- Incoming IQC
- Store Handling
- Production Use
- Repair Station
- QA / FQA
- Other

reject_or_scrap_reason dropdown:

- Incoming Reject
- Material Damage
- Wrong Material
- Qty Shortage
- Label / Packing Issue
- Process Damage
- Repair Scrap
- QA Reject
- Other

impact_to_plan dropdown:

- No Impact
- Watch Only
- Delay Risk
- Capacity Reduced
- Line Stop Risk
- Cannot Run

Boundary:

Planning cannot decide incoming reject, scrap, or replacement approval. Planning only sees whether rejected or scrapped material affects schedule readiness.

## Page-to-Schema Alignment

Capacity / Load Check reads from:

- Planning Schedule Entry
- ST / IE Capacity Reference
- Capacity / Load Schema
- Capacity Constraint Reference
- Repair Station Impact Reference
- Incoming Reject / Scrap Impact Reference
- Material Readiness Reference
- Kitting / Line Handover Reference

Capacity / Load Check writes to:

- no official execution data
- trial what-if adjustment only, if explicitly opened

LINE OVERVIEW may display:

- Capacity Constraint summary
- Repair waiting impact
- Incoming reject / scrap risk
- impact_to_plan
- impact_level

Production Schedule Grid may display:

- Watch / High / Line Stop indicator
- Short reason label only

Production Schedule Grid must not become a downtime entry page.

## Forbidden Actions

Planning must not:

- create official repair records
- approve repair completion
- approve incoming reject
- approve scrap
- issue replacement material
- execute Stock In
- close WO
- release WO
- approve OT
- overwrite QA / Store / Production truth
- convert downtime reason into automatic schedule change

## Factory Meaning

This addendum helps Planner and supervisor understand why the schedule cannot run as planned.

Examples:

- Line has manpower, but jig is broken.
- Material arrived, but incoming IQC rejected key parts.
- Store said kitted, but rack is not enough.
- WO is almost complete, but last pieces are still waiting at repair station.
- Some parts were scrapped, replacement is not ready.

Planning needs to see these impacts, but the real action still belongs to the correct department.

## Factory Usability Check

This addendum must stay dropdown-based and light.

Capacity Check should not become a long downtime report.

For trial UI, show only:

- Reason
- impact_to_plan
- impact_level
- Lost Hours / Affected Qty
- Owner / PIC
- Expected Recovery
- Remark

If more details are needed, they belong to Production / Repair / QA / Store modules later.

## Frozen Boundary

This addendum extends Capacity / Load Check read-side visibility only.

It does not authorize:

- backend implementation
- database migration
- UI mock change
- production execution
- inventory update
- WO release
- WO close
- ERP integration
- Step 47 Phase B
