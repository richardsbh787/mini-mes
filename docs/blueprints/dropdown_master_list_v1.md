# Dropdown Master List v1.1

Status: FROZEN TRIAL BASELINE / Factory Dropdown Dictionary

Parent references:

- docs/blueprints/planning_scheduling_master_list_schemas_v1.md
- docs/blueprints/planning_scheduling_capacity_constraint_repair_reject_addendum_v1_1.md

## 1. Purpose & Scope

This file is the single source of truth for all Planning & Scheduling dropdown values in the trial baseline.

Core rule:

- Schema defines which field is a dropdown.
- Dropdown Master List defines exactly which options exist.
- Pages must reference this file.
- Hardcoding dropdown options in HTML / JS / components is forbidden.
- Any new, modified, deprecated, or removed dropdown option must go through Dropdown Master List Change Request first.

This baseline covers Planning & Scheduling trial dropdown values used by:

- Planning Schedule Entry
- LINE OVERVIEW
- Production Schedule Grid
- Capacity / Load Check
- Pending Stock-In List visibility
- Material readiness filters
- Capacity constraint, repair impact, and incoming reject / scrap impact references

This file does not authorize backend implementation, database migration, UI mock change, production execution, inventory update, WO release, WO close, ERP integration, or Step 47 Phase B.

All dropdown values must use:

Display Label | Internal_Code

Internal_Code must be UPPER_SNAKE_CASE with no spaces.

## 2. Governance & Change Control Rule

Pages may not hardcode, modify, or guess dropdown options.

If dropdown values need change:

1. Stop page work.
2. Submit a Dropdown Master List Change Request.
3. Assess Schema, UI, Role Responsibility, and Factory Meaning impact.
4. Approve update by Planning Lead plus relevant domain owner when needed.
5. Update only Dropdown Master List and bump version.
6. Notify page owners.
7. Continue development only after the dropdown source is updated.

Dropdown fields must not silently change meaning inside page code, HTML, JavaScript, component state, mock DOM, or local UI notes.

UI / Filter dropdowns must be marked Non-Persistent / UI Only.

The following separation is frozen:

- plan_status = workflow state machine
- planning_display_label = UI Display / Filter only

planning_display_label cannot drive plan_status logic or trigger automation.

## 3. Dropdown Groups v1.1

### 3.1 plan_status

Classification: Persistent workflow state machine.

Allowed values:

- Draft | DRAFT
- Pending Daily Confirmation | PENDING_CONFIRM
- Confirmed | CONFIRMED
- Changed | CHANGED
- Cancelled | CANCELLED

Boundary:

plan_status remains the workflow state machine and contains only the five options listed above.

planning_display_label must not be mixed into plan_status.

### 3.2 planning_display_label

Classification: Non-Persistent / UI Only.

Allowed values:

- Planned | PLANNED
- Gap | GAP
- Cannot Plan | CANNOT_PLAN
- Holiday | HOLIDAY
- What-if | WHAT_IF
- Buffer | BUFFER

Boundary:

planning_display_label is UI Display / Filter only.

It cannot drive plan_status logic, trigger automation, release work, close work, move schedule, or create official execution state.

### 3.3 planning_action

Classification: Non-Persistent / UI Only.

Allowed values:

- Create / Add | CREATE_ADD
- Search / Find | SEARCH_FIND

Boundary:

This dropdown controls page navigation or action grouping only. It does not authorize write behavior by itself.

### 3.4 planning_search_view

Classification: Non-Persistent / UI Only.

Allowed values:

- LINE OVERVIEW | LINE_OVERVIEW
- Production Schedule Grid | PRODUCTION_SCHEDULE_GRID

Boundary:

These are two views of the same planning readiness problem. They must not become duplicate business analyses or separate hidden logic paths.

### 3.5 line_filter

Classification: Non-Persistent / UI Only.

Allowed values:

- All | ALL
- Line 1 | LINE_1
- Line 2 | LINE_2

Boundary:

Additional lines must come from Line Master reference before being added here.

### 3.6 shop_filter

Classification: Non-Persistent / UI Only.

Allowed values:

- All | ALL
- Assembly Shop | ASSEMBLY_SHOP
- Packing Shop | PACKING_SHOP

Boundary:

Additional values must come from approved Shop / Line Master reference.

### 3.7 model_filter

Classification: Non-Persistent / UI Only.

Allowed values:

- All | ALL

Boundary:

Model-specific values must be sourced from Sales Order / Model Master reference. Free invented model labels are forbidden.

### 3.8 mat_status_filter

Classification: Non-Persistent / UI Only.

Allowed values:

- All | ALL
- Ready | READY
- Not Ready | NOT_READY
- Partial | PARTIAL
- Pending Stock-In | PENDING_STOCK_IN
- IQC Hold | IQC_HOLD
- Store Kitting Pending | STORE_KITTING_PENDING
- Line Receive Pending | LINE_RECEIVE_PENDING

Boundary:

This filter does not override QA, Warehouse, Store Kitting, or Line Receive truth.

### 3.9 quick_risk_filter

Classification: Non-Persistent / UI Only.

Allowed values:

- All | ALL
- Gap | GAP
- Cannot Plan | CANNOT_PLAN
- Material Risk | MATERIAL_RISK
- Release Hold | RELEASE_HOLD
- Capacity Watch | CAPACITY_WATCH
- Holiday | HOLIDAY

Boundary:

This filter is for reading and narrowing visible records only. It cannot create risk truth or release decisions.

### 3.10 production_schedule_grid_status_filter

Classification: Non-Persistent / UI Only.

Allowed values:

- All | ALL
- RUN OK | RUN_OK
- PLANNING GAP | PLANNING_GAP
- PUBLIC HOLIDAY | PUBLIC_HOLIDAY
- CANNOT PLAN | CANNOT_PLAN

Boundary:

This is a grid display filter only. It cannot write schedule truth.

### 3.11 production_schedule_grid_view_filter

Classification: Non-Persistent / UI Only.

Allowed values:

- 5-Day | FIVE_DAY

Boundary:

Future week/month/shift views require a Dropdown Master List Change Request and relevant schema/UI review if they change operator burden or imply additional planning logic.

### 3.12 constraint_reason

Classification: Reference dropdown.

Allowed values:

- Manpower Shortage | MANPOWER_SHORTAGE
- Model Changeover | MODEL_CHANGEOVER
- Jig / Fixture Breakdown | JIG_FIXTURE_BREAKDOWN
- Rack Not Enough | RACK_NOT_ENOUGH
- Waiting Rework Return | WAITING_REWORK_RETURN
- Store Kitting Delay | STORE_KITTING_DELAY
- Material Short | MATERIAL_SHORT
- IQC Hold | IQC_HOLD
- QA Hold | QA_HOLD
- Machine / Tooling Issue | MACHINE_TOOLING_ISSUE
- Line Balance Issue | LINE_BALANCE_ISSUE
- Incoming Reject Impact | INCOMING_REJECT_IMPACT
- Material Scrap Impact | MATERIAL_SCRAP_IMPACT
- Other | OTHER

Boundary:

constraint_reason explains why capacity or schedule readiness is affected. It cannot approve OT, release WO, move line, close WO, or update inventory.

### 3.13 constraint_source

Classification: Reference dropdown.

Allowed values:

- Planning Observation | PLANNING_OBSERVATION
- Production Line | PRODUCTION_LINE
- Store / Warehouse | STORE_WAREHOUSE
- QA / IQC | QA_IQC
- Repair Station | REPAIR_STATION
- Engineering / IE | ENGINEERING_IE
- Supervisor Judgment | SUPERVISOR_JUDGMENT

Boundary:

constraint_source identifies the origin of a read-side signal. It does not transfer source ownership to Planning.

### 3.14 impact_to_plan

Classification: Authoritative enum.

Allowed values:

- No Impact | NO_IMPACT
- Watch Only | WATCH_ONLY
- Delay Risk | DELAY_RISK
- Capacity Reduced | CAPACITY_REDUCED
- Line Stop Risk | LINE_STOP_RISK
- Cannot Run | CANNOT_RUN

Boundary:

impact_to_plan is the authoritative enum for schedule/capacity impact display across Capacity Constraint, Repair Station Impact, and Incoming Reject / Scrap Impact references.

It is advisory for Planning unless a later governed implementation explicitly opens stronger behavior.

### 3.15 impact_level

Classification: Reference dropdown.

Allowed values:

- Low | LOW
- Watch | WATCH
- High | HIGH
- Line Stop | LINE_STOP

Boundary:

impact_level supports display priority. It cannot auto-stop production or auto-change the schedule.

### 3.16 suggested_action

Classification: Advisory / Read-Side Recommendation.

Type:

- Advisory / Read-Side Recommendation
- Non-Executable

Allowed values:

- Keep Plan | KEEP_PLAN
- Split Batch | SPLIT_BATCH
- Use OT | USE_OT
- Move Line | MOVE_LINE
- Move Date | MOVE_DATE
- Review Manpower | REVIEW_MANPOWER
- Hold Plan | HOLD_PLAN

Boundary:

`suggested_action` is advisory only.

It does not:

- approve OT
- automatically move line
- automatically move date
- change plan_status
- release WO
- trigger production execution
- change inventory
- execute Stock-In
- close WO
- override Store, QA, Repair, Warehouse, Production, or Engineering truth

Formal plan adjustment must still go through the proper future path:

- Plan Change Reason Log
- Daily Plan Confirmation
- Create/Add Draft Edit

For v1 trial mock, "Create Plan Change Draft (Future Path)" may be displayed only as a non-executable placeholder.

Hardcoding `suggested_action` values directly in HTML / JS / components remains forbidden.

### 3.17 repair_status

Classification: Reference dropdown.

Allowed values:

- Not Sent | NOT_SENT
- Waiting Repair | WAITING_REPAIR
- Under Repair | UNDER_REPAIR
- Partial Returned | PARTIAL_RETURNED
- Returned | RETURNED
- Scrap Confirmed | SCRAP_CONFIRMED
- Hold | HOLD

Boundary:

repair_status is owned by Repair Station / relevant repair governance. Planning reads it only.

### 3.18 repair_reason

Classification: Reference dropdown.

Allowed values:

- Function Fail | FUNCTION_FAIL
- Cosmetic Defect | COSMETIC_DEFECT
- Assembly Defect | ASSEMBLY_DEFECT
- Missing Part | MISSING_PART
- Wrong Part | WRONG_PART
- Customer Requirement | CUSTOMER_REQUIREMENT
- QA Hold | QA_HOLD
- Other | OTHER

Boundary:

repair_reason helps Planning understand schedule impact. It does not manage repair work.

### 3.19 source_stage

Classification: Reference dropdown.

Allowed values:

- Incoming IQC | INCOMING_IQC
- Store Handling | STORE_HANDLING
- Production Use | PRODUCTION_USE
- Repair Station | REPAIR_STATION
- QA / FQA | QA_FQA
- Other | OTHER

Boundary:

source_stage identifies where reject/scrap impact originated. Planning reads it only.

### 3.20 reject_or_scrap_reason

Classification: Reference dropdown.

Allowed values:

- Incoming Reject | INCOMING_REJECT
- Material Damage | MATERIAL_DAMAGE
- Wrong Material | WRONG_MATERIAL
- Qty Shortage | QTY_SHORTAGE
- Label / Packing Issue | LABEL_PACKING_ISSUE
- Process Damage | PROCESS_DAMAGE
- Repair Scrap | REPAIR_SCRAP
- QA Reject | QA_REJECT
- Other | OTHER

Boundary:

reject_or_scrap_reason does not approve reject, scrap, or replacement. Planning only sees whether rejected or scrapped material affects schedule readiness.

### 3.21 planning_version

Classification: Reference dropdown.

Allowed values:

- Trial Plan v1 | TRIAL_PLAN_V1
- Trial Plan v2 | TRIAL_PLAN_V2

Boundary:

planning_version labels trial planning versions. It does not imply production approval.

## 4. Version & Deprecation Policy

Dropdown Master List v1.1 is the frozen trial baseline.

v1.1 update record:

- DCR-2026-001-SUGGESTED-ACTION added `suggested_action` as an advisory-only dropdown for Planning & Scheduling -> Search / Find -> Capacity / Load Check.
- `suggested_action` is non-executable and cannot approve OT, move line, move date, change plan_status, release WO, trigger production, update inventory, execute Stock-In, close WO, or override Store / QA / Repair / Warehouse / Production / Engineering truth.

Version rules:

- Any option addition requires a Dropdown Master List Change Request.
- Any option label change requires a Dropdown Master List Change Request.
- Any Internal_Code change requires impact review because persisted or referenced records may depend on the code.
- Any deprecation must keep historical readability.
- Removed options must not disappear from historical records without a migration/reconciliation decision.

Deprecation format:

- keep Display Label | Internal_Code
- mark status as Deprecated
- record replacement option if applicable
- record effective date if applicable
- notify page owners before UI removal

Hard rule:

Pages must not hardcode dropdown options in HTML / JS / components. They must reference this Dropdown Master List as the source of truth.

If the dropdown source is not yet implemented, the mock may display static values only as a visual representation of this frozen list, not as an independent page-owned option set.

## Frozen Boundary

Dropdown Master List v1.1 is frozen as the official trial dropdown dictionary for Planning & Scheduling.

This freeze does not authorize:

- backend implementation
- database migration
- UI mock change
- production execution
- inventory update
- WO release
- WO close
- ERP integration
- Step 47 Phase B
