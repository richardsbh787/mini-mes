# Planning & Scheduling — Master List Schemas v1.2

Status: FROZEN TRIAL BASELINE / Planning & Scheduling Master List Schemas v1

Authority layer: Trial schema baseline for Planning & Scheduling master lists and mock-stage page alignment.

This document freezes the Planning & Scheduling master-list field baseline for the trial mock and downstream design discussion. It does not authorize backend implementation, database migration, ERP integration, production execution, inventory update, WO release, WO close, or Step 47 Phase B.

## 1. Purpose

Planning & Scheduling needs one clear field baseline so factory users, planners, supervisors, Engineering / IE, Store, QA, and management all read the same planning meaning.

This baseline defines:

- the official trial input path for Planning Schedule Entry
- the master-list schemas that Planning pages may read or display
- the dropdown values that may appear in the trial UI
- the page-to-schema alignment for Create / Add, Search / Find, LINE OVERVIEW, Production Schedule Grid, Pending Stock-In List, and related planning surfaces
- the calculation and derived-field boundaries for ST, UPH, HC, material readiness, capacity/load, and advisory checks
- role responsibility boundaries
- forbidden field and fake-field rules

The goal is a simple, factory-readable Planning & Scheduling baseline that prevents duplicate fields, hidden renamed fields, uncontrolled planning logic, and accidental promotion of advisory views into execution authority.

## 2. Scope

This baseline covers Planning & Scheduling trial master-list schemas only.

In scope:

- Planning Schedule Entry
- Planning search/read views
- LINE OVERVIEW
- Production Schedule Grid
- Pending Stock-In List
- material readiness reference fields used by Planning
- capacity/load advisory fields used by Planning
- Engineering / IE reference fields read by Planning
- Store / Kitting / Line Receive readiness references used by Planning
- replacement candidate and cannot-plan advisory fields used by Planning
- trial dropdown values for the above surfaces

Create / Add is the only official Planning Schedule Entry input path.

Search / Find pages are read-only views or explicitly marked what-if workspaces. A Search / Find surface must not silently become an official input path.

## 3. Explicit Non-Scope

This freeze does not define or authorize:

- backend implementation
- database migration
- ERP integration
- production execution
- inventory update
- Stock In execution
- QA release execution
- Store transaction execution
- Line Receive execution
- WO release
- WO close
- production reporting
- barcode scan flow
- auto-scheduling engine
- auto-planning
- auto-release
- auto-move-line
- auto-replacement
- auto-approve OT
- validation/save logic
- localStorage or browser persistence
- Step 47 Phase B

This baseline is a schema and page-alignment freeze only. It freezes what Planning may show, read, or ask for during trial design. It does not open any execution write path.

## 4. Master Schemas

### 4.1 Planning Schedule Entry

Official input path: Planning & Scheduling -> Create / Add -> Planning Schedule Entry.

This is the only official Planning Schedule Entry input path.

| Field | Meaning | Owner / Source | Required | Notes |
| --- | --- | --- | --- | --- |
| schedule_entry_no | Trial schedule entry identifier | Planning | Yes | Unique trial reference for the planned slot entry. |
| planning_version | Planning version label | Planning | Yes | Example: Trial Plan v1, Trial Plan v2. Does not imply production approval. |
| schedule_date | Planned production date | Planning | Yes | Date only. Public holidays and non-working days remain visible as no-production slots. |
| line_code | Production line code | Planning / Line Master reference | Yes | Must reference a known line. |
| line_name | Production line display name | Line Master reference | Yes | Display-only name, not free text if line_code exists. |
| shift_code | Shift code | Planning / Shift Calendar reference | Trial optional | If not used in trial, day-level planning remains the baseline. |
| work_order_no | Work order number | WO / Order reference | Yes for planned WO slot | Must not create or release a WO by itself. |
| sales_order_no | Sales order number | Sales Order reference | Read reference | Used for traceability only. |
| order_item_no | Sales order item number | Sales Order reference | Read reference | Used for traceability only. |
| model_no | Model number | Sales Order / Model Master reference | Yes | Planning reads this value; Planning does not maintain Model Master. |
| customer_part_no | Customer part number | Sales Order / Customer Part reference | Trial optional | Display/reference field only. |
| process_code | Process code | Routing / Engineering reference | Yes | Example: Assembly, Packing, PP-PSU, Sub assembly. |
| process_name | Process display name | Routing / Engineering reference | Yes | Display text for operators and supervisors. |
| wo_qty | Work order quantity | WO reference | Yes | Not editable from schedule grid. |
| plan_qty | Planned quantity for this slot | Planning | Yes | Must not exceed governed trial assumptions without review. |
| plan_qty_total_for_wo | Total planned quantity across visible slots | Derived / Planning view | Read-only | Display only. |
| btg_qty | Balance-to-go quantity | Derived / Planning view | Read-only | Advisory display; source formula must be separately implemented if backend opens. |
| day_seq | Day number in multi-day spread | Derived / Planning view | Read-only | Example: Day 1 / 3. |
| day_count | Total days in spread | Derived / Planning view | Read-only | Used with day_seq. |
| planned_hours | Planned hours for slot | Derived from Planning qty and ST/UPH references | Read-only/advisory | Advisory unless separately governed. |
| total_work_hours | Total work hours for WO or planned spread | Derived | Read-only/advisory | Must not be treated as payroll or legal capacity truth. |
| hc_required | Headcount required | Engineering / IE reference or derived advisory | Read-only/advisory | Planning reads; Planning does not own HC rule. |
| material_ready_state | Material readiness state | Material readiness reference | Read-only | Must follow Material Ready for Production Start rule below. |
| release_decision_state | Release decision signal | Work Order Release reference | Read-only | Planning display cannot approve release. |
| capacity_load_state | Capacity/load advisory state | Derived advisory | Read-only/advisory | Cannot auto-block, auto-release, auto-move-line, or auto-approve OT. |
| planning_status | Planning slot status | Planning | Yes | Draft / Planned / Gap / Cannot Plan / Holiday / What-if. |
| cannot_plan_reason | Cannot-plan explanation | Planning / readiness references | Required when cannot plan | Must be operational language, not vague status-only wording. |
| replacement_candidate_wo | Candidate replacement WO | Planning advisory | Optional | Advisory only; no auto-replacement. |
| required_action | Next human action | Planning advisory | Required when blocked/gap | Example: Replace this slot with runnable WO. |
| follow_up_owner | Follow-up owner | Planning / role assignment | Required when blocked/gap | Role/person display only; does not grant authority. |
| mock_only_note | Trial/mock boundary note | UI/documentation | Optional | Must mark what-if or static trial behavior where relevant. |

### 4.2 Production Line Master Reference

Planning may read this reference to populate line filters, line labels, and line-grid rows.

| Field | Meaning | Owner / Source | Notes |
| --- | --- | --- | --- |
| line_code | Line identifier | Production / Master Data | Stable code. |
| line_name | Line display name | Production / Master Data | Example: Line 1, Line 2. |
| shop_code | Shop/factory area code | Production / Master Data | Used by LINE OVERVIEW filters. |
| shop_name | Shop/factory display name | Production / Master Data | Display only. |
| line_type | Line type | Production / Engineering reference | Example: Assembly, Packing, Mixed. |
| active_flag | Whether line is available for planning display | Production / Master Data | Hidden lines must not be silently used. |

Line labels in the grid should stay simple. Extra process text should live inside the planned WO card when needed, not under the line label.

### 4.3 Engineering / IE Capacity Reference

Planning reads these references but does not own or maintain them.

| Field | Meaning | Owner / Source | Notes |
| --- | --- | --- | --- |
| model_no | Model number | Engineering / Model Master | Reference key. |
| process_code | Process code | Engineering / Routing / IE | Reference key. |
| st_minutes | Standard time | Engineering / IE Master Data | Planning reads only. |
| uph | Units per hour | Engineering / IE Master Data | Planning reads only. |
| hc_standard | Standard headcount | Engineering / IE Master Data | Planning reads only. |
| effective_from | Effective date | Engineering / IE Master Data | Required when versions exist. |
| effective_to | End date | Engineering / IE Master Data | Optional. |
| reference_status | Reference state | Engineering / IE Master Data | Draft / Active / Obsolete. Planning must not silently use obsolete records. |

ST / UPH / HC are Engineering / IE Master Data references. Planning reads them but does not own or maintain them.

### 4.4 Material Readiness Reference

Material Ready for Production Start requires all of the following:

1. physical availability
2. IQC pass or formal exemption
3. release for production
4. Store Kitting confirmation
5. Line Receive confirmation

| Field | Meaning | Owner / Source | Notes |
| --- | --- | --- | --- |
| work_order_no | WO reference | WO / Material readiness view | Read key. |
| material_physical_available | Physical material available | Store / Inventory reference | Must be true for ready. |
| iqc_state | IQC state | QA / IQC reference | Pass or formal exemption required. |
| iqc_exemption_ref | Formal exemption reference | QA | Required if IQC not pass but exempted. |
| production_release_state | Released for production | Authorized release source | Must be released for ready. |
| store_kitting_state | Store kitting state | Store | Confirmed required. |
| line_receive_state | Line receive state | Line / Production | Confirmed required. |
| material_ready_for_start | Combined readiness signal | Derived read surface | True only when all required conditions are met. |
| material_ready_reason | Human-readable reason | Derived read surface | Must show missing condition when not ready. |

Planning may display material readiness but cannot override QA, Warehouse, Store Kitting, or Line Receive status.

### 4.5 Pending Stock-In List

Pending Stock-In List is a planning visibility surface only.

| Field | Meaning | Owner / Source | Notes |
| --- | --- | --- | --- |
| pending_stock_in_no | Pending stock-in reference | Warehouse / purchasing reference | Display key. |
| supplier_or_source | Supplier/source | Purchasing / Warehouse reference | Display only. |
| item_code | Material item code | Item Master reference | Display key. |
| item_name | Material item display name | Item Master reference | Display only. |
| expected_qty | Expected quantity | Purchasing / Warehouse reference | Display only. |
| expected_date | Expected date | Purchasing / Warehouse reference | Advisory. |
| warehouse_status | Warehouse receiving state | Warehouse | Planning cannot override. |
| qa_status | QA/IQC state | QA | Planning cannot override. |
| usable_for_planning | Whether likely usable for planning | Derived advisory | Cannot execute Stock In. |
| blocking_note | Why not usable | Derived/read note | Must be visible when not usable. |

Pending Stock-In List cannot execute Stock In or override QA / Warehouse status.

### 4.6 Replacement Candidate Advisory

Replacement candidate data is advisory only.

| Field | Meaning | Owner / Source | Notes |
| --- | --- | --- | --- |
| blocked_work_order_no | Blocked WO | Planning / readiness view | Must not appear as planned work in grid. |
| blocked_qty | Blocked WO quantity | WO reference | Display only. |
| blocked_model_no | Blocked model | WO / Sales Order reference | Display only. |
| blocked_customer_part_no | Blocked customer part | Sales Order reference | Display only. |
| cannot_plan_reason | Cannot-plan reason | Planning / readiness references | Must be clear and actionable. |
| replacement_work_order_no | Candidate replacement WO | Planning advisory | No auto-replacement. |
| replacement_model_no | Replacement model | WO / Sales Order reference | Display only. |
| replacement_total_hours | Replacement total hours | Derived advisory | Display only. |
| required_action | Required planner action | Planning advisory | Example: Replace this slot with runnable WO. |
| follow_up_owner | Follow-up owner | Planning / role display | Display only. |

Blocked WOs must not be shown as planned cards in the main Production Schedule Grid. They may appear only in cannot-plan / replacement advisory areas.

### 4.7 Holiday / Calendar Reference

| Field | Meaning | Owner / Source | Notes |
| --- | --- | --- | --- |
| calendar_date | Date | Calendar reference | Display key. |
| workday_flag | Whether production workday | Calendar owner | False for public holiday/non-working day. |
| holiday_name | Holiday name | Calendar owner | Example: PUBLIC HOLIDAY. |
| production_allowed_flag | Whether production allowed | Calendar owner | Trial display only unless execution governance is opened. |
| note | Display note | Calendar owner | Example: No Production. |

Public holidays must remain visible and clearly skipped in the grid.

## 5. Dropdown Values

### 5.1 Planning Action / Sub-Module

- Create / Add
- Search / Find

Search / Find visible Planning views:

- LINE OVERVIEW
- Production Schedule Grid

No third hidden Schedule Grid page is opened by this baseline.

### 5.2 Line Filter

- All
- Line 1
- Line 2
- Additional lines may be added only from Line Master reference.

### 5.3 Shop Filter

- All
- Assembly Shop
- Packing Shop
- Other values only from approved Shop / Line Master reference.

### 5.4 Model Filter

- All
- Model values must come from Sales Order / Model Master reference.
- Free invented model labels are forbidden.

### 5.5 MatStatus / Material Status Filter

- All
- Ready
- Not Ready
- Partial
- Pending Stock-In
- IQC Hold
- Store Kitting Pending
- Line Receive Pending

### 5.6 QuickRisk Filter

- All
- Gap
- Cannot Plan
- Material Risk
- Release Hold
- Capacity Watch
- Holiday

### 5.7 Production Schedule Grid Status Filter

- All
- RUN OK
- PLANNING GAP
- PUBLIC HOLIDAY
- CANNOT PLAN

### 5.8 Production Schedule Grid View Filter

- 5-Day

Future week/month/shift views require separate design approval if they change operator burden or imply additional planning logic.

### 5.9 Planning Status

- Draft
- Planned
- Gap
- Cannot Plan
- Holiday
- What-if

What-if must be visibly marked when used. It must not be confused with official schedule entry.

## 6. Page-to-Schema Alignment

### 6.1 Create / Add -> Planning Schedule Entry

Create / Add is the only official Planning Schedule Entry input path.

It may create or edit trial schedule-entry records only if a later implementation card explicitly opens that behavior. In this freeze, it is schema baseline only.

The Create / Add page may use:

- Planning Schedule Entry
- Production Line Master Reference
- Engineering / IE Capacity Reference
- Material Readiness Reference
- Holiday / Calendar Reference

It must not execute production, release WO, close WO, update inventory, or perform Stock In.

### 6.2 Search / Find -> LINE OVERVIEW

LINE OVERVIEW is a read-side supervisor/planner view.

It may show:

- line/item list
- selected line band
- planning table
- Expand A / Expand B details
- material readiness references
- release decision references
- capacity/load advisory values
- cannot-plan or risk indicators

It must not become an official schedule-entry input path unless explicitly changed by later governance.

### 6.3 Search / Find -> Production Schedule Grid

Production Schedule Grid is read-only.

It may show:

- dates across the top
- lines on the left
- WO / gap / holiday / cannot-plan status inside each slot
- runnable WO card examples
- public holiday / no production slots
- cannot-plan / replacement advisory panel
- trial OT reference only

It must not:

- auto-plan
- auto-release
- auto-move
- auto-replace
- auto-approve OT
- execute schedule changes
- update WO or inventory truth

### 6.4 Pending Stock-In List

Pending Stock-In List is a visibility surface only.

It may show expected material, warehouse state, QA/IQC state, and whether the pending stock-in appears usable for planning.

It cannot execute Stock In and cannot override QA or Warehouse status.

## 7. Calculation / Derived Field Notes

Derived fields are advisory unless a later implementation and governance record explicitly opens execution strength.

### 7.1 ST / UPH / HC

ST / UPH / HC are Engineering / IE Master Data references.

Planning reads but does not own or maintain them.

Planning may display:

- planned hours
- total work hours
- HC required
- capacity/load advisory state

Planning must not silently edit or override Engineering / IE values.

### 7.2 Plan Qty / BTG / Day Counter

Plan Qty, BTG, and Day x / y are display/derived planning fields.

They help the planner understand the visible schedule spread. They do not by themselves prove production completion, inventory movement, WO closure, or shipment readiness.

### 7.3 Material Ready for Production Start

Material Ready for Production Start is true only when all required readiness conditions are satisfied:

- physical availability
- IQC pass or formal exemption
- release for production
- Store Kitting confirmation
- Line Receive confirmation

If any condition is missing, the display must not show the WO as fully material-ready for production start.

### 7.4 Capacity / Load Check

Capacity / Load Check is advisory only.

It cannot:

- auto-block
- auto-release
- auto-move-line
- auto-approve OT
- authorize production
- replace planner/supervisor decision

OT wording must remain customer-policy configurable. Trial OT reference must not be presented as a universal product rule.

## 8. Role Responsibility Notes

### Planning

Planning owns planning entry intent, planning status, gap/cannot-plan visibility, replacement candidate advisory, and follow-up coordination.

Planning does not own Engineering / IE ST/UPH/HC values, QA status, Warehouse Stock In, Store Kitting truth, Line Receive truth, WO release, or WO close.

### Engineering / IE

Engineering / IE owns ST, UPH, HC, process/routing reference values, and their effective versions.

### Store / Warehouse

Store / Warehouse owns physical availability, receiving/warehouse status, and Store Kitting confirmation according to separately governed flows.

### QA / IQC

QA / IQC owns IQC pass/hold and formal exemption status.

### Production Line / Line Lead

Production Line / Line Lead owns Line Receive confirmation and line-side readiness observation according to separately governed flows.

### Supervisor / Manager

Supervisor / Manager may review blocked/gap/cannot-plan states and follow-up owner/action visibility. Displaying a role in Planning does not grant authority by itself.

## 9. Forbidden Field Rule

No Planning page may invent, duplicate, rename, or hide fields outside the frozen schema.

Forbidden patterns:

- duplicate names for the same business meaning
- hidden UI-only fields that look like official truth
- renamed material readiness fields that bypass QA / Warehouse / Store / Line Receive meanings
- local Planning-owned copies of ST / UPH / HC
- capacity fields that imply automatic approval or production authorization
- Stock-In fields that imply Planning can execute receiving
- replacement fields that imply auto-replacement
- grid fields that imply Production Schedule Grid can write schedule truth
- mock-only fields shown without mock/what-if boundary where needed

If a new field is required, it must be added through a later schema-governance update, not silently inserted into a page.

## 10. Factory Usability Check

The frozen schema must remain usable on a real factory day.

Minimum usability conclusions:

- A planner can understand what to enter in Create / Add without reconstructing hidden upstream truth.
- A supervisor can read LINE OVERVIEW to see which line/order is risky.
- A supervisor can read Production Schedule Grid to see where runnable work can be placed.
- Blocked WOs remain visible in advisory/cannot-plan context, not disguised as planned work.
- Public holidays and no-production days remain visible.
- Material readiness is strict enough to avoid false readiness but still readable in simple factory language.
- Capacity/load remains advisory so the floor is not accidentally dead-stopped by a trial mock.
- Pending Stock-In List gives visibility without pretending to receive goods.
- Operators and supervisors are not forced to understand backend schema complexity to use the visible surfaces.

Factory-language check:

Planning should answer two practical questions quickly:

1. Which line/order is risky?
2. Where can runnable work be placed?

This baseline preserves that simple operator-facing meaning while keeping truth ownership separated behind the scenes.

## Frozen Boundary

This freeze records Planning & Scheduling Master List Schemas v1 as the official trial schema baseline.

It does not authorize:

- backend implementation
- database migration
- ERP integration
- production execution
- inventory update
- WO release
- WO close
- Step 47 Phase B

Any later implementation must open under a separate governed implementation card.
