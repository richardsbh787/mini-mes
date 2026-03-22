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
6. Implement only within that boundary.
7. Add focused tests for frozen semantics and no-mutation guarantees.
8. Return review-ready artifacts only.

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
