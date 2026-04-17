from __future__ import annotations


def normalize_service_term(raw_item: str) -> str | None:
    """Legacy migration helper.

    This helper is no longer a primary semantic resolver in invoice runtime flows.
    Bounded candidate selection via resolver contract is the source of semantic choice.
    """
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
