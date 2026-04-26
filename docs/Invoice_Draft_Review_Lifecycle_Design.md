# Invoice Draft Review Lifecycle Design

## Purpose

This document records a docs/code audit and design proposal for moving `upravit fakturu` from the current post-PDF approval step to the review / `nahlad faktury` step before final invoice creation, final numbering, PDF generation, and `pripravena` status.

No runtime code is changed by this document.

## Sources Audited

- `README.md`
- `docs/TZ_FakturaBot.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/Confirmation_Decision_Audit_2026-04-14.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `PROJECT_LOG.md`, especially sessions about bounded confirmation, post-PDF decision routing, edit-flow redesign, item edit wording, `novy opis polozky`, and date edit expansion
- `bot/handlers/invoice.py`
- `bot/handlers/voice.py`
- `bot/services/invoice_service.py`
- `bot/services/semantic_action_resolver.py`
- `bot/services/pdf_generator.py`
- `tests/test_invoice_state_decisions.py`
- `tests/test_invoice_intent_prerouter.py`
- `tests/test_voice_state_routing.py`

## Current Lifecycle

The current runtime lifecycle is:

1. User sends text or voice invoice input.
2. Voice is transcribed in `bot/handlers/voice.py` and routed to `process_invoice_text(...)` when there is no active invoice FSM state.
3. `process_invoice_text(...)` resolves top-level action and parses the invoice payload.
4. `_build_and_store_preview(...)` normalizes the parsed payload, resolves local contact and service aliases, computes dates and totals, then stores a temporary `invoice_draft` dict in FSM state.
5. FSM moves to `InvoiceStates.waiting_confirm`.
6. Bot sends a text preview via `_format_preview(...)`.
7. `process_invoice_preview_confirmation(...)` accepts only `ano`, `nie`, or `unknown` through bounded confirmation context `invoice_preview_confirmation`.
8. `nie` clears FSM and cancels creation.
9. `ano` creates a DB invoice row through `InvoiceService.create_invoice_with_items(...)`.
10. `create_invoice_with_items(...)` assigns `invoice_number` immediately inside the insert transaction.
11. The inserted row is saved with status `draft_pdf_ready` and `pdf_path = NULL`.
12. Runtime loads the persisted invoice and items, generates a PDF with `generate_invoice_pdf(...)`, saves `pdf_path`, sends the PDF document to the user, then moves to `InvoiceStates.waiting_pdf_decision`.
13. FSM stores:
    - `last_invoice_id`
    - `last_invoice_number`
    - `last_pdf_path`
14. `process_invoice_postpdf_decision(...)` accepts `schvalit`, `upravit`, `zrusit`, or `unknown` through bounded confirmation context `invoice_postpdf_decision`.
15. `schvalit` updates invoice status to `pripravena`, clears FSM, and keeps the invoice row and PDF.
16. `upravit` starts `start_invoice_edit_flow(...)`, which requires a persisted `invoice_id`.
17. Edit handlers mutate persisted `invoice` / `invoice_item` rows, rebuild and resend the PDF after successful edits, and return to `waiting_pdf_decision`.
18. `zrusit` deletes invoice items + invoice row, unlinks the PDF if available, clears FSM, and frees the invoice number for reuse by deleting the row.

## Current Confirmation Semantics

At the text preview / `nahlad faktury` stage, `ano` does more than acknowledge the preview:

- it persists the invoice row;
- it assigns a real invoice number;
- it generates and sends the PDF;
- it stores `last_invoice_id`;
- it transitions to post-PDF approval.

Therefore the current preview confirmation is not a pure review approval. It is a save + number allocation + PDF generation step.

`nie` is a pure draft cancellation because no DB row exists before `ano`.

`upravit` is not currently accepted in `waiting_confirm`.

## Current Draft Model

There is a temporary draft object, but it is not a DB draft:

- current preview data lives in FSM as `invoice_draft`;
- there is no persisted invoice row before `ano`;
- there are no persisted `invoice_item.id` values before `ano`;
- there is no `last_invoice_id` before `ano`;
- the current edit-flow cannot operate on this FSM-only draft because it expects either `edit_invoice_id` or `last_invoice_id` and then loads data from `InvoiceService`.

This answers the core audit questions:

- A real DB draft object does not exist before `ano`; only FSM `invoice_draft` exists.
- The invoice row is created after `ano` in `process_invoice_preview_confirmation(...)`.
- Preview could be edited without creating an invoice row, but current edit handlers cannot do that without new draft-edit plumbing.
- If the existing edit-flow is reused unchanged, it needs a persisted `invoice_id`.
- Current invoice numbering happens at DB insert in `InvoiceService.create_invoice_with_items(...)`.
- Current PDF generation happens immediately after DB insert during `ano` handling.
- Current final user approval is `schvalit` in `waiting_pdf_decision`, which sets status `pripravena`.

## Problem Statement

The current architecture makes `upravit` available only after PDF generation. This creates three issues.

First, the object being edited is already a persisted invoice row with a real invoice number and generated PDF path, even though the user has not finally approved it.

Second, the UX asks the user to approve the text preview with `ano`, then shows a PDF, then allows `upravit`. If the user spots an error in the first preview, there is no natural `upravit` branch in that state.

Third, future billing or quota logic should likely count the final generation event, not draft review activity. The current `ano` step is too heavy to serve as a free draft-review confirmation because it already creates invoice persistence and PDF side effects.

## Target Lifecycle

Target lifecycle:

```text
input
  -> AI parse / bounded canonicalization
  -> Python validation / lookup
  -> draft_created
  -> draft_review
  -> draft_editing
  -> draft_review
  -> draft_confirmed
  -> invoice_finalized
  -> pdf_generated
  -> pripravena
```

The key rule:

Until `draft_confirmed`, this is not a final invoice. It is a review draft.

Recommended user-facing preview prompt:

```text
Skontrolujte navrh faktury.
Napiste: schvalit, upravit alebo zrusit.
```

Long-term canonical actions at preview stage should be:

- `schvalit` - approve the draft and run final generation;
- `upravit` - enter draft edit-flow;
- `zrusit` - discard the draft.

For transition safety, `ano` may remain an alias for `schvalit` and `nie` may remain an alias for `zrusit`, but the primary Slovak UX should move to `schvalit / upravit / zrusit`.

## State Machine Proposal

Current states to keep:

- `waiting_input`
- `waiting_service_clarification`
- `waiting_slot_clarification`
- edit subflow control states, if refactored behind stage-aware edit adapters:
  - `waiting_edit_scope`
  - `waiting_edit_invoice_action`
  - `waiting_edit_item_target`
  - `waiting_edit_item_action`
  - `waiting_edit_invoice_number_value`
  - `waiting_edit_invoice_date_value`
  - `waiting_edit_service_value`
  - `waiting_edit_description_value`

Current states to redefine or split:

- `waiting_confirm` should become draft review decision, not yes/no save confirmation.
- `waiting_pdf_decision` should become optional compatibility/fallback/admin step, not the primary edit entry.

Recommended new naming for future clarity:

- `waiting_draft_review_decision`
- `waiting_draft_edit_scope`
- `waiting_draft_edit_invoice_action`
- `waiting_draft_edit_item_target`
- `waiting_draft_edit_item_action`
- `waiting_draft_edit_invoice_date_value`
- `waiting_draft_edit_service_value`
- `waiting_draft_edit_description_value`

However, a migration can reuse existing state names internally in Phase 2 if behavior is tightly documented and tests make the stage distinction explicit. The important part is to avoid adding another narrow patch inside `waiting_confirm` that only recognizes one keyword without changing lifecycle ownership.

## Edit-Flow Reuse Assessment

The existing edit-flow already provides useful bounded UX and resolver contracts:

- invoice-level operation selection;
- item-level operation selection;
- single-item default and multi-item target selection;
- service replacement through alias resolution;
- main item description replacement;
- item detail add/clear;
- invoice issue/delivery/due date edits;
- invoice number edit;
- voice routing for edit control states;
- text guard for precision-sensitive description state;
- PDF rebuild and return-to-approval behavior.

Parts that are reusable for draft review:

- state-scoped resolver contexts and allowed operation tokens;
- prompts and Slovak UX wording after cleanup;
- item targeting logic conceptually;
- date normalization contract;
- service alias resolution;
- validation principles: fail loud, no silent business mutation.

Parts tied to post-PDF persisted invoices:

- `start_invoice_edit_flow(...)` loads invoice by `invoice_id`;
- item targeting depends on `invoice_item.id`;
- every edit value handler reads or writes via `InvoiceService`;
- successful edits call `_rebuild_pdf_for_existing_invoice(...)`;
- post-edit success returns to `waiting_pdf_decision`;
- invoice-number edit assumes an existing invoice number and may clean up old PDF file paths;
- `last_invoice_id`, `last_invoice_number`, and `last_pdf_path` are the continuation anchors.

Conclusion:

The existing flow should not be reused unchanged for draft review. It should be extracted into stage-aware edit orchestration:

- shared bounded resolution and prompts;
- separate draft mutation backend for FSM/persisted draft data;
- separate persisted invoice mutation backend for post-PDF compatibility;
- side effects selected by stage.

## Data Model Impact

### Current Schema Constraint

The `invoice` table currently requires:

- `invoice_number TEXT NOT NULL UNIQUE`
- `status TEXT NOT NULL`
- optional `pdf_path`

Because `invoice_number` is required and generated inside invoice insert, using `invoice` rows as pre-confirmation drafts would currently reserve real invoice numbers.

### Preferred Target

Preferred target for clean lifecycle:

- no invoice row and no invoice number before final approval, or
- a separate persisted draft model that does not require final invoice number.

Recommended options:

1. FSM-only draft editing for the near-term migration.
   - Pros: no schema change, no invoice number reservation, no abandoned DB drafts.
   - Cons: less reuse of current DB-oriented edit handlers; draft can be lost with FSM/session loss.

2. Separate `invoice_draft` / `invoice_draft_item` tables.
   - Pros: clean durable draft model, no final number reservation, supports abandoned draft cleanup and future UX.
   - Cons: schema and service work; requires migration and draft cleanup policy.

3. Persist drafts in `invoice` with status `draft_review` and nullable/provisional invoice number.
   - Pros: more reuse of current service/edit structure.
   - Cons: requires changing `invoice_number NOT NULL UNIQUE`; riskier for numbering invariants; mixes draft and final invoice concepts unless carefully constrained.

Recommendation:

- Phase 2 can use FSM-only draft editing for minimal runtime risk.
- Long-term architecture should use a separate draft persistence model if durability is needed.
- Avoid using final `invoice` rows as pre-confirmation drafts unless there is a separate decision to change numbering semantics.

## Numbering Timing

Current timing:

- invoice number is assigned when `create_invoice_with_items(...)` inserts the row after `ano`.

Target timing:

- invoice number should be assigned only at `draft_confirmed -> invoice_finalized`;
- final invoice number should be generated in the same transaction as final invoice row creation;
- draft edits to issue date must not silently reserve or reshuffle final numbers;
- if issue date changes before approval, final numbering should use the approved issue date at finalization time.

Post-PDF invoice number edit should remain a compatibility/admin operation, not a normal draft review operation. In the draft review stage, "edit invoice number" should usually be hidden or treated as advanced/manual only, because the final number does not exist yet.

## PDF Generation Timing

Current timing:

- PDF is generated during `ano` handling at the text preview stage.

Target timing:

- PDF generation should happen only after the user chooses `schvalit` at draft review.
- PDF generation should be part of finalization, after final invoice row and number are created.
- `pdf_path` should be saved only after successful PDF generation.
- If PDF generation fails after invoice row creation, cleanup should preserve current fail-loud and DB-first cleanup discipline.

Storage impact:

- Draft review should not create files in `storage/invoices`.
- Draft editing should not rebuild PDFs.
- Post-final PDF regeneration should be explicit compatibility/admin behavior.

## LLM Contract Impact

Current `invoice_preview_confirmation` contract:

- expected reply type: `yes_no_confirmation`;
- allowed outputs: `ano`, `nie`, `unknown`.

Target preview decision contract:

- context name: `invoice_draft_review_decision` or upgraded `invoice_preview_confirmation`;
- expected reply type: `draft_review_decision`;
- allowed outputs: `schvalit`, `upravit`, `zrusit`, `unknown`;
- transition aliases:
  - approve/confirm/save/ano -> `schvalit`
  - edit/change/correct/upravit -> `upravit`
  - cancel/delete/discard/nie -> `zrusit`

Python must still own all side effects:

- LLM only returns the canonical token;
- Python validates the current state;
- Python mutates draft data, creates invoice rows, generates PDFs, or cancels.

Draft edit-flow contract:

- use the existing `edit_invoice` in-action/subflow operation map where possible;
- keep `edit_invoice` as a reserved top-level token;
- do not add a standalone top-level edit executor;
- make stage explicit in resolver auxiliary context:
  - `stage = draft_review` for draft edits;
  - `stage = post_pdf` for compatibility edits;
- keep precision-sensitive value capture text-first where current runtime already requires it.

## Migration Plan

### Phase 1: Docs Only

This document.

No runtime behavior change.

### Phase 2: Allow `upravit` at Review Stage

Upgrade `waiting_confirm` semantics from `ano/nie` to review decision:

- accept `schvalit`, `upravit`, `zrusit`, `unknown`;
- keep `ano` and `nie` as aliases during transition;
- `schvalit` initially may continue calling the current save + PDF path;
- `upravit` should enter draft edit mode and mutate `invoice_draft`, not create a DB invoice row;
- after each draft edit, regenerate the text preview and return to draft review;
- no PDF generation during draft edits.

This phase should not move numbering/PDF generation yet unless approved separately.

### Phase 3: Move PDF Generation After Final Approval

Make `schvalit` at draft review the finalization boundary:

- create final invoice row;
- assign final invoice number;
- generate PDF;
- save `pdf_path`;
- set status to `pripravena` or a clearly documented final/ready status;
- send final PDF.

At this point, `waiting_pdf_decision` is no longer the main approval loop.

### Phase 4: Billing / Quota Event

Add billing/quota only after lifecycle is clean:

- billable event = successful final generation;
- draft creation, preview, and draft edits remain non-billable;
- failed PDF generation should not count unless a separate policy says otherwise.

Billing is explicitly out of scope for the current task.

## Post-PDF Edit Policy

Do not remove post-PDF edit-flow immediately.

Recommended policy:

- keep post-PDF edit as fallback/admin/compatibility mode during migration;
- stop presenting it as the primary happy-path edit point once draft review edit exists;
- eventually restrict it to explicit "edit finalized invoice" semantics with stronger warnings and audit expectations;
- do not delete working post-PDF edit runtime until draft review edit has equivalent coverage and production confidence.

## Risks

### Numbering

If drafts use `invoice` rows, real invoice numbers may be reserved by abandoned drafts. The current cleanup strategy frees numbers by deleting rows, but that is not a robust long-term accounting model.

### Duplicate Drafts

Users may start several draft review flows. FSM-only drafts avoid DB clutter but are session-scoped. Persisted drafts require owner/user scoping and abandoned draft cleanup.

### Abandoned Drafts

Persisted drafts need expiration, listing, and cleanup policy. FSM-only drafts can be lost but do not pollute invoice numbering.

### PDF Cleanup

Moving PDF generation later reduces cleanup needs. During migration, old post-PDF paths still need guarded unlink behavior.

### User Confusion

The current two-stage wording has both `ano/nie` and `schvalit/upravit/zrusit`. Target UX should use one clear review vocabulary: `schvalit / upravit / zrusit`.

### DB Compatibility

Changing `invoice_number` nullability or adding draft tables is a real migration decision. It should not be bundled into a small handler patch.

### Edit-Flow Coupling

Existing handlers mix operation resolution, persistence, PDF rebuild, and next-state messaging. Reusing them for draft review requires extraction or stage-aware adapters, not direct call-through.

## Recommended Architecture

Implement a stage-aware edit orchestrator with two mutation backends.

Draft backend:

- source: FSM `invoice_draft` or future `invoice_draft` tables;
- mutates draft dict/item candidates;
- returns updated text preview;
- no invoice row requirement;
- no invoice number requirement;
- no PDF side effects.

Persisted invoice backend:

- source: `InvoiceService` by `invoice_id`;
- mutates `invoice` / `invoice_item`;
- rebuilds PDF only in post-PDF compatibility flow;
- returns to compatibility approval state.

Shared layer:

- bounded resolver contexts;
- operation tokens;
- item targeting policy;
- validation helpers;
- Slovak prompts where they are stage-neutral.

Do not implement this as a one-off `if text == "upravit"` branch in `waiting_confirm`. The lifecycle boundary has to become explicit.

## No-Runtime-Change Guarantee

This task changes documentation only.

No code, tests, DB schema, runtime routing, numbering logic, PDF generation logic, billing logic, or post-PDF edit behavior is changed by this document.
