# PAY by Square Manual Verification Checklist

Purpose: local manual verification that the generated invoice PDF contains a real PAY by square QR which is accepted by a real banking mobile app.

Scope:
- verification only;
- no runtime code changes;
- no Phase 5 work;
- no email flow work.

## Preconditions

- Local environment is configured and the bot can run.
- Supplier profile already exists and contains a real IBAN and beneficiary name.
- A customer contact already exists.
- You have access to a banking mobile app that supports PAY by square scanning.

## Generate Local PDF Invoice

1. Start the bot locally:
   - `python -m bot.main`
2. In Telegram, run `/invoice`.
3. Submit a small test invoice draft and confirm PDF generation.
4. Wait for the bot to send the generated PDF back in chat.

## Find Generated PDF

- Default path: `storage/invoices/<invoice_number>.pdf`
- If `STORAGE_DIR` is overridden, use: `<STORAGE_DIR>/invoices/<invoice_number>.pdf`
- The runtime path is built in `bot/handlers/invoice.py` and the storage directories are created in `bot/config.py`.

## Manual Scan Checklist

1. Open the generated PDF on a desktop or another device so the QR is clearly visible.
2. In the banking app, open the PAY by square / QR payment scanner.
3. Scan the QR from the PDF.
4. Verify that the banking app accepted the QR at all.
5. Compare scanned values against the PDF invoice and expected payment data:
   - `IBAN`
   - `suma`
   - `mena`
   - `variabilny symbol`
   - `datum splatnosti`
   - `nazov prijemcu / beneficiary`
   - `poznamka`, if present
6. Confirm there is no obvious field shift:
   - wrong IBAN with correct amount;
   - wrong due date with correct VS;
   - missing beneficiary while the rest is present.

## Expected Outcomes

- Success:
  - QR scans successfully.
  - Banking app pre-fills all expected fields correctly.
  - No manual correction is needed before payment confirmation.
- Partial success:
  - QR scans successfully.
  - Core payment fields are usable, but one or more optional or non-core fields are missing or altered.
  - A follow-up patch may still be needed.
- Fail:
  - QR is not recognized as a valid payment QR.
  - Banking app rejects the QR.
  - Critical fields are missing or wrong, especially `IBAN`, `suma`, `mena`, `variabilny symbol`, or `datum splatnosti`.

## What To Record After Test

- Banking app name and version, if visible
- Did the app scan the QR at all: yes / no
- Which fields were populated correctly
- Which fields were missing, empty, or wrong
- Whether a follow-up patch is needed

## Suggested Test Note

Keep one short note per banking app test:

`<bank app> | scan: yes/no | IBAN: ok/fail | amount: ok/fail | currency: ok/fail | VS: ok/fail | due date: ok/fail | beneficiary: ok/fail | note: ok/missing/n-a | follow-up patch: yes/no`
