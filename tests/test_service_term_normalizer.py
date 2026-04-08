from bot.services.service_term_normalizer import normalize_service_term


def test_normalize_opravy() -> None:
    assert normalize_service_term('opravy') == 'oprava'


def test_normalize_remont_ru() -> None:
    assert normalize_service_term('ремонт') == 'oprava'


def test_normalize_montazh_ru() -> None:
    assert normalize_service_term('монтаж') == 'montáž'
