import pytest

from bot.services.service_term_normalizer import normalize_service_term


@pytest.mark.unit
@pytest.mark.parametrize(
    ('raw_term', 'expected'),
    [
        pytest.param('opravy', 'oprava', id='slovak-plural-opravy'),
        pytest.param('ремонт', 'oprava', id='russian-remont'),
        pytest.param('монтаж', 'montáž', id='russian-montazh'),
    ],
)
def test_normalize_service_term(raw_term: str, expected: str) -> None:
    assert normalize_service_term(raw_term) == expected
