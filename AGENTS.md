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

## Harness / Entrix / Engineering Controllability Governance Rules

Top-Level Rule 1 — Stability comes from system control, not AI improvisation
Mini-MES stability must come from system-defined boundaries, gates, feedback chains, and recovery paths.
AI improvisation must never be treated as a substitute for governance.

Top-Level Rule 2 — A rule is not “effective” unless it enters an execution path
A critical rule must not be treated as effective merely because it exists in a document, handoff, Task Card, or human memory.
Before any flow may be claimed as governed or runnable, each critical boundary must enter at least one execution-layer carrier:

* repo rule
* process gate
* interface constraint
* state validation
* runtime interception

Task Cards, handoff records, and design documents are not execution-layer carriers.

Top-Level Rule 3 — No external claim before execution-layer entry
Before a rule enters at least one execution-layer carrier, no party may claim that:

* the rule is already effective
* the boundary is already enforced
* the flow is already governed

Top-Level Rule 4 — Every governed key business flow must define four elements
Any governed key business flow must explicitly define:

* flow decomposition
* state model
* acceptance gate
* recovery path

If any one is missing, the flow must not be claimed as controllable or governance-complete.

Top-Level Rule 5 — Failure is a default design assumption
System design must not cover only happy paths.
All key flows must predefine failure handling, including where applicable:

* reject
* retry
* fallback
* timeout
* escalation
* correction-with-trace
* reversal / separate correction path

Implementation layers must not self-add recovery logic without review and freeze.

Top-Level Rule 6 — Strong evidence and weak evidence must remain separated
Mini-MES must continue to uphold:

* trace ≠ truth
* declared/manual ≠ legal truth
* auditability ≠ legal truth
* implementation complete ≠ activated
* activated ≠ runtime production-use authorized

Weak-layer data must never silently upgrade into strong-layer truth.

Top-Level Rule 7 — Activation and production-use authorization are governance decisions
Activation and runtime production-use authorization must be granted only through independent governance decision records.
They must not be inferred from implementation completion, deployment status, test pass, operations action, or product demand.

Under the current mainline, lawful activation / runtime production-use authorization requires explicit confirmation by Rui Chen as Project Owner.

Top-Level Rule 8 — Manual mode is a controlled degraded mode only
Manual / Declared / Non-scan modes may exist only as an independent layer that is:

* degraded
* auditable
* explicitly marked
* downstream-recognizable

MANUAL must not be silently packaged as SCAN.
Phase A must not be silently packaged as Phase B.
Declared/manual data must not be silently packaged as legal truth.

Top-Level Rule 9 — Governance relationships must become visible
Mini-MES must not depend long-term on human memory to preserve governance.
The system should progressively expose:

* frozen baseline status
* blocked / authorized / activated / runtime-use status
* truth / trace / declared boundaries
* acceptance gate positions
* unresolved governance gaps
* recovery path existence

Top-Level Rule 10 — Unreviewed artifacts have no mainline legal standing
Any implementation artifact created without governance review and freeze, including but not limited to:

* recovery logic
* gate condition
* state transition
* truth judgment rule
* AI-generated content

has legal status: UNREVIEWED.

UNREVIEWED artifacts:

* must not enter the mainline
* must not be claimed as governed by Mini-MES
* must not be cited as frozen boundaries by later steps

They must either complete review flow or be explicitly discarded.

Top-Level Rule 11 — AI may assist, but may not decide governance
AI may assist with:

* explanation
* prompting
* anomaly discovery
* governance-structure reading
* assisted checking
* constrained auxiliary drafting

AI must not:

* determine legal truth
* cross frozen boundaries
* upgrade manual data
* rewrite blocked / inactive / unauthorized status
* rewrite frozen semantics
* generate new states
* generate new gate conditions
* generate new recovery logic
* generate new truth-judgment rules

Top-Level Rule 12 — AI outputs that affect governance require full human review
Any AI-generated content involving:

* business rules
* state transitions
* gate conditions
* recovery paths
* truth judgment
* evidence-strength classification

must pass the same governance review grade required for human-written content before adoption.
AI must not be the sole decision-maker for any of the above.

Factory-Language Short Explanation
The system must not stay stable only because “someone happens to be smart today.”
Fixtures, limiters, inspection points, abnormal isolation, rework routes, and release conditions must be installed first.
That way, whether the work is done by a person or by AI, neither can drift freely.
----------------------------------------------------------------------------------

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
