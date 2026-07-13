# Технічне завдання: FakturaBot

## Telegram-бот для створення фактур з голосу, тексту та договору

**Версія:** 2.0 Concept Update  
**Дата:** 30.03.2026  
**Автор:** Mykhailo Alieksieienko

---

## 2026-05-09 Addendum: state reset and read-only invoice view

Approved users may view an already created outgoing invoice through the canonical top-level action `show_existing_invoice`. User wording such as “show/open invoice/faktura 04” must resolve to read-only invoice display, not to persisted invoice editing. Python resolves the invoice only inside the current supplier scope, sends the invoice summary and available PDF, and then clears FSM state / returns the bot to idle.

Approved users may ask read-only questions about already saved outgoing invoices through canonical top-level action `invoice_analytics`. Simple yearly total/count wording such as "Na aku sumu som vystavil faktury tento rok?" or "Suhrn faktur za 2026" uses an internal deterministic fast path with Python-owned period parsing and tenant-scoped invoice aggregation by `supplier_telegram_id` and `issue_date`. The old `invoice_period_summary` behavior remains only as an internal analytics strategy, not as a competing user-facing top-level action. It must not create/edit/delete invoices, generate PDFs, summarize receipts, expenses, incoming invoices, bank data, VAT, tax, or claim broad accounting analytics.

Persisted invoice editing remains the separate canonical action `edit_existing_invoice`. User wording that means edit/change/correct an invoice by number may enter the bounded invoice edit FSM after Python supplier-scoped lookup.

System/read-only surfaces are stateless interruptions: `/start`, `/menu`, `/moj_profil` when the profile exists, `/blocek`, `show_existing_invoice`, read-only `invoice_analytics`, and read-only `accounting_document_analytics` answers may clear the current FSM state and show their result without leaving the user in a workflow.

Global state cancellation is supported through `/cancel` and shared DecisionResolver-backed cancel wording in text or voice transcripts, such as `zrušiť`, `скасувати`, `відмінити`, `відминити`, `отменить`, and “почни з початку”. Cancellation must be state-aware: temporary Document Intake/OfficeFlow staging is cleaned; draft invoice states are cleared; newly generated unconfirmed post-PDF invoices keep the existing cancel cleanup behavior; persisted invoice edit cancellation only exits edit mode and must not delete the already stored invoice. Voice cancellation must not bypass exact typed destructive confirmations.

---

## 2026-06-15 Addendum: automatic overdue invoice follow-up

The bot runtime automatically checks saved outgoing invoices for overdue
`due_date` values through an in-process aiogram background scheduler. The
default check interval is once per day (`86400` seconds). The Phase 1 runtime
detects invoices where `due_date` is before today, no paid/muted follow-up
state exists, and any `remind_after` value is due. Missing
`invoice_followup_state` rows are treated as unpaid and active for legacy
invoices.

The reminder is tenant-scoped by `supplier_telegram_id` and offers three
Telegram decisions: mark as paid, remind later, or do not remind again. These
decisions persist only follow-up state in `invoice_followup_state`; the existing
local invoice PDF generation and `invoice.pdf_path` behavior are unchanged.

Current status is `partial`: automatic Telegram reminders are implemented
inside the bot process, while email reminders, SMS reminders, bank matching,
accounting export, and external cron/worker deployment remain out of scope.

When owner OAuth Google Drive archive is configured, marking an invoice paid or
using an equivalent due-date control event enqueues the existing local invoice
PDF for Drive upload through the archive worker. If Drive is disabled or not
configured, the runtime falls back to the deterministic local Drive archive
stub. Local invoice PDFs are not deleted in this MVP.

---

## 2026-06-22 Addendum: manual mark-paid action for saved outgoing invoices

Approved users may mark one already saved outgoing invoice as paid/uhradena through canonical top-level action `mark_existing_invoice_paid`. Natural text or voice such as `Oznac fakturu 06 ako uhradenu` resolves only to a bounded intent; Python still performs supplier-scoped invoice lookup, handles ambiguity, shows a confirmation step, and writes state only after the user confirms.

The action writes bot-local payment/follow-up state through `invoice_followup_state` and `InvoiceFollowupService.mark_paid()`. It does not edit invoice content, change invoice PDF paths, delete PDFs, confirm bank settlement, or perform bank matching. When owner OAuth Google Drive archive is enabled and configured, the action may enqueue the existing local PDF for Drive upload; otherwise it records the existing local Drive archive stub.

Voice may start the action and may answer the bounded confirmation. Confirmation uses shared `yes_no` DecisionResolver context `mark_existing_invoice_paid_confirm`, with buttons `Označiť ako uhradenú` and `Späť do hlavného menu`.

---

## 2026-06-16 Addendum: invoice analytics runtime pilot

Approved users may ask broader read-only analytics questions over their saved
outgoing invoices through canonical top-level action `invoice_analytics`.
Examples include counts, sums, period comparisons, customer/month/currency
grouping, normalized bot payment-status grouping, and bounded lists of
matching saved outgoing invoices.

Current status is `partial`: the pilot reads only already persisted outgoing
invoice rows for the current supplier scope. Python builds a sanitized
dataframe, injects the current runtime date for relative questions, normalizes
bot payment state into `pending_payment`, `paid`, `overdue`, or `unknown`,
validates any LLM-planned analysis code, and executes it without DB/file/
network/write access. The dataframe does not expose `pdf_path` or absolute
storage paths. Payment status is the bot's stored/derived state from follow-up
data and due dates, not bank-confirmed settlement.

The pilot does not create, edit, delete, send, archive, mark paid, or generate
invoices/PDFs. It does not analyze receipts, expenses, incoming invoices, bank
statements, cashflow, VAT, tax, or accounting-export data. It must not claim
full accounting analytics. The deterministic yearly summary remains
implemented as an internal fast path under `invoice_analytics`; month-specific,
multi-month, comparison, customer, status, grouping, list, and average
questions stay in the safe analytics runtime.

---

## 2026-06-18 Addendum: Safe Data Analyst runtime checklist and analytics boundaries

`docs/llm/Safe_Data_Analyst_Runtime_Checklist.md` is now the reusable
architecture checklist for future read-only analytics runtimes. The checklist
defines the required authority split, data boundary, sandbox, Product Truth,
language, testing, and unsupported-domain controls before a new data analyst
runtime can be considered product-safe.

`docs/llm/Invoice_Analytics_Runtime_Contract.md` is the first implemented
domain contract that applies the checklist. It remains invoice-specific:
current authorized supplier, saved outgoing invoices only, sanitized dataframe,
normalized bot payment status, Python-owned execution, and no write
operations.

Final business answers in end-user flows must use Slovak business language by
default. User input language or planner metadata must not override that policy
unless a future Python-owned product decision explicitly changes it.

Controlled receipt/incoming-invoice categories are now partially implemented inside the existing `/add_blocek` / `/dodat_blocek` accounting Document Intake preview flow. This is not a standalone top-level action. Python owns the category registry, allowed-category payload, validation, confirmation, and persistence. The LMM may suggest only bounded candidates from Python-provided categories or `unknown_review`; it must not create categories, decide tax treatment, or execute side effects. Workspace categories are created only after typed label plus explicit confirmation, and confirmed metadata stores category ids with `label_snapshot`. The category preview, unknown-category choice, duplicate warning, new-category confirmation, similar-category warning, and reasonable category selection steps may show Telegram reply buttons; those buttons feed the same state-aware DecisionResolver paths as text and voice. After confirmed save, the user sees a clean saved message with `/add_blocek`, `/blocek`, and `/menu` next steps instead of an internal metadata path.

Confirmed receipt/blocek save is date-bounded for the current controlled rollout: receipt issue dates before 2026 are rejected by Python validation before storage path, metadata JSON, DB archive state, or Google Drive archive jobs are created. This guard is specific to receipts; incoming-invoice date policy remains the existing validation contract unless changed separately.

Receipt/blocek analytics must not be built or claimed before all of these exist:

1. a separate read-only analytics contract and dataset;
2. evaluated category aggregation semantics;
3. Python validation of allowed analytics questions;
4. tenant-scoped execution without writes;
5. Product Truth and InfoHelp status for analytics;
6. tests and product UX smoke for category totals/reporting;
7. explicit no-tax-advice and no-accounting-export boundaries.

Raw OCR/LMM extraction and confirmed intake categories are not tax deductibility evidence, accounting approval, accounting export data, or a basis for spending analytics until a separate analytics layer proves those controls.

---

## 2026-06-21 Addendum: accounting document analytics runtime pilot

Approved users may ask read-only analytics questions over confirmed
receipts/bloceky and incoming invoices/prijate faktury through canonical
top-level action `accounting_document_analytics`.

This runtime is separate from `invoice_analytics`. `invoice_analytics` covers
saved outgoing invoices and income-side questions. `accounting_document_analytics`
covers expense-side accounting documents only: confirmed receipts and incoming
invoices stored in the current accounting workspace.

Python owns the workspace scope, metadata scan, dataframe schema, current-date
injection, code validation, process-isolated execution, and final Slovak answer
grounding. LLM may only plan bounded pandas code over Python-provided
`accounting_documents_df` and cannot access DB/storage/files/network or cause
side effects.

Supported partial questions include counts, sums, vendor/category/month or
period grouping, document-type grouping, comparisons, limited lists, averages,
and top rankings from confirmed metadata. Old metadata without category remains
readable as `uncategorized` / `Bez kategorie`.

The pilot must not create, edit, delete, save, or persist documents,
categories, files, registry entries, DB rows, suggested labels, or any other
side effect. It must not answer outgoing invoice analytics, bank/cashflow,
VAT/tax reports, accounting export, tax deductibility, settlement, or full
accounting judgement from this dataset.

---

## 2026-05-06 Addendum: STT transcription context prompt

Voice transcription may pass a compact STT context prompt to the transcription model. The prompt describes the expected FakturaBot / OfficeFlow domain and possible spoken languages: Slovak, Ukrainian, Russian, English, and mixed Surzhyk / mixed Slovak-Ukrainian-Russian-English speech.

The STT prompt is not a command router. It must not decide canonical actions, confirmations, or business side effects. It only helps the transcription layer avoid unrelated-language guesses such as Portuguese or Vietnamese artifacts and preserve mixed-language business wording, company names, invoice numbers, amounts, dates, and common invoice/accounting terms.

After transcription, Python authorization, FSM state, Canonical DecisionResolver, bounded Semantic Action Resolver, and Python-side validation remain the execution authority.

---

## 2026-05-06 Addendum: invoice raw customer mention for confirmed aliases

Invoice draft extraction may return an optional `biznis_sk.odberatel_raw_mention` field. This field preserves the exact or near-exact phrase from the original text/STT transcript that names the customer/company, while `biznis_sk.odberatel_kandidat` remains the normalized lookup-ready customer candidate.

The raw mention is candidate trace data only. It must not include the full invoice command, service description, amount, date, invoice number, IBAN, email, phone number, payment terms, or unrelated invoice details. If the customer phrase cannot be isolated safely, it remains empty/null.

Python remains the authority for contact lookup, ambiguity handling, preview display, and alias persistence. A raw customer mention may become a confirmed contact alias only after the matched contact is validated in the current supplier scope and the invoice preview is approved or the user explicitly confirms the alias.

The extraction prompt may also preserve optional service raw mention fields: `biznis_sk.service_raw_mention` and `biznis_sk.items[].service_raw_mention`. Python may use these fields as candidates for confirmed semantic service aliases after the invoice preview is approved, but only when the service has already resolved to one existing manual `/sluzbu` mapping for the current supplier.

Service self-learning stores practical STT/text variants in `confirmed_semantic_alias` under the `invoice_service` domain and points them to the existing `supplier_service_alias` row. It does not create or edit `/sluzbu` manual mappings, does not rewrite service display titles, and does not mutate invoice item descriptions. The default cap is 10 confirmed semantic aliases per service target per supplier/domain.

---

## 2026-05-06 Addendum: in-action voice control vs exact value entry

Voice may be used inside an active FSM flow to choose a bounded action, field, item, route, or confirmation option when Python provides the allowed outputs and validates the active state.

Voice may also provide the natural-language invoice request while the user is in `InvoiceStates.waiting_input` after `/invoice`; it follows the same bounded invoice draft extraction path as idle voice invoice creation.

Voice must not fill precision-sensitive exact values. Exact invoice numbers, invoice item numeric values, supplier/contact identifiers, IBAN, IČO, DIČ, IČ DPH, email, final item descriptions, service alias names, and destructive exact confirmations remain text-first.

Supplier profile edit supports voice for choosing which profile field to edit. The new field value itself remains text-only. Contact missing-field intake is also text-first because it captures business data, not a control command.

---

## 2026-05-06 Addendum: top-level action implementation standard

For the current Phase 2 voice-capable runtime, a new canonical top-level action is implemented only when the runtime route, canonical registry entry, bounded resolver integration, command/text entry path, tests, documentation, and voice reachability are aligned.

If voice is inappropriate for the action, the exclusion must be explicit and tested. Valid exclusions include exact typed destructive confirmations, precision-sensitive identifiers and numbers, email/IBAN/tax IDs, exact service/contact/invoice values, and upload steps that require a photo or PDF.

Reserved registry entries, documentation-only names, or resolver hints without a Python route are not runtime implementation.

---

## 2026-05-05 Addendum: top-level voice command reachability

Approved users may reach the existing top-level/system flows by voice or natural text through the bounded semantic resolver when the resolved canonical action is in Python-provided `allowed_actions`:
- `start` routes to the existing `/start` setup/status flow;
- `show_supplier_profile` routes to `/moj_profil`;
- `edit_supplier` routes to `/upravit_profil`;
- `show_recent_accounting_documents` routes to the existing read-only `/blocek` recent accounting documents view;
- `add_receipt` routes to the existing `/add_blocek`/`/dodat_blocek` upload-waiting FSM.

This does not make LLM/STT an executor. Python authorization still runs before STT/LLM/LMM, the resolver returns only an allowed canonical token or `unknown`, and Python/FSM executes existing routes.

Receipt/blocek voice intent starts the upload flow and asks for a photo/PDF. It must not create an outgoing invoice, extract receipt metadata, or save an accounting document from voice text alone. If OCR/LMM recognition is wrong later, the correction path remains a better photo/PDF re-upload, not arbitrary manual editing as if the receipt were a generated invoice.

`edit_invoice` remains reserved for in-action/FSM invoice draft editing. Persisted invoice editing remains the separate canonical runtime action `edit_existing_invoice`. `delete_user_database` is implemented as a separate destructive leave/reset flow with exact typed final confirmation only.

---

## 2026-05-03 Addendum: supplier onboarding invoice-number baseline

Controlled user onboarding must collect one additional invoice setting before the default due-days question:
- first invoice number FakturaBot should generate for the current calendar year;
- format stays canonical `RRRRNNNN`, for example `20260025`;
- the setting is tenant-scoped by `supplier_telegram_id` and `issue_year`.

Runtime numbering rule:
- if the supplier has no bot-created invoice in that year, the next generated number is the configured first number;
- if bot-created invoices already exist, the next generated number is the larger of the configured first number and the next number after the supplier's latest invoice;
- the setting does not import historical external invoices and does not create placeholder invoice rows.

Supplier email sending remains optional in the controlled dry run. Legacy local/server SQLite databases with `supplier.smtp_host`, `supplier.smtp_user`, or `supplier.smtp_pass` as `NOT NULL` must be migrated by application bootstrap to the current nullable schema so supplier onboarding can save without SMTP credentials.

## 2026-07-01 Addendum: contact wizard recovery and inactivity timeout

Manual and AI-assisted contact intake is text-first for precision-sensitive company/contact values. The first company-name prompt and contact recovery hints must also expose a clickable `/menu` escape so the user is not trapped if they do not want to continue the contact flow.

Contact intake FSM state expires after five minutes of inactivity. On the next contact-state input after expiry, Python clears the FSM and answers that contact creation ended because of inactivity. Active contact input before expiry refreshes the five-minute window. This does not add voice entry for exact contact values and does not create or delete persisted contact data.
## 2026-05-03 Addendum: contact address and optional customer email

Customer/contact onboarding must not require the customer's email address. If the user does not provide it, the contact may still be saved and the local SQLite `contact.email` value may remain an empty string for compatibility with the current schema.

The contact address must include a house/building number. City-only or street-only values are not sufficient for invoice contact data and must be clarified before contact confirmation.

When a contact email is empty, the generated invoice PDF must omit the customer `Email:` line entirely instead of rendering an empty value or placeholder. Supplier email remains part of the supplier profile block.

## 2026-05-03 Addendum: voice delete intent and known STT `ano` noise

Explicit voice/text requests to delete an existing invoice must route to the bounded top-level action `delete_existing_invoice`, not to generic `create_invoice`, whenever the user input contains a clear delete/remove verb together with an invoice/faktura target. The rule is independent of the invoice number value; numbers such as `7`, `10`, `11`, or full canonical invoice numbers are all references to be resolved later by supplier-scoped Python lookup.

Deletion must remain outside the `create_invoice` flow. `delete_existing_invoice` still requires a separate shared `yes_no` DecisionResolver confirmation before Python deletes invoice rows or PDF files.

The observed STT phrase `Ah, nao` / `Ah, nao!` is treated narrowly as Slovak `ano` in confirmation contexts because the current STT repeatedly produces that phrase for spoken `ano`. This is an STT-noise compatibility rule, not broad Portuguese language support.

## 2026-05-03 Addendum: confirmed semantic aliases for invoice customer lookup

When `create_invoice` cannot directly resolve the extracted customer candidate but the existing supplier-scoped contact lookup finds exactly one safe high-confidence candidate, the bot may use that local contact directly in the invoice preview instead of asking a separate `áno / nie` alias question. The preview must show the canonical local contact name, and the invoice is still saved only after the user approves the preview.

The bot may save a supplier-scoped confirmed alias from the cleaned extracted customer candidate to that contact only after either an explicit shared `yes_no` DecisionResolver confirmation or approval of an invoice preview that visibly used the resolved contact. The raw full STT transcript must not be stored as an alias. If the user rejects/cancels the suggestion or preview, the flow must not save an alias.

Country suffix tokens are safety-sensitive. A candidate without a country suffix may be matched to one unique stored country-suffixed contact when it is the only plausible high-confidence target. If both `SK` and `CZ` variants are plausible and the user omits the country token, the bot must ask for clarification. A user candidate with an explicit country token such as `CZ` must not silently match an `SK` contact.

## 2026-05-04 Addendum: staged profile onboarding and user database deletion wording

After administrator approval, the user is authorized in `authorized_users` and the access request is marked approved. The user-facing approval notification must not say that the supplier profile already exists. It may say that the user's FakturaBot working database is ready, and the next action is `/start`.

For an approved user without a supplier profile, `/start` must point to `/moj_profil` as the main user-facing profile command. `/supplier` remains a legacy/technical alias for the same supplier onboarding surface.

After the supplier profile is saved, the bot must guide the user to one next step only: create the first service through `/sluzbu`. It must not present `/contact` and `/invoice` in the same first next-step message for a new user.

`/moj_profil` is the user-facing profile surface. If no supplier profile exists, it starts supplier profile creation. If the profile exists, it shows a read-only profile summary and points to `/upravit_profil` for targeted field edits.

`/upravit_profil` edits one supplier-profile field at a time and must validate the new value in Python before saving. The save confirmation uses the shared `yes_no` DecisionResolver context `supplier_profile_edit_confirm`.

Full user database deletion is the destructive top-level action `delete_user_database`. User-facing entry examples are `/vymazat_databazu`, `Chcem vymazať moju databázu`, and similar voice/text phrases. These entries only start a warning/confirmation FSM. The manual destructive confirmation phrase is exactly `vymazať databázu`; it must be typed as text, and voice must be rejected in the final confirmation state. Successful confirmation deletes the user's scoped FakturaBot business data/files, marks `authorized_users.status = deleted_database`, marks `access_requests.status = deleted_database`, removes active access, and requires a fresh `/start` access request plus admin approval before the user can use the bot again. Old business data is not restored after reapproval.

After the first staged setup, `/start` becomes a deterministic setup/status router for approved users:
- approved without supplier profile: show only the next step `/moj_profil`;
- supplier profile exists but no service alias exists: show only the next step `/sluzbu`;
- supplier profile and service alias exist but no contact exists: show only the next step `/contact`;
- supplier profile, service alias, and contacts exist: show the main operational menu with `/invoice`, read-only invoice view wording, existing-invoice edit wording, `/add_blocek`, `/blocek`, `/upravit_profil`, and `/moj_profil`.

`/menu` should show the broader user-facing capability list, including create/show/edit/delete existing invoice flows, setup/profile/contact/service actions, accounting document actions, and the user database deletion entry. The database deletion entry must make clear that it deletes the user's scoped data and removes bot access; it is not a simple restart command. It must not expose internal Python canonical tokens as slash commands when no such Telegram command exists.

After a targeted `/upravit_profil` save, the bot must return the same staged/status navigation as `/start`: novice users continue to the next missing setup step, while ready users see the main operational menu rather than the first-service onboarding prompt.

For accounting receipts, `/blocek` is the user-facing read-only recent receipts/accounting-documents view. `/add_blocek` and `/dodat_blocek` start adding a new receipt/blocek through the existing accounting Document Intake flow. `/doklad` remains a broader legacy/reserved document-intake entry and must not be promoted as the main receipt command in `/start`.

## 1. Опис продукту

FakturaBot — це Telegram-бот, який допомагає створювати фактури зі смартфона через голосові повідомлення, текстові команди та витяг реквізитів із договору.

На старті це **не масовий SaaS**, а **практична демонстраційна вітрина та робочий інструмент для самого автора**. Перший інстанс розгортається на власному сервері автора, де автор є першим реальним користувачем.

Проєкт розглядається як **перша вітрина для ширшої моделі**: розробка та розгортання Telegram-ботів під конкретні бізнес-процеси клієнта.

Перший конкретний кейс — **бот для фактур**. У майбутньому на тому ж підході можуть будуватись боти для:
- прийому замовлень,
- резервацій,
- заявок,
- запису клієнтів,
- сервісних повідомлень.

Docs-first архітектурний напрямок для цієї ширшої моделі зафіксовано як **OfficeFlow**: umbrella-система для документних workflows малого бізнесу. У цій моделі FakturaBot залишається модулем outgoing invoices. Поточне ТЗ не змінює runtime invoice flow, supplier SZČO profile, `pdf_path`, DB schema або поточну структуру `storage/invoices/`.

### 1.1 Стартова бізнес-модель

На першому етапі FakturaBot продається не як універсальна SaaS-платформа, а як:
- розгортання бота,
- налаштування під конкретний процес,
- підтримка,
- подальші доопрацювання,
- кастомізація під клієнта.

Формат позиціонування:

**«Роблю та розгортаю Telegram-ботів під задачі малого бізнесу»**

FakturaBot є першим демонстраційним продуктом у цій лінійці.

### 1.2 Чому не класичний SaaS

Масовий multi-tenant SaaS для цього продукту на старті не є пріоритетом, тому що:
- у різних користувачів різна мова і манера диктування,
- різні скорочення назв робіт,
- різні шаблони документів,
- різні бізнес-процеси,
- висока відповідальність за дані та інфраструктуру,
- занадто велика складність для першої версії.

Замість цього обирається **гібридна модель**:
- спільне технічне ядро,
- індивідуальні налаштування,
- окреме розгортання,
- кастомізація під потреби конкретного користувача.

### 1.3 Головна цінність MVP

Головна цінність першої версії:
- надиктувати фактуру голосом,
- отримати структуровану чернетку,
- підтвердити,
- згенерувати PDF з QR-кодом Pay by Square,
- зберегти/показати PDF; real outbound email sending is not current runtime support,
- зберегти історію та контрагентів.

Ключовий wow-ефект MVP — **голосовий сценарій + PDF з QR**. Real outbound email/send-by-one-click is a planned/unsupported integration until current runtime Product Truth proves otherwise.

### 1.4 Ключовий принцип продукту

AI не є джерелом істини. У v2.0 контракт AI базується на **Bounded Semantic Canonicalization**: Python задає контекст і дозволені канонічні виходи, LLM повертає один дозволений канонічний вихід або `unknown`, Python валідовує і виконує дії.

Додатковий project-level принцип для confirmation-like відповідей зафіксовано в `docs/Canonical_Decision_Resolver_Contract.md`: усі рішення типу approve/edit/cancel або yes/no мають проходити через спільний Canonical DecisionResolver. Поточні локальні парсери `ano/nie` або `schvalit/upravit/zrusit` вважаються технічним боргом і мають мігрувати після тестів; це не означає, що спільний resolver уже повністю впроваджений у runtime.

Phase 1 migration частково впроваджує цей принцип у runtime: поточні invoice preview/post-PDF, contact confirmation, onboarding confirmation і existing-invoice delete confirmation flows проходять через `bot/services/decision_resolver.py`. Це не додає OfficeFlow Document Intake runtime, Telegram button callbacks, DB schema changes, storage migration або зміну `pdf_path`.

Decision UI Layer Phase 1 adds Telegram inline buttons only for stable confirmation flows. Buttons emit canonical `decision:*` tokens and must converge into the same state-aware execution path as text/voice decisions after DecisionResolver normalization. Callback queries must pass authorization before any side effect. Phase 1 does not add standalone contract archive/save buttons, OfficeFlow route/document-type buttons, accounting-document edit buttons, DB schema changes, storage model changes, server actions, or LLM prompt changes.

---

## 2. Архітектурна концепція

### 2.1 Current controlled dry-run deployment model

Це активна поточна модель для контрольованого dry run і безпечного onboarding другого реального користувача:
- один shared Telegram bot token (`BOT_TOKEN`);
- один backend process / deployable service;
- одна SQLite DB;
- кілька allowlisted Telegram users через `ALLOWED_TELEGRAM_USER_IDS`;
- strict tenant isolation by `telegram_id` / `supplier_telegram_id`;
- без per-user Telegram bot tokens;
- без public SaaS;
- без public self-service onboarding;
- без automatic signup;
- без збору per-user SMTP credentials.

Unknown Telegram users must be blocked neutrally before onboarding or business data mutation. Unknown users must not create supplier profiles, contacts, invoices, invoice PDFs, accounting documents, metadata, temporary upload files, tenant storage directories, or any other business/runtime artifacts, and must not trigger LLM, STT, or LMM calls.

This controlled shared-bot model is the current runtime model for safely onboarding the second user. It does not replace the future commercial / installation-as-a-service deployment model.

Ціль цієї версії:
- отримати живий продукт;
- пройти повний user flow на реальних даних власника;
- безпечно додати другого контрольованого користувача;
- перевірити tenant isolation перед будь-яким ширшим onboarding;
- на цій основі приймати окреме рішення про майбутнє комерційне розгортання та кастомізацію.

### 2.2 Future commercial / installation-as-a-service deployment model

Після успішного MVP базове ядро може підтримувати future commercial / installation-as-a-service model. Це не поточний runtime:
- один клієнт = один інстанс або інша окрема deployment/workspace одиниця;
- possible separate Telegram bot token per client;
- possible per-client VPS/container/workspace;
- possible separate DB/storage/API keys/secrets per client;
- окремі налаштування;
- окремі реквізити;
- окремий prompt/context;
- окремий словник скорочень;
- окремі сценарії;
- possible SaaS/admin UI, billing, support tooling, and stronger secrets management.

Ця future commercial / installation-as-a-service model не є поточним dry-run runtime і не є Phase 2 access-request automation. Її не можна трактувати як уже реалізовану або як вимогу для контрольованого другого користувача. Per-client Telegram bot tokens, per-client VPS/container, and per-client API keys are future/commercial options only.

OfficeFlow has a deployed target-schema partial multi-workspace runtime: workspace context, isolated supplier/contact/invoice/accounting/work-time ownership, /profily, explicit switch_business_profile, and additional supplier-profile onboarding are implemented. The production legacy database was migrated on 2026-07-13 at exact SHA 7408399239eba8cb221ba7b6e7267ccf1d60a867 after a frozen dry-run, verified host backup, fingerprint-pinned apply, post-apply audit, and bounded smoke. Public profile runtime readiness is proven; full same-user two-profile conversation acceptance remains pending until a real second profile is created through the bot and text/voice switching plus lightweight object isolation are exercised.

### 2.3 Стек технологій

| Компонент | Технологія |
|-----------|-----------|
| Мова | Python 3.11+ |
| Telegram | aiogram 3.x |
| STT | Whisper API |
| LLM-парсинг | OpenAI API / Claude API |
| PDF | reportlab |
| QR-код (Pay by Square) | internal PAY by square encoder + qrcode |
| Email | smtplib (SMTP/TLS) |
| База даних | SQLite |
| Деплой | Docker |

### 2.4 Що НЕ входить у першу версію

У v1.0 не входить:
- класичний SaaS,
- multi-tenant архітектура,
- lookup контрагентів з інтернету,
- FinStat,
- ORSR інтеграція,
- OCR як окремий складний модуль,
- автоматичне підтягування даних з реєстрів,
- Google Drive,
- складні звіти,
- billing,
- кабінет користувача.

---

## 3. Концепція MVP v1.0

### 3.1 Що входить у першу версію

Обов’язково:
- Telegram-бот,
- голосові повідомлення,
- текстові повідомлення,
- розпізнавання голосу в текст,
- AI-побудова invoice draft,
- ручне додавання постачальника,
- ручне додавання контрагента,
- додавання контрагента з договору через AI,
- локальна адресна книга,
- збереження оригіналу договору в локальне сховище,
- генерація PDF з QR-кодом Pay by Square,
- прев’ю перед підтвердженням,
- PDF generation and local/Telegram access; real outbound email sending is not current runtime support,
- історія фактур,
- статуси фактур,
- автонумерація фактур (RRRRNNNN, послідовна číselná rada).

### 3.2 Що свідомо відкладено

У v1.0 не робиться:
- підтягування компаній з інтернету,
- пошук через ORSR / ŽRSR / FinStat,
- повний OCR-конвеєр,
- універсальний парсинг будь-яких документів,
- Google Drive,
- складна бухгалтерська аналітика,
- повноцінна багатокористувацька рольова система.

---

## 4. Основні сценарії користувача

### 4.1 Онбординг постачальника

Перший запуск бота повинен зібрати реквізити постачальника.

На v1.0 основний сценарій — **вручну**.

Поля:
- ім’я / obchodné meno,
- IČO,
- DIČ,
- IČ DPH,
- адреса,
- IBAN,
- SWIFT/BIC,
- email,
- стандартна splatnosť у днях.

Зберігається один профіль постачальника.

### 4.2 Додавання контрагента вручну

Користувач вручну вводить:
- назву компанії,
- адресу,
- IČO,
- DIČ,
- IČ DPH,
- email,
- контактну особу.

Після підтвердження бот зберігає картку у локальній БД.

### 4.3 Додавання контрагента з договору

Це один із ключових сценаріїв оновленої концепції.

Flow:
1. Користувач надсилає PDF або фото договору.
2. Python зберігає оригінал у `storage/contracts/` (для архіву).
3. Python витягує текст із документа (для text-based PDF — PDF text extraction; для фото або scan-PDF — vision/OCR fallback).
4. Python викликає AI з чітким промптом.
5. AI повинен знайти саме **замовника / objednávateľ**, а не виконавця / zhotoviteľ.
6. AI повертає строго структурований JSON.
7. Python валідовує поля (IČO = 8 цифр, DIČ = 10 цифр, назва не порожня).
8. Бот показує картку контрагента.
9. Користувач підтверджує або редагує.
10. Контрагент зберігається в локальній БД з посиланням на оригінал договору.

#### 4.3.1 Критичний принцип

Дані з договору **ніколи не зберігаються автоматично без підтвердження користувача**.

#### 4.3.2 Модель роботи

Не робити «OCR все вирішив».

Правильна модель:

**Python orchestrates → AI extracts → Python validates → user reviews/edits draft → user approves final generation**

### 4.4 Створення фактури голосом

Це центральний wow-сценарій продукту.

Приклад диктування:

> «Тесла Словакія за оправи один кус там 2000 євр, датум виставлення 30 марта 2026, сплатност 30 днів»

#### 4.4.1 Що повинен зробити бот

1. Прийняти голосове повідомлення.
2. Віддати його в Whisper.
3. Отримати текст.
4. Передати текст у LLM.
5. Побудувати чернетку фактури.
6. Нормалізувати значення.
7. Показати чернетку користувачу як `Náhľad faktúry`.
8. У preview показати proposed номер фактури у форматі `Číslo faktúry: <number> (návrh)`.
9. Прийняти preview-stage рішення: `schváliť`, `upraviť` або `zrušiť`.
10. Якщо користувач обирає `upraviť`, редагувати FSM draft і знову показати оновлений `Náhľad faktúry`.
11. Якщо користувач обирає `zrušiť`, скасувати draft без створення invoice row і без PDF.
12. Якщо користувач обирає `schváliť`, перевірити номер, створити final invoice row, присвоїти final number і згенерувати PDF.

Backward compatibility:
- `ano` у preview трактується як `schváliť`;
- `nie` у preview трактується як `zrušiť`.

Decision normalization for preview/post-PDF states:
- Python first applies local deterministic markers before trusting LLM output.
- Clear save/approve markers (`zachovať`, `uložiť`, `uloz`, `save`, `save changes`, `зберегти`, `збережи`, `сохрани`, `сохранить изменения`) map to `schvalit`.
- Clear edit markers (`upraviť`, `opravit`, `edit`, `change`, `редагувати`, `відредагувати`, `исправить`, `изменить`) map to `upravit`.
- Clear cancel markers (`zrušiť`, `cancel`, `скасувати`, `отменить`, `nie`, `ні`, `нет`) map to `zrusit`.
- Nouns like `zmeny` / `зміни` / `изменения` must not by themselves override an explicit save marker.
- If local markers conflict, Python must return `unknown` and ask the user to clarify instead of guessing.

До `schváliť` invoice row, final invoice number і PDF не створюються. Preview number є тільки proposed number, збереженим у FSM `invoice_draft`.

Правило proposed invoice number у draft stage:
- proposed number не резервується в DB;
- якщо користувач вручну редагує `číslo faktúry`, draft отримує `invoice_number_manual_override = true`;
- якщо користувач редагує `Dátum vystavenia` і `invoice_number_manual_override = false`, proposed number перераховується відповідно до нового року `Dátum vystavenia`;
- якщо `invoice_number_manual_override = true`, редагування `Dátum vystavenia` не перераховує proposed number автоматично;
- на `schváliť` Python перевіряє, що proposed/final number досі вільний.

#### 4.4.2 Які поля повинні витягуватись

- контрагент,
- назва роботи / позиції,
- кількість,
- одиниця,
- сума,
- валюта,
- дата dodania / виконання,
- кількість днів до сплатності,
- обчислена дата сплатності.

#### 4.4.3 Правила інтерпретації дат

- `Dátum vystavenia` = дата створення фактури; бот ставить її автоматично завжди.
- Якщо в повідомленні користувача є дата, вона трактується як `Dátum dodania`.
- Якщо дата в повідомленні не вказана, тоді `Dátum dodania = Dátum vystavenia`.
- `Dátum splatnosti = Dátum vystavenia + splatnosť XX dní`.
- Якщо AI повернув `Dátum dodania`, який старший за `Dátum vystavenia` більше ніж приблизно на 2 місяці, Python не приймає такий рік без явного підтвердження у raw/STT-тексті; у разі сумніву бот просить уточнити дату.
- Якщо `Dátum dodania` виходить більше ніж приблизно на 3 місяці в майбутньому від `Dátum vystavenia`, Python також вимагає явне підтвердження року у raw/STT-тексті; інакше бот просить уточнити дату.

### 4.5 Створення фактури текстом

Користувач може писати короткі інструкції вручну. Логіка така сама:

**text/voice → action resolution + content/value canonicalization (Bounded Semantic Canonicalization) → Python validation/execution → draft preview/edit → final approval → PDF**

`Semantic Action Resolver` покриває лише вибір дії; структуровані поля фактури окремо проходять semantic value/content canonicalization перед Python validation та execution.

### 4.6 Робота тільки з локально збереженими контрагентами

У v1.0 бот не шукає контрагентів у реєстрах щоразу.

Правильна модель:
- контрагент додається один раз,
- підтверджується,
- зберігається локально,
- далі використовується тільки локальна картка.

Зовнішні джерела в першій версії не є частиною критичного flow.

### 4.7 Full `edit_invoice` / `upraviť` edit surface map (docs-first contract)

`edit_invoice` залишається **reserved top-level action token**.

Runtime-модель для цього токена: тільки bounded in-action/subflow edits в межах invoice flow, а не окремий top-level executor. Основний happy path тепер редагує draft на етапі preview / `Náhľad faktúry`; post-PDF edit-flow лишається compatibility/fallback шляхом.

Це важливо:
- це **не** нова top-level action;
- це **не** add item flow;
- add item свідомо винесений за межі цього docs patch.

#### 4.7.1 A) Invoice-level edit operations

Canonical machine-facing operations:
- `edit_invoice_number`
- `edit_invoice_issue_date`
- `edit_invoice_delivery_date`
- `edit_invoice_due_date`
- `edit_invoice_date` (clarification-only umbrella intent)
- `edit_invoice_contact`
- `unknown`

Статус:
- `edit_invoice_number` — implemented;
- `edit_invoice_issue_date` — implemented;
- `edit_invoice_delivery_date` — implemented;
- `edit_invoice_due_date` — implemented;
- `edit_invoice_date` — implemented as clarification trigger (`Ktorý dátum chcete upraviť...`);
- `edit_invoice_contact` — planned (not yet implemented).

Fail-safe рішення для invoice-level полів:
- ці операції є integrity-sensitive;
- при неоднозначності/конфлікті Python має fail loud (з bounded clarification), без silent auto-fix;
- інваріанти нумерації, дат і contact linkage не можна “тихо виправляти”.

#### 4.7.2 B) Item-level edit operations

Canonical machine-facing operations:
- `replace_service`
- `edit_item_description`
- `edit_item_quantity`
- `edit_item_unit_price`
- `edit_item_total_amount`
- `unknown`

Статус:
- implemented: `replace_service`, `edit_item_description`, `edit_item_quantity`, `edit_item_unit_price`, `edit_item_total_amount`.

#### 4.7.3 Операційна семантика item-level

**A) `replace_service` (replace service alias / canonical service)**
- змінює service identity позиції;
- оновлює canonical service term для item;
- може оновити short service name (де застосовно);
- повний display title має резолвитись із service alias / service dictionary.

**B) `edit_item_description` (edit free-text item detail)**
- змінює тільки optional manual detail field `item_description_raw`;
- це manual free-text;
- це не canonical alias;
- це не зміна service dictionary.

Для `edit_item_description` обов’язкові mutation modes:
- `set`,
- `replace`,
- `clear`.

**C) `edit_item_quantity` / `edit_item_unit_price` / `edit_item_total_amount`**
- змінюють тільки відповідне поле item;
- не повинні руйнувати arithmetic/business invariants;
- при нерозв’язному конфлікті — fail loud + bounded clarification.

#### 4.7.4 Precision-sensitive policy + item targeting

Precision-sensitive item fields:
- `item_description_raw`
- `edit_item_quantity`
- `edit_item_unit_price`
- `edit_item_total_amount`

Правила:
- precision-sensitive поля — text-first там, де voice може спотворити значення;
- voice не повинен “вгадувати” фінальні значення для precision-sensitive полів;
- для ambiguous voice input бот переходить на bounded Slovak prompt і просить текст.

Item targeting контракт:
- precision-sensitive item-level edits вимагають item targeting;
- single-item invoices можуть за замовчуванням таргетити перший item;
- multi-item invoices вимагають explicit item selection або bounded clarification.

#### 4.7.5 Data/model + render contract

- canonical service/title семантика зберігається без підміни;
- `item_description_raw` лишається окремим optional detail полем;
- головний service title береться з service alias/service DB;
- optional `item_description_raw` рендериться під головним title;
- detail text обмежений максимум 2 rendered lines;
- silent truncation заборонений; якщо не вміщується — bounded prompt на скорочення тексту.

#### 4.7.6 Minimal canonical contract block for `edit_invoice:subflow`

Machine-facing мінімальний bounded contract:
- `target_item_index`
- `operation`
- `value`

Де:
- `operation` ∈ {`edit_invoice_number`, `edit_invoice_issue_date`, `edit_invoice_delivery_date`, `edit_invoice_due_date`, `edit_invoice_date`, `edit_invoice_contact`, `replace_service`, `edit_item_description`, `edit_item_quantity`, `edit_item_unit_price`, `edit_item_total_amount`, `unknown`};
- `target_item_index` обов’язковий для item-level операцій (для invoice-level ігнорується/`unknown`);
- `value` завжди candidate-only; Python робить final validation/execution або fail loud.

#### 4.7.7 Explicit implementation boundary for this docs map

- Цей docs patch фіксує єдину карту повного `edit_invoice` scope для майбутніх runtime патчів.
- У runtime досі не реалізована: `edit_invoice_contact`.
- Поточний runtime coverage у межах `upraviť`: `edit_invoice_number`, `edit_invoice_issue_date`, `edit_invoice_delivery_date`, `edit_invoice_due_date`, `edit_invoice_date` (clarification), `replace_service`, `edit_item_description`, `edit_item_quantity`, `edit_item_unit_price`, `edit_item_total_amount`.
- Для invoice-level date edits застосовується bounded LLM normalization contract:
  - input: natural-language/text/STT date phrase;
  - output: тільки `DD.MM.RRRR` або `unknown`;
  - Python виконує тільки strict validate/parse та persistence/reject (без Python semantic date guessing).
- Guardrail: `dátum splatnosti` не може бути раніше за `dátum vystavenia` (fail-loud reject).
- Поточна поведінка для номеру фактури при зміні дати: номер **не змінюється автоматично** (без hidden auto-renumbering).

---

## 5. Роль AI у системі

### 5.1 Технічний контракт використання AI

У FakturaBot AI працює як **Semantic Action Resolver** в моделі **Bounded Semantic Canonicalization**:
- Python передає поточний state/context,
- Python передає дозволені канонічні дії або значення,
- LLM повертає тільки один дозволений канонічний вихід або `unknown`,
- Python виконує перевірку, state-check і side effects.

### 5.2 Єдиний семантичний шар (цільовий напрям)

Один і той самий підхід має уніфікувати:
- top-level action resolution (`create_invoice`, `add_contact`, `send_invoice`, `edit_invoice`),
- top-level action resolution (`create_invoice`, `add_contact`, `send_invoice`, `edit_invoice`, `edit_existing_invoice`),
- reply-state resolution (`ano`/`nie`, `schvalit`/`upravit`/`zrusit`),
- value/slot canonicalization (наприклад: `oprava`, `revizia`, `servis`).

### 5.3 Невідмінне правило безпеки

Навіть якщо LLM повернув канонічну дію (`zrusit`, `schvalit`, `send_invoice`),
виконання дозволене тільки Python після валідації контексту.

LLM не має права:
- виконувати side effects,
- змінювати DB/FSM напряму,
- позначати операцію як завершену.

### 5.4 Мовна політика

- Вхід користувача може бути multilingual/mixed/noisy/STT-distorted.
- Відповіді бота користувачу — словацькою.
- Сирий transcript може зберігатися окремо як trace/debug.
- Внутрішні канонічні виходи — тільки project-defined canonical tokens.

### 5.5 Обов’язкова вимога для structured workflows: slot-level clarification

Для кожного structured workflow (invoice, contact intake, create contract, майбутні structured assistant actions) обов’язково визначати:
- required slots;
- recoverable slot failures;
- fatal failures;
- partial draft retention behavior;
- clarification continuation behavior.

Обов’язковий контракт:
- якщо unresolved лише один slot і решта draft придатна — workflow не скидається повністю;
- Python зберігає partial draft/state;
- бот просить тільки unresolved slot;
- після уточнення workflow продовжується з поточного кроку;
- full reset дозволений тільки для fatal помилок.

### 5.6 Неоднозначні top-level actions: optional semantic hints

Для top-level bounded action resolution дозволяється використовувати компактні semantic action hints, якщо дія семантично неоднозначна в шумному multilingual вводі.

Правила:
- це **опційний** інструмент, не обов’язковий для кожної дії;
- застосовується вибірково, коли plain allowed-actions недостатньо для стабільного bounded розпізнавання;
- canonical bot wording і noisy user examples повинні бути чітко розділені в документації.

### 5.7 Planned `info_help` guidance/navigation/recovery layer (high-level TZ alignment)

`info_help` у плані продукту — це bounded guidance/navigation/recovery шар, а не free-form chat mode і не дубль direct top-level actions.

Routing precedence (обов’язково):
- authorization and exact deterministic controls run first;
- active FSM state owns the conversation before idle top-level routing;
- direct action execution wins only when the user clearly asks to perform a supported action;
- capability/how-to/support questions are eligible for InfoHelp/Product Truth and must not be forced into action execution;
- `info_help` handles capability/support/recovery/customization questions and bounded fallback only after safer direct routes are not applicable;
- direct actions stay direct, but informational questions must not create side effects.

Поведінка planned `info_help` на рівні TZ:
- відповіді на informational usage/capability питання;
- навігація до linked actions/subtargets (лише через safe handoff правила);
- truthful planned-feature/unsupported notices;
- guidance для recovery/reset/start-over сценаріїв.

Contract precedence:
- усі `info_help` взаємодії залишаються підпорядкованими bounded Python→LLM контракту (`docs/llm`);
- цей шар не послаблює і не обходить існуючі contract rules.

Capability status для guidance topics:
- `supported`
- `partial`
- `planned`
- `unsupported`
- `unknown`
- `dangerous`
- `requires_setup`
- `requires_admin`
- `requires_external_credentials`

Вимога truthfulness:
- user-facing відповідь повинна відповідати фактичному status;
- не можна представляти planned/unsupported як implemented.

Logging requirement (product signal):
- кожен вхід у `info_help` має логуватись як structured product signal для подальшого аналізу UX/roadmap.

Phase 2/3 future direction (high-level):
- state-aware guidance + reset/new-task допомога;
- bounded runtime explainability через sanitized Python-prepared facts;
- explicit заборона на arbitrary source-code reading або arbitrary raw-log reading з боку LLM у цьому шарі.

Caution for unconfirmed runtime coverage in info/guidance answers:
- dedicated end-to-end edit existing contact details flow;
- historical old-invoice deletion as user-facing feature;
- send-invoice/send-email style capability;
- support/ticket escalation workflow.
Поки runtime-реалізація не підтверджена — ці пункти мають відповідатися як planned/unsupported, без overstatement.

Детальна архітектура і behavioral contract для planned `info_help` визначені в:
- `docs/Info_Help_Guidance_Layer.md`
TZ фіксує high-level product/requirements alignment і не дублює повний детальний spec.

---

## 6. Структура чернетки фактури

### 6.1 Мінімальна модель invoice draft

```json
{
  "customer_name": "TECH COMPANY, s. r. o.",
  "item_name_raw": "оправи",
  "item_name_normalized": "Opravy vyhradených technických zariadení elektrických",
  "quantity": 1,
  "unit": "ks",
  "amount": 2000.0,
  "currency": "EUR",
  "delivery_date": "2026-03-30",
  "issue_date": "2026-03-30",
  "due_days": 30,
  "due_date": "2026-04-29"
}
```

### 6.1.1 Dual-shape multi-item intake (Phase 1, bounded)

Поточний runtime для create/invoice intake підтримує backward-compatible dual-shape:
- singleton shape залишається валідним;
- optional bounded `biznis_sk.items[]` підтримується для candidate multi-item intake.

Contract decisions:
- Backward compatibility обов’язкова:
  - існуючий singleton shape лишається валідним;
  - додається опційний bounded `biznis_sk.items[]` для candidate multi-item extraction;
  - list-only hard cutover не входить у цей етап.
- Python лишається execution/workflow owner:
  - LLM може повертати лише bounded candidate item segmentation;
  - LLM не приймає рішення про persistence/side effects;
  - Python валідовує boundaries, numeric coherence, totals, max item count, render safety.
- Safe outcomes:
  - accept + continue,
  - bounded clarification,
  - safe fallback (без silent merge/guess).

Phase 1 bounds:
- `items[]` max size = 3;
- без open-ended extraction довільної кількості позицій;
- при перевищенні bounds або неоднозначності — bounded clarification/fallback.

Candidate item shape (conceptual, machine-safe):
- `polozka_povodna`,
- `termin_sluzby_sk`,
- `mnozstvo`,
- `jednotka`,
- `cena_za_jednotku`,
- `suma`,
- optional future-compatible `item_description_raw`.

Split semantics rules:
- `montáž dva razy po 1000` => одна позиція (`mnozstvo=2`, `cena_za_jednotku=1000`);
- `oprava 3000 a montáž 1000` => дві candidate позиції;
- `oprava 3000, montáž 2x1000` => дві candidate позиції (друга з multiplier semantics);
- якщо межі позицій або quantity semantics неясні — Python запитує bounded clarification.

Fail-safe triggers (no silent auto-accept):
- ambiguous boundaries;
- ambiguous quantity semantics;
- ambiguous service resolution по будь-якій позиції;
- total incoherence (per-item або aggregate);
- render/page safety exceeded.

Runtime follow-up areas (future patches):
- richer bounded clarification for complex multi-item boundary ambiguity,
- stricter render/page-fit guards for larger real-world item text,
- optional per-item detail extraction policy hardening.

Правила дат для invoice draft:
- `issue_date` відповідає `Dátum vystavenia`. За замовчуванням ставиться ботом автоматично в момент створення фактури, але якщо користувач явно назвав дату виставлення у запиті на створення фактури, Python runtime детерміновано бере цю дату в draft.
- Дата, яку користувач продиктував або написав як дату додання/доставки, інтерпретується як `delivery_date` (`Dátum dodania`).
- Якщо користувач не вказав дату, `delivery_date` дорівнює `issue_date`.
- `due_date` обчислюється як `issue_date + due_days`.

### 6.2 Принцип preview

Будь-яка фактура проходить flow:

**draft → PDF preview → schváliť / upraviť**

Після генерації faktúry і PDF бот обов’язково дає її користувачу на перевірку.

На етапі preview користувач повинен бачити:
- контрагент,
- позиція,
- кількість,
- сума,
- дата dodania,
- дата виставлення,
- дата сплатності.

Доступні дії:
- `schváliť`
- `upraviť`

### 6.3 Explicit edit of existing persisted invoice by number

- Existing/finalized invoice edit is entered only by explicit command semantics (`upraviť faktúru 15`, `uprav faktúru číslo 20260015`, etc.).
- LLM responsibility is bounded to intent detection + extracting number reference text; LLM must not query DB.
- Python normalizes reference and searches supplier-scoped invoices by numeric suffix (`15` -> `...0015`) or full number.
- If 0 matches: `Faktúru s týmto číslom som nenašiel.`
- If >1 matches: `Našiel som viac faktúr. Napíšte celé číslo faktúry.`
- If exactly 1 match:
  1) load current persisted invoice data;
  2) show current invoice summary before edit menu;
  3) optionally send current PDF preview when stored `pdf_path` file is available;
  4) then open persisted edit-flow (`start_invoice_edit_flow`) without creating new draft.
- Current invoice summary must include:
  - invoice number,
  - customer/contact,
  - dates (issue/delivery/due),
  - item lines,
  - quantities,
  - unit prices,
  - item totals,
  - invoice total.
- Missing `pdf_path` or missing PDF file must not block entering persisted edit-flow.
- This does not restore post-PDF menu after each new invoice; explicit entrypoint only.

---

## 6.3 QR-код Pay by Square

Кожна PDF-фактура містить QR-код стандарту Pay by Square (Slovenská banková asociácia).

QR-код генерується автоматично з полів:
- IBAN постачальника (з профілю),
- suma k úhrade,
- variabilný symbol = číslo faktúry,
- dátum splatnosti,
- mena (EUR).

Реалізація: internal Python encoder (`bot/services/pay_by_square.py`) + `qrcode`.

Мінімальні required поля для payload у FakturaBot:
- IBAN,
- Amount (> 0),
- Currency (`^[A-Z]{3}$`),
- Variable symbol (numeric, max 10),
- Due date (`YYYY-MM-DD` → payload date),
- Beneficiary name (non-empty).

Якщо валідація не проходить — генерація payload зупиняється з явним exception (fail-loud), без fallback-placeholder.

Клієнт контрагента сканує QR у банківській аплікації → платіжний príkaz заповнений автоматично.

---

## 6.4 Відправка на email

Active status correction 2026-05-17:
- Real outbound invoice email sending is not implemented in the current runtime unless later code, tests, setup, and Product Truth prove otherwise.
- The flow below is legacy/planned behavior only and must not be used as proof that email sending is supported.
- Current user-facing answers about email must classify it as `unsupported`, `planned`, or `requires_external_credentials` according to Product Truth.

Після підтвердження чернетки бот показує:

```
📄 Faktúra č. 20260015
Odberateľ: TECH COMPANY, s. r. o.
Suma: 2 000,00 €
Splatnosť: 29.04.2026

[✅ Odoslať na email] [💾 Len uložiť] [❌ Zrušiť]
```

Legacy planned flow if real outbound email is implemented later:
1. Future sender would send email to the contact address from DB only after provider/setup/Product Truth gates exist.
2. Тема: `Faktúra č. 20260015 — [Názov dodávateľa]`
3. Тіло (словацькою): привітання + сума + splatnosť + подяка.
4. Вкладення: PDF фактура.
5. Future sender would confirm delivery only after the provider reports success.

Per-user SMTP host/user/password collection is deprecated. Supplier onboarding collects only the business email; future sending should use a centralized transactional provider such as Postmark or equivalent.

---

## 6.5 Автонумерація фактур

Формат: `RRRRNNNN` (рік + послідовний номер).

Приклад: `20260001`, `20260002`, ... `20260099`.

Номер автоматично інкрементується. Скид лічильника — 1 січня кожного року.
Номер фактури присвоюється тільки в момент фінального підтвердження і збереження, а не на етапі draft.
Číselná rada послідовна, без пропусків — відповідно до вимог словацького законодавства.

---

## 6.6 Збереження договору

При додаванні контрагента з договору оригінальний файл (PDF або фото) зберігається в `storage/contracts/`.

Формат імені: `{ICO}_{date}_{original_filename}`

Приклад: `47983973_20260330_zmluva_tech_company.pdf`

Шлях записується в таблицю `contact.contract_path`. Це дає:
- архів договорів для účtovníka,
- можливість перевірити витягнуті дані пізніше,
- юридичне підтвердження реквізитів.

OfficeFlow storage proposal розглядає договори як long-living workspace/master-data documents, а не як документи, обов’язково прив’язані до одного року. Це поки лише proposal; поточний runtime і надалі використовує `storage/contracts/`.

---

## 7. Витяг контрагента з договору

### 7.1 Контракт взаємодії з AI

Для сценарію витягу з договору діє той самий bounded-контракт:
- Python передає AI поточний контекст задачі та дозволені канонічні значення полів/ролей,
- LLM повертає лише одне канонічне значення на поле або `unknown`,
- Python виконує валідацію, рольову перевірку (`objednavatel`), і тільки потім дозволяє user confirmation/save.

### 7.2 Очікуваний JSON

```json
{
  "company_name": "TECH COMPANY, s. r. o.",
  "address": "Oravské Veselé 966, 029 62 Oravské Veselé",
  "ico": "47983973",
  "dic": "2024169488",
  "ic_dph": "SK2024169488",
  "statutory_person": "Tomáš Sameliak",
  "email": "",
  "role_detected": "objednavatel"
}
```

### 7.3 Валідація після AI

Python повинен перевіряти:
- чи знайдено саме замовника,
- чи не порожня назва,
- чи IČO має валідний формат,
- чи IČ DPH не схоже на випадковий текст,
- чи не витягнуті реквізити виконавця замість замовника.

### 7.4 Остаточна логіка

Навіть при високому confidence дані лише пропонуються, а не зберігаються автоматично.

---

## 8. База даних

### 8.1 Таблиця supplier

Містить профіль постачальника.

Мінімальні поля:
- id,
- telegram_id,
- name,
- ico,
- dic,
- ic_dph,
- address,
- iban,
- swift,
- email,
- smtp_host,
- smtp_user,
- smtp_pass (шифровано; ключ шифрування не зберігається в БД і передається через безпечну конфігурацію середовища),
- days_due,
- created_at,
- updated_at.

### 8.2 Таблиця contact

Містить локальні картки контрагентів.

Мінімальні поля:
- id,
- supplier_id,
- name,
- ico,
- dic,
- ic_dph,
- address,
- email,
- contact_person,
- source_type,
- source_note,
- contract_path (шлях до оригіналу договору, nullable),
- created_at,
- updated_at.

`source_type` може мати значення:
- `manual`,
- `contract_ai`.

### 8.3 Таблиця invoice

Мінімальні поля:
- id,
- supplier_id,
- contact_id,
- invoice_number,
- issue_date,
- due_date,
- total_amount,
- currency,
- status,
- pdf_path,
- created_at,
- updated_at.

### 8.4 Таблиця invoice_item

У першій версії достатньо підтримати **одну позицію на фактуру**, але технічна структура може вже бути табличною.

Мінімальні поля:
- id,
- invoice_id,
- description_raw,
- description_normalized,
- item_description_raw (optional manual free-text detail below canonical service title; не alias і не dictionary-term),
- quantity,
- unit,
- unit_price,
- total_price.

Примітка для Phase 1 item edit contract:
- поточний single-item draft може дефолтно редагувати перший item;
- модель зберігається future-ready для multi-item через item-targeted edits.

---

## 9. Модулі системи

### 9.1 Обов’язкові модулі v1.0

- bot core,
- speech-to-text,
- LLM draft parser,
- contract extractor (AI витяг реквізитів + збереження оригіналу),
- contacts,
- supplier profile,
- invoices,
- PDF generator з QR-кодом Pay by Square,
- real outbound email sender: not current runtime MVP; unsupported/planned unless later code, setup, tests, and Product Truth prove otherwise,
- validation layer,
- SQLite storage.

У майбутньому OfficeFlow framing цей набір відповідає модулю **FakturaBot / Outgoing Invoices**.

Для всіх модулів, які приймають confirmation-like відповіді користувача, цільова архітектура вимагає shared Canonical DecisionResolver. Нові модулі не повинні додавати власні локальні парсери підтверджень.

### 9.2 Відкладені модулі

Модулі, які не є обов’язковими для v1.0:
- Google Drive,
- external company lookup,
- OCR pipeline,
- broad Document Intake beyond current receipt/incoming-invoice Phase 1,
- bank statement intake,
- broad document categories beyond the partial receipt/incoming-invoice intake category flow,
- e-faktura 2027,
- extended reports.

Active status correction 2026-05-17:
- Accounting Document Intake Phase 1 is implemented/partial for confirmed receipt (`blocek`) and incoming-invoice (`prijata faktura`) intake, bounded category candidates, workspace category creation after confirmation, duplicate preview, user approval, confirmed metadata storage, idle attachment routing, and recent document view where current code/tests prove it.
- Broader Document Intake remains planned/not implemented for standalone contract archive, bank statements, broad OCR for arbitrary scanned documents, broad category administration, accounting software export, Google Drive sync, and full OfficeFlow workspace runtime unless later code/docs prove otherwise. Receipt/incoming-invoice analytics is supported only by the separate partial read-only `accounting_document_analytics` runtime over confirmed metadata.

---

## 10. Структура проекту

```text
faktura-bot/
├── bot/
│   ├── main.py
│   ├── handlers/
│   │   ├── onboarding.py
│   │   ├── contacts.py
│   │   ├── contracts.py
│   │   ├── invoice.py
│   │   └── settings.py
│   ├── services/
│   │   ├── whisper.py
│   │   ├── llm_invoice_parser.py
│   │   ├── llm_contract_extractor.py
│   │   ├── pdf_generator.py        # PDF + Pay by Square QR
│   │   ├── email_sender.py         # legacy/planned SMTP sender; not current supported runtime capability
│   │   └── validation.py
│   ├── models/
│   │   ├── database.py
│   │   ├── supplier.py
│   │   ├── contact.py
│   │   └── invoice.py
│   └── config.py
├── storage/
│   ├── invoices/                    # Згенеровані PDF-фактури
│   ├── contracts/                   # Оригінали договорів (PDF/фото)
│   └── uploads/                     # Тимчасові файли
├── prompts/
│   ├── invoice_draft_prompt.txt
│   └── contract_customer_prompt.txt
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

Майбутня OfficeFlow storage model описана в `docs/architecture/OfficeFlow_Storage_Model_Proposal.md` як non-runtime proposal. Вона не переносить існуючі PDF, не змінює `pdf_path` і не створює yearly folders у поточному коді.

---

## 11. Безпека

### 11.1 Базовий принцип

Усі зовнішні дані вважаються недовіреними:
- голос,
- текст,
- PDF,
- фото договору,
- відповідь LLM.

### 11.2 Критичні правила

- AI ніколи не зберігає дані напряму в БД.
- Усі результати AI проходять Python-валідацію.
- Усі важливі дії потребують підтвердження користувача.
- Дані контрагентів беруться з локальної БД, а не з інтернету.
- Перша версія не залежить від зовнішніх lookup-сервісів.

### 11.3 Захист від помилкових витягів

Для договорів обов’язково перевіряється, щоб:
- не переплутати `objednávateľ` і `zhotoviteľ`,
- не зберегти власні реквізити користувача як контрагента,
- не створити контакт без назви та базових реквізитів.

---

## 12. Стратегічний висновок

FakturaBot v1.0 — це не спроба побудувати великий SaaS, а **живий демонстраційний продукт**, який:
- реально вирішує задачу автора,
- показує wow-ефект через голос,
- витягує контрагентів з договорів і зберігає оригінали,
- створює PDF-фактури з QR-кодом Pay by Square,
- does not currently send invoices by real outbound email unless later runtime integration, credentials/setup, tests, and Product Truth prove otherwise,
- демонструє підхід до кастомних Telegram-ботів для малого бізнесу.

Після цієї версії продукт може розвиватися двома напрямками:
1. як індивідуально налаштований FakturaBot для клієнтів,
2. як ядро для інших ботів під конкретні бізнес-процеси.

---

## 13. Документаційний супровід проєкту

У репозиторії обов'язково ведеться PROJECT_LOG.md.

Після кожної змістовної сесії фіксуються:
- прийняті рішення,
- зміни scope,
- відкладені модулі,
- уточнення архітектури,
- наступні кроки.

Зміни, що впливають на продуктову логіку або межі MVP, мають відображатися і в PROJECT_LOG.md, і в цьому ТЗ.

---

## 14. Підсумок рішень, зафіксованих у цьому оновленні

1. Повноцінний масовий SaaS на старті відкинуто.  
2. Перший інстанс розгортається для самого автора.  
3. Голосовий сценарій є обов’язковою частиною MVP.  
4. Lookup компаній з інтернету (FinStat, ORSR) у v1.0 не використовується — API платний, парсинг з договору достатній.  
5. Додавання контрагента з договору через AI + validation + confirmation. Оригінал договору зберігається.  
6. Дані контрагентів надалі беруться з локальної БД.  
7. AI використовується як інструмент побудови чернетки, а не як автономний виконавець.  
8. PDF-фактура обов’язково містить QR-код Pay by Square.  
9. Real outbound email sending is not part of the current runtime MVP; it is unsupported/planned and requires Product Truth, external credentials/setup, tests, and explicit implementation evidence before it may be called supported.  
10. Продукт мислиться як частина ширшої моделі кастомних ботів для малого бізнесу.  
11. Для test/dev операцій додано явну дію `delete_existing_invoice` з обов’язковим підтвердженням `áno/nie` та supplier-scoped пошуком за суфіксом/повним номером.  

## 2026-05-02 Controlled Two-User Dry Run Addendum

Current controlled multi-user model for the next dry run:
- one shared backend/codebase;
- one Telegram bot token for now;
- one SQLite DB for now;
- Phase 1 access only for Telegram users listed in bootstrap `ALLOWED_TELEGRAM_USER_IDS`;
- Phase 2 may add admin-approved access without `.env` edits only when the current code and `PROJECT_LOG.md` confirm it is implemented/deployed;
- no public self-service onboarding;
- deterministic tenant isolation by `telegram_id` / `supplier_telegram_id`.

This is not full SaaS multi-tenancy. Out of scope for this step:
- multiple bot-token orchestration;
- workspace admin UI;
- billing;
- Postmark integration;
- encrypted secret vault for per-tenant secrets;
- bank-statement matching;
- expense categorization.

Python remains the source of truth for authorization, tenant identity, DB filters, invoice-number generation, file-path generation, duplicate checks, and persistence. LLM/STT may help with bounded extraction or action/value resolution only after the Telegram user is authorized, and must not decide authorization or tenant identity.

Tenant-sensitive runtime rules:
- invoice numbers are unique per supplier: `UNIQUE(supplier_telegram_id, invoice_number)`;
- the same invoice number may exist for different suppliers;
- invoice PDF files are stored under `storage/invoices/{supplier_telegram_id}/{invoice_number}.pdf`;
- accounting document confirmed storage uses a tenant workspace key such as `telegram-{supplier_telegram_id}`;
- accounting document temporary upload staging is tenant-scoped before any LMM call or confirmed save;
- contact and supplier profile operations are scoped to the current Telegram user.

Persisted data migration rule:
- changing DB engine, DB schema, tenant scoping, workspace keys, file paths, `pdf_path` semantics, accounting metadata JSON schema, or cleanup/archive behavior is migration-sensitive;
- before implementation, the project must document current data shape, proposed data shape, affected existing data, audit plan, backup/rollback plan, dry-run plan, and explicit apply approval;
- legacy data must be repaired or migrated explicitly, not hidden behind cross-tenant fallback reads;
- server-side persisted data writes require backup and post-repair validation;
- practical workflow is maintained in `docs/FakturaBot_Data_Migration_Runbook.md`.

Legacy per-user SMTP credential collection is deprecated for the dry run. Supplier onboarding collects only the business email. Existing DB columns `smtp_host`, `smtp_user`, and `smtp_pass` remain for compatibility but are unused by the dry-run flow and should be cleared if legacy values exist:

```sql
UPDATE supplier
SET smtp_host = NULL,
    smtp_user = NULL,
    smtp_pass = NULL;
```

Future email sending should use a centralized transactional email provider, for example Postmark or equivalent, with a project-owned sender domain and DKIM/DMARC/Return-Path configured later. Per-user SMTP credentials must not be collected in onboarding.

## 2026-05-02 Controlled Access-Request Onboarding Addendum

This section specifies Phase 2 controlled onboarding automation. Do not treat it as the current dry-run model unless the current code and `PROJECT_LOG.md` confirm it is implemented and deployed.

When Phase 2 is implemented, unknown Telegram users may request access through `/start`, but this is not public automatic signup:
- `/start` from an unknown user records or refreshes a minimal `access_requests` row with Telegram metadata only;
- no supplier profile, tenant workspace, contact, invoice, accounting document, temp intake workspace, LLM, STT, or LMM call is created for unknown users;
- the user receives a neutral Slovak message that administrator approval is required;
- configured admins may review pending requests with `/access_requests`;
- configured admins may use `/approve <telegram_id>`, `/reject <telegram_id>`, `/block <telegram_id>`, and `/users`;
- `/approve` transactionally restores one migration-created inactive owner membership and active selection only when supplier/workspace ownership is unique and matches the approved Telegram actor;
- this approval repair creates no workspace or supplier and fails closed with a full rollback on multiple memberships or contradictory ownership;
- non-admin users cannot run access-management commands.

Authorization model:
- a user is authorized when their Telegram ID is in `ALLOWED_TELEGRAM_USER_IDS`, or when `authorized_users.status = 'active'`;
- a user is an admin when their Telegram ID is in `ADMIN_TELEGRAM_USER_IDS`, or when `authorized_users.role` is `admin`/`owner` and status is `active`;
- blocked users are denied before normal handlers run, even if they previously had access;
- approved users still must complete `/supplier` onboarding before invoice creation.

Operational config:
- `ALLOWED_TELEGRAM_USER_IDS` remains a bootstrap/static allowlist for compatibility and emergency access;
- `ADMIN_TELEGRAM_USER_IDS` is the bootstrap admin configuration;
- real Telegram IDs must be configured in environment variables only, not committed or documented with real values.

Out of scope remains public signup, email/password accounts, billing, payments, SaaS dashboard, multiple Telegram bot tokens, per-user bot-token orchestration, Postmark sending, and automatic tenant creation with full privileges.

## Addendum 2026-06-30 - Google Drive Owner OAuth Archive

Current status: partial runtime integration, live-smoked on 2026-07-01.

FakturaBot can run an owner-managed Google Drive archive worker when
`GOOGLE_DRIVE_ENABLED=1`, `GOOGLE_DRIVE_MODE=owner_oauth`, Google OAuth client
credentials, `GOOGLE_TOKEN_CRYPTO_SECRET`, an encrypted owner refresh token, and
a personal My Drive root folder id are configured. This is not per-client OAuth
and not SaaS Drive sync. Uploads consume the owner Google account quota.

Runtime behavior:

- confirmed receipts and incoming invoices already saved through the accounting
  document intake outbox can be uploaded by the archive worker;
- receipt originals go to `FakturaBot/<year>/blocky/<year-month>/`;
- incoming invoice originals go to `FakturaBot/<year>/prijate_faktury/<year-month>/`;
- outgoing invoice PDFs are enqueued only after a control event such as marking
  the invoice paid and go to `FakturaBot/<year>/faktury/<year-month>/`;
- local invoice PDFs remain stored locally and are not deleted in this MVP;
- confirmed accounting metadata JSON remains local;
- receipt/incoming originals are deleted only after successful upload and DB
  state update to `uploaded`, and only when the corresponding retention env flag
  is enabled;
- service-account mode is unsupported for personal My Drive unless a future
  Google Workspace/Shared Drive setup is explicitly configured.

Setup uses the manual owner OAuth bootstrap command
`python -m bot.google_drive_owner_oauth_bootstrap authorize --telegram-id <admin_telegram_id>`
and then `python -m bot.google_drive_owner_oauth_bootstrap exchange --state-token <state> --code <code> --root-folder-id <folder_id>`.

Live smoke evidence on 2026-07-01:

- invoice `20260006` was marked paid through voice/text intent `mark_existing_invoice_paid`;
- the bot created one `invoice_pdf` archive job;
- the archive worker uploaded the PDF to Google Drive and set DB state to `uploaded`;
- local invoice PDF remained available;
- no bank confirmation or bank matching was implied.

Receipt date incident noted during Drive backfill:

- two confirmed receipt metadata/archive records were extracted under year 2023 and repaired to 2026 in DB, local metadata paths, and Google Drive file names/folders;
- current runtime rejects receipt issue dates before 2026 before confirmed save;
- this fixed floor is a controlled-rollout guard, not a permanent yearly policy. Before the 2027 accounting year, replace it with an explicit configurable accepted-year/window policy, because January may legitimately need backfill of prior-year receipts.

## 2026-07-01 - OfficeFlow Work-Time / Dochadzka MVP

Current status: `partial`.

Implemented runtime slice:
- top-level actions `open_work_day`, `close_work_day`, `add_work_time_entry`, `generate_work_time_report`, `update_work_time_lunch_break`, and `delete_work_time_month`;
- Telegram text and voice entry through the existing bounded top-level action router;
- work-time runtime `now`/`today`/`yesterday`/default report month uses `OFFICEFLOW_TIMEZONE`, default `Europe/Bratislava`, not the server/container UTC clock;
- `/dochadzka` help command;
- additive SQLite storage in `work_time_days`, `work_time_events`, and `work_time_settings` scoped by `telegram_id`; `delete_work_time_month` removes only the current user's rows/events for the selected month after preview confirmation;
- additive `work_time_days` columns for gross minutes, lunch-break snapshot, net-duration override, and close input mode; existing rows are not rewritten;
- first report asks once whether lunch break should be deducted; later `update_work_time_lunch_break` changes or disables the fixed deduction after preview confirmation;
- preview-confirmed manual time ranges, close-time/duration decisions, lunch-break changes, and monthly deletion through shared DecisionResolver paths;
- monthly Excel report generation with all days, Sunday highlighting, and net total hours after configured lunch deduction.

Explicitly out of scope:
- payroll, salary calculation, and legal HR attendance compliance;
- multi-employee attendance administration;
- accounting/payroll export;
- automatic work-time detection;
- deletion of generated monthly Excel report files as canonical data; reports are generated on demand from DB rows;
- legal lunch-break, payroll, or HR compliance calculations; the lunch setting is only a fixed net-hours deduction for MVP reports.
- official payroll/legal HR document claims.

## Multi-Workspace Business Profiles V1 - Internal Runtime Status (2026-07-12)

Current status is partial internal foundation, not a public capability.

Implemented locally:

- additive workspace, workspace_membership, and active_workspace_selection tables;
- authorization-first WorkspaceContext resolution and membership validation;
- read-only redacted migration audit/dry-run tooling;
- transitional supplier persistence with workspace-aware lookup;
- atomic first/additional workspace profile persistence with full transaction rollback.
- workspace-isolated contact CRUD with same-name support across workspaces and fail-closed legacy ambiguity handling.
- workspace-scoped confirmed contact alias storage and resolver isolation.
- workspace-scoped invoice persistence and numbering with independent same-number support across profiles and contact ownership validation.
- workspace-scoped invoice follow-up/payment/reminder state, callback ownership checks, and background scheduling independent of active profile selection.
- workspace-scoped outgoing-invoice analytics datasets with legacy readers restricted to workspace_id NULL rows.
- PDF target paths owned by immutable workspace.storage_key, while existing persisted invoice.pdf_path values remain unchanged.

Not yet implemented or exposed:

- migration apply for persisted production data;
- workspace-scoped Telegram contact and invoice creation/edit FSM binding, accounting documents, work-time, general archive jobs, remaining analytics domains, and deletion;
- production deployment of `/profily` / `switch_business_profile` before backup, migration apply, post-apply audit, and server smoke approval;
- Product Truth/InfoHelp status partial for end users.

Legacy single-profile runtime remains supported. Public switching must stay disabled until every mandatory business domain, migration fixture, FSM binding, callback guard, Product Truth/InfoHelp surface, and Conversation Acceptance Proof passes.
## Multi-workspace business profiles target runtime (2026-07-13)

Implementation status: `partial / production migrated and deployed / same-user two-profile acceptance pending`.

Implemented code surface:

- `/profily` lists only active memberships, marks the active workspace, supports exact reply-keyboard selection, add-profile entry, and cancel;
- canonical `switch_business_profile` is reachable from idle semantic text and voice; voice requires shared `yes_no` confirmation before mutation;
- active foreign FSM state blocks profile switching without clearing or retargeting the flow;
- `/moj_profil`, `/upravit_profil`, supplier onboarding, service aliases, contacts, invoices/numbering/PDF/follow-up/analytics, accounting document intake/categories/storage/analytics/archive, and work-time DB/report storage are workspace-bound on the target schema;
- full `/vymazat_databazu` remains account-level and removes all owned local workspaces while preserving remote Drive files and shared provider credentials;
- `/start` and `/menu` identify the active firemný profil when a valid workspace exists.

Explicitly outside MVP: cross-workspace analytics, per-request temporary overrides, deleting one profile, billing, public signup, and broad multi-member workspace administration.

Production migration boundary: the 2026-07-13 apply preserved row counts, existing invoice/accounting paths, and storage fingerprints; no Google Drive mutation was performed. The verified rollback backup at `/var/backups/fakturabot/20260713T173948Z_7408399` must remain retained until real two-profile acceptance and a later explicit retention decision.

Acceptance boundary: production currently has two workspaces and two memberships, but no authorized Telegram actor has two active memberships. Do not claim the interactive two-profile journey complete until `/profily` creates a second profile for one actor, text and voice switch are exercised, lightweight objects are proven isolated in both profiles, and temporary test objects are removed through normal product flows when no longer needed.
