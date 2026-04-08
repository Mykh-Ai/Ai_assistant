from __future__ import annotations


def normalize_service_term(raw_item: str) -> str | None:
    normalized = ' '.join((raw_item or '').casefold().split())
    if not normalized:
        return None

    mapping = {
        'opravy': 'oprava',
        'ремонт': 'oprava',
        'монтаж': 'montáž',
    }

    return mapping.get(normalized)
