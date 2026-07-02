from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
import json
import re
import sqlite3
import unicodedata

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openai import AsyncOpenAI

from bot.services.db import managed_connection


STATUS_OPEN = 'open'
STATUS_CLOSED = 'closed'
STATUS_SKIPPED = 'skipped'
STATUS_DAY_OFF = 'day_off'
STATUS_NON_WORKING = 'non_working'

SOURCE_OPENED_LIVE = 'opened_live'
SOURCE_CLOSED_LIVE = 'closed_live'
SOURCE_MANUAL_RANGE = 'manual_range'
SOURCE_MANUAL_DURATION = 'manual_duration'
SOURCE_GENERATED_CALENDAR = 'generated_calendar'


MONTH_NAMES_SK = {
    1: 'január',
    2: 'február',
    3: 'marec',
    4: 'apríl',
    5: 'máj',
    6: 'jún',
    7: 'júl',
    8: 'august',
    9: 'september',
    10: 'oktober',
    11: 'november',
    12: 'december',
}


@dataclass(frozen=True)
class WorkTimeDay:
    id: int
    telegram_id: int
    work_date: str
    start_time: str | None
    end_time: str | None
    total_minutes: int | None
    status: str
    source: str
    note: str | None


@dataclass(frozen=True)
class WorkTimeOperationResult:
    ok: bool
    day: WorkTimeDay | None = None
    reason: str = ''
    conflict_day: WorkTimeDay | None = None
    report_path: Path | None = None


@dataclass(frozen=True)
class WorkTimeCandidate:
    work_date: date
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int | None = None
    close_mode: str = 'unknown'
    needs_confirmation: bool = True

    @property
    def calculated_end_time(self) -> time | None:
        if self.end_time is not None:
            return self.end_time
        if self.start_time is not None and self.duration_minutes is not None:
            base = datetime.combine(self.work_date, self.start_time)
            return (base + timedelta(minutes=self.duration_minutes)).time().replace(second=0, microsecond=0)
        return None


class WorkTimeService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def open_day(
        self,
        *,
        telegram_id: int,
        now: datetime | None = None,
        source_message_id: int | None = None,
    ) -> WorkTimeOperationResult:
        current = _local_now(now)
        work_date = current.date().isoformat()
        start_value = _format_time(current.time())
        with managed_connection(self.db_path) as connection:
            open_day = self.get_open_day(telegram_id=telegram_id, connection=connection)
            if open_day is not None:
                if open_day.work_date == work_date:
                    return WorkTimeOperationResult(ok=True, day=open_day, reason='already_open')
                return WorkTimeOperationResult(ok=False, reason='previous_open_day', conflict_day=open_day)

            existing = self.get_day(telegram_id=telegram_id, work_date=work_date, connection=connection)
            if existing is not None:
                return WorkTimeOperationResult(ok=False, reason=f'already_{existing.status}', conflict_day=existing)

            cursor = connection.execute(
                """
                INSERT INTO work_time_days
                    (telegram_id, work_date, start_time, end_time, total_minutes, status, source, note)
                VALUES (?, ?, ?, NULL, NULL, ?, ?, NULL)
                """,
                (telegram_id, work_date, start_value, STATUS_OPEN, SOURCE_OPENED_LIVE),
            )
            day_id = int(cursor.lastrowid)
            self._record_event(
                connection,
                day_id=day_id,
                event_type='open',
                old_value=None,
                new_value={'start_time': start_value, 'work_date': work_date},
                source_message_id=source_message_id,
                telegram_id=telegram_id,
            )
            connection.commit()
            return WorkTimeOperationResult(ok=True, day=self.get_day_by_id(day_id, connection=connection))

    def close_open_day(
        self,
        *,
        telegram_id: int,
        end_datetime: datetime | None = None,
        duration_minutes: int | None = None,
        source: str = SOURCE_CLOSED_LIVE,
        source_message_id: int | None = None,
    ) -> WorkTimeOperationResult:
        current = _local_now(end_datetime)
        with managed_connection(self.db_path) as connection:
            day = self.get_open_day(telegram_id=telegram_id, connection=connection)
            if day is None:
                return WorkTimeOperationResult(ok=False, reason='no_open_day')
            if day.start_time is None:
                return WorkTimeOperationResult(ok=False, reason='missing_start_time', conflict_day=day)

            start_dt = datetime.combine(date.fromisoformat(day.work_date), _parse_time_value(day.start_time))
            if duration_minutes is not None:
                if duration_minutes <= 0:
                    return WorkTimeOperationResult(ok=False, reason='invalid_duration', conflict_day=day)
                end_dt = start_dt + timedelta(minutes=duration_minutes)
                close_source = SOURCE_MANUAL_DURATION
            else:
                end_dt = datetime.combine(date.fromisoformat(day.work_date), current.time().replace(second=0, microsecond=0))
                close_source = source
            if end_dt < start_dt:
                return WorkTimeOperationResult(ok=False, reason='end_before_start', conflict_day=day)
            total_minutes = int((end_dt - start_dt).total_seconds() // 60)
            end_value = _format_time(end_dt.time())
            connection.execute(
                """
                UPDATE work_time_days
                SET end_time = ?, total_minutes = ?, status = ?, source = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND telegram_id = ?
                """,
                (end_value, total_minutes, STATUS_CLOSED, close_source, day.id, telegram_id),
            )
            self._record_event(
                connection,
                day_id=day.id,
                event_type='close',
                old_value=day.__dict__,
                new_value={'end_time': end_value, 'total_minutes': total_minutes, 'source': close_source},
                source_message_id=source_message_id,
                telegram_id=telegram_id,
            )
            connection.commit()
            return WorkTimeOperationResult(ok=True, day=self.get_day_by_id(day.id, connection=connection))

    def add_manual_range(
        self,
        *,
        telegram_id: int,
        candidate: WorkTimeCandidate,
        source_message_id: int | None = None,
    ) -> WorkTimeOperationResult:
        if candidate.start_time is None or candidate.calculated_end_time is None:
            return WorkTimeOperationResult(ok=False, reason='missing_range')
        start_dt = datetime.combine(candidate.work_date, candidate.start_time)
        end_dt = datetime.combine(candidate.work_date, candidate.calculated_end_time)
        if end_dt < start_dt:
            return WorkTimeOperationResult(ok=False, reason='end_before_start')
        total_minutes = int((end_dt - start_dt).total_seconds() // 60)
        with managed_connection(self.db_path) as connection:
            existing = self.get_day(
                telegram_id=telegram_id,
                work_date=candidate.work_date.isoformat(),
                connection=connection,
            )
            if existing is not None and existing.status in {STATUS_OPEN, STATUS_CLOSED}:
                return WorkTimeOperationResult(ok=False, reason='conflict_same_day', conflict_day=existing)
            if existing is not None:
                connection.execute('DELETE FROM work_time_days WHERE id = ? AND telegram_id = ?', (existing.id, telegram_id))
            cursor = connection.execute(
                """
                INSERT INTO work_time_days
                    (telegram_id, work_date, start_time, end_time, total_minutes, status, source, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    telegram_id,
                    candidate.work_date.isoformat(),
                    _format_time(candidate.start_time),
                    _format_time(candidate.calculated_end_time),
                    total_minutes,
                    STATUS_CLOSED,
                    SOURCE_MANUAL_RANGE,
                ),
            )
            day_id = int(cursor.lastrowid)
            self._record_event(
                connection,
                day_id=day_id,
                event_type='open',
                old_value=None,
                new_value={'manual_range': True, 'total_minutes': total_minutes},
                source_message_id=source_message_id,
                telegram_id=telegram_id,
            )
            connection.commit()
            return WorkTimeOperationResult(ok=True, day=self.get_day_by_id(day_id, connection=connection))

    def add_duration_entry(
        self,
        *,
        telegram_id: int,
        candidate: WorkTimeCandidate,
        source_message_id: int | None = None,
    ) -> WorkTimeOperationResult:
        if candidate.duration_minutes is None or candidate.duration_minutes <= 0:
            return WorkTimeOperationResult(ok=False, reason='invalid_duration')
        with managed_connection(self.db_path) as connection:
            existing = self.get_day(
                telegram_id=telegram_id,
                work_date=candidate.work_date.isoformat(),
                connection=connection,
            )
            if existing is not None and existing.status in {STATUS_OPEN, STATUS_CLOSED}:
                return WorkTimeOperationResult(ok=False, reason='conflict_same_day', conflict_day=existing)
            if existing is not None:
                connection.execute('DELETE FROM work_time_days WHERE id = ? AND telegram_id = ?', (existing.id, telegram_id))
            cursor = connection.execute(
                """
                INSERT INTO work_time_days
                    (telegram_id, work_date, start_time, end_time, total_minutes, status, source, note)
                VALUES (?, ?, NULL, NULL, ?, ?, ?, NULL)
                """,
                (
                    telegram_id,
                    candidate.work_date.isoformat(),
                    candidate.duration_minutes,
                    STATUS_CLOSED,
                    SOURCE_MANUAL_DURATION,
                ),
            )
            day_id = int(cursor.lastrowid)
            self._record_event(
                connection,
                day_id=day_id,
                event_type='duration_entry',
                old_value=None,
                new_value={'duration_only': True, 'total_minutes': candidate.duration_minutes},
                source_message_id=source_message_id,
                telegram_id=telegram_id,
            )
            connection.commit()
            return WorkTimeOperationResult(ok=True, day=self.get_day_by_id(day_id, connection=connection))

    def skip_open_day(
        self,
        *,
        telegram_id: int,
        note: str = 'Preskocene pouzivatelom pri otvorenom dni.',
        source_message_id: int | None = None,
    ) -> WorkTimeOperationResult:
        with managed_connection(self.db_path) as connection:
            day = self.get_open_day(telegram_id=telegram_id, connection=connection)
            if day is None:
                return WorkTimeOperationResult(ok=False, reason='no_open_day')
            connection.execute(
                """
                UPDATE work_time_days
                SET status = ?, end_time = NULL, total_minutes = NULL, note = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND telegram_id = ?
                """,
                (STATUS_SKIPPED, note, day.id, telegram_id),
            )
            self._record_event(
                connection,
                day_id=day.id,
                event_type='skip',
                old_value=day.__dict__,
                new_value={'status': STATUS_SKIPPED, 'note': note},
                source_message_id=source_message_id,
                telegram_id=telegram_id,
            )
            connection.commit()
            return WorkTimeOperationResult(ok=True, day=self.get_day_by_id(day.id, connection=connection))

    def generate_monthly_report(
        self,
        *,
        telegram_id: int,
        year: int,
        month: int,
        output_dir: Path,
    ) -> WorkTimeOperationResult:
        rows = self.list_days_for_month(telegram_id=telegram_id, year=year, month=month)
        by_date = {row.work_date: row for row in rows}
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f'dochadzka_{year:04d}_{month:02d}.xlsx'
        title = f"Dochádzka — {MONTH_NAMES_SK[month]} {year}"

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Dochadzka'
        sheet['A1'] = title
        sheet['A1'].font = Font(bold=True, size=13)
        sheet.merge_cells('A1:D1')
        sheet.append([])
        sheet.append(['Dátum', 'Príchod', 'Odchod', 'Hodiny'])
        thin_side = Side(style='thin', color='D9E2EC')
        strong_side = Side(style='medium', color='7A8794')
        table_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        header_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=strong_side)
        total_border = Border(left=thin_side, right=thin_side, top=strong_side, bottom=thin_side)
        for cell in sheet[3]:
            cell.font = Font(bold=True)
            cell.border = header_border
            cell.alignment = Alignment(horizontal='center')

        total_minutes = 0
        _, day_count = monthrange(year, month)
        sunday_fill = PatternFill(fill_type='solid', fgColor='C6EFCE')
        for day_number in range(1, day_count + 1):
            current_date = date(year, month, day_number)
            record = by_date.get(current_date.isoformat())
            if record and record.status == STATUS_CLOSED and record.total_minutes is not None:
                hours = _format_duration(record.total_minutes)
                total_minutes += record.total_minutes
                row_values = [current_date.strftime('%d.%m.%Y'), record.start_time or '', record.end_time or '', hours]
            elif record and record.status == STATUS_SKIPPED:
                row_values = [current_date.strftime('%d.%m.%Y'), '', '', 'preskocene']
            else:
                row_values = [current_date.strftime('%d.%m.%Y'), '', '', '']
            sheet.append(row_values)
            for cell in sheet[sheet.max_row]:
                cell.border = table_border
            if current_date.weekday() == 6:
                for cell in sheet[sheet.max_row]:
                    cell.fill = sunday_fill

        sheet.append(['Spolu', '', '', _format_duration(total_minutes)])
        for cell in sheet[sheet.max_row]:
            cell.font = Font(bold=True)
            cell.border = total_border
        sheet.column_dimensions['A'].width = 14
        sheet.column_dimensions['B'].width = 11
        sheet.column_dimensions['C'].width = 11
        sheet.column_dimensions['D'].width = 14
        sheet.freeze_panes = 'A4'
        sheet.sheet_view.showGridLines = False
        sheet.print_area = f'A1:D{sheet.max_row}'
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(horizontal='center', vertical='center')
        workbook.save(report_path)

        with managed_connection(self.db_path) as connection:
            self._record_event(
                connection,
                day_id=None,
                event_type='report_generated',
                old_value=None,
                new_value={'year': year, 'month': month, 'path': str(report_path)},
                source_message_id=None,
                telegram_id=telegram_id,
            )
            connection.commit()
        return WorkTimeOperationResult(ok=True, report_path=report_path)

    def get_open_day(
        self,
        *,
        telegram_id: int,
        connection: sqlite3.Connection | None = None,
    ) -> WorkTimeDay | None:
        def _query(conn: sqlite3.Connection) -> WorkTimeDay | None:
            row = conn.execute(
                """
                SELECT id, telegram_id, work_date, start_time, end_time, total_minutes, status, source, note
                FROM work_time_days
                WHERE telegram_id = ? AND status = ?
                ORDER BY work_date ASC, id ASC
                LIMIT 1
                """,
                (telegram_id, STATUS_OPEN),
            ).fetchone()
            return _row_to_day(row)

        if connection is not None:
            return _query(connection)
        with managed_connection(self.db_path) as conn:
            return _query(conn)

    def get_day(
        self,
        *,
        telegram_id: int,
        work_date: str,
        connection: sqlite3.Connection | None = None,
    ) -> WorkTimeDay | None:
        def _query(conn: sqlite3.Connection) -> WorkTimeDay | None:
            row = conn.execute(
                """
                SELECT id, telegram_id, work_date, start_time, end_time, total_minutes, status, source, note
                FROM work_time_days
                WHERE telegram_id = ? AND work_date = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (telegram_id, work_date),
            ).fetchone()
            return _row_to_day(row)

        if connection is not None:
            return _query(connection)
        with managed_connection(self.db_path) as conn:
            return _query(conn)

    def get_day_by_id(
        self,
        day_id: int,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> WorkTimeDay | None:
        def _query(conn: sqlite3.Connection) -> WorkTimeDay | None:
            row = conn.execute(
                """
                SELECT id, telegram_id, work_date, start_time, end_time, total_minutes, status, source, note
                FROM work_time_days
                WHERE id = ?
                """,
                (day_id,),
            ).fetchone()
            return _row_to_day(row)

        if connection is not None:
            return _query(connection)
        with managed_connection(self.db_path) as conn:
            return _query(conn)

    def list_days_for_month(self, *, telegram_id: int, year: int, month: int) -> list[WorkTimeDay]:
        start = date(year, month, 1).isoformat()
        end = date(year, month, monthrange(year, month)[1]).isoformat()
        with managed_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, telegram_id, work_date, start_time, end_time, total_minutes, status, source, note
                FROM work_time_days
                WHERE telegram_id = ? AND work_date BETWEEN ? AND ?
                ORDER BY work_date ASC, id ASC
                """,
                (telegram_id, start, end),
            ).fetchall()
            return [_row_to_day(row) for row in rows if _row_to_day(row) is not None]

    def _record_event(
        self,
        connection: sqlite3.Connection,
        *,
        day_id: int | None,
        event_type: str,
        old_value: dict | None,
        new_value: dict | None,
        source_message_id: int | None,
        telegram_id: int | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO work_time_events
                (work_time_day_id, telegram_id, event_type, old_value, new_value, source_message_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                day_id,
                telegram_id,
                event_type,
                json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
                json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
                source_message_id,
            ),
        )


def parse_manual_range_candidate(text: str, *, today: date | None = None) -> WorkTimeCandidate | None:
    normalized = _normalize(text)
    work_date = _resolve_relative_date(normalized, today=today)
    matches = re.findall(r'\b(\d{1,2})(?::(\d{2}))?\b', normalized)
    if len(matches) < 2:
        return None
    start = _parse_match_time(matches[0])
    end = _parse_match_time(matches[1])
    if start is None or end is None:
        return None
    return WorkTimeCandidate(work_date=work_date, start_time=start, end_time=end, close_mode='manual_range')


def parse_duration_entry_candidate(text: str, *, today: date | None = None) -> WorkTimeCandidate | None:
    normalized = _normalize(text)
    duration_minutes = _parse_duration_minutes(normalized)
    if duration_minutes is None:
        return None
    return WorkTimeCandidate(
        work_date=_resolve_relative_date(normalized, today=today),
        duration_minutes=duration_minutes,
        close_mode='manual_duration',
    )

def parse_close_candidate(text: str, *, open_day: WorkTimeDay, today: date | None = None) -> WorkTimeCandidate | None:
    normalized = _normalize(text)
    work_date = date.fromisoformat(open_day.work_date)
    duration_match = re.search(
        r'\b(\d{1,2})(?:[,.](\d{1,2}))?\s*(?:hodin|hodiny|hodina|hod|h|godin|chas|casov|час|часов|годин)\b',
        normalized,
    )
    if duration_match:
        hours = int(duration_match.group(1))
        fraction = duration_match.group(2)
        minutes = 0
        if fraction:
            minutes = int(round(float(f'0.{fraction}') * 60))
        return WorkTimeCandidate(work_date=work_date, duration_minutes=hours * 60 + minutes, close_mode='close_with_duration')

    time_match = re.search(r'(?:\bo\b|\bv\b|\bat\b|в|о)\s*(\d{1,2})(?::(\d{2}))\b', normalized)
    if time_match:
        end_time = _parse_match_time((time_match.group(1), time_match.group(2)))
        if end_time is not None:
            return WorkTimeCandidate(work_date=work_date, end_time=end_time, close_mode='close_at_time')

    if any(term in normalized for term in ('teraz', 'now', 'зараз', 'сейчас')):
        return WorkTimeCandidate(work_date=_resolve_relative_date(normalized, today=today), close_mode='close_now', needs_confirmation=False)
    return WorkTimeCandidate(work_date=work_date, close_mode='close_now', needs_confirmation=False)


def parse_report_month(text: str, *, today: date | None = None) -> tuple[int, int]:
    current = today or date.today()
    normalized = _normalize(text)
    explicit_year = re.findall(r'\b((?:19|20)\d{2})\b', normalized)
    year = int(explicit_year[-1]) if explicit_year else current.year
    for month, names in _MONTH_ALIASES.items():
        if any(name in normalized for name in names):
            return year, month
    if 'minuly mesiac' in normalized or 'minuly mesiac' in normalized:
        previous = (current.replace(day=1) - timedelta(days=1))
        return previous.year, previous.month
    return year, current.month


async def resolve_work_time_entry_candidate(
    *,
    user_input_text: str,
    api_key: str | None,
    model: str,
    today: date | None = None,
    open_day: WorkTimeDay | None = None,
) -> WorkTimeCandidate | None:
    cleaned = user_input_text.strip()
    if not cleaned or not api_key or not api_key.startswith('sk-'):
        return None
    current = today or date.today()
    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={'type': 'json_object'},
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a bounded slot extractor for OfficeFlow work-time tracking. '
                        'Return strict JSON only. Supported input languages are Slovak, Ukrainian, Russian, English, and mixed STT-noisy text. '
                        'Extract only candidate work-time slots; never claim anything was saved. '
                        'Allowed shape: {"canonical":"work_time_entry","date":"YYYY-MM-DD","start_time":"HH:MM|null","end_time":"HH:MM|null","duration_minutes":<integer|null>} '
                        'or {"canonical":"unknown"}. '
                        'If the user says today/dnes/ukrainian today, use today_iso. If a work day is already open, use open_day_date. '
                        'Verbal hours such as "z piatej do deviatej", "from fifth morning to ninth morning", or "nine and a half hours" must be normalized to 24-hour HH:MM or duration minutes when clear. '
                        'For duration-only requests like "zapis dnes 10 hodin" or "close today nine and a half hours", set start_time and end_time to null and duration_minutes to the total. '
                        'Use unknown when date/time/duration is ambiguous.'
                    ),
                },
                {
                    'role': 'user',
                    'content': json.dumps(
                        {
                            'context_name': 'work_time_slot_extraction',
                            'today_iso': current.isoformat(),
                            'open_day_date': open_day.work_date if open_day else None,
                            'open_day_start_time': open_day.start_time if open_day else None,
                            'user_input_text': cleaned,
                            'expected_output': {
                                'canonical': 'work_time_entry or unknown',
                                'date': 'YYYY-MM-DD',
                                'start_time': 'HH:MM or null',
                                'end_time': 'HH:MM or null',
                                'duration_minutes': 'positive integer or null',
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        parsed = json.loads(response.choices[0].message.content or '{}')
    except Exception:
        return None

    if str(parsed.get('canonical') or '').strip() != 'work_time_entry':
        return None
    fallback_date = current if open_day is None else date.fromisoformat(open_day.work_date)
    candidate_date = _parse_llm_date(str(parsed.get('date') or ''), fallback=fallback_date)
    if candidate_date is None:
        return None
    start_time = _parse_llm_hhmm(parsed.get('start_time'))
    end_time = _parse_llm_hhmm(parsed.get('end_time'))
    duration_minutes = _parse_llm_duration(parsed.get('duration_minutes'))

    if open_day is not None:
        candidate_date = date.fromisoformat(open_day.work_date)
        if duration_minutes is not None:
            return WorkTimeCandidate(work_date=candidate_date, duration_minutes=duration_minutes, close_mode='close_with_duration')
        if end_time is not None:
            return WorkTimeCandidate(work_date=candidate_date, end_time=end_time, close_mode='close_at_time')
        return None

    if start_time is not None and end_time is not None:
        return WorkTimeCandidate(work_date=candidate_date, start_time=start_time, end_time=end_time, close_mode='manual_range')
    if duration_minutes is not None:
        return WorkTimeCandidate(work_date=candidate_date, duration_minutes=duration_minutes, close_mode='manual_duration')
    return None


def format_day_summary(day: WorkTimeDay) -> str:
    if day.status == STATUS_CLOSED:
        return f"{_format_date_sk(day.work_date)}: {day.start_time or '-'} - {day.end_time or '-'} ({_format_duration(day.total_minutes or 0)})"
    if day.status == STATUS_OPEN:
        return f"{_format_date_sk(day.work_date)}: otvoreny od {day.start_time or '-'}"
    if day.status == STATUS_SKIPPED:
        return f"{_format_date_sk(day.work_date)}: preskocene"
    return f"{_format_date_sk(day.work_date)}: {day.status}"


def format_candidate_preview(candidate: WorkTimeCandidate, *, open_day: WorkTimeDay | None = None) -> str:
    start_value = candidate.start_time
    if start_value is None and open_day is not None and open_day.start_time is not None:
        start_value = _parse_time_value(open_day.start_time)
    end_value = candidate.calculated_end_time
    if end_value is None and candidate.end_time is not None:
        end_value = candidate.end_time
    total = ''
    if start_value is not None and end_value is not None:
        total_minutes = int(
            (
                datetime.combine(candidate.work_date, end_value)
                - datetime.combine(candidate.work_date, start_value)
            ).total_seconds()
            // 60
        )
        total = _format_duration(total_minutes)
    elif candidate.duration_minutes is not None:
        total = _format_duration(candidate.duration_minutes)
    return (
        f"Datum: {_format_date_sk(candidate.work_date.isoformat())}\n"
        f"Prichod: {_format_time(start_value) if start_value else '-'}\n"
        f"Odchod: {_format_time(end_value) if end_value else '-'}\n"
        f"Hodiny: {total or '-'}"
    )


def _row_to_day(row) -> WorkTimeDay | None:
    if row is None:
        return None
    return WorkTimeDay(
        id=int(row[0]),
        telegram_id=int(row[1]),
        work_date=str(row[2]),
        start_time=row[3],
        end_time=row[4],
        total_minutes=None if row[5] is None else int(row[5]),
        status=str(row[6]),
        source=str(row[7]),
        note=row[8],
    )


def _local_now(value: datetime | None = None) -> datetime:
    return (value or datetime.now()).replace(second=0, microsecond=0)


def _format_time(value: time) -> str:
    return value.replace(second=0, microsecond=0).strftime('%H:%M')


def _parse_time_value(value: str) -> time:
    return datetime.strptime(value, '%H:%M').time()


def _format_duration(total_minutes: int) -> str:
    total_minutes = int(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    if minutes == 0:
        return f'{hours} hod.'
    decimal_hours = total_minutes / 60
    value = f'{decimal_hours:.2f}'.rstrip('0').rstrip('.').replace('.', ',')
    return f'{value} hod.'


def _parse_duration_minutes(normalized: str) -> int | None:
    match = re.search(
        r'\b(\d{1,3})(?:[,.](\d{1,2}))?\s*(?:hodin|hodiny|hodina|hod|h|godin|casov|chas)\b',
        normalized,
    )
    if not match:
        return None
    hours = int(match.group(1))
    fraction = match.group(2)
    minutes = 0
    if fraction:
        minutes = int(round(float(f'0.{fraction}') * 60))
    total = hours * 60 + minutes
    if total <= 0 or total > 24 * 60:
        return None
    return total


def _format_date_sk(value: str) -> str:
    parsed = date.fromisoformat(value)
    return parsed.strftime('%d.%m.%Y')


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value.casefold())
    without_marks = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', without_marks).strip()


def _parse_llm_date(value: str, *, fallback: date) -> date | None:
    if value in {'', 'None', 'null', 'unknown'}:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_llm_hhmm(value: object) -> time | None:
    if value is None:
        return None
    raw = str(value).strip()
    if raw.lower() in {'', 'none', 'null', 'unknown'}:
        return None
    if not re.fullmatch(r'\d{2}:\d{2}', raw):
        return None
    parsed = _parse_time_value(raw)
    if parsed.hour > 23 or parsed.minute > 59:
        return None
    return parsed


def _parse_llm_duration(value: object) -> int | None:
    if value is None:
        return None
    try:
        total = int(value)
    except (TypeError, ValueError):
        return None
    if total <= 0 or total > 24 * 60:
        return None
    return total


def _parse_match_time(match: tuple[str, str]) -> time | None:
    hour = int(match[0])
    minute = int(match[1] or '0')
    if hour > 23 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def _resolve_relative_date(normalized: str, *, today: date | None = None) -> date:
    current = today or date.today()
    if any(term in normalized for term in ('vcera', 'včera', 'vchera', 'вчора', 'вчера')):
        return current - timedelta(days=1)
    return current


_MONTH_ALIASES = {
    1: ('januar', 'jan', 'січень', 'январ'),
    2: ('februar', 'feb', 'лютий', 'феврал'),
    3: ('marec', 'marci', 'march', 'березень', 'март'),
    4: ('april', 'apr', 'квітень', 'апрел'),
    5: ('maj', 'may', 'травень', 'май'),
    6: ('jun', 'june', 'jún', 'червень', 'июн'),
    7: ('jul', 'july', 'júl', 'липень', 'июл'),
    8: ('august', 'aug', 'серпень', 'август'),
    9: ('september', 'sep', 'вересень', 'сентябр'),
    10: ('oktober', 'oct', 'жовтень', 'октябр'),
    11: ('november', 'nov', 'листопад', 'ноябр'),
    12: ('december', 'dec', 'грудень', 'декабр'),
}
