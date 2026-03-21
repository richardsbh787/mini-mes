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

## Step Review Template
When asked to prepare a step, structure the work like this:
- Objective
- T-1 / T0 / T+1 truth interpretation
- S-1 / S0 / S+1 step-development interpretation
- Allowed writes
- Forbidden writes
- Guard type and guard order
- Test expectations
- Non-goals

## Guard Type Alignment
Use the frozen guard definitions explicitly during step review:
- **Pure validation guard** = validate only; no writes; no side effects; no transaction ownership.
- **Execution truth guard** = validate + persist execution truth + commit/rollback inside the guard; upper service layer must not own the transaction.

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
