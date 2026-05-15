from __future__ import annotations


def build_top_level_unknown_guidance(*, user_input_text: str | None = None) -> str:
    """Build deterministic Phase 1 guidance for idle top-level unknown input."""
    return (
        'Nerozumiem, čo chcete spraviť.\n\n'
        'Môžem vám pomôcť napríklad s týmito vecami:\n'
        '- vytvoriť faktúru,\n'
        '- zobraziť alebo upraviť existujúcu faktúru,\n'
        '- pridať kontakt,\n'
        '- upraviť môj profil,\n'
        '- pridať službu používanú vo faktúrach,\n'
        '- pridať bloček alebo prijatú faktúru.\n\n'
        'Skúste napísať konkrétne, čo chcete urobiť, napríklad „vytvor faktúru“, '
        '„pridaj kontakt“ alebo „pridaj bloček“.'
    )
