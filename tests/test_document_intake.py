from __future__ import annotations

import asyncio
from pathlib import Path

from bot.services.document_intake import extract_message_document_text


class _DummyDoc:
    def __init__(self, file_id: str, file_name: str) -> None:
        self.file_id = file_id
        self.file_name = file_name


class _DummyMessage:
    def __init__(self, file_name: str) -> None:
        self.document = _DummyDoc('file-id', file_name)


class _DummyBot:
    class _File:
        def __init__(self) -> None:
            self.file_path = 'remote/path'

    async def get_file(self, file_id: str):
        return self._File()

    async def download_file(self, file_path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b'%PDF')


def test_text_pdf_branch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.services.document_intake._extract_text_pdf', lambda path: 'obsah zmluvy')
    result = asyncio.run(extract_message_document_text(_DummyMessage('contract.pdf'), _DummyBot(), tmp_path))
    assert result.status == 'text_pdf'
    assert result.extracted_text == 'obsah zmluvy'


def test_scan_pdf_detection_branch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.services.document_intake._extract_text_pdf', lambda path: '')
    result = asyncio.run(extract_message_document_text(_DummyMessage('scan.pdf'), _DummyBot(), tmp_path))
    assert result.status == 'scan_pdf_needs_ocr'


def test_unsupported_file_branch(tmp_path: Path) -> None:
    result = asyncio.run(extract_message_document_text(_DummyMessage('contract.docx'), _DummyBot(), tmp_path))
    assert result.status == 'unsupported'
