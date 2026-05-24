# Product UX Eval Artifacts

## Purpose

This document defines where product UX evals and smoke checks should live and
how they should be recorded.

`docs/Evaluation_and_Smoke_Test_Standards.md` defines what must be evaluated.
This document defines the first repository convention for storing eval cases
and results.

## Current Status

Docs-first convention. A complete eval suite does not exist until files,
fixtures, tests/manual logs, and `PROJECT_LOG.md` evidence exist.

## Recommended Directory

Use:

```text
docs/evals/
```

Recommended initial files:

```text
docs/evals/product_truth_infohelp_smoke.md
docs/evals/customization_request_mvp_smoke.md
docs/evals/pdf_layout_manual_review.md
docs/evals/access_tenant_safety_smoke.md
```

Automated tests may later live under `tests/`, but human-readable eval
scenarios and manual results should be recorded under `docs/evals/`.

## Eval Case Format

Each scenario should record:

```text
eval_id
feature_or_layer
declared_maturity_level
account_state
input_channel
user_input
expected_product_truth_status
expected_response_behavior
forbidden_behavior
side_effect_expectation
automation_status
last_result
last_run_at
notes
```

For manual checks, also record:

```text
observed_behavior
pass_fail
artifact_paths
remaining_risk
reviewer
```

## Minimum First Eval Set

For Product Truth + InfoHelp MVP:

- user asks whether invoice email sending is supported;
- user asks whether Google Drive invoice storage is supported;
- user asks whether SMS reminders are supported;
- user asks how to create an invoice;
- user asks for old/custom PDF template;
- user asks for accounting export;
- unauthorized user asks a capability question;
- user with missing setup asks why invoice creation cannot proceed.

For customization request MVP:

- draft request for Google Drive storage;
- draft request for old PDF template;
- submit unanswered product question for admin review;
- cancel before save;
- edit draft;
- approve draft;
- high-risk request requires admin review;
- credentials/secrets pasted into chat are rejected.

For Admin Response / Human Review Loop:

- bot cannot answer product question and asks to submit for admin review;
- user confirms and the review item is saved;
- admin sends an `answer` response and user receives it;
- future/next slice: admin rejects with reason and user receives the
  explanation;
- future/next slice: admin asks for clarification and user receives it as
  one-way outbound copy, without an automatic structured reply-thread workflow;
- confirmed response metadata/text persists before Telegram send attempt and
  delivery status updates after the send result;
- failed send keeps the response persisted with `send_failed` and no automatic
  retry;
- MVP stores only latest response metadata, not multi-response/threaded
  conversation history;
- out-of-domain/spam do not create a human-review item;
- possible Product Truth gap does not auto-mutate Product Truth.

Current Admin Response MVP implements only the explicit admin `answer` send
path. Rejection-reason and clarification-request response kinds remain future
eval scenarios until command/runtime support exists.

For PDF/layout:

- normal invoice;
- long customer/supplier names;
- long item description;
- multi-item invoice;
- QR placement;
- footer placement;
- optional custom block if implemented.

## Result Policy

Do not call a layer complete unless the relevant eval result is recorded.

If evals are not run, the final implementation summary must say why and must
not claim runtime completion beyond the tested scope.

## No-Go Rules

Do not:

- replace eval artifacts with vague confidence claims;
- hide failed manual checks;
- call Level 2+ complete without Product Truth/InfoHelp scenarios;
- accept PDF/layout changes without rendered review or regression evidence;
- store secrets or private customer data in eval artifacts.
