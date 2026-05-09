from __future__ import annotations

import asyncio
import json
from pathlib import Path

from bot.config import Config
from bot.handlers import routers
from bot.handlers.accounting_documents import cmd_blocky, recent_accounting_documents_alias, router as accounting_documents_router
from bot.handlers.invoice import router as invoice_router


class _DummyMessage:
    def __init__(self, text: str = '/blocky') -> None:
        self.text = text
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'fakturabot.db',
        storage_dir=tmp_path,
    )


def _write_metadata(
    storage_dir: Path,
    *,
    stem: str,
    document_type: str = 'receipt',
    folder: str = 'receipts',
    vendor_name: str | None = 'ASFINAG',
    issue_date: str | None = '2026-03-14',
    total_amount: str | None = '9.60',
    currency: str | None = 'EUR',
    purchase_subject: str | None = '1-dnova dialnicna znamka Rakusko - osobne vozidlo',
    upload_date: str = '2026-03-14',
) -> None:
    metadata_dir = storage_dir / 'workspaces' / 'mykhailo-szco' / 'years' / '2026' / 'expenses' / '03' / folder / 'metadata'
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / f'{stem}.json'
    metadata_path.write_text(
        json.dumps(
            {
                'document_type': document_type,
                'source': {'upload_date': upload_date},
                'business': {
                    'vendor_name': vendor_name,
                    'issue_date': issue_date,
                    'total_amount': total_amount,
                    'currency': currency,
                    'purchase_subject': purchase_subject,
                },
                'storage': {'original_path': str(metadata_dir.parent / 'originals' / f'{stem}.jpg')},
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )


def test_blocky_command_shows_last_5_documents(tmp_path: Path) -> None:
    for index in range(6):
        _write_metadata(
            tmp_path,
            stem=f'doc-{index}',
            vendor_name=f'Vendor {index}',
            issue_date=f'2026-03-{index + 1:02d}',
            upload_date=f'2026-03-{index + 1:02d}',
        )
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, _config(tmp_path)))

    answer = message.answers[-1]
    assert answer.startswith('Posledné bločky a prijaté doklady:')
    assert 'Vendor 5' in answer
    assert 'Vendor 1' in answer
    assert 'Vendor 0' not in answer


def test_blocky_command_with_no_documents_shows_empty_response(tmp_path: Path) -> None:
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, _config(tmp_path)))

    assert message.answers[-1] == 'Zatiaľ nemáte uložené žiadne bločky ani prijaté doklady.'


def test_blocek_command_uses_recent_blocky_view(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', vendor_name='ASFINAG')
    message = _DummyMessage('/blocek')

    asyncio.run(cmd_blocky(message, _config(tmp_path)))

    assert 'ASFINAG' in message.answers[-1]


def test_blocky_output_maps_document_type_labels(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', document_type='receipt', folder='receipts', vendor_name='Receipt')
    _write_metadata(
        tmp_path,
        stem='invoice',
        document_type='incoming_invoice',
        folder='incoming_invoices',
        vendor_name='Invoice',
        upload_date='2026-03-15',
    )
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, _config(tmp_path)))

    answer = message.answers[-1]
    assert 'Typ: bloček' in answer
    assert 'Typ: prijatá faktúra' in answer


def test_blocky_output_displays_missing_fields_as_nezistene(tmp_path: Path) -> None:
    _write_metadata(
        tmp_path,
        stem='missing',
        vendor_name=None,
        issue_date=None,
        total_amount=None,
        currency=None,
        purchase_subject=None,
    )
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, _config(tmp_path)))

    assert '1. nezistené — nezistené — nezistené' in message.answers[-1]
    assert 'Predmet nákupu: nezistené' in message.answers[-1]


def test_blocky_deterministic_aliases_work(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', vendor_name='ASFINAG')
    for alias in ('posledné bločky', 'покажи останні чеки', 'последние чеки'):
        message = _DummyMessage(alias)

        asyncio.run(recent_accounting_documents_alias(message, _config(tmp_path)))

        assert 'ASFINAG' in message.answers[-1]


def test_blocky_router_is_registered_before_invoice_router() -> None:
    assert routers.index(accounting_documents_router) < routers.index(invoice_router)


def test_blocky_command_clears_active_state(tmp_path: Path) -> None:
    message = _DummyMessage('/blocek')
    state = _DummyState()

    asyncio.run(cmd_blocky(message, _config(tmp_path), state))

    assert state.cleared is True
    assert message.answers[-1] == 'Zatiaľ nemáte uložené žiadne bločky ani prijaté doklady.'


def test_blocky_alias_filter_does_not_match_generic_invoice_text() -> None:
    alias_handler = accounting_documents_router.message.handlers[1]
    generic_message = _DummyMessage('vystav fakturu pre ACME za servis 100 eur')

    assert alias_handler.filters[0].callback(generic_message) is False
