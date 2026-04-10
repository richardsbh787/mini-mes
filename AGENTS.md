# AGENTS.md

## Purpose
This repository uses strict execution discipline. Do not treat this as a generic CRUD project. Every task must respect frozen semantics, truth surfaces, and review gates.

## Core Operating Mode
Always work under:

- Ontology
- Guard V2
- GUARD MODE
- Operator Minimal Action Rule
- T-1/T0/T+1 Truth Audit
- S-1/S0/S+1 Step Development Audit
- P-1/P0/P+1 PlantFit / Practicality Audit

### Meaning of the mode
- **Ontology** = model business reality as objects, properties, relations, truth surfaces, rules, and guarded actions.
- **Guard V2** = preserve strict boundary order, validation discipline, and no shortcut writes.
- **GUARD MODE** = do not self-expand scope, do not invent owners/semantics, do not skip approval gates.
- **Operator Minimal Action Rule** = absorb complexity in system/backend; keep frontline actions minimal.
- **T-1/T0/T+1 Truth Audit**:
  - **T-1 Precondition Truth Check** = what valid prerequisite truth must already exist before the event
  - **T0 Event Truth Check** = what exactly happens at the event moment
  - **T+1 Post-Event Truth Check** = what evidence, state, and consequences remain after the event
- **S-1/S0/S+1 Step Development Audit**:
  - **S-1 Previous Frozen Step Context** = identify the nearest frozen prerequisite truth layer that the current step stands on; if multiple prerequisite layers are each missing and would invalidate S0, the nearest layer is S-1 and earlier layers should be treated as S-2, S-3, etc.
  - **S0 Current Step Boundary Check** = define what the current step is, whether it is a legal source step or a dependent step, what minimal upstream truth chain it depends on, what it may write/read, and whether it is a pure validation guard or an execution truth guard.
  - **S+1 Next-Step Dependency Check** = verify what stable outputs, state, linkage, and evidence the current step leaves for the next step so downstream logic does not have to guess or re-infer truth.

## Operator Minimal Action Rule
Design every step and surface so the frontline operator performs the minimum necessary action only.

Rules:
- Do not push system complexity onto operators.
- Prefer backend absorption over frontline burden.
- Minimize clicks, inputs, decisions, and manual interpretation.
- Do not require operators to reconstruct missing upstream truth by themselves.
- If the system can derive, validate, default, or infer safely, do it in the system.
- Read/write surfaces must stay simple enough for ordinary factory users to operate reliably.
- When trade-offs exist, prefer lower operator burden unless that would break truth integrity or auditability.

## Absolute Rules
1. Single locked mainline only.
2. If the current step is not frozen, do not jump to the next step.
3. Do not invent new semantics, state machines, owners, or shortcut flows unless explicitly requested.
4. Do not mutate upstream truth surfaces unless the task explicitly requires it.
5. Keep diffs scoped to the locked step only.
6. Preserve frozen public contracts unless the task explicitly says to patch them.
7. If boundary is unclear, stop and surface the ambiguity rather than improvising.

## Review Discipline
Every implementation should aim to pass this sequence:
1. Main review
2. Final review
3. Freeze

Main review pass does **not** mean frozen.

## Mini-MES Domain Guidance
This project values:
- truth before convenience
- auditability before automation
- controlled exceptions before hidden bypasses
- simple operator actions with strong backend discipline

When designing or modifying flows:
- prefer explicit truth objects over temporary implicit logic
- prefer read surfaces before wider writebacks
- avoid turning one focused step into a broad workflow platform
- keep Starter V1 minimal unless expansion is explicitly approved

## Mini-MES Product Mission — Extreme Simplicity Is the Moat
Mini-MES must treat extreme simplicity as a core competitive advantage.

### Core mission
Mini-MES is built for SME industrial users, not enterprise "big and full" software buyers.
Frontline users should be able to understand core flows in about 10 minutes.
The product should solve the sharpest operational pain first.

### Product principle
Extreme simplicity is part of the product moat.
The system should absorb complexity instead of pushing burden to operators.
Every new feature or module must be checked against simplicity, usability, and operational value.
Do not copy large-enterprise MES complexity unless clearly justified.

### Mandatory design rules
When designing future steps, modules, or surfaces:

1. Keep core frontline flows understandable in about 10 minutes.
2. Solve the sharpest operational pain before expanding surrounding feature scope.
3. Prefer backend absorption of complexity over operator-side reconstruction, clicks, or interpretation.
4. Require each new feature or module to justify simplicity cost, usability impact, and operational value.
5. Preserve narrow, understandable surfaces even when backend truth and guard logic become more rigorous.
6. Reject feature growth that makes the product broader but less learnable or less useful.

### Anti-bloat rule
The following are forbidden unless clearly justified:

- feature bloat that weakens core operational clarity
- enterprise-style workflow expansion without sharp SME pain justification
- operator-facing complexity added only because larger MES products have it
- convenience feature accumulation that dilutes the mainline product
- broad module expansion without strong operational value

### Design intent
The purpose of this mission is to keep Mini-MES sharp, understandable, and operationally useful.
Mini-MES should win by being simple enough to adopt quickly, focused enough to remove real daily pain, and disciplined enough to preserve truth without overwhelming the user.

### Human version
Mini-MES 不是靠“功能很多”取胜，而是靠“足够简单、上手够快、真正解决现场最痛的问题”取胜。
复杂度尽量让系统自己吸收，不要转嫁给一线人员。

## Cross-Cutting Governance Rules

The following rules supplement the Core Operating Mode.
They do not replace Ontology, Guard V2, GUARD MODE, Operator Minimal Action Rule, or the T-1/T0/T+1 and S-1/S0/S+1 audit disciplines.
They add durable cross-cutting governance requirements on controllability, evidence strength, failure handling, AI boundaries, and explicit activation discipline.

### 1. System Control Over Improvisation

System stability must come from explicit control design, not from ad hoc human interpretation, temporary convenience logic, or AI improvisation.

### 2. Strong-vs-Weak Truth Separation

The system must keep explicit separation between stronger and weaker forms of business meaning, including but not limited to:

* trace vs truth
* declared/manual vs legal/verified
* reviewable evidence vs convenience inference
* degraded mode vs normal controlled mode

Weaker forms must not be silently promoted into stronger ones.

### 3. Failure Must Be Governed

Failure paths are part of system design, not afterthoughts.
Operator-facing flows must not rely on silent failure, indefinite waiting, or forced shutdown as normal handling.
Where recovery cannot yet be fully implemented, the failure type, responsible party, and next required action must still be made explicit.
Where a timeout or waiting limit is used, the system must explicitly transition to a blocked or failed state after the limit is reached; operator-facing errors must separate technical details from actionable guidance.

### 4. Manual Mode Is Degraded and Auditable

Any manual, non-scan, declared, fallback, or degraded operation mode must remain explicitly marked as weaker than controlled legal-strength mode, and must remain auditable.
Manual convenience must not be disguised as equal-strength system truth.

### 5. AI Assists but Does Not Govern

AI may assist with drafting, analysis, summarization, review support, and implementation acceleration.
AI must not silently define ontology, upgrade evidence strength, authorize production use, replace governance decisions, or erase required review boundaries.

### 6. Activation and Production Use Require Explicit Authorization

Design completion, implementation completion, review pass, or feature existence do not by themselves authorize activation, production deployment, or runtime production use.
Such transitions must remain explicitly governed and separately authorized where required by the frozen chain.

### Human Version

系统要稳，不可以靠人临场猜，也不可以靠 AI 自行发挥。
弱证据不能偷偷当强证据，手工模式不能假装等于正式模式。
出错时不能假死，启用和上生产也不能因为“已经做出来了”就自动算通过。

## Global Governance - P-Series PlantFit Practicality Audit Rule v1

Review carry-forward for this repo-wide governance insertion:

* Secondary review: PASS
* Final review: PASS WITH WARNINGS
* Freeze status: PASS WITH WARNINGS / FROZEN WITH FINAL REVIEW NOTES

Purpose
This rule introduces the P-series audit lens as a permanent cross-cutting governance rule for Mini-MES, to prevent architecture, freeze text, flow design, recovery-path design, and future implementation-opening conditions from becoming logically elegant but operationally unusable on the shopfloor.

Why this rule exists
Mini-MES is not intended to become a heavyweight enterprise system that is formally complete but unable to help when the shopfloor is under pressure.

The system must preserve frozen governance, truth, evidence, audit, and approval boundaries, but it must also remain usable under real-world factory conditions where interruptions, missing people, incomplete tooling, unstable discipline, temporary trade-offs, and emergency continuity needs do occur.

This rule exists to stop paper-perfect but field-unusable design drift.

Core rule
The P-series is a permanent horizontal review lens alongside, and not replacing:

* Ontology
* Guard V2
* GUARD MODE
* Operator Minimal Action Rule
* T-1 / T0 / T+1
* S-1 / S0 / S+1

Any key Task Card, frozen baseline, governed flow, operator-facing rule set, recovery path, trace discipline, deferred reconciliation rule, or implementation-opening prerequisite must pass not only the T-series and S-series lenses, but also the P-series lens.

If T passes and S passes but P fails, the item is not considered practically fit for advancement unless an explicit override is granted under the override rule defined in this rule.

P-1 definition
P-1 checks whether the proposed design depends on unrealistic factory preconditions.

Mandatory review questions

1. Does this design assume the constant availability of a specific role, supervisor, approver, or ideal operator that may not reliably exist on the actual shopfloor?
2. Does this design assume tools, terminals, labels, scanners, network quality, discipline level, or master-data completeness that are not yet realistically established?
3. Does this design assume extra time, extra manpower, or management attention that a live production floor may not actually have?
4. Does this design quietly depend on perfect compliance before it becomes usable?

PASS definition
P-1 passes only if the design can still operate under realistic factory conditions without depending on ideal staffing, ideal discipline, ideal tooling, or ideal data completeness.

FAIL definition
P-1 fails if the design only works under idealized staffing, idealized discipline, idealized tooling, or idealized data conditions.

Required correction direction
When P-1 fails, the design must be narrowed, simplified, staged, or made more resilient to real factory conditions before advancement.

Plant-fit reviewer rule
When P-1 fails, the design cannot advance unless a designated plant-fit reviewer explicitly confirms that the proposed narrowing is sufficient for real factory use.

Plant-fit reviewer designation must be completed before the first P-series review is triggered.
The reviewer must not be appointed ad hoc only after a P-fail already occurs.
The reviewer should be a production manager, manufacturing lead, or experienced supervisor-level reviewer with actual shopfloor familiarity.
Exact named person / role assignment should be recorded separately in handoff or equivalent governed record.
If no plant-fit reviewer has been designated when a P-fail item arises, the item must escalate directly to Ruichen.

Minimum plant-fit reviewer record requirement
The review record must include, at minimum:

* reviewer role
* reviewer scope of authority for the reviewed item
* reviewed item name / version / date
* short conclusion: sufficient / not sufficient for real factory use
* key practical reason
* whether disagreement remains between design intent and shopfloor practicality

Disagreement escalation rule
If disagreement remains between design intent and shopfloor practicality, the matter must be escalated to Ruichen for final decision.

P0 definition
P0 checks whether the design remains operable at the moment of execution on the shopfloor.

Mandatory review questions

1. Who exactly performs this step at the real shopfloor moment?
2. Does this rule add extra operator action, extra approval waiting, or extra friction that may cause bypass behavior?
3. When an exception occurs, can the operation continue through a governed degraded path, or does the rule simply dead-stop the floor?
4. Is the rule forcing the shopfloor to satisfy design elegance, instead of helping the shopfloor preserve control with minimal action?
5. Can the same control objective be achieved with fewer operator actions?

PASS definition
P0 passes only if the flow can be executed by real shopfloor actors with manageable action burden, without predictable bypass pressure, and without unnecessary dead-stop behavior in common exception scenarios.

FAIL definition
P0 fails if:

* the design introduces unnecessary operator burden
* the design creates predictable bypass pressure
* the design dead-stops common exception scenarios without a governed fallback
* the design protects formal neatness at the cost of real operational continuity

Required correction direction
When P0 fails, the design must be simplified, decomposed, or re-routed toward a lower-friction controlled path that preserves minimum truth and audit discipline without freezing the live operation unnecessarily.

Lower-friction controlled path examples
Examples of lower-friction controlled paths include:

* a supervisor-witnessed declaration with later reconciliation
* a photo-based evidence capture
* a simple dropdown selection instead of free-text typing

Such paths must still preserve auditability and must not become an unbounded bypass.

Independent review rule against Operator Minimal Action Rule
P0 review and Operator Minimal Action Rule review are independent.
If both are triggered, both findings must be recorded separately and both corrections must be confirmed separately.
P0 pass does not automatically mean Operator Minimal Action Rule pass.
Operator Minimal Action Rule pass does not automatically mean P0 pass.

P+1 definition
P+1 checks whether allowed real-world flexibility can still be closed back into a controlled, auditable, and understandable state afterward.

Mandatory review questions

1. If the floor uses a controlled workaround, can the system still capture what happened afterward?
2. Can the event still be traced, reconciled, reviewed, and corrected without overwriting frozen truth improperly?
3. Does the workaround preserve boundary separation between truth, evidence, audit trace, and approval?
4. Can a later reviewer still understand what happened, why it happened, who did it, and what remains unresolved?

PASS definition
P+1 passes only if the allowed practical flexibility can still be closed into a recoverable, traceable, reviewable, and bounded post-event state.

FAIL definition
P+1 fails if the design allows practical bypass or emergency continuation but leaves behind ambiguity, untraceable actions, overwritten truth, or unrecoverable audit gaps.

Required correction direction
When P+1 fails, the design must add a governed recovery path, trace discipline, deferred reconciliation rule, or explicit unresolved-state handling before advancement.

Recursive practicality rule
Any recovery path, trace discipline, deferred reconciliation rule added to satisfy P+1 must itself be reviewed under the P-series before acceptance. Otherwise, Mini-MES risks fixing one impracticality with another.

Hard governance rule
T-series guards truth discipline.
S-series guards sequence discipline.
P-series guards plant-fit discipline.

Therefore:

* T fail = truth risk, cannot advance
* S fail = sequence / dependency risk, cannot advance
* P fail = plant-fit / practicality risk, cannot advance unless an explicit override is granted under the override rule below

No key item may be considered ready if it is semantically clean but operationally unrealistic.

Override rule
A P-series failure may be overridden only by a written decision from Ruichen.

Override trigger condition
Override may be considered only when:

* business necessity is explicit
* T-series and S-series boundaries are still preserved
* the plant-fit shortfall is known and consciously accepted
* normal correction is not feasible in the needed timeframe

Minimum written approval form
The override record must state:

* the exact reviewed item
* the exact business justification
* the specific plant-fit shortfall being temporarily accepted
* the agreed risk acceptance
* the allowed scope of the override
* the allowed duration of the override
* the required follow-up review timing

Default review discipline
The override must be documented in handoff and must be re-reviewed within a defined period.
Default re-review period: within 3 months from the written override approval date, unless the override record explicitly defines a different start date.

Override boundary
Override is an exception path only. It must not be treated as proof that the design is plant-fit, and it must not silently convert a P-failed design into a generally approved design.

Relationship to existing Mini-MES principles
This rule strengthens, and does not weaken, the following already-established directions:

* Operator Minimal Action Rule remains active
* Frozen governance and truth/evidence/approval boundaries remain non-negotiable
* Controlled flexibility is allowed only where boundaries are preserved
* Design-layer completeness does not automatically mean field readiness
* Shopfloor usability is not optional polish; it is part of controllability

Minimum application requirement
From this rule onward, every future key Task Card / freeze candidate / major governed flow should include an explicit plant-fit check section, at minimum covering:

1. real actor availability
2. action burden
3. exception survivability
4. post-event recoverability
5. whether operators would realistically use the flow

Recommended review prompt
For every future key design item, reviewers should ask:

"Can this still run on a bad day in a real factory, without destroying truth and without forcing the floor into paralysis?"

Non-scope
This rule does not:

* authorize any implementation
* weaken existing frozen truth/evidence/approval boundaries
* allow convenience inference where explicit governed records are required
* replace T-series or S-series
* guarantee that every exception path is open by default
* justify uncontrolled shopfloor freedom

This rule only freezes the governance requirement that practicality / plant-fit must be reviewed explicitly and must be able to block advancement when a design is too idealized for real factory use, unless a documented override is granted under this same rule.

Factory Usability Check
Minimum check:

* Will operators feel this is troublesome?
* Will supervisors skip it because it is too complicated?
* When the floor is under stress, is there a governed workaround path?
* After the workaround, can the account / record still be closed cleanly?
* Is this rule helping the floor, or punishing the floor?

Business Logic Confirmation / Corresponding Factory Floor Scenario
This rule does not exist to loosen the system, and it does not allow the floor to do whatever it wants.

It establishes a new hard gate:
from now on, no card, no flow, and no rule may be judged only by whether the logic looks clean. It must also be judged by whether it can still run on the day the factory is under pressure.

A real factory is not an office.
On a real day, someone is absent, material is short, the network is unstable, a supervisor is busy, a machine is stuck, or a customer is pushing.
If a rule only works in calm conditions, but not in battle conditions, then it is not a good system rule no matter how elegant it looks.

This rule adds three practical closures:

1. If design says "I already simplified it," but the floor says "it is still impractical," there must be a plant-fit reviewer to close that gap first; if the disagreement remains, it escalates to Ruichen.
2. If someone tries to repair an impractical path by inventing a new and even more complicated paper path, that new recovery path must also pass the P-series.
3. If business urgency is real, a P-fail item is not automatically dead forever, but it may move only through Ruichen's written override, with explicit reason, scope, duration, and re-review timing.

Factory-language explanation
Mini-MES must hold two things at the same time:
first, truth must not be corrupted;
second, the shopfloor must not be written into paralysis.

A system that protects boundaries while still letting the floor stay alive under pressure is the system Mini-MES actually wants.

## Mini-MES Ontology Global Extension — Six-Layer Model
Mini-MES Ontology is no longer treated as only:

- Object
- Property
- Relationship
- Action

It is globally extended into six layers:

- **T = Type** (object types)
- **P = Predicate** (judgment / filter predicates)
- **F = Function** (conversion / normalization / derivation functions)
- **Agg = Aggregate** (governed aggregates)
- **Action = Business Action** (guarded business actions)
- **Role = Authority Boundary** (who may read / approve / execute)

### Global rule
For future ontology-driven design, especially from Step 46 onward, every new business domain or module should be checked through all six layers:

- T
- P
- F
- Agg
- Action
- Role

A design is not considered ontology-complete if it defines only objects and relationships but leaves predicates, functions, aggregates, actions, or authority boundaries outside the model.

### Meaning of each layer
- **T** defines what business objects exist.
- **P** defines how the system judges, filters, gates, or classifies reality.
- **F** defines how quantities, evidence, or semantic meaning are converted / normalized / derived.
- **Agg** defines governed read-side summaries and grouped truths; aggregates must not be left as ad hoc SQL/report leftovers.
- **Action** defines legal business operations with guard conditions and write boundaries.
- **Role** defines authority, approval, read/write boundary, and execution responsibility.

### Mandatory ontology design discipline
When designing future steps:

1. Do not stop at T / relationship modeling only.
2. Predicates must be made explicit when business judgment exists.
3. Functions must be made explicit when conversion / normalization / derivation exists.
4. Aggregates must be explicitly governed when the business depends on summaries, counts, balances, frequencies, or overdue views.
5. Actions must be modeled as guarded business actions, not hidden in procedural logic.
6. Roles must be explicit; authority is part of the semantic model, not an afterthought.

### Frozen-boundary protection
This AGENTS patch is a global design rule only.
It does **not** retroactively alter any frozen step semantics.
It does **not** auto-expand current locked tasks.
It does **not** authorize implementation by itself.
All frozen steps remain governed by their own accepted boundaries unless a later freeze record explicitly changes them.

### Anti-fake-ontology rule
The following are forbidden:

- object-only ontology with missing predicate/function/action/role logic
- aggregates that exist only as informal report logic outside the model
- hidden authority decisions not represented in Role
- convenience inference pretending to be legal ontology truth
- switching database / graph stack as a substitute for missing semantic design

### Current Mini-MES mapping examples
Examples of the six layers in the current system include:

**T**

- WorkOrder
- Material
- StockLedger
- InventoryState
- WipTransfer
- FgReceive
- Shipment
- Complaint
- CAPA

**P**

- is_shortage
- is_negative_stock
- is_final_step
- is_available_for_next_step
- is_shadow_batch
- is_authorized_prebuild

**F**

- qty/uom conversion
- shortage gap calculation
- inventory evidence normalization
- complaint source resolution

**Agg**

- item balance by bucket
- open shortage count
- complaint frequency by model/customer
- CAPA overdue count
- monthly FG in/out summary

**Action**

- Detect Shortage
- Open Shadow Case
- Approve Prebuild
- Create Complaint
- Open CAPA
- Close CAPA

**Role**

- operator
- supervisor
- planner
- store
- QA
- manager

### Design intent
The purpose of this extension is not to force a new database choice.
The purpose is to ensure Mini-MES ontology becomes executable and governed:

- semantic
- evidence-linked
- action-aware
- aggregate-aware
- role-aware

This rule should guide future ontology design, especially in later knowledge/read-side layers such as quality, complaint, and CAPA domains.

## Truth Surface Protection
Unless the task explicitly requires it, do not mutate:
- StockLedger
- Routing execution truth
- WIP transfer truth
- FG receive truth
- Shipment truth
- other already-frozen upstream truth objects

## Step Execution Pattern
For each step:
1. Restate the locked objective in one sentence.
2. List what this step may write.
3. List what this step may read.
4. List what this step must not touch.
5. State the S-1 / S0 / S+1 audit briefly.
6. Run the Pre-Freeze Crisis Check before any freeze recommendation, implementation authorization, formal final review, or decision to continue the current mainline.
7. Implement only within that boundary.
8. Add focused tests for frozen semantics and no-mutation guarantees.
9. Return review-ready artifacts only.

### Pre-Freeze Crisis Check (Required)
**Purpose**

Before any step may enter freeze, implementation, implementation authorization, or formal final review, the current owner must run a Pre-Freeze Crisis Check. This check exists to catch forward-looking structural risk that may not be visible inside normal step-local review.

This check does not replace S-1 / S0 / S+1. S-1 / S0 / S+1 asks whether the current step is locally sound in relation to the nearest frozen chain. Pre-Freeze Crisis Check asks whether the current step, if accepted now, is likely to create a future mainline failure, dependency collapse, operator-use break, or freeze pollution later.

**Placement**

Add this section inside the Step Execution Pattern before:

- freeze recommendation
- implementation authorization
- formal final review
- any decision to continue the current mainline

**Maximum Length**

One page maximum. State only the highest-risk forward-looking points and the resulting gate decision.

**Required Six Checks**

1. **Foundation Check**
   Question: Does this step rely on any upstream truth, master data, admitted source, legal evidence, or runtime prerequisite that is not truly ready yet?
   Must state:
   - what upstream foundation this step stands on
   - whether that foundation is genuinely usable now
   - what remains missing
2. **Dependency Chain Check**
   Question: If this step is accepted now, which downstream steps will rely on it, and what breaks if this step is weaker than assumed?
   Must state:
   - immediate downstream dependency chain
   - highest-cost future failure if current assumptions are wrong
   - whether delay now is cheaper than repair later
3. **Reality Intrusion Check**
   Question: Will factory reality create bypass, shadow flow, verbal override, illegal release, or off-system workaround before the full designed control layer exists?
   Must state:
   - likely real-world bypass modes
   - whether minimum observation should start earlier
   - what must be visible now even if full control is not yet implemented
   - earliest step at which minimum observation must begin, even if full control is not yet implemented
4. **Operator Action Surface Check**
   Question: Can the operator understand what to do, what not to do, and what to do next when blocked?
   Must state:
   - operator-visible action entry
   - minimum operator action path
   - operator-visible error exits that must eventually exist
   Note: Do not force final UI copy here. At this stage, identify the operator-visible error exits and required next-action guidance only.
5. **Freeze Pollution Check**
   Question: If this step is wrong, what frozen semantics, handoff records, or upstream interpretations become polluted?
   Must state:
   - which frozen layers would be contaminated
   - whether correction would require an independent correction path
   - whether the risk is local or chain-wide
6. **Stop-or-Go Gate**
   A final explicit gate decision is required.
   Allowed outputs only:
   - GO
   - CONDITIONAL GO
   - PAUSE
   - ROLLBACK REVIEW

**Definitions**

GO: Current step may proceed without additional preconditions.
CONDITIONAL GO: Current step may proceed only after explicitly listed preconditions are met.
PAUSE: Current mainline must stop until the named issue is resolved or formally bounded.
ROLLBACK REVIEW: The current issue may invalidate an upstream frozen assumption and requires upstream review before continuing.

**Gate Authority**

Gate decision draft: Qingchen.
Gate decision confirmation: Ruichen only.
No gate output is binding without Ruichen's explicit confirmation.

**Required Output Format**

Pre-Freeze Crisis Check

- Current highest risk:
- Risk level: P0 / P1 / P2
- Affected scope:
- Foundation check:
- Dependency chain check:
- Reality intrusion check:
- Operator action surface check:
- Freeze pollution check:
- Gate decision draft: GO / CONDITIONAL GO / PAUSE / ROLLBACK REVIEW
- Preconditions before resume:
- Gate decision confirmation: Ruichen [confirmed / not yet confirmed]

**Execution Rule**

No freeze recommendation, no implementation authorization, and no formal final review may proceed without this section for:

- any key mainline step
- any step that becomes a dependency base for multiple downstream steps
- any step that touches truth admission, legal evidence, identity, availability, reconciliation, or operator-facing blocking flow

**Review Roles**

- Draft: Qingchen
- Final direction decision: Ruichen
- Final review confirmation: Qinran
- Adversarial challenge / counterexample pressure test: Lao Xiao (DeepSeek), when requested

**UI / Operator Error Discipline Link**

For any step with operator-visible failure paths, the Pre-Freeze Crisis Check must identify operator-visible error exits. At freeze stage, the system does not need final Chinese wording yet. But the step must not be treated as operator-ready if it cannot later provide:

- developer/log technical error detail
- separate operator-facing understandable action guidance

**Current Recorded Application**

If Step 47 admitted source foundation remains not truly ready because `location_code` repair path is not yet formally designed and frozen, then Step 48 and later Starter steps may continue only at design layer and must not enter implementation authorization.

## Preferred Deliverables
When finishing a task, provide:
1. commit page
2. relevant schema/service/test files
3. direct-review txt files if remote visibility is not available

Never provide guessed or fake links.

## Main Handoff Baseline
The only valid main handoff baseline is:
- `docs/handoffs/current_main_handoff.md`

Do not guess the latest handoff by filename or timestamp.
Do not use patch, patch_pack, or archive handoff files as the main baseline unless explicitly instructed.

## S-1 / S0 / S+1 Development Audit Rule
Apply this before starting any new step design, implementation, or main review.

### S-1: nearest frozen prerequisite layer
Check:
1. What already-frozen truth, state, binding, or context must already exist for S0 to be legal?
2. Which frozen step wrote that truth?
3. What may S0 read from that layer?
4. What must S0 not mutate or reinterpret from that layer?
5. What known scope limits or non-blocking notes from that layer must be inherited?

If multiple prerequisite truths would each make S0 invalid if missing, order them by dependency distance:
- the nearest layer is **S-1**
- earlier layers are **S-2**, **S-3**, etc.

Do not turn S-1 into a full historical chain dump.

### S0: current step definition
Check:
1. What type of step is this? (truth surface / write surface / read surface / action surface / guard / trace)
2. Is this a legal source step?
3. If not a source step, what is the minimum upstream truth chain required before it can start?
4. What does this step itself do?
5. What does this step explicitly not do?
6. What exact truth, state, event, or read surface does this step newly create?
7. Who owns commit / rollback responsibility?

Rule:
- If S0 is not a source step, and its upstream truth is not frozen, not readable, or only assumed, do not start implementation.

### S+1: downstream continuity check
Check:
1. Which next step, read surface, audit surface, or exception flow will rely on this step?
2. What exact fields, states, relations, IDs, or evidence will they need?
3. Does S0 leave those results in a stable, single-meaning form?
4. Will downstream steps need to guess or reconstruct key context again?
5. Does S0 create dual semantics, dual state sources, or broken continuity?

Rule:
- A step is not development-ready if its output forces downstream logic to guess.

## Step Review Template
When asked to prepare a step, structure the work like this:
- Objective
- T-1 / T0 / T+1 truth interpretation
- S-1 / S0 / S+1 step-development interpretation
- Allowed writes
- Allowed reads
- Forbidden writes / forbidden mutations
- Guard type and guard order
- Test expectations
- Non-goals

## Guard Type Alignment
Use the frozen guard definitions explicitly during step review:
- **Pure validation guard** = validate only; no writes; no side effects; no transaction ownership.
- **Execution truth guard** = validate + persist execution truth + commit/rollback inside the guard; upper service layer must not own the transaction.

Do not blur these two guard types.

## Evolving Rules
This file is intentionally evolvable.
When a rule becomes stable across multiple accepted steps, promote it here.
When a rule is only temporary or step-specific, keep it out of this file and place it in the step handoff instead.

## Keep AGENTS.md Small
This file should hold durable repo-wide behavior rules only.
Do not dump entire handoff documents here.
Put large step-by-step details in handoff, plans, or step-specific docs.

## If You Are Unsure
Default to:
- smaller scope
- stricter boundary
- clearer audit trail
- no upstream mutation

## 人话
- **T series** = investigate real-world event truth.
- **S series** = audit step-development continuity.
- **If the floor under the current step is unclear, do not build the step.**
