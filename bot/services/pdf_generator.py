from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from bot.services.contact_service import ContactProfile
from bot.services.supplier_service import SupplierProfile
from bot.services.pay_by_square import PayBySquarePayment, build_pay_by_square_payload


@dataclass
class PdfInvoiceItem:
    description: str
    quantity: float
    unit: str | None
    unit_price: float
    total_price: float


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


def _draw_party_block(
    pdf: canvas.Canvas,
    x: float,
    y_top: float,
    width: float,
    title: str,
    lines: list[str],
    block_fill: colors.Color,
) -> None:
    block_height = 52 * mm
    pdf.setFillColor(block_fill)
    pdf.roundRect(x, y_top - block_height, width, block_height, 4, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor('#1f2937'))
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(x + 4 * mm, y_top - 7 * mm, title)

    pdf.setFont('Helvetica', 9)
    line_y = y_top - 13 * mm
    for line in lines:
        pdf.drawString(x + 4 * mm, line_y, line)
        line_y -= 5 * mm


def _draw_qr(pdf: canvas.Canvas, payload: str, x: float, y: float, size: float) -> None:
    image = qrcode.make(payload)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    pdf.drawImage(ImageReader(buffer), x, y, width=size, height=size)


def generate_invoice_pdf(
    *,
    target_path: Path,
    supplier: SupplierProfile,
    customer: ContactProfile,
    invoice: PdfInvoiceData,
    items: list[PdfInvoiceItem],
) -> None:
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
    pdf.setFont('Helvetica-Bold', 24)
    pdf.drawString(margin + 6 * mm, page_height - margin - 10 * mm, 'Faktúra')

    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawRightString(page_width - margin - 6 * mm, page_height - margin - 10 * mm, f'Číslo: {invoice.invoice_number}')

    left_x = margin
    col_gap = 8 * mm
    col_width = (page_width - 2 * margin - col_gap) / 2
    block_top = page_height - margin - header_height - 8 * mm

    supplier_lines = [
        supplier.name,
        f'IČO: {supplier.ico}   DIČ: {supplier.dic}',
        f'IČ DPH: {supplier.ic_dph or "-"}',
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

    _draw_party_block(pdf, left_x, block_top, col_width, 'Dodávateľ', supplier_lines, bg_secondary)
    _draw_party_block(pdf, left_x + col_width + col_gap, block_top, col_width, 'Odberateľ', customer_lines, bg_secondary)

    meta_top = block_top - 56 * mm
    meta_h = 24 * mm
    pdf.setFillColor(bg_secondary)
    pdf.roundRect(margin, meta_top - meta_h, page_width - 2 * margin, meta_h, 4, fill=1, stroke=0)

    pdf.setFillColor(colors.HexColor('#111827'))
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(margin + 4 * mm, meta_top - 6 * mm, 'Dátum vystavenia')
    pdf.drawString(margin + 50 * mm, meta_top - 6 * mm, 'Dátum dodania')
    pdf.drawString(margin + 96 * mm, meta_top - 6 * mm, 'Dátum splatnosti')
    pdf.drawString(margin + 142 * mm, meta_top - 6 * mm, 'Variabilný symbol')

    pdf.setFont('Helvetica', 10)
    pdf.drawString(margin + 4 * mm, meta_top - 13 * mm, invoice.issue_date)
    pdf.drawString(margin + 50 * mm, meta_top - 13 * mm, invoice.delivery_date)
    pdf.drawString(margin + 96 * mm, meta_top - 13 * mm, invoice.due_date)
    pdf.drawString(margin + 142 * mm, meta_top - 13 * mm, invoice.variable_symbol)

    pay_top = meta_top - meta_h - 5 * mm
    pay_h = 18 * mm
    pdf.setFillColor(bg_secondary)
    pdf.roundRect(margin, pay_top - pay_h, page_width - 2 * margin, pay_h, 4, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor('#111827'))
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(margin + 4 * mm, pay_top - 6 * mm, 'Platobné údaje')
    pdf.setFont('Helvetica', 10)
    pdf.drawString(margin + 4 * mm, pay_top - 12 * mm, f'IBAN: {supplier.iban}')
    pdf.drawString(margin + 90 * mm, pay_top - 12 * mm, f'SWIFT/BIC: {supplier.swift}')
    pdf.drawString(margin + 145 * mm, pay_top - 12 * mm, f'Spôsob úhrady: {invoice.payment_method}')

    table_top = pay_top - pay_h - 8 * mm
    headers = ['položka', 'množstvo', 'm.j.', 'cena za m.j.', 'spolu']
    col_widths = [85 * mm, 22 * mm, 16 * mm, 30 * mm, 30 * mm]

    x = margin
    y = table_top
    pdf.setFillColor(accent)
    pdf.roundRect(margin, y - 8 * mm, sum(col_widths), 8 * mm, 2, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont('Helvetica-Bold', 9)
    for idx, header in enumerate(headers):
        pdf.drawString(x + 2 * mm, y - 5.5 * mm, header)
        x += col_widths[idx]

    row_h = 10 * mm
    y -= 8 * mm
    pdf.setFont('Helvetica', 9)
    for item in items:
        pdf.setFillColor(bg_secondary)
        pdf.rect(margin, y - row_h, sum(col_widths), row_h, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor('#111827'))
        row_vals = [
            item.description,
            str(item.quantity),
            item.unit or '-',
            _format_amount(item.unit_price, invoice.currency),
            _format_amount(item.total_price, invoice.currency),
        ]
        x = margin
        for idx, value in enumerate(row_vals):
            pdf.drawString(x + 2 * mm, y - 6.5 * mm, value)
            x += col_widths[idx]
        y -= row_h

    total_w = 62 * mm
    total_h = 22 * mm
    total_x = page_width - margin - total_w
    total_y = y - 12 * mm
    pdf.setFillColor(accent)
    pdf.roundRect(total_x, total_y - total_h, total_w, total_h, 4, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(total_x + 4 * mm, total_y - 7 * mm, 'Na úhradu')
    pdf.setFont('Helvetica-Bold', 16)
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
    pdf.setFont('Helvetica', 8)
    pdf.drawString(margin, 12 * mm, 'Dokument bol vygenerovaný systémom FakturaBot.')

    pdf.showPage()
    pdf.save()
