from __future__ import annotations

from datetime import date
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from bot.services.gmail_statement_period import (
    STATEMENT_PERIOD_AMBIGUOUS,
    STATEMENT_PERIOD_DETECTED,
    STATEMENT_PERIOD_PASSWORD_INVALID,
    STATEMENT_PERIOD_PASSWORD_REQUIRED,
    detect_gmail_statement_period,
    greatest_covered_month,
)


def _pdf_with_text(text: str) -> bytes:
    output = BytesIO()
    document = canvas.Canvas(output)
    y = 800
    for line in text.splitlines():
        document.drawString(50, y, line)
        y -= 20
    document.save()
    return output.getvalue()


def _encrypted_pdf(text: str, *, user: str, owner: str) -> bytes:
    reader = PdfReader(BytesIO(_pdf_with_text(text)))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=user, owner_password=owner)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_encrypted_statement_uses_opening_password_without_owner_password() -> None:
    content = _encrypted_pdf(
        "Datum 24.07.2026\nPosledny vypis 24.06.2026",
        user="same-opening-password",
        owner="unknown-edit-password",
    )

    result = detect_gmail_statement_period(
        content, open_password="same-opening-password"
    )

    assert result.status == STATEMENT_PERIOD_DETECTED
    assert result.start_date == date(2026, 6, 25)
    assert result.end_date == date(2026, 7, 24)
    assert (result.period_year, result.period_month) == (2026, 7)


def test_encrypted_statement_fails_closed_for_missing_or_wrong_password() -> None:
    content = _encrypted_pdf(
        "Datum 30.06.2026\nPosledny vypis 31.05.2026",
        user="opening-secret",
        owner="different-owner-secret",
    )

    missing = detect_gmail_statement_period(content)
    wrong = detect_gmail_statement_period(content, open_password="not-the-secret")

    assert missing.status == STATEMENT_PERIOD_PASSWORD_REQUIRED
    assert wrong.status == STATEMENT_PERIOD_PASSWORD_INVALID
    assert "opening-secret" not in repr(missing)
    assert "opening-secret" not in repr(wrong)


def test_explicit_period_uses_most_covered_calendar_days() -> None:
    result = detect_gmail_statement_period(
        _pdf_with_text("Obdobie: 25.06.2026 do 24.07.2026")
    )

    assert result.status == STATEMENT_PERIOD_DETECTED
    assert result.source == "explicit_range"
    assert (result.period_year, result.period_month) == (2026, 7)


def test_end_month_wins_equal_day_tie() -> None:
    assert greatest_covered_month(
        date(2026, 6, 16), date(2026, 7, 15)
    ) == (2026, 7)


def test_conflicting_statement_dates_are_ambiguous() -> None:
    result = detect_gmail_statement_period(
        _pdf_with_text(
            "Datum 30.06.2026\nDatum 31.07.2026\nPosledny vypis 31.05.2026"
        )
    )

    assert result.status == STATEMENT_PERIOD_AMBIGUOUS
    assert result.period_year is None
    assert result.period_month is None


def test_statement_header_accepts_pdf_text_without_space_between_label_words() -> None:
    result = detect_gmail_statement_period(
        _pdf_with_text("Datum31.07.2026\nPoslednyvypis30.06.2026")
    )

    assert result.status == STATEMENT_PERIOD_DETECTED
    assert result.start_date == date(2026, 7, 1)
    assert result.end_date == date(2026, 7, 31)
    assert (result.period_year, result.period_month) == (2026, 7)
