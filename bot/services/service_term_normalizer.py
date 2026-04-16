from __future__ import annotations


def normalize_service_term(raw_item: str) -> str | None:
    normalized = ' '.join((raw_item or '').casefold().split())
    if not normalized:
        return None

    mapping = {
        'oprava': 'oprava',
        'opravy': 'oprava',
        'ремонт': 'oprava',
        'montáž': 'montáž',
        'montaz': 'montáž',
        'монтаж': 'montáž',
    }

    return mapping.get(normalized)
