from __future__ import annotations

from datetime import date
import re


def validate_ico(value: str) -> bool:
    return bool(re.fullmatch(r'\d{8}', value.strip()))


def validate_dic(value: str) -> bool:
    return bool(re.fullmatch(r'\d{10}', value.strip()))


def validate_ic_dph(value: str) -> bool:
    normalized = value.strip().upper().replace(' ', '')
    return bool(re.fullmatch(r'[A-Z]{2}\d{8,12}', normalized))


def validate_email(value: str) -> bool:
    return bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value.strip()))


def validate_contact_address(value: str) -> bool:
    normalized = value.strip()
    return bool(normalized) and bool(re.search(r'[^\W\d_]', normalized, flags=re.UNICODE)) and bool(re.search(r'\d', normalized))


def validate_iban(value: str) -> bool:
    normalized = value.strip().upper().replace(' ', '')
    return bool(re.fullmatch(r'[A-Z]{2}[0-9A-Z]{13,32}', normalized))


def normalize_contact_iban(value: str) -> str:
    return re.sub(r'\s+', '', value).upper()


def validate_contact_iban(value: str) -> bool:
    normalized = normalize_contact_iban(value)
    if not re.fullmatch(r'[A-Z]{2}\d{2}[0-9A-Z]{11,30}', normalized):
        return False
    rearranged = normalized[4:] + normalized[:4]
    numeric = ''.join(str(ord(char) - 55) if char.isalpha() else char for char in rearranged)
    return int(numeric) % 97 == 1


def validate_days_due(value: str) -> bool:
    if not value.strip().isdigit():
        return False
    return int(value.strip()) > 0


def validate_invoice_number_for_year(value: str, issue_year: int) -> bool:
    normalized = value.strip()
    return bool(re.fullmatch(r'\d{8}', normalized)) and normalized.startswith(str(issue_year))


def parse_strict_date_dd_mm_yyyy(value: str) -> date | None:
    normalized = value.strip()
    if not re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', normalized):
        return None
    day, month, year = normalized.split('.')
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None
