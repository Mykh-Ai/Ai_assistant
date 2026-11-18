"""Deterministic Phase 2 invoice calendar, arithmetic and summary."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from zoneinfo import ZoneInfo


BUSINESS_TIMEZONE = 'Europe/Bratislava'
CENT = Decimal('0.01')

CALCULATION_PROMPTS = {
    'calculation_service': 'Napíšte presný názov služby pre túto faktúru.',
    'calculation_period': 'Spresnite fakturované týždne alebo dátumy vrátane roka, ak je nejasný.',
    'calculation_issue': 'Napíšte dátum vystavenia vrátane roka, ak je nejasný.',
    'calculation_delivery': 'Spresnite dátum dodania alebo uveďte, ku ktorému týždňu patrí.',
    'calculation_due': 'Napíšte dátum alebo počet dní splatnosti.',
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


def _explicit_year(value, *, raw_text: str, default: int, slot: str) -> int:
    if value is None:
        return default
    if type(value) is not int:
        raise CalculationInputError(slot)
    for match in re.finditer(rf'(?<!\d){value}(?!\d)', raw_text):
        before = raw_text[max(0, match.start() - 5):match.start()]
        after = raw_text[match.end():match.end() + 16]
        if not re.search(r'(?:€|EUR|\$)\s*$', before, flags=re.IGNORECASE) and not re.match(
            r'(?:[.,]\d+)?\s*(?:€|EUR\b|USD\b|\$)', after, flags=re.IGNORECASE,
        ):
            return value
    raise CalculationInputError(slot)


def _week(week: int, year: int) -> dict:
    try:
        if type(week) is not int or type(year) is not int:
            raise ValueError
        monday = date.fromisocalendar(year, week, 1)
        sunday = monday + timedelta(days=6)
    except (ValueError, OverflowError) as exc:
        raise CalculationInputError('period') from exc
    return {'iso_year': year, 'kw': week, 'start': monday.isoformat(), 'end': sunday.isoformat()}


def resolve_date(intent, *, today: date, raw_text: str, slot: str, weeks: list[dict]) -> date | None:
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
            year = _explicit_year(intent.get('year'), raw_text=raw_text, default=today.year, slot=slot)
            return date(year, intent['month'], intent['day'])
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


def resolve_period(calculation: dict, *, today: date, raw_text: str) -> tuple[list[dict], str | None, str | None]:
    period = calculation.get('period_intent')
    explicit = calculation.get('iso_weeks')
    monday = today - timedelta(days=today.weekday())
    if explicit is not None:
        if not isinstance(explicit, list) or not 1 <= len(explicit) <= 53:
            raise CalculationInputError('period')
        weeks = []
        for item in explicit:
            if not isinstance(item, dict):
                raise CalculationInputError('period')
            iso_year = _explicit_year(
                item.get('iso_year'), raw_text=raw_text, default=today.isocalendar().year, slot='period',
            )
            if item.get('iso_year') is None and (today.month == 1 or today.month == 12) and item.get('kw') in (1, 52, 53):
                raise CalculationInputError('period')
            weeks.append(_week(item.get('kw'), iso_year))
        weeks.sort(key=lambda week: week['start'])
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
        start = resolve_date(calculation.get('period_start'), today=today, raw_text=raw_text, slot='period', weeks=[])
        end = resolve_date(calculation.get('period_end'), today=today, raw_text=raw_text, slot='period', weeks=[])
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
