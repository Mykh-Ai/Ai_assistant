import unittest

from bot.services.pdf_generator import (
    FONT_BOLD,
    FONT_REGULAR,
    _font_supports_glyphs,
    _measure_party_block_height,
    _register_unicode_fonts,
    _resolve_unicode_font_paths,
    _wrap_text_lines,
)
from reportlab.lib.units import mm


class PdfGeneratorLayoutWrappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _register_unicode_fonts()

    def test_wrap_text_lines_splits_long_description(self) -> None:
        wrapped = _wrap_text_lines(
            'Implementácia služby pre mestskú časť Rača s dlhým popisom položky ľ ť č á é í ý',
            max_width=50 * mm,
            font_name='FakturaBot-Regular',
            font_size=9,
        )

        self.assertGreaterEqual(len(wrapped), 2)

    def test_selected_unicode_fonts_cover_remaining_slovak_glyphs(self) -> None:
        regular_font_path, bold_font_path = _resolve_unicode_font_paths()

        self.assertTrue(_font_supports_glyphs(regular_font_path, ('ľ', 'ť')))
        self.assertTrue(_font_supports_glyphs(bold_font_path, ('ľ', 'ť')))
        self.assertEqual(FONT_REGULAR, 'FakturaBot-Regular')
        self.assertEqual(FONT_BOLD, 'FakturaBot-Bold')

    def test_party_block_height_expands_for_wrapped_address(self) -> None:
        short_lines = ['Firma s.r.o.', 'Bratislava']
        long_lines = [
            'Firma s.r.o.',
            'Hlavná 123/45, mestská časť Rača, Bratislava, Slovenská republika, prevádzka č. 2, kancelária 12',
            'Dopĺňajúca adresa: budova A, vchod B, poschodie 3, dvere 34',
            'Email: test@example.com',
        ]
        short_h = _measure_party_block_height(short_lines, width=60 * mm)
        long_h = _measure_party_block_height(long_lines, width=60 * mm)

        self.assertGreater(long_h, short_h)


if __name__ == '__main__':
    unittest.main()
