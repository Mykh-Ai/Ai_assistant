from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DOCUMENT_TYPE_RECEIPT = 'receipt'
DOCUMENT_TYPE_INCOMING_INVOICE = 'incoming_invoice'
DOCUMENT_TYPE_CONTRACT = 'contract'
DOCUMENT_TYPE_CONTACT_SOURCE = 'contact_source'
DOCUMENT_TYPE_UNKNOWN = 'unknown'

DOCUMENT_TYPES = {
    DOCUMENT_TYPE_RECEIPT,
    DOCUMENT_TYPE_INCOMING_INVOICE,
    DOCUMENT_TYPE_CONTRACT,
    DOCUMENT_TYPE_CONTACT_SOURCE,
    DOCUMENT_TYPE_UNKNOWN,
}

CONFIDENCE_HIGH = 'high'
CONFIDENCE_MEDIUM = 'medium'
CONFIDENCE_LOW = 'low'
CONFIDENCE_VALUES = {
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
}


@dataclass(frozen=True)
class OfficeFlowAttachment:
    file_id: str
    file_unique_id: str
    input_type: str
    original_filename: str
    mime_type: str
    extension: str
    staged_path: Path
    caption: str | None = None
    file_size: int | None = None
    extracted_pdf_text: str | None = None


@dataclass(frozen=True)
class OfficeFlowAttachmentClassification:
    document_type: str
    confidence: str
    reason: str
