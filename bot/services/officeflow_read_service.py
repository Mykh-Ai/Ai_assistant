from __future__ import annotations

from pathlib import Path

from bot.services.contact_service import ContactProfile
from bot.services.invoice_service import InvoiceItemRecord, InvoiceRecord
from bot.services.workspace_contact_service import WorkspaceContactService
from bot.services.workspace_context import WorkspaceContext
from bot.services.workspace_invoice_pdf_storage import (
    WorkspaceInvoicePdfStorageError,
    WorkspaceInvoicePdfStorageService,
)
from bot.services.workspace_invoice_service import WorkspaceInvoiceService


class OfficeFlowReadNotFound(RuntimeError):
    pass


class OfficeFlowReadService:
    def __init__(self, db_path: Path, storage_dir: Path) -> None:
        self._invoices = WorkspaceInvoiceService(db_path)
        self._contacts = WorkspaceContactService(db_path)
        self._pdf = WorkspaceInvoicePdfStorageService(db_path, storage_dir)

    def list_invoices(
        self,
        context: WorkspaceContext,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, object]]:
        invoices = self._invoices.list_invoices(
            context,
            limit=limit,
            offset=offset,
        )
        return [self._invoice_projection(context, invoice) for invoice in invoices]

    def get_invoice_detail(
        self,
        context: WorkspaceContext,
        invoice_id: int,
    ) -> dict[str, object]:
        invoice = self._invoices.get_by_id(context, invoice_id)
        if invoice is None:
            raise OfficeFlowReadNotFound('invoice_not_found')
        result = self._invoice_projection(context, invoice)
        result['items'] = [
            _invoice_item_projection(item)
            for item in self._invoices.get_items(context, invoice.id)
        ]
        return result

    def resolve_invoice_pdf(
        self,
        context: WorkspaceContext,
        invoice_id: int,
    ) -> tuple[Path, str]:
        invoice = self._invoices.get_by_id(context, invoice_id)
        if invoice is None:
            raise OfficeFlowReadNotFound('invoice_not_found')
        try:
            path = self._pdf.resolve_existing_read_path(context, invoice)
        except WorkspaceInvoicePdfStorageError as exc:
            raise OfficeFlowReadNotFound('invoice_not_found') from exc
        return path, f'invoice-{invoice.id}.pdf'

    def list_contacts(
        self,
        context: WorkspaceContext,
    ) -> list[dict[str, object]]:
        return [
            _contact_projection(contact)
            for contact in self._contacts.list_contacts(context)
        ]

    def _invoice_projection(
        self,
        context: WorkspaceContext,
        invoice: InvoiceRecord,
    ) -> dict[str, object]:
        contact = self._contacts.get_by_id(context, invoice.contact_id)
        customer: dict[str, object] | None = None
        if contact is not None:
            customer = {'id': contact.id, 'name': contact.name}
        return {
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'issue_date': invoice.issue_date,
            'delivery_date': invoice.delivery_date,
            'due_date': invoice.due_date,
            'due_days': invoice.due_days,
            'total_amount': invoice.total_amount,
            'currency': invoice.currency,
            'status': invoice.status,
            'customer': customer,
        }


def _invoice_item_projection(item: InvoiceItemRecord) -> dict[str, object]:
    return {
        'description': item.description_normalized or item.description_raw,
        'detail': item.item_description_raw,
        'quantity': item.quantity,
        'unit': item.unit,
        'unit_price': item.unit_price,
        'total_price': item.total_price,
    }


def _contact_projection(contact: ContactProfile) -> dict[str, object]:
    return {
        'id': contact.id,
        'name': contact.name,
        'ico': contact.ico,
        'dic': contact.dic,
        'ic_dph': contact.ic_dph,
        'address': contact.address,
        'email': contact.email,
        'iban': contact.iban,
        'contact_person': contact.contact_person,
    }
