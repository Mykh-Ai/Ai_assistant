from __future__ import annotations

from datetime import datetime, date
from pathlib import Path

from openpyxl import load_workbook

from bot.services.db import init_db
from bot.services.work_time import (
    WorkTimeCandidate,
    WorkTimeService,
    parse_close_candidate,
    parse_manual_range_candidate,
    parse_report_month,
    _format_duration,
)


def test_close_with_duration_calculates_end_time_and_total(tmp_path: Path) -> None:
    db_path = tmp_path / 'test.db'
    init_db(db_path)
    service = WorkTimeService(db_path)

    opened = service.open_day(telegram_id=1001, now=datetime(2026, 6, 15, 7, 12))
    assert opened.ok
    closed = service.close_open_day(telegram_id=1001, duration_minutes=600)

    assert closed.ok
    assert closed.day is not None
    assert closed.day.start_time == '07:12'
    assert closed.day.end_time == '17:12'
    assert closed.day.total_minutes == 600
    assert closed.day.status == 'closed'


def test_manual_range_requires_no_conflicting_same_day_entry(tmp_path: Path) -> None:
    db_path = tmp_path / 'test.db'
    init_db(db_path)
    service = WorkTimeService(db_path)
    candidate = parse_manual_range_candidate('pracoval som dnes od 5:30 do 17:00', today=date(2026, 6, 15))
    assert candidate is not None

    first = service.add_manual_range(telegram_id=1001, candidate=candidate)
    second = service.add_manual_range(telegram_id=1001, candidate=candidate)

    assert first.ok
    assert not second.ok
    assert second.reason == 'conflict_same_day'


def test_previous_open_day_blocks_new_open_day(tmp_path: Path) -> None:
    db_path = tmp_path / 'test.db'
    init_db(db_path)
    service = WorkTimeService(db_path)

    assert service.open_day(telegram_id=1001, now=datetime(2026, 6, 14, 7, 0)).ok
    blocked = service.open_day(telegram_id=1001, now=datetime(2026, 6, 15, 7, 0))

    assert not blocked.ok
    assert blocked.reason == 'previous_open_day'
    assert blocked.conflict_day is not None
    assert blocked.conflict_day.work_date == '2026-06-14'


def test_report_includes_all_days_sundays_and_total(tmp_path: Path) -> None:
    db_path = tmp_path / 'test.db'
    init_db(db_path)
    service = WorkTimeService(db_path)
    candidate = parse_manual_range_candidate('pracoval som dnes od 08:00 do 17:00', today=date(2026, 7, 1))
    assert candidate is not None
    assert service.add_manual_range(telegram_id=1001, candidate=candidate).ok

    report = service.generate_monthly_report(
        telegram_id=1001,
        year=2026,
        month=7,
        output_dir=tmp_path / 'reports',
    )

    assert report.ok
    assert report.report_path is not None
    assert report.report_path.name == 'dochadzka_2026_07.xlsx'
    workbook = load_workbook(report.report_path)
    sheet = workbook.active
    assert sheet.max_column == 4
    assert sheet.max_row == 35  # title, blank, header, 31 days, total
    assert 'A1:D1' in {str(range_) for range_ in sheet.merged_cells.ranges}
    assert sheet['A1'].value == 'Dochádzka — júl 2026'
    assert sheet['A1'].font.bold
    assert sheet['A1'].font.sz == 13
    assert [sheet[f'{column}3'].value for column in 'ABCD'] == ['Dátum', 'Príchod', 'Odchod', 'Hodiny']
    assert all(sheet[f'{column}3'].font.bold for column in 'ABCD')
    assert all(sheet[f'{column}3'].border.bottom.style == 'medium' for column in 'ABCD')
    assert sheet['A4'].value == '01.07.2026'
    assert sheet['B4'].value == '08:00'
    assert sheet['C4'].value == '17:00'
    assert sheet['D4'].value == '9 hod.'
    assert sheet['A35'].value == 'Spolu'
    assert sheet['D35'].value == '9 hod.'
    assert sheet['A35'].font.bold
    assert sheet['D35'].font.bold
    assert all(sheet[f'{column}35'].border.top.style == 'medium' for column in 'ABCD')
    sunday_row = 8  # 05.07.2026
    assert all(sheet[f'{column}{sunday_row}'].fill.fgColor.rgb in {'00C6EFCE', 'C6EFCE'} for column in 'ABCD')
    assert [sheet.column_dimensions[column].width for column in 'ABCD'] == [14, 11, 11, 14]


def test_format_duration_uses_compact_hour_labels() -> None:
    assert _format_duration(540) == '9 hod.'
    assert _format_duration(570) == '9,5 hod.'
    assert _format_duration(6000) == '100 hod.'
    assert _format_duration(6030) == '100,5 hod.'


def test_parsers_separate_duration_from_clock_time() -> None:
    open_day = WorkTimeService.__new__(WorkTimeService)  # type: ignore[misc]
    del open_day
    from bot.services.work_time import WorkTimeDay

    day = WorkTimeDay(1, 1001, '2026-06-15', '07:12', None, None, 'open', 'opened_live', None)
    duration = parse_close_candidate('zatvor den 10 hodin', open_day=day)
    explicit = parse_close_candidate('zatvor dnes o 17:00', open_day=day)

    assert duration is not None
    assert duration.duration_minutes == 600
    assert duration.close_mode == 'close_with_duration'
    assert explicit is not None
    assert explicit.end_time is not None
    assert explicit.end_time.strftime('%H:%M') == '17:00'
    assert explicit.close_mode == 'close_at_time'


def test_report_month_defaults_year_and_month() -> None:
    assert parse_report_month('vytvor vykaz hodin za jun', today=date(2026, 7, 1)) == (2026, 6)
    assert parse_report_month('sformuj dochadzku za jun 2025', today=date(2026, 7, 1)) == (2025, 6)
