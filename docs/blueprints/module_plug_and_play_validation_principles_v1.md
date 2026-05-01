# Module Plug-and-Play Validation Principles v1

Status: FROZEN TRIAL ARCHITECTURE VALIDATION BASELINE

Authority layer: Trial architecture validation baseline for module visibility, dependency declaration, degraded reference behavior, and future package-fit review.

This document freezes module plug-and-play validation principles only. It does not authorize backend implementation, config file creation, feature flag implementation, UI navigation refactoring, database migration, production execution, inventory update, WO release, WO close, ERP integration, or Step 47 Phase B.

## 1. Purpose

Mini-MES must validate that modules can remain clear, bounded, and configurable without weakening frozen governance or turning optional references into hidden execution truth.

Module Plug-and-Play is a core architecture validation goal. The product should support hiding, restoring, reordering, enabling/disabling, and future package composition without breaking core workflows.

This baseline exists to make sure future Planning & Scheduling work can declare module dependencies explicitly before implementation, and can handle missing optional modules without pretending that missing data is passed, ready, approved, or completed.

## 2. Scope

This baseline applies to future Planning & Scheduling Task Cards and any module-facing architecture review that depends on cross-module references.

In scope:

- module visibility / hide / restore behavior
- module reorder and enable/disable expectations
- read-only cross-module reference rules
- degraded mode wording and truth boundaries
- package-fit review for Starter / Pro / Add-on discussions
- Task Card Module Dependency Declaration requirements
- review authority for module dependency boundaries

This baseline is architecture validation guidance only. It does not create runtime package logic, permission logic, navigation config, or feature flags.

## 3. Core Principles

Module Plug-and-Play is a core architecture validation goal, but it cannot weaken, override, or bypass frozen baselines, handoff rules, schema, dropdowns, role responsibilities, or legal truth boundaries.

Core principles:

- modules should be hideable without corrupting remaining visible flows
- modules should be restorable without reinterpreting historical truth
- modules should be reorderable in navigation without changing business authority
- modules may be enabled/disabled by future deployment composition, but disabled visibility is not the same as passed control
- future package composition must not convert unavailable module truth into approval
- cross-module data is read-only / reference-only by default
- missing optional references must display as unavailable or not applicable, not as success
- Planning visibility does not grant Planning execution authority over QA, Store, Warehouse, Repair, ERP, or Production

## 4. Module Visibility / Hide / Restore Rule

Modules should support hiding, reordering, enabling/disabling, and future package composition without breaking core workflows.

Hiding a module may remove its navigation surface, but it must not:

- delete or rewrite records owned by that module
- silently mark module-owned truth as passed, ready, approved, or completed
- transfer the hidden module's execution authority to another module
- force another module to invent replacement truth
- make frozen handoff, schema, dropdown, role, or legal truth boundaries disappear

Restoring a module must preserve the same ownership meaning it had before it was hidden.

If a page depends on a hidden or disabled optional module, the page must show the reference as unavailable or not applicable according to the degraded mode rule.

## 5. Cross-Module Reference Rule

Cross-module data is read-only / reference-only by default.

A module may display another module's status, summary, warning, or reference only as visibility unless a separate governed write path explicitly authorizes stronger behavior.

Planning may read or display references from QA, IQC, Store, Warehouse, Repair Station, ERP, Production, Engineering / IE, and related domains where the parent schemas allow it.

Planning must not use visibility to:

- approve QA or IQC status
- complete Store Kitting
- complete Warehouse Stock-In
- manage Repair Station work
- release or close WO
- execute Production truth
- override ERP truth
- convert missing reference data into readiness

Cross-module references must preserve source ownership. Displaying a field does not move its authority boundary.

## 6. Degraded Mode Rule

When an optional reference module is not enabled, not installed, hidden, unavailable, or outside the current package scope, the dependent page must enter degraded reference behavior.

Allowed degraded labels include:

- Reference Unavailable
- N/A
- Optional Module Not Enabled
- Reference Only - Source Module Not Active

Reference Unavailable / N/A must not be treated as Passed, Ready, Approved, or Completed.

Locked degraded meanings:

- QA unavailable is not QA passed.
- IQC unavailable is not IQC passed.
- Store module unavailable is not Kitting completed.
- Warehouse unavailable is not Stock-In completed.
- Repair Station unavailable is not repair returned.
- ERP unavailable is not ERP confirmed.
- Production unavailable is not production complete.

Degraded mode must be visible enough that users understand the reference is missing or not active. It must not quietly disappear if its absence changes operational interpretation.

## 7. Package Fit Rule: Starter / Pro / Add-on

Package examples are illustrative only and do not freeze commercial Starter / Pro / Add-on package contents.

Future package-fit review may classify a module or reference as:

- Starter
- Pro
- Add-on
- Not package-relevant

This classification is for architecture validation and commercial discussion only. It does not authorize production use, implementation, pricing commitment, runtime packaging, or customer entitlement.

Package fit must preserve frozen truth boundaries:

- Starter cannot fake Pro-owned reference truth.
- Pro cannot override legal truth boundaries.
- Add-on absence cannot be treated as successful completion.
- Package availability cannot change role authority.
- Commercial package composition cannot weaken governance.

If a future Task Card relies on a module that may not exist in every package, it must define degraded mode before the Task Card can freeze.

## 8. Task Card Requirement: Module Dependency Declaration

All future Planning & Scheduling Task Cards must include Module Dependency Declaration.

Minimum required declaration:

- Required modules
- Optional reference modules
- Degraded mode if optional module is not enabled
- Read-only cross-module references
- Forbidden cross-module writes
- Package impact: Starter / Pro / Add-on / Not package-relevant

The declaration must state whether each referenced module is:

- required for the page to function
- optional read-side visibility
- unavailable in degraded mode
- forbidden as a write target
- outside package scope

Dependency Declaration must be reviewed and approved by the owner of architecture governance - Qingchen / 清尘 - before the corresponding Task Card can be frozen or passed to Codex for implementation.

Lao Xiao / 老萧, Qinran / 沁然, or Ruichen / 睿辰 may perform secondary or final review checks when the dependency risk is material, cross-module, or boundary-sensitive.

No Task Card can self-approve its own module dependency boundary.

## 9. Explicit Non-Scope

This document does not authorize:

- creation of nav_config.json
- feature_flags
- module_availability engines
- backend permissions
- HTML navigation refactoring
- runtime package logic
- database migration
- backend implementation
- UI mock change
- production execution
- inventory update
- WO release
- WO close
- ERP integration
- commercial package freeze
- Step 47 Phase B

This document also does not define customer contract packaging. Starter / Pro / Add-on examples remain illustrative until separately frozen by commercial package governance.

## 10. Factory Usability Check

Module plug-and-play must help Mini-MES stay simple enough for SME factory use.

Factory usability checks:

- Can a customer hide an unused module without breaking the daily core flow?
- Can a supervisor still understand whether missing data means unavailable, not applicable, or truly passed?
- Can Planning still show useful schedule context without pretending to own QA, Store, Warehouse, Repair, ERP, or Production truth?
- Can optional modules be added later without renaming frozen fields or changing existing truth meaning?
- Can future package composition avoid confusing operators with unavailable controls or false-ready statuses?

Factory-language meaning:

If a module is not enabled, Mini-MES must say the reference is unavailable. It must not pretend the work is passed.

The product can stay flexible only if missing module data remains honest and readable.

## Frozen Boundary

Module Plug-and-Play Validation Principles v1 is frozen as a trial architecture validation baseline after Lao Xiao secondary review PASS WITH WARNINGS and required Section 8 review-authority correction.

This freeze validates the architecture principle that modules can be hidden, restored, reordered, enabled/disabled, and combined into future package structures without breaking core workflows.

It does not authorize backend implementation, config files, feature flag engine, permission system, UI mock refactor, production execution, inventory update, WO release, WO close, ERP integration, commercial package freeze, or Step 47 Phase B.
