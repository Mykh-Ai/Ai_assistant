from aiogram import Router

from .accounting_document_intake import router as accounting_document_intake_router
from .contacts import router as contacts_router
from .contracts import router as contracts_router
from .invoice import router as invoice_router
from .officeflow_attachment_router import router as officeflow_attachment_router
from .onboarding import router as onboarding_router
from .settings import router as settings_router
from .supplier import router as supplier_router
from .start import router as start_router
from .voice import router as voice_router

routers: list[Router] = [
    start_router,
    voice_router,
    onboarding_router,
    supplier_router,
    accounting_document_intake_router,
    officeflow_attachment_router,
    contacts_router,
    contracts_router,
    invoice_router,
    settings_router,
]
