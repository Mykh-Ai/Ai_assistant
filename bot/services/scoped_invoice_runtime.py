from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from bot.services.contact_service import ContactLookupResult, ContactProfile, ContactService
from bot.services.invoice_analytics_dataset import InvoiceAnalyticsDatasetService
from bot.services.invoice_service import (
    CreateInvoiceItemPayload,
    InvoiceItemRecord,
    InvoicePeriodSummary,
    InvoiceRecord,
    InvoiceService,
)
from bot.services.supplier_service import SupplierProfile, SupplierService
from bot.services.workspace_contact_service import WorkspaceContactService
from bot.services.workspace_context import WorkspaceContext
from bot.services.workspace_invoice_analytics_dataset import (
    WorkspaceInvoiceAnalyticsDatasetService,
)
from bot.services.workspace_invoice_pdf_storage import WorkspaceInvoicePdfStorageService
from bot.services.workspace_invoice_service import WorkspaceInvoiceService


class ScopedInvoiceRuntime:
    """Transitional handler facade with an explicit workspace or legacy scope."""

    def __init__(
        self,
        *,
        db_path: Path,
        storage_dir: Path,
        actor_telegram_id: int,
        context: WorkspaceContext | None,
        legacy_invoice_service: InvoiceService | None = None,
    ) -> None:
        self.db_path = db_path
        self.storage_dir = storage_dir
        self.actor_telegram_id = actor_telegram_id
        self.context = context
        self._legacy_invoices = legacy_invoice_service or InvoiceService(db_path)
        self._workspace_invoices = WorkspaceInvoiceService(db_path)
        self._legacy_contacts = ContactService(db_path)
        self._workspace_contacts = WorkspaceContactService(db_path)

    @property
    def is_workspace(self) -> bool:
        return self.context is not None

    def get_supplier(self) -> SupplierProfile | None:
        if self.context is None:
            return SupplierService(self.db_path).get_by_telegram_id(self.actor_telegram_id)
        return SupplierService(self.db_path).get_by_workspace_id(self.context.workspace_id)

    def resolve_contact_lookup(self, name: str) -> ContactLookupResult:
        if self.context is None:
            return self._legacy_contacts.resolve_contact_lookup(self.actor_telegram_id, name)
        return self._workspace_contacts.resolve_contact_lookup(self.context, name)

    def list_contacts(self) -> list[ContactProfile]:
        if self.context is None:
            return self._legacy_contacts.get_all_by_supplier(self.actor_telegram_id)
        return self._workspace_contacts.list_contacts(self.context)

    def get_contact_by_id(self, contact_id: int) -> ContactProfile | None:
        if self.context is None:
            return self._legacy_contacts.get_by_id_for_supplier(
                telegram_id=self.actor_telegram_id,
                contact_id=contact_id,
            )
        return self._workspace_contacts.get_by_id(self.context, contact_id)

    def get_contact_by_name(self, name: str) -> ContactProfile | None:
        if self.context is None:
            return self._legacy_contacts.get_by_name_case_insensitive(
                self.actor_telegram_id,
                name,
            )
        matches = [
            contact
            for contact in self._workspace_contacts.list_contacts(self.context)
            if contact.name.casefold() == name.strip().casefold()
        ]
        return matches[0] if len(matches) == 1 else None

    def create_confirmed_contact_alias(
        self,
        *,
        alias_text: str,
        contact_id: int,
        source: str,
    ) -> None:
        if self.context is None:
            self._legacy_contacts.create_confirmed_contact_alias(
                supplier_telegram_id=self.actor_telegram_id,
                alias_text=alias_text,
                contact_id=contact_id,
                source=source,
            )
            return
        self._workspace_contacts.create_confirmed_alias(
            self.context,
            alias_text=alias_text,
            contact_id=contact_id,
            source=source,
        )

    def generate_next_invoice_number(
        self,
        issue_year: int,
        supplier_telegram_id: int | None = None,
    ) -> str:
        if self.context is None:
            return self._legacy_invoices.generate_next_invoice_number(
                issue_year,
                supplier_telegram_id=self.actor_telegram_id,
            )
        return self._workspace_invoices.generate_next_invoice_number(
            self.context,
            issue_year,
        )

    def create_invoice_with_items(
        self,
        *,
        contact_id: int,
        issue_date: str,
        delivery_date: str,
        due_date: str,
        due_days: int,
        total_amount: float,
        currency: str,
        status: str,
        items: list[CreateInvoiceItemPayload],
        invoice_number: str | None = None,
    ) -> InvoiceRecord:
        if self.context is None:
            invoice_id = self._legacy_invoices.create_invoice_with_items(
                supplier_telegram_id=self.actor_telegram_id,
                contact_id=contact_id,
                issue_date=issue_date,
                delivery_date=delivery_date,
                due_date=due_date,
                due_days=due_days,
                total_amount=total_amount,
                currency=currency,
                status=status,
                items=items,
                invoice_number=invoice_number,
            )
            saved = self._legacy_invoices.get_invoice_for_supplier_by_id(
                supplier_telegram_id=self.actor_telegram_id,
                invoice_id=invoice_id,
            )
            if saved is None:
                raise RuntimeError('legacy_invoice_save_failed')
            return saved
        return self._workspace_invoices.create_invoice_with_items(
            self.context,
            contact_id=contact_id,
            issue_date=issue_date,
            delivery_date=delivery_date,
            due_date=due_date,
            due_days=due_days,
            total_amount=total_amount,
            currency=currency,
            status=status,
            items=items,
            invoice_number=invoice_number,
        )

    def get_invoice(self, invoice_id: int) -> InvoiceRecord | None:
        if self.context is None:
            return self._legacy_invoices.get_invoice_for_supplier_by_id(
                supplier_telegram_id=self.actor_telegram_id,
                invoice_id=invoice_id,
            )
        return self._workspace_invoices.get_by_id(self.context, invoice_id)

    def get_invoice_for_supplier_by_id(
        self,
        *,
        supplier_telegram_id: int,
        invoice_id: int,
    ) -> InvoiceRecord | None:
        return self.get_invoice(invoice_id)
    def find_invoices(self, invoice_reference: str) -> list[InvoiceRecord]:
        if self.context is None:
            return self._legacy_invoices.find_invoices_for_supplier_by_number_reference(
                supplier_telegram_id=self.actor_telegram_id,
                invoice_reference=invoice_reference,
            )
        return self._workspace_invoices.find_by_number_reference(
            self.context,
            invoice_reference,
        )

    def find_invoices_for_supplier_by_number_reference(
        self,
        *,
        supplier_telegram_id: int,
        invoice_reference: str,
    ) -> list[InvoiceRecord]:
        return self.find_invoices(invoice_reference)
    def summarize_period(self, *, start_date: str, end_date: str) -> InvoicePeriodSummary:
        if self.context is None:
            return self._legacy_invoices.summarize_invoices_for_supplier_period(
                supplier_telegram_id=self.actor_telegram_id,
                start_date=start_date,
                end_date=end_date,
            )
        return self._workspace_invoices.summarize_period(
            self.context,
            start_date=start_date,
            end_date=end_date,
        )

    def summarize_invoices_for_supplier_period(
        self,
        *,
        supplier_telegram_id: int,
        start_date: str,
        end_date: str,
    ) -> InvoicePeriodSummary:
        return self.summarize_period(start_date=start_date, end_date=end_date)
    def is_invoice_number_available(
        self,
        invoice_number: str,
        *,
        supplier_telegram_id: int | None = None,
        exclude_invoice_id: int | None = None,
    ) -> bool:
        if self.context is None:
            return self._legacy_invoices.is_invoice_number_available(
                invoice_number=invoice_number,
                supplier_telegram_id=self.actor_telegram_id,
                exclude_invoice_id=exclude_invoice_id,
            )
        return self._workspace_invoices.is_invoice_number_available(
            self.context,
            invoice_number=invoice_number,
            exclude_invoice_id=exclude_invoice_id,
        )

    def get_items(self, invoice_id: int) -> list[InvoiceItemRecord]:
        if self.context is None:
            if self.get_invoice(invoice_id) is None:
                return []
            return self._legacy_invoices.get_items_by_invoice_id(invoice_id)
        return self._workspace_invoices.get_items(self.context, invoice_id)

    def get_items_by_invoice_id(self, invoice_id: int) -> list[InvoiceItemRecord]:
        return self.get_items(invoice_id)
    def build_analytics_dataframe(self, *, current_date: date) -> pd.DataFrame:
        if self.context is None:
            return InvoiceAnalyticsDatasetService(self.db_path).build_invoice_dataframe_for_supplier(
                supplier_telegram_id=self.actor_telegram_id,
                current_date=current_date,
            )
        return WorkspaceInvoiceAnalyticsDatasetService(self.db_path).build_invoice_dataframe(
            self.context,
            current_date=current_date,
        )

    def pdf_target_path(self, invoice_number: str) -> Path:
        if self.context is None:
            return self.storage_dir / 'invoices' / str(self.actor_telegram_id) / f'{invoice_number}.pdf'
        return WorkspaceInvoicePdfStorageService(
            self.db_path,
            self.storage_dir,
        ).target_path(self.context, invoice_number=invoice_number)

    def save_pdf_path(self, invoice_id: int, pdf_path: str | Path) -> None:
        pdf_path = Path(pdf_path)
        if self.context is None:
            if self.get_invoice(invoice_id) is None:
                raise ValueError('invoice_not_found_for_supplier')
            self._legacy_invoices.save_pdf_path(invoice_id, str(pdf_path))
            return
        WorkspaceInvoicePdfStorageService(
            self.db_path,
            self.storage_dir,
        ).persist_path(self.context, invoice_id=invoice_id, pdf_path=pdf_path)

    def update_item_service(self, **kwargs) -> None:
        self._item_write('update_item_service', **kwargs)

    def update_item_main_description(self, **kwargs) -> None:
        self._item_write('update_item_main_description', **kwargs)

    def update_item_description(self, **kwargs) -> None:
        self._item_write('update_item_description', **kwargs)

    def update_item_financials(self, **kwargs) -> None:
        self._item_write('update_item_financials', **kwargs)

    def update_invoice_total_amount(self, *, invoice_id: int) -> None:
        self._invoice_write('update_invoice_total_amount', invoice_id=invoice_id)

    def update_invoice_number(self, *, invoice_id: int, invoice_number: str) -> bool:
        if self.context is None:
            if self.get_invoice(invoice_id) is None:
                return False
            return self._legacy_invoices.update_invoice_number(
                invoice_id=invoice_id,
                invoice_number=invoice_number,
            )
        return self._workspace_invoices.update_invoice_number(
            self.context,
            invoice_id=invoice_id,
            invoice_number=invoice_number,
        )

    def update_invoice_issue_date(self, **kwargs) -> None:
        self._invoice_write('update_invoice_issue_date', **kwargs)

    def update_invoice_delivery_date(self, **kwargs) -> None:
        self._invoice_write('update_invoice_delivery_date', **kwargs)

    def update_invoice_due_date(self, **kwargs) -> None:
        self._invoice_write('update_invoice_due_date', **kwargs)

    def update_invoice_status(self, invoice_id: int, status: str) -> None:
        self._invoice_write('update_invoice_status', invoice_id=invoice_id, status=status)

    def delete_invoice_with_items(self, invoice_id: int) -> None:
        self._invoice_write('delete_invoice_with_items', invoice_id=invoice_id)

    def _item_write(self, method_name: str, **kwargs) -> None:
        if self.context is None:
            getattr(self._legacy_invoices, method_name)(**kwargs)
            return
        getattr(self._workspace_invoices, method_name)(self.context, **kwargs)

    def _invoice_write(self, method_name: str, **kwargs) -> None:
        invoice_id = int(kwargs['invoice_id'])
        if self.context is None:
            if self.get_invoice(invoice_id) is None:
                raise ValueError('invoice_not_found_for_supplier')
            method = getattr(self._legacy_invoices, method_name)
            if method_name in {'update_invoice_status', 'delete_invoice_with_items'}:
                method(invoice_id, kwargs.get('status')) if method_name == 'update_invoice_status' else method(invoice_id)
            else:
                method(**kwargs)
            return
        getattr(self._workspace_invoices, method_name)(self.context, **kwargs)
