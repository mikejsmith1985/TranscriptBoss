# Specification Quality Checklist: External Audio Import & Transcript Reconciliation for Omi

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-05
**Last Updated**: 2026-08-05 (iteration 2 — clarifications resolved)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

**Iteration 2 — all checklist items pass.** The three open questions are resolved:

| Question | Resolution | Where it landed |
|---|---|---|
| OQ-1 — import surface | Desktop component does the work; a thin linked surface handles authorisation, queue review and approvals | FR-006 |
| OQ-2 — who transcribes and pays | Tiered strategy, defaulting to the user's own Omi pipeline at zero cost; metered services require explicit per-account consent | Transcription Strategy, FR-015 – FR-021 |
| OQ-3 — superseded originals | Cross-reference by default; opt-in advanced mode using the user's own personal credentials for cleanup | FR-047, FR-048 |

**Correction recorded against iteration 1.** Iteration 1 stated that Omi will not transcribe supplied audio and that the product must therefore buy transcription. That is true only of Omi's REST import API. Omi's app-device protocol is public, third-party recorder integration is explicitly invited, and Omi's free plan includes unlimited on-phone transcription. The specification was rewritten around this; it changes the product's economics from metered to free and is the reason the project is viable at all.

**One item deliberately retained that reads like an implementation detail.** The *Platform Reality Check* and *Transcription Strategy* sections name Omi platform capabilities and the absence of an edit path. These are external product constraints that bind requirements and set the product's cost model — not solution choices. Removing them would leave FR-015, FR-021, FR-028, FR-031 and FR-047 unexplained.

**One gate remains before `/speckit-plan` can finalise.** The *Critical Assumption Under Test* — whether audio can be delivered to Omi faster than it was recorded — is not settled by public documentation and must be answered by experiment. It does not block specification: SC-014 requires the product to remain shippable under every outcome, and only the default tier and the promised speed change. It does bind the plan, which must not assume the favourable outcome.
