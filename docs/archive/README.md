# Documentation Archive

This folder keeps historical planning and research documents that are no longer current sources of truth.

Use active project sources first:

1. `docs/Product_Doctrine_2030.md` for product direction.
2. current repository code for implemented runtime behavior.
3. `PROJECT_LOG.md` for decision history.
4. `docs/TZ_FakturaBot.md` and focused contract docs for active product/runtime contracts.
5. `CHANGELOG.md`

Archived documents may still be useful as context, but they can describe older implementation phases, superseded assumptions, or research state that has since changed.

Current archived documents:

- `FakturaBot_Implementation_Phases_Spec.md` - early MVP phase-order plan from 2026-03-31.
- `FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md` - historical rollout plan superseded by the active LLM orchestrator contract, action registries, and Product Doctrine direction.
- `Invoice_Draft_Review_Lifecycle_Design.md` - historical design audit for draft-review lifecycle work that has since been partially implemented and split across active runtime/contracts.
- `PayBySquare_Research_Spike.md` - historical PAY by Square research/rationale; runtime now uses the internal encoder.
- `PayBySquare_Manual_Verification_Checklist.md` - historical manual QR scan checklist, linked from README as a verification reference.

Archived LLM/task documents:

- `llm/Confirmation_Decision_Audit_2026-04-14.md` - audit-only map superseded by `docs/Canonical_Decision_Resolver_Contract.md`.
- `llm/TASK_invoice_customer_raw_mention_for_alias_learning.md` - completed task context for customer raw mention / alias-learning work; active learning rules belong in the current alias-learning contract and runtime code.
