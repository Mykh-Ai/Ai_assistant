from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError


STATEMENT_PERIOD_DETECTED = "detected"
STATEMENT_PERIOD_NOT_PDF = "not_pdf"
STATEMENT_PERIOD_PASSWORD_REQUIRED = "password_required"
STATEMENT_PERIOD_PASSWORD_INVALID = "password_invalid"
STATEMENT_PERIOD_PDF_UNREADABLE = "pdf_unreadable"
STATEMENT_PERIOD_TEXT_UNAVAILABLE = "text_unavailable"
STATEMENT_PERIOD_AMBIGUOUS = "period_ambiguous"

_MAX_PAGES = 3
_MAX_TEXT_CHARACTERS = 64 * 1024
_MAX_INTERVAL_DAYS = 93
_DATE = r"(?P<{name}>\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{4}})"


@dataclass(frozen=True)
class GmailStatementPeriodResult:
    status: str
    start_date: date | None = None
    end_date: date | None = None
    period_year: int | None = None
    period_month: int | None = None
    source: str | None = None
    error_code: str | None = None


def detect_gmail_statement_period(
    content: bytes, *, open_password: str | None = None
) -> GmailStatementPeriodResult:
    """Resolve a bounded statement period without persisting decrypted content."""
    if not content.startswith(b"%PDF-"):
        return _failure(STATEMENT_PERIOD_NOT_PDF)

    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            if open_password is None:
                return _failure(STATEMENT_PERIOD_PASSWORD_REQUIRED)
            if not reader.decrypt(open_password):
                return _failure(STATEMENT_PERIOD_PASSWORD_INVALID)
        text = _bounded_text(reader)
    except (PdfReadError, ValueError, TypeError, OSError, NotImplementedError):
        return _failure(STATEMENT_PERIOD_PDF_UNREADABLE)
    except Exception:
        # Parser/library failures are deliberately collapsed to a bounded code.
        return _failure(STATEMENT_PERIOD_PDF_UNREADABLE)

    if not text.strip():
        return _failure(STATEMENT_PERIOD_TEXT_UNAVAILABLE)

    interval = _explicit_interval(text)
    source = "explicit_range"
    if interval is None:
        interval = _statement_date_interval(text)
        source = "previous_statement_and_statement_date"
    if interval is None:
        return _failure(STATEMENT_PERIOD_AMBIGUOUS)

    start, end = interval
    if start > end or (end - start).days + 1 > _MAX_INTERVAL_DAYS:
        return _failure(STATEMENT_PERIOD_AMBIGUOUS)
    year, month = greatest_covered_month(start, end)
    return GmailStatementPeriodResult(
        status=STATEMENT_PERIOD_DETECTED,
        start_date=start,
        end_date=end,
        period_year=year,
        period_month=month,
        source=source,
    )


def greatest_covered_month(start: date, end: date) -> tuple[int, int]:
    if start > end:
        raise ValueError("statement_period_reversed")
    counts: dict[tuple[int, int], int] = {}
    cursor = start
    while cursor <= end:
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)
        segment_end = min(end, next_month - timedelta(days=1))
        counts[(cursor.year, cursor.month)] = (segment_end - cursor).days + 1
        cursor = segment_end + timedelta(days=1)

    maximum = max(counts.values())
    winners = {key for key, value in counts.items() if value == maximum}
    end_month = (end.year, end.month)
    if end_month in winners:
        return end_month
    return max(winners)


def _bounded_text(reader: PdfReader) -> str:
    chunks: list[str] = []
    remaining = _MAX_TEXT_CHARACTERS
    for page in reader.pages[:_MAX_PAGES]:
        if remaining <= 0:
            break
        value = page.extract_text() or ""
        chunks.append(value[:remaining])
        remaining -= len(chunks[-1])
    return "\n".join(chunks)


def _explicit_interval(text: str) -> tuple[date, date] | None:
    start_pattern = _DATE.format(name="start")
    end_pattern = _DATE.format(name="end")
    patterns = (
        rf"\bod\s*{start_pattern}\s*\bdo\s*{end_pattern}",
        rf"\b(?:obdobie|obdob\u00ed|v\u00fdpis\s+za\s+obdobie)\s*[:\-]?\s*"
        rf"{start_pattern}\s*(?:\bdo\b|\u2013|\u2014)\s*{end_pattern}",
    )
    intervals: set[tuple[date, date]] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            parsed = _parse_pair(match.group("start"), match.group("end"))
            if parsed is not None:
                intervals.add(parsed)
    if len(intervals) != 1:
        return None
    return next(iter(intervals))


def _statement_date_interval(text: str) -> tuple[date, date] | None:
    current_values = _label_dates(text, r"(?<!posledn[\u00fd y]\s)\bd[\u00e1a]tum")
    previous_values = _label_dates(
        text, r"\bposledn[\u00fd y]\s+v[\u00fd y]pis"
    )
    if len(current_values) != 1 or len(previous_values) != 1:
        return None
    previous = next(iter(previous_values))
    current = next(iter(current_values))
    return previous + timedelta(days=1), current


def _label_dates(text: str, label_pattern: str) -> set[date]:
    values: set[date] = set()
    pattern = rf"{label_pattern}\s*[:\-]?\s*(\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{4}})"
    for raw in re.findall(pattern, text, flags=re.IGNORECASE):
        parsed = _parse_date(raw)
        if parsed is not None:
            values.add(parsed)
    return values


def _parse_pair(start: str, end: str) -> tuple[date, date] | None:
    parsed_start = _parse_date(start)
    parsed_end = _parse_date(end)
    if parsed_start is None or parsed_end is None:
        return None
    return parsed_start, parsed_end


def _parse_date(raw: str) -> date | None:
    try:
        day, month, year = (int(part) for part in re.split(r"[./-]", raw))
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def _failure(status: str) -> GmailStatementPeriodResult:
    return GmailStatementPeriodResult(status=status, error_code=status)

