from __future__ import annotations

from pathlib import Path
import re
from uuid import uuid4

from aiogram import Bot
from aiogram.types import Message

from bot.services.officeflow_attachment_models import OfficeFlowAttachment


class OfficeFlowAttachmentStorageError(ValueError):
    pass


def extract_supported_attachment_metadata(message: Message) -> dict[str, str | int | None] | None:
    if message.photo:
        photo = message.photo[-1]
        return {
            'file_id': photo.file_id,
            'file_unique_id': getattr(photo, 'file_unique_id', None) or photo.file_id,
            'input_type': 'photo',
            'original_filename': 'photo.jpg',
            'mime_type': 'image/jpeg',
            'extension': '.jpg',
            'file_size': getattr(photo, 'file_size', None),
            'caption': getattr(message, 'caption', None),
        }

    document = message.document
    if document is None:
        return None

    file_name = document.file_name or 'document.pdf'
    mime_type = document.mime_type or ''
    suffix = Path(file_name).suffix.lower()
    if suffix != '.pdf' and mime_type != 'application/pdf':
        return None

    return {
        'file_id': document.file_id,
        'file_unique_id': getattr(document, 'file_unique_id', None) or document.file_id,
        'input_type': 'pdf',
        'original_filename': file_name,
        'mime_type': mime_type or 'application/pdf',
        'extension': '.pdf',
        'file_size': getattr(document, 'file_size', None),
        'caption': getattr(message, 'caption', None),
    }


async def stage_message_attachment(
    *,
    message: Message,
    bot: Bot,
    storage_dir: Path,
) -> OfficeFlowAttachment | None:
    metadata = extract_supported_attachment_metadata(message)
    if metadata is None:
        return None

    safe_id = _safe_id(str(metadata['file_unique_id'] or uuid4()))
    extension = str(metadata['extension'])
    staged_path = storage_dir / 'uploads' / 'attachment_intake' / safe_id / f'original{extension}'
    staged_path.parent.mkdir(parents=True, exist_ok=True)

    file_meta = await bot.get_file(str(metadata['file_id']))
    await bot.download_file(file_meta.file_path, destination=staged_path)

    extracted_pdf_text = None
    if metadata['input_type'] == 'pdf':
        extracted_pdf_text = _extract_pdf_text_quietly(staged_path)

    return OfficeFlowAttachment(
        file_id=str(metadata['file_id']),
        file_unique_id=str(metadata['file_unique_id']),
        input_type=str(metadata['input_type']),
        original_filename=str(metadata['original_filename']),
        mime_type=str(metadata['mime_type']),
        extension=extension,
        staged_path=staged_path,
        caption=_optional_str(metadata.get('caption')),
        file_size=metadata.get('file_size') if isinstance(metadata.get('file_size'), int) else None,
        extracted_pdf_text=extracted_pdf_text,
    )


def cleanup_staged_attachment(*, storage_dir: Path, staged_path: Path) -> None:
    attachment_intake_dir = (storage_dir / 'uploads' / 'attachment_intake').resolve()
    resolved_path = staged_path.resolve()
    if attachment_intake_dir != resolved_path and attachment_intake_dir not in resolved_path.parents:
        raise OfficeFlowAttachmentStorageError('refusing_to_cleanup_non_attachment_intake_path')

    if staged_path.is_file():
        staged_path.unlink()

    parent = staged_path.parent
    if parent.exists() and parent.resolve().parent == attachment_intake_dir:
        try:
            parent.rmdir()
        except OSError:
            pass


def _safe_id(value: str) -> str:
    safe = re.sub(r'[^A-Za-z0-9_-]+', '-', value.strip()).strip('-')
    return (safe or str(uuid4()))[:96]


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_pdf_text_quietly(path: Path) -> str | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        chunks = [(page.extract_text() or '') for page in reader.pages]
        text = '\n'.join(chunks).strip()
    except Exception:
        return None
    return text or None
