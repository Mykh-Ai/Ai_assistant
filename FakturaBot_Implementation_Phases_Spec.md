# FakturaBot — Implementation Phases Spec

## Purpose

This document fixes the implementation order for FakturaBot MVP so development follows a stable, evidence-based path without jumping ahead into later modules.

The goal is to move from documentation and repository bootstrap to a living MVP in small, testable phases.

Core rule:

**Do not implement later-phase complexity before earlier-phase basics are proven working.**

---

## Phase 0 — Repository & Runtime Skeleton

### Goal
Create the minimal executable project skeleton so the bot can start and the repository has a stable technical base.

### In scope
- project folder structure
- bot entrypoint
- config loading from `.env`
- base aiogram startup
- SQLite connection bootstrap
- empty handler modules
- storage folders
- prompts folder
- Docker/Docker Compose baseline

### Deliverable
A minimal bot starts successfully and responds to `/start`.

### Exit criteria
- app launches without crash
- config loads from environment
- DB connection initializes
- `/start` handler works
- repo structure matches documentation

---

## Phase 1 — Voice Input Smoke Test

### Goal
Prove the core wow-channel works technically: voice message → speech-to-text.

### In scope
- receive Telegram voice message
- download audio file
- store temporary file
- send audio to Whisper STT
- return recognized text back to Telegram chat
- basic error handling for unsupported/failed STT

### Out of scope
- invoice parsing
- PDF generation
- contact detection
- contract extraction

### Deliverable
User sends a voice message and receives recognized text back in chat.

### Exit criteria
- Telegram voice input handled end-to-end
- temporary file lifecycle is controlled
- Whisper/STT integration works reliably on test cases
- failure path gives understandable message

---

## Phase 2 — Supplier Onboarding

### Goal
Create the supplier profile required for all future invoice flows.

### In scope
- manual supplier onboarding flow
- fields:
  - name / obchodné meno
  - IČO
  - DIČ
  - IČ DPH
  - address
  - IBAN
  - SWIFT/BIC
  - email
  - default due days
  - SMTP settings
- validation of critical fields
- save/update supplier profile in DB

### Deliverable
One complete local supplier profile can be created and edited.

### Exit criteria
- supplier can be created from chat
- fields persist in DB
- validation works for key identifiers
- supplier profile can be read back correctly

---

## Phase 3 — Manual Contact Creation

### Goal
Add local customer/contact cards manually.

### In scope
- create contact flow
- edit contact flow
- save contact in local DB
- list contacts
- select contact from local address book

### Deliverable
Contacts can be manually added and reused later.

### Exit criteria
- contact record can be created
- contact record persists correctly
- local contact selection works
- no dependency on internet lookup

---

## Phase 4 — Invoice Draft From Text and Voice

### Goal
Build the first real business flow: user says or types invoice intent, system creates a draft.

### In scope
- text invoice command/input
- voice → STT → invoice parsing path
- LLM-based invoice draft extraction
- normalization of:
  - customer
  - item name
  - quantity
  - unit
  - amount
  - currency
  - issue date
  - due days
  - due date
- preview screen
- confirm / edit / cancel actions

### Core rule
AI produces a draft only.

**AI/parser → draft → validation → user confirmation**

### Deliverable
A user can create a structured invoice draft from text or voice and confirm it.

### Exit criteria
- draft object produced reliably
- preview shown before save
- validation layer blocks invalid critical values
- confirmed draft becomes invoice record

---

## Phase 5 — PDF Generation With Pay by Square QR

### Goal
Turn a confirmed invoice into a usable Slovak invoice PDF.

### In scope
- PDF invoice template
- supplier data fill-in
- customer data fill-in
- one invoice item support
- invoice number assignment at final save
- Pay by Square QR generation
- local PDF file storage

### Deliverable
A confirmed invoice generates a PDF with QR code.

### Exit criteria
- PDF file is created successfully
- invoice numbering works on final confirmation/save
- Pay by Square QR contains correct payment fields
- stored file path is linked to invoice record

---

## Phase 6 — Email Sending

### Goal
Allow one-click sending of the generated invoice PDF to the customer.

### In scope
- SMTP configuration usage
- email subject/body template
- attach generated PDF
- send email to contact email from DB
- mark invoice as sent
- delivery result feedback in chat

### Deliverable
Confirmed invoice PDF can be emailed directly from the bot.

### Exit criteria
- email sends successfully using configured SMTP
- PDF attachment included
- invoice status updated
- failures are surfaced clearly

---

## Phase 7 — Contract-Based Contact Extraction

### Goal
Allow adding a customer/contact from a contract using AI-assisted extraction.

### In scope
- upload PDF/photo contract
- save original file in `storage/contracts/`
- extract document text:
  - PDF text extraction for text-based PDFs
  - vision/OCR fallback for photos or scanned PDFs
- LLM extraction of customer block
- strict focus on customer/orderer side, not contractor side
- validation of extracted identifiers
- preview card
- user confirm / edit / cancel
- save contact with contract file reference

### Core rule
Do not auto-save extracted data.

**Python orchestrates → AI extracts → Python validates → user confirms**

### Deliverable
A contact can be created from a contract with the original document archived.

### Exit criteria
- contract file stored locally
- extracted customer preview shown
- wrong-side extraction is guarded against
- confirmed contact saved with contract path

---

## Phase Discipline

### Ordering rule
Recommended order:

1. Phase 0 — skeleton
2. Phase 1 — voice smoke test
3. Phase 2 — supplier onboarding
4. Phase 3 — manual contact creation
5. Phase 4 — invoice draft from text/voice
6. Phase 5 — PDF + QR
7. Phase 6 — email send
8. Phase 7 — contract extraction

### Why this order
- voice is a key product differentiator, so it should be proven early
- supplier and contact data must exist before real invoice generation
- PDF and email only make sense after invoice draft flow exists
- contract extraction is valuable, but belongs after the basic invoice engine works

### Anti-chaos rule
Do not implement:
- internet company lookup
- multi-tenant SaaS logic
- Google Drive
- billing
- advanced OCR pipeline
- role system
before the above phases are stable.

---

## Completion Standard

A phase is considered complete only when:
- the main flow works end-to-end
- failure states are handled reasonably
- core data persists correctly
- the result can be demonstrated manually
- the phase outcome is recorded in `PROJECT_LOG.md`

---

## Documentation Rule

Whenever a phase is completed or re-scoped:
- update `PROJECT_LOG.md`
- update relevant implementation docs if needed
- update the main TЗ if the MVP boundary changes

---

## Strategic Note

FakturaBot is not being built first as a mass SaaS platform.

The first goal is a real, demonstrable, working product for the author’s own use.

This implementation order supports that goal:
- prove the wow effect early,
- keep dependencies low,
- validate the business flow,
- turn the product into a live showcase,
- then expand carefully.