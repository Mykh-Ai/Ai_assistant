"""Deterministic Phase 2 invoice calendar, arithmetic and summary."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from zoneinfo import ZoneInfo

from bot.services.invoice_date_evidence import explicit_date_year


BUSINESS_TIMEZONE = 'Europe/Bratislava'
CENT = Decimal('0.01')
MAX_IMPLICIT_DATE_PAST_DAYS = 120
MAX_IMPLICIT_DATE_FUTURE_DAYS = 30
_KW_MARKER = re.compile(r'(?<!\w)(?:(?P<year>\d{4})-W|(?:KW|ISO[- ]?(?:week|W))(?=\d|\W|$))\s*', re.I)
_WEEK_NUMBER = re.compile(r'\d+')
_WEEK_UNIT = r'(?:[€$]|EUR\b|USD\b|euro\b|євро\b|евро\b|h\b|hod\w*\b|годин\w*\b|час\w*\b|noc\w*\b|ноч\w*\b)'
_NON_WEEK_VALUE = re.compile(rf'(?:[.,]\d+)?\s*{_WEEK_UNIT}', re.I)
_WEEK_YEAR = re.compile(rf'(?:\s*/\s*|\s+(?:rok(?:u)?\s+|року\s+|года\s+)?)(\d{{4}})(?!\w|[.,]\d|\s*{_WEEK_UNIT})', re.I)
_WEEK_SEPARATOR = re.compile(
    r'\s*(?:(?P<range>[-–—]|\.{2}|\b(?:až|до|по)\b)|'
    r'(?P<list>(?:,\s*)?\b(?:а\s+так(?:ож|же)|a|aj|and|i|і|й|та|и)\b|[,;/&+])|'
    r'(?P<alternative>\b(?:alebo|або|или|либо)\b))\s*', re.I,
)
_SPOKEN_WEEK_NUMBER = re.compile(
    r'(?:jed(?:en|na)|dva|dve|tri|štyr\w*|päť\w*|šesť\w*|sedem\w*|osem\w*|deväť\w*|'
    r'desať\w*|dvadsať\w*|tridsať\w*|štyridsať\w*|päťdesiat\w*|'
    r'один|одна|два|дві|две|три|чотир\w*|четыр\w*|п[’\']?ят\w*|'
    r'шіст\w*|шест\w*|сім\w*|сем\w*|вісім\w*|восем\w*|дев[’\']?ят\w*|'
    r'десят\w*|двадцят\w*|двадцат\w*|тридцят\w*|тридцат\w*|сорок\w*)\b', re.I,
)
_NUMBERED_WEEK = re.compile(
    r'(?<![\d.,])(?P<week>\d{1,2})(?:[.]|-(?:й|ий|ій|го|му|я|ю|ої)|(?=\s+(?:kalendárn\w*|календарн\w*|ISO)\b))\s*'
    r'(?:(?:kalendárn\w*|календарн\w*|ISO)\s+)?(?:týžd\w*|тиж\w*|недел\w*|weeks?)\b',
    re.IGNORECASE,
)

CALCULATION_PROMPTS = {
    'calculation_service': 'Napíšte presný názov služby pre túto faktúru.',
    'calculation_period': 'Spresnite fakturované týždne alebo dátumy vrátane roka, ak je nejasný.',
    'calculation_issue': 'Napíšte dátum vystavenia vrátane roka, ak je nejasný.',
    'calculation_delivery': 'Spresnite dátum dodania vrátane roka, ak je nejasný, alebo uveďte týždeň.',
    'calculation_due': 'Napíšte počet dní splatnosti alebo dátum vrátane roka, ak je nejasný.',
    'calculation_hours': 'Uveďte celkový počet hodín alebo úplný rozpis po týždňoch.',
    'calculation_rate': 'Uveďte hodinovú sadzbu v EUR.',
    'calculation_lodging': 'Uveďte počet nocí a cenu za noc pre každú skupinu ubytovania.',
    'calculation_amount': 'Spresnite sumu za prácu a konečnú sumu po prípadnom odpočítaní ubytovania.',
}


class CalculationInputError(ValueError):
    def __init__(self, slot: str) -> None:
        self.slot = f'calculation_{slot}'
        super().__init__(CALCULATION_PROMPTS[self.slot])


def business_clock() -> dict:
    now = datetime.now(UTC)
    today = now.astimezone(ZoneInfo(BUSINESS_TIMEZONE)).date()
    year, week, weekday = today.isocalendar()
    return {
        'business_now_utc': now.isoformat(), 'business_today': today.isoformat(),
        'business_timezone': BUSINESS_TIMEZONE,
        'iso_year': year, 'iso_week': week, 'iso_weekday': weekday,
    }


def decimal_value(value, slot: str, *, zero_allowed: bool = False) -> Decimal:
    number_text = str(value).strip().replace(',', '.')
    if not re.fullmatch(r'[0-9]{1,10}(?:\.[0-9]{1,6})?', number_text):
        raise CalculationInputError(slot)
    try:
        number = Decimal(number_text)
    except InvalidOperation as exc:
        raise CalculationInputError(slot) from exc
    if not zero_allowed and number == 0:
        raise CalculationInputError(slot)
    return number


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _week(week: int, year: int) -> dict:
    try:
        if type(week) is not int or type(year) is not int:
            raise ValueError
        monday = date.fromisocalendar(year, week, 1)
        sunday = monday + timedelta(days=6)
    except (ValueError, OverflowError) as exc:
        raise CalculationInputError('period') from exc
    return {'iso_year': year, 'kw': week, 'start': monday.isoformat(), 'end': sunday.isoformat()}


def _implicit_date(month: int, day: int, references: tuple[date, ...], slot: str) -> date:
    if type(month) is not int or type(day) is not int:
        raise CalculationInputError(slot)
    for reference in references:
        for year in (reference.year, reference.year - 1, reference.year + 1):
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            if -MAX_IMPLICIT_DATE_PAST_DAYS <= (candidate - reference).days <= MAX_IMPLICIT_DATE_FUTURE_DAYS:
                return candidate
    raise CalculationInputError(slot)


def resolve_date(
    intent, *, today: date, raw_text: str, slot: str, weeks: list[dict],
    references: tuple[date, ...] = (), field: str | None = None,
) -> date | None:
    if intent is None:
        return None
    if not isinstance(intent, dict):
        raise CalculationInputError(slot)
    kind = intent.get('kind')
    try:
        if kind in ('today', 'yesterday', 'day_before_yesterday', 'tomorrow'):
            offset = {'today': 0, 'yesterday': -1, 'day_before_yesterday': -2, 'tomorrow': 1}[kind]
            return today + timedelta(days=offset)
        if kind == 'date':
            day, month = intent['day'], intent['month']
            if type(day) is not int or type(month) is not int:
                raise CalculationInputError(slot)
            year = explicit_date_year(raw_text, day=day, month=month, field=field or slot)
            if year is not None:
                return date(year, month, day)
            return _implicit_date(month, day, references or (today,), slot)
        if kind in ('last_weekday', 'period_last_weekday'):
            weekday = intent.get('weekday')
            if type(weekday) is not int or not 1 <= weekday <= 7:
                raise ValueError
            if kind == 'period_last_weekday':
                if not weeks:
                    raise ValueError
                return date.fromisoformat(weeks[-1]['start']) + timedelta(days=weekday - 1)
            return today - timedelta(days=(today.isoweekday() - weekday) % 7 or 7)
    except (KeyError, OverflowError, ValueError, TypeError) as exc:
        raise CalculationInputError(slot) from exc
    raise CalculationInputError(slot)


def _nearest_iso_week(kw: int, reference: date) -> dict:
    candidates = []
    iso_year = reference.isocalendar().year
    for year in (iso_year - 1, iso_year, iso_year + 1):
        try:
            week = _week(kw, year)
        except CalculationInputError:
            continue
        start, end = date.fromisoformat(week['start']), date.fromisoformat(week['end'])
        distance = max((start - reference).days, (reference - end).days, 0)
        candidates.append((distance, start, week))
    if not candidates:
        raise CalculationInputError('period')
    return min(candidates)[2]


def _week_member(raw_text: str, start: int, marker: re.Match | None) -> tuple[tuple[int, int | None], int] | None:
    number = _WEEK_NUMBER.match(raw_text, marker.end() if marker else start)
    if number is None or (marker is None and _NON_WEEK_VALUE.match(raw_text, number.end())):
        return None
    kw = int(number[0]) if len(number[0]) <= 2 else 0
    if not 1 <= kw <= 53 or (number.end() < len(raw_text) and raw_text[number.end()].isalpha()):
        raise CalculationInputError('period')
    suffix = _WEEK_YEAR.match(raw_text, number.end())
    literal_year = marker['year'] if marker else None
    if literal_year and suffix and literal_year != suffix[1]:
        raise CalculationInputError('period')
    year = literal_year or (suffix[1] if suffix else None)
    return (kw, int(year) if year else None), suffix.end() if suffix else number.end()


def _week_range(
    first: tuple[int, int | None], last: tuple[int, int | None], reference: date | None,
) -> list[tuple[int, int | None]]:
    start_kw, start_year = first
    end_kw, end_year = last
    rollover = end_kw < start_kw
    if start_year is None and end_year is None:
        if reference is None and not rollover:
            return [(kw, None) for kw in range(start_kw, end_kw + 1)]
        if reference is None:
            raise CalculationInputError('period')
        start_year = _nearest_iso_week(start_kw, reference)['iso_year']
        if rollover:
            end_year = _nearest_iso_week(end_kw, reference)['iso_year']
            if end_year != start_year + 1:
                raise CalculationInputError('period')
    if start_year is None:
        start_year = end_year - rollover
    if end_year is None:
        end_year = start_year + rollover
    start = date.fromisoformat(_week(start_kw, start_year)['start'])
    end = date.fromisoformat(_week(end_kw, end_year)['start'])
    count = (end - start).days // 7 + 1
    if not 1 <= count <= 53:
        raise CalculationInputError('period')
    weeks = []
    for offset in range(count):
        year, kw, _ = (start + timedelta(weeks=offset)).isocalendar()
        weeks.append((kw, year))
    return weeks


def explicit_week_references(raw_text: str, *, reference: date | None = None) -> list[tuple[int, int | None]]:
    references = []
    cursor = 0
    while marker := _KW_MARKER.search(raw_text, cursor):
        first = _week_member(raw_text, marker.start(), marker)
        if first is None:
            raise CalculationInputError('period')
        current, cursor = first
        group = [current]
        previous_was_range = False
        while separator := _WEEK_SEPARATOR.match(raw_text, cursor):
            start = separator.end()
            next_marker = _KW_MARKER.match(raw_text, start)
            member = _week_member(raw_text, start, next_marker)
            if member is None:
                value = _WEEK_NUMBER.match(raw_text, start)
                non_week = _NON_WEEK_VALUE.match(raw_text, value.end()) if value else None
                if non_week:
                    if separator[0] == ',' and non_week[0].startswith(','):
                        raise CalculationInputError('period')
                    break
                if (separator['range'] or separator['list'] == '/' or next_marker or _SPOKEN_WEEK_NUMBER.match(raw_text, start)
                        or start == len(raw_text) or raw_text[start] == '?'):
                    raise CalculationInputError('period')
                break
            following, cursor = member
            if separator['alternative'] or (previous_was_range and separator['range']):
                raise CalculationInputError('period')
            if separator['range']:
                group[-1:] = _week_range(current, following, reference)
            else:
                group.append(following)
            current = following
            previous_was_range = bool(separator['range'])
        references.extend(group)
    for match in _NUMBERED_WEEK.finditer(raw_text):
        suffix = _WEEK_YEAR.match(raw_text, match.end())
        references.append((int(match['week']), int(suffix[1]) if suffix else None))
    return list(dict.fromkeys(references))


def resolve_period(
    calculation: dict, *, today: date, raw_text: str, issue: date | None = None,
    date_sources: dict[str, str] | None = None,
) -> tuple[list[dict], str | None, str | None]:
    period = calculation.get('period_intent')
    monday = today - timedelta(days=today.weekday())
    literals = explicit_week_references(raw_text, reference=issue or today)
    if literals or period == 'explicit_iso_weeks':
        if not 1 <= len(literals) <= 53:
            raise CalculationInputError('period')
        weeks = sorted((
            _week(kw, year) if year is not None else _nearest_iso_week(kw, issue or today)
            for kw, year in literals
        ), key=lambda week: week['start'])
        if len({week['start'] for week in weeks}) != len(weeks):
            raise CalculationInputError('period')
        return weeks, weeks[0]['start'], weeks[-1]['end']
    if period in (None, 'none'):
        return [], None, None
    offsets = {'this_week': (0,), 'previous_week': (-1,), 'previous_two_completed_weeks': (-2, -1)}
    if isinstance(period, str) and period in offsets:
        weeks = []
        for offset in offsets[period]:
            year, week, _ = (monday + timedelta(weeks=offset)).isocalendar()
            weeks.append(_week(week, year))
        return weeks, weeks[0]['start'], weeks[-1]['end']
    if period == 'explicit_dates':
        sources = date_sources or {}
        endpoints = {}
        # An explicit/relative endpoint is a stronger reference than the issue date for its yearless partner.
        fields = ('period_start', 'period_end')
        try:
            order = sorted(fields, key=lambda field: _is_yearless(
                calculation.get(field), raw_text=sources.get(field, raw_text), field=field,
            ))
        except ValueError as exc:
            raise CalculationInputError('period') from exc
        for field in order:
            other = next(iter(endpoints.values()), None)
            endpoints[field] = resolve_date(
                calculation.get(field), today=today, raw_text=sources.get(field, raw_text), slot='period',
                weeks=[], references=(other or issue or today,), field=field,
            )
        start, end = (endpoints[field] for field in fields)
        if start is None or end is None or not 0 <= (end - start).days <= 366:
            raise CalculationInputError('period')
        cursor = start - timedelta(days=start.weekday())
        weeks = []
        while cursor <= end:
            year, week, _ = cursor.isocalendar()
            weeks.append(_week(week, year))
            cursor += timedelta(weeks=1)
        return weeks, start.isoformat(), end.isoformat()
    raise CalculationInputError('period')


def _is_yearless(intent, *, raw_text: str, field: str) -> bool:
    return (
        isinstance(intent, dict) and intent.get('kind') == 'date'
        and explicit_date_year(raw_text, day=intent.get('day'), month=intent.get('month'), field=field) is None
    )


def needs_calculation(calculation: dict) -> bool:
    return any(calculation.get(key) is not None for key in (
        'hours_total', 'hours_by_kw', 'hourly_rate',
        'gross_amount', 'net_amount',
    )) or bool(calculation.get('lodging_groups')) or calculation.get('lodging_mentioned') is True


def calculate_amounts(calculation: dict, *, contact_rate, weeks: list[dict]) -> dict:
    hours_given = calculation.get('hours_total')
    split = calculation.get('hours_by_kw')
    split_result = None
    hours = decimal_value(hours_given, 'hours') if hours_given is not None else None
    if split is not None:
        if not isinstance(split, list) or not weeks or len(split) != len(weeks):
            raise CalculationInputError('hours')
        expected = {(week['iso_year'], week['kw']) for week in weeks}
        split_result = []
        allocated = Decimal(0)
        for group in split:
            if not isinstance(group, dict):
                raise CalculationInputError('hours')
            kw = group.get('kw')
            year = group.get('iso_year')
            if year is None:
                matches = [week['iso_year'] for week in weeks if week['kw'] == kw]
                year = matches[0] if len(matches) == 1 else None
            if type(kw) is not int or type(year) is not int or (year, kw) not in expected:
                raise CalculationInputError('hours')
            expected.remove((year, kw))
            duration = decimal_value(group.get('hours'), 'hours', zero_allowed=True)
            allocated += duration
            split_result.append({'iso_year': year, 'kw': kw, 'hours': str(duration)})
        if not allocated or (hours is not None and allocated != hours):
            raise CalculationInputError('hours')
        hours = allocated
        split_result.sort(key=lambda group: (group['iso_year'], group['kw']))

    raw_rate = calculation.get('hourly_rate')
    rate = None
    rate_source = None
    if hours is not None or raw_rate is not None:
        if hours is None:
            raise CalculationInputError('hours')
        rate = decimal_value(raw_rate if raw_rate is not None else contact_rate, 'rate')
        rate_source = 'explicit' if raw_rate is not None else 'contact'

    lodging = calculation.get('lodging_groups')
    if lodging is None:
        if calculation.get('lodging_mentioned'):
            raise CalculationInputError('lodging')
        lodging = []
    if not isinstance(lodging, list) or len(lodging) > 24 or (not lodging and calculation.get('lodging_mentioned')):
        raise CalculationInputError('lodging')
    groups = []
    lodging_total = Decimal(0)
    for group in lodging:
        if not isinstance(group, dict) or type(group.get('nights')) is not int or not 1 <= group['nights'] <= 366:
            raise CalculationInputError('lodging')
        price = decimal_value(group.get('price_per_night'), 'lodging', zero_allowed=True)
        subtotal = money(price * group['nights'])
        lodging_total += subtotal
        groups.append({'nights': group['nights'], 'price_per_night': str(price), 'subtotal': str(subtotal)})

    gross_raw = calculation.get('gross_amount')
    net_raw = calculation.get('net_amount')
    explicit_gross = money(decimal_value(gross_raw, 'amount')) if gross_raw is not None else None
    explicit_net = money(decimal_value(net_raw, 'amount')) if net_raw is not None else None
    if calculation.get('amount_kind') == 'ambiguous':
        raise CalculationInputError('amount')
    gross = money(hours * rate) if hours is not None and rate is not None else explicit_gross
    if gross is None and explicit_net is not None:
        gross = explicit_net + lodging_total
    if gross is None or (explicit_gross is not None and explicit_gross != gross):
        raise CalculationInputError('amount')
    net = gross - lodging_total
    if net <= 0 or Decimal(str(float(net))) != net or (explicit_net is not None and explicit_net != net):
        raise CalculationInputError('amount')
    return {
        'hours_total': str(hours) if hours is not None else None,
        'hours_by_kw': split_result, 'hours_by_kw_source': 'explicit' if split_result is not None else None,
        'hourly_rate': str(rate) if rate is not None else None, 'rate_source': rate_source,
        'gross': str(gross), 'lodging_groups': groups, 'lodging_total': str(money(lodging_total)), 'net': str(net),
    }


def invalidate_calculation(bundle: dict, *, effective_total) -> dict:
    historical = dict(bundle)
    if historical.get('status') == 'valid':
        historical['historical_net'] = historical.pop('net')
        historical['invalidated_at'] = datetime.now(UTC).isoformat()
        historical['invalidation_reason'] = 'manual_invoice_edit'
    historical['status'] = 'invalidated'
    historical['effective_invoice_total'] = str(money(Decimal(str(effective_total))))
    return historical


def format_calculation_summary(bundle: dict, *, supplier_name: str, customer_name: str) -> str:
    lines = ['Kontrola výpočtu faktúry', f'Dodávateľ: {supplier_name}', f'Odberateľ: {customer_name}']
    if bundle['status'] == 'invalidated':
        return '\n'.join(lines + [
            'Suma bola upravená ručne. Predchádzajúci výpočet je už len historický.',
            f"Konečná suma: {bundle['effective_invoice_total']} EUR",
        ])
    source = bundle.get('service_source_invoice')
    if profile := bundle.get('workspace_id'):
        lines.append(f'Profil: {profile}')
    lines.append(f"Služba: {bundle['service_name']}" + (f' (z faktúry {source})' if source else ''))
    for week in bundle['iso_weeks']:
        lines.append(f"KW {week['kw']}/{week['iso_year']} ({week['start']} – {week['end']})")
    if bundle.get('project_name'):
        lines.append(f"Projekt: {bundle['project_name']}")
    if bundle.get('hours_total') is not None:
        lines.append(f"Hodiny spolu: {bundle['hours_total']}")
        if bundle['hours_by_kw'] is None and bundle['iso_weeks']:
            lines.append('Rozpis hodín po týždňoch nebol zadaný.')
        for group in bundle['hours_by_kw'] or ():
            lines.append(f"KW {group['kw']}/{group['iso_year']}: {group['hours']} h")
    if bundle.get('hourly_rate') is not None:
        source = 'z kontaktu' if bundle['rate_source'] == 'contact' else 'zadaná pre túto faktúru'
        lines.append(f"Sadzba: {bundle['hourly_rate']} EUR/h ({source})")
    lines.append(f"Práca: {bundle['gross']} {bundle['currency']}")
    for group in bundle['lodging_groups']:
        lines.append(f"Ubytovanie: {group['nights']} × {group['price_per_night']} EUR = {group['subtotal']} EUR")
    if bundle['lodging_groups']:
        lines.append(f"Ubytovanie spolu: −{bundle['lodging_total']} EUR")
    lines.extend((
        f"Konečná suma: {bundle['net']} {bundle['currency']}",
        f"Vystavenie: {bundle['issue_date']} · Dodanie: {bundle['delivery_date']} · Splatnosť: {bundle['due_date']}",
    ))
    if bundle.get('overlap_invoice_numbers'):
        lines.append('Rovnaký fakturovaný týždeň je už v: ' + ', '.join(bundle['overlap_invoice_numbers']) + '.')
    return '\n'.join(lines)
