from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import reportlab

from bot.services.contact_service import ContactProfile
from bot.services.pay_by_square import PayBySquarePayment, build_pay_by_square_payload
from bot.services.supplier_service import SupplierProfile

FONT_REGULAR = 'FakturaBot-Regular'
FONT_BOLD = 'FakturaBot-Bold'
REQUIRED_GLYPHS = ('ľ', 'ť', 'á', 'č', 'ú', 'ž', 'ý')
WINDOWS_FONT_CANDIDATES = [
    (Path('C:/Windows/Fonts/arial.ttf'), Path('C:/Windows/Fonts/arialbd.ttf')),
    (Path('C:/Windows/Fonts/calibri.ttf'), Path('C:/Windows/Fonts/calibrib.ttf')),
    (Path('C:/Windows/Fonts/CEARIAL.TTF'), Path('C:/Windows/Fonts/arialbd.ttf')),
]


@dataclass
class PdfInvoiceItem:
    description: str
    quantity: float
    unit: str | None
    unit_price: float
    total_price: float
    detail: str | None = None


@dataclass
class PdfInvoiceData:
    invoice_number: str
    issue_date: str
    delivery_date: str
    due_date: str
    variable_symbol: str
    payment_method: str
    total_amount: float
    currency: str


def _format_amount(value: float, currency: str) -> str:
    return f'{value:,.2f} {currency}'.replace(',', ' ')


def _format_supplier_ic_dph_line(ic_dph: str | None) -> str:
    return f'IČ DPH: {ic_dph or "Nie je platiteľ DPH"}'


def _font_supports_glyphs(font_path: Path, glyphs: tuple[str, ...] = REQUIRED_GLYPHS) -> bool:
    font = TTFont('FakturaBot-Glyph-Probe', str(font_path))
    cmap = font.face.charToGlyph
    return all(ord(glyph) in cmap for glyph in glyphs)


def _resolve_unicode_font_paths() -> tuple[Path, Path]:
    for regular_font_path, bold_font_path in WINDOWS_FONT_CANDIDATES:
        if not regular_font_path.exists() or not bold_font_path.exists():
            continue
        if _font_supports_glyphs(regular_font_path) and _font_supports_glyphs(bold_font_path):
            return regular_font_path, bold_font_path

    reportlab_fonts = Path(reportlab.__file__).resolve().parent / 'fonts'
    fallback_regular = reportlab_fonts / 'Vera.ttf'
    fallback_bold = reportlab_fonts / 'VeraBd.ttf'
    if _font_supports_glyphs(fallback_regular) and _font_supports_glyphs(fallback_bold):
        return fallback_regular, fallback_bold

    raise RuntimeError('No available PDF font with required Slovak glyph support (ľ, ť).')


def _register_unicode_fonts() -> None:
    try:
        pdfmetrics.getFont(FONT_REGULAR)
        pdfmetrics.getFont(FONT_BOLD)
        return
    except KeyError:
        pass

    regular_font_path, bold_font_path = _resolve_unicode_font_paths()
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular_font_path)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold_font_path)))


def _wrap_text_lines(text: str, max_width: float, font_name: str, font_size: float) -> list[str]:
    normalized = ' '.join((text or '').split())
    if not normalized:
        return ['-']

    words = normalized.split(' ')
    wrapped: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f'{current} {word}'
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue
        wrapped.append(current)
        current = word
    wrapped.append(current)
    return wrapped


def _measure_party_block_height(lines: list[str], width: float) -> float:
    title_top_offset = 7 * mm
    line_start_offset = 13 * mm
    line_height = 5 * mm
    bottom_padding = 5 * mm
    text_width = width - 8 * mm

    wrapped_count = 0
    for line in lines:
        wrapped_count += len(_wrap_text_lines(line, text_width, FONT_REGULAR, 9))

    text_height = line_start_offset + (wrapped_count * line_height) + bottom_padding
    return max(52 * mm, title_top_offset + text_height)


def _draw_party_block(
    pdf: canvas.Canvas,
    x: float,
    y_top: float,
    width: float,
    title: str,
    lines: list[str],
    block_fill: colors.Color,
) -> float:
    block_height = _measure_party_block_height(lines, width)
    text_width = width - 8 * mm
    pdf.setFillColor(block_fill)
    pdf.roundRect(x, y_top - block_height, width, block_height, 4, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor('#1f2937'))
    pdf.setFont(FONT_BOLD, 11)
    pdf.drawString(x + 4 * mm, y_top - 7 * mm, title)

    pdf.setFont(FONT_REGULAR, 9)
    line_y = y_top - 13 * mm
    for line in lines:
        wrapped_lines = _wrap_text_lines(line, text_width, FONT_REGULAR, 9)
        for wrapped_line in wrapped_lines:
            pdf.drawString(x + 4 * mm, line_y, wrapped_line)
            line_y -= 5 * mm
    return block_height


def _draw_qr(pdf: canvas.Canvas, payload: str, x: float, y: float, size: float) -> None:
    image = qrcode.make(payload)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    pdf.drawImage(ImageReader(buffer), x, y, width=size, height=size)


def _measure_item_row(description_lines: list[str], *, row_min_h: float, row_line_h: float) -> tuple[list[str], float]:
    desc_lines = description_lines
    row_h = max(row_min_h, (len(desc_lines) * row_line_h) + 4 * mm)
    return desc_lines, row_h


def validate_item_detail_render_fit(detail_text: str, *, max_lines: int = 2) -> bool:
    normalized = ' '.join((detail_text or '').split())
    if not normalized:
        return True
    try:
        _register_unicode_fonts()
        font_name = FONT_REGULAR
    except Exception:
        font_name = 'Helvetica'
    desc_text_width = (85 * mm) - (4 * mm)
    wrapped_lines = _wrap_text_lines(normalized, desc_text_width, font_name, 9)
    return len(wrapped_lines) <= max_lines


def _item_row_numeric_baseline(y_top: float, row_h: float) -> float:
    return y_top - (row_h / 2) - 0.6 * mm


def _item_row_description_first_baseline(y_top: float, row_h: float, line_count: int, row_line_h: float) -> float:
    center_baseline = _item_row_numeric_baseline(y_top, row_h)
    if line_count <= 1:
        return center_baseline
    return center_baseline + ((line_count - 1) * row_line_h / 2)


def generate_invoice_pdf(
    *,
    target_path: Path,
    supplier: SupplierProfile,
    customer: ContactProfile,
    invoice: PdfInvoiceData,
    items: list[PdfInvoiceItem],
) -> None:
    _register_unicode_fonts()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    page_width, page_height = A4
    margin = 14 * mm

    bg_primary = colors.white
    bg_secondary = colors.HexColor('#f5f7fb')
    accent = colors.HexColor('#2f4f6f')

    pdf = canvas.Canvas(str(target_path), pagesize=A4)
    pdf.setFillColor(bg_primary)
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    header_height = 28 * mm
    pdf.setFillColor(bg_secondary)
    pdf.rect(margin, page_height - margin - header_height, page_width - 2 * margin, header_height, fill=1, stroke=0)

    pdf.setFillColor(accent)
    pdf.setFont(FONT_BOLD, 24)
    pdf.drawString(margin + 6 * mm, page_height - margin - 10 * mm, 'Faktúra')

    pdf.setFont(FONT_BOLD, 12)
    pdf.drawRightString(page_width - margin - 6 * mm, page_height - margin - 10 * mm, f'Číslo: {invoice.invoice_number}')

    left_x = margin
    col_gap = 8 * mm
    col_width = (page_width - 2 * margin - col_gap) / 2
    block_top = page_height - margin - header_height - 8 * mm

    supplier_lines = [
        supplier.name,
        f'IČO: {supplier.ico}   DIČ: {supplier.dic}',
        _format_supplier_ic_dph_line(supplier.ic_dph),
        supplier.address,
        f'Email: {supplier.email}',
    ]
    customer_lines = [
        customer.name,
        f'IČO: {customer.ico}   DIČ: {customer.dic}',
        f'IČ DPH: {customer.ic_dph or "-"}',
        customer.address,
        f'Email: {customer.email}',
    ]

    supplier_block_h = _draw_party_block(pdf, left_x, block_top, col_width, 'Dodávateľ', supplier_lines, bg_secondary)
    customer_block_h = _draw_party_block(
        pdf, left_x + col_width + col_gap, block_top, col_width, 'Odberateľ', customer_lines, bg_secondary
    )
    block_bottom_y = block_top - max(supplier_block_h, customer_block_h)

    meta_top = block_bottom_y - 4 * mm
    meta_h = 24 * mm
    pdf.setFillColor(bg_secondary)
    pdf.roundRect(margin, meta_top - meta_h, page_width - 2 * margin, meta_h, 4, fill=1, stroke=0)

    pdf.setFillColor(colors.HexColor('#111827'))
    pdf.setFont(FONT_BOLD, 10)
    pdf.drawString(margin + 4 * mm, meta_top - 6 * mm, 'Dátum vystavenia')
    pdf.drawString(margin + 50 * mm, meta_top - 6 * mm, 'Dátum dodania')
    pdf.drawString(margin + 96 * mm, meta_top - 6 * mm, 'Dátum splatnosti')
    pdf.drawString(margin + 142 * mm, meta_top - 6 * mm, 'Variabilný symbol')

    pdf.setFont(FONT_REGULAR, 10)
    pdf.drawString(margin + 4 * mm, meta_top - 13 * mm, invoice.issue_date)
    pdf.drawString(margin + 50 * mm, meta_top - 13 * mm, invoice.delivery_date)
    pdf.drawString(margin + 96 * mm, meta_top - 13 * mm, invoice.due_date)
    pdf.drawString(margin + 142 * mm, meta_top - 13 * mm, invoice.variable_symbol)

    pay_top = meta_top - meta_h - 5 * mm
    pay_h = 24 * mm
    pdf.setFillColor(bg_secondary)
    pdf.roundRect(margin, pay_top - pay_h, page_width - 2 * margin, pay_h, 4, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor('#111827'))
    pdf.setFont(FONT_BOLD, 10)
    pdf.drawString(margin + 4 * mm, pay_top - 6 * mm, 'Platobné údaje')
    pdf.setFont(FONT_REGULAR, 9.5)
    pdf.drawString(margin + 4 * mm, pay_top - 12 * mm, f'IBAN: {supplier.iban}')
    pdf.drawString(margin + 4 * mm, pay_top - 17 * mm, f'SWIFT/BIC: {supplier.swift}')
    pdf.drawString(margin + 90 * mm, pay_top - 12 * mm, f'Spôsob úhrady: {invoice.payment_method}')

    table_top = pay_top - pay_h - 8 * mm
    headers = ['položka', 'množstvo', 'm.j.', 'cena za m.j.', 'spolu']
    col_widths = [85 * mm, 22 * mm, 16 * mm, 30 * mm, 30 * mm]

    x = margin
    y = table_top
    pdf.setFillColor(accent)
    pdf.roundRect(margin, y - 8 * mm, sum(col_widths), 8 * mm, 2, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont(FONT_BOLD, 9)
    for idx, header in enumerate(headers):
        pdf.drawString(x + 2 * mm, y - 5.5 * mm, header)
        x += col_widths[idx]

    row_min_h = 10 * mm
    row_line_h = 4.2 * mm
    desc_text_width = col_widths[0] - 4 * mm
    y -= 8 * mm
    pdf.setFont(FONT_REGULAR, 9)
    for item in items:
        desc_lines = _wrap_text_lines(item.description, desc_text_width, FONT_REGULAR, 9)
        if item.detail:
            desc_lines.extend(_wrap_text_lines(item.detail, desc_text_width, FONT_REGULAR, 9))
        desc_lines, row_h = _measure_item_row(
            desc_lines, row_min_h=row_min_h, row_line_h=row_line_h
        )
        pdf.setFillColor(bg_secondary)
        pdf.rect(margin, y - row_h, sum(col_widths), row_h, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor('#111827'))
        row_vals = [
            str(item.quantity),
            item.unit or '-',
            _format_amount(item.unit_price, invoice.currency),
            _format_amount(item.total_price, invoice.currency),
        ]
        desc_y = _item_row_description_first_baseline(y, row_h, len(desc_lines), row_line_h)
        for desc_line in desc_lines:
            pdf.drawString(margin + 2 * mm, desc_y, desc_line)
            desc_y -= row_line_h

        numeric_y = _item_row_numeric_baseline(y, row_h)
        x = margin + col_widths[0]
        for idx, value in enumerate(row_vals):
            pdf.drawString(x + 2 * mm, numeric_y, value)
            x += col_widths[idx + 1]
        y -= row_h

    total_w = 62 * mm
    total_h = 22 * mm
    total_x = page_width - margin - total_w
    total_y = y - 12 * mm
    pdf.setFillColor(accent)
    pdf.roundRect(total_x, total_y - total_h, total_w, total_h, 4, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont(FONT_BOLD, 11)
    pdf.drawString(total_x + 4 * mm, total_y - 7 * mm, 'Na úhradu')
    pdf.setFont(FONT_BOLD, 16)
    pdf.drawRightString(total_x + total_w - 4 * mm, total_y - 15 * mm, _format_amount(invoice.total_amount, invoice.currency))

    qr_payload = build_pay_by_square_payload(
        PayBySquarePayment(
            iban=supplier.iban,
            amount=invoice.total_amount,
            currency=invoice.currency,
            variable_symbol=invoice.variable_symbol,
            due_date=invoice.due_date,
            beneficiary_name=supplier.name,
            payment_note=f'Faktura {invoice.invoice_number}',
            swift=supplier.swift,
        )
    )
    qr_size = 28 * mm
    _draw_qr(pdf, qr_payload, total_x - qr_size - 8 * mm, total_y - qr_size, qr_size)

    pdf.setFillColor(colors.HexColor('#4b5563'))
    pdf.setFont(FONT_REGULAR, 8)
    pdf.drawString(margin, 12 * mm, 'Dokument bol vygenerovaný systémom FakturaBot.')

    pdf.showPage()
    pdf.save()
