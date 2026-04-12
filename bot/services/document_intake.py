from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.types import Message


@dataclass
class DocumentIntakeResult:
    status: str
    extracted_text: str
    saved_path: Path | None
    detail: str | None = None


async def extract_message_document_text(message: Message, bot: Bot, storage_dir: Path) -> DocumentIntakeResult:
    if message.document is None:
        return DocumentIntakeResult(status='no_document', extracted_text='', saved_path=None)

    file_name = message.document.file_name or ''
    suffix = Path(file_name).suffix.lower()
    upload_path = storage_dir / 'contracts' / f'{message.document.file_id}_{file_name or "file"}'
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    file_meta = await bot.get_file(message.document.file_id)
    await bot.download_file(file_meta.file_path, destination=upload_path)

    if suffix != '.pdf':
        return DocumentIntakeResult(
            status='unsupported',
            extracted_text='',
            saved_path=upload_path,
            detail='unsupported_file_type',
        )

    text = _extract_text_pdf(upload_path)
    if text.strip():
        return DocumentIntakeResult(status='text_pdf', extracted_text=text, saved_path=upload_path)

    return DocumentIntakeResult(
        status='scan_pdf_needs_ocr',
        extracted_text='',
        saved_path=upload_path,
        detail='pdf_without_text_layer',
    )


def _extract_text_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks: list[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or '')
    return '\n'.join(chunks).strip()
