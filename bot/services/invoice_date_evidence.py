"""Literal calendar-date evidence shared by invoice intake paths."""

import re


ISSUE_DATE_CUE_PATTERN = re.compile(
    r'(?:'
    r'\b(?:d[aá]tum\s+)?vystavenia\b'
    r'|\b(?:datum|d[aá]tum)\s+vystavenia\b'
    r'|(?:дата|датом|датум)\s+'
    r'(?:'
    r'виставлення|выставления|виставлен[іяя]|выставлен[ияя]'
    r'|вытворення|вытворения|створення|создания'
    r')'
    r')',
    flags=re.IGNORECASE,
)
DAY_MONTH_NAME_PATTERN = re.compile(
    r'(?<!\d)(?P<day>0?[1-9]|[12]\d|3[01])\s*(?:[.\-/]\s*|\s+)'
    r'(?P<month>'
    r'janu[aá]r[a]?|jan'
    r'|febru[aá]r[a]?|feb'
    r'|marec|marca|mar'
    r'|apr[ií]l[a]?|apr'
    r'|m[aá]j[a]?'
    r'|j[uú]n[a]?'
    r'|j[uú]l[a]?'
    r'|august[a]?|aug'
    r'|sept(?:ember|embra)?|sep'
    r'|okt(?:[oó]ber|[oó]bra)?|okt'
    r'|nov(?:ember|embra)?|nov'
    r'|dec(?:ember|embra)?|dec'
    r'|январ[ья]|янв'
    r'|феврал[ья]|фев'
    r'|март[ае]?|марта|мар'
    r'|апрел[ья]|апр'
    r'|ма[йя]'
    r'|июн[ья]|июн'
    r'|июл[ья]|июл'
    r'|август[ае]?|авг'
    r'|сентябр[ья]|сен'
    r'|октябр[ья]|окт'
    r'|ноябр[ья]|ноя'
    r'|декабр[ья]|дек'
    r'|січня|січ'
    r'|лютого|лют'
    r'|березня|бер'
    r'|квітня|квіт'
    r'|травня|трав'
    r'|червня|черв'
    r'|липня|лип'
    r'|серпня|серп'
    r'|вересня|вер'
    r'|жовтня|жовт'
    r'|листопада|лист'
    r'|грудня|груд'
    r')\b',
    flags=re.IGNORECASE,
)
MONTH_TOKEN_TO_NUMBER = {
    'januar': 1,
    'januara': 1,
    'jan': 1,
    'februar': 2,
    'februara': 2,
    'feb': 2,
    'marec': 3,
    'marca': 3,
    'mar': 3,
    'april': 4,
    'aprila': 4,
    'apr': 4,
    'maj': 5,
    'maja': 5,
    'jun': 6,
    'juna': 6,
    'jul': 7,
    'jula': 7,
    'august': 8,
    'augusta': 8,
    'aug': 8,
    'september': 9,
    'septembra': 9,
    'sep': 9,
    'oktober': 10,
    'oktobra': 10,
    'okt': 10,
    'november': 11,
    'novembra': 11,
    'nov': 11,
    'december': 12,
    'decembra': 12,
    'dec': 12,
    'январь': 1,
    'января': 1,
    'янв': 1,
    'февраль': 2,
    'февраля': 2,
    'фев': 2,
    'март': 3,
    'марта': 3,
    'апрель': 4,
    'апреля': 4,
    'апр': 4,
    'май': 5,
    'мая': 5,
    'июнь': 6,
    'июня': 6,
    'июн': 6,
    'июль': 7,
    'июля': 7,
    'июл': 7,
    'август': 8,
    'августа': 8,
    'авг': 8,
    'сентябрь': 9,
    'сентября': 9,
    'сен': 9,
    'октябрь': 10,
    'октября': 10,
    'окт': 10,
    'ноябрь': 11,
    'ноября': 11,
    'ноя': 11,
    'декабрь': 12,
    'декабря': 12,
    'дек': 12,
    'січня': 1,
    'січ': 1,
    'лютого': 2,
    'лют': 2,
    'березня': 3,
    'бер': 3,
    'квітня': 4,
    'квіт': 4,
    'травня': 5,
    'трав': 5,
    'червня': 6,
    'черв': 6,
    'липня': 7,
    'лип': 7,
    'серпня': 8,
    'серп': 8,
    'вересня': 9,
    'вер': 9,
    'жовтня': 10,
    'жовт': 10,
    'листопада': 11,
    'лист': 11,
    'грудня': 12,
    'груд': 12,
}


def normalize_month_token(token: str) -> str:
    return (
        token.strip()
        .lower()
        .replace('á', 'a')
        .replace('í', 'i')
        .replace('ú', 'u')
        .replace('ó', 'o')
    )


_DATE_FIELD_LABELS = {
    'period_start': re.compile(r'\b(?:od|від|з|с)\b', re.I),
    'period_end': re.compile(r'\b(?:do|до|по)\b', re.I),
    'issue': ISSUE_DATE_CUE_PATTERN,
    'delivery': re.compile(r'\b(?:dátum\s+|datum\s+)?dodania\b|\b(?:дата|датою)\s+(?:постачання|поставки)\b', re.I),
    'due': re.compile(
        r'\b(?:(?:(?:dátum|datum)\s+)?splatnos(?:ti|ť)|дата\s+(?:оплати|оплаты|платежа)|'
        r'сплатити|оплатити|оплатить|оплата)(?:\s+(?:do|до))?\b', re.I,
    ),
    'other': re.compile(
        r'\b(?:číslo\s+faktúry|faktúra\s+číslo|invoice\s+number|номер\s+(?:фактури|фактуры|рахунку)|'
        r'suma|сума|сумма|odberateľ|customer|контрагент)\b', re.I,
    ),
}
_LABEL_GAP = re.compile(r'\s*[:=–—-]?\s*(?:je\b\s*)?')
_ISO_DATE = re.compile(r'(?<![\w./-])(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})(?![\w/-])')
_NUMERIC_DATE = re.compile(r'(?<![\w./-])(?P<day>\d{1,2})[./]\s*(?P<month>\d{1,2})(?!\d)')
_YEAR_SUFFIX = re.compile(
    r'(?:[./]\s*|\s+)(?:(?:roku?|рік|року|год(?:а)?)\s+)?(?P<year>\d{4})(?!\w|[.,/-]\d|\s*(?:'
    r'EUR\b|USD\b|euro\b|євро\b|евро\b|[€$]|s\.?\s*r\.?\s*o\b|hod\w*\b|годин\w*\b|час\w*\b))', re.I,
)


def _date_literals(raw_text: str):
    # Specific date labels override an immediately adjacent generic od/do range word.
    fields = {
        _LABEL_GAP.match(raw_text, label.end()).end(): field
        for field, pattern in _DATE_FIELD_LABELS.items()
        for label in pattern.finditer(raw_text)
    }
    for pattern in (_ISO_DATE, _NUMERIC_DATE, DAY_MONTH_NAME_PATTERN):
        for match in pattern.finditer(raw_text):
            month = match['month']
            month = int(month) if month.isdecimal() else MONTH_TOKEN_TO_NUMBER.get(normalize_month_token(month))
            if month is None:
                continue
            year = match.groupdict().get('year')
            if year is None and (suffix := _YEAR_SUFFIX.match(raw_text, match.end())):
                year = suffix['year']
            yield fields.get(match.start()), int(match['day']), month, int(year) if year else None


def _date_intent(candidates: set[tuple[int, int, int | None]]) -> dict | None:
    if len(candidates) > 1:
        return {'kind': 'ambiguous'}
    if candidates:
        day, month, year = candidates.pop()
        return {'kind': 'date', 'day': day, 'month': month, 'year': year}
    return None


def labeled_date_intent(raw_text: str, field: str) -> dict | None:
    """Recover an exact date immediately following the label of this field."""
    return _date_intent({(day, month, year) for owner, day, month, year in _date_literals(raw_text) if owner == field})


def explicit_date_year(raw_text: str, *, day: int, month: int, field: str) -> int | None:
    """Accept years attached to the matching day and month in this field."""
    matching = [(owner, year) for owner, d, m, year in _date_literals(raw_text) if (d, m) == (day, month)]
    owned = {year for owner, year in matching if owner == field}
    candidates = owned or {year for owner, year in matching if owner is None}
    if len(candidates) > 1:
        raise ValueError('Conflicting year evidence for invoice date')
    return next(iter(candidates), None)
