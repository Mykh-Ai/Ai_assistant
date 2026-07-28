from aiogram import Router

from .access_admin import router as access_admin_router
from .accounting_documents import router as accounting_documents_router
from .accounting_document_intake import router as accounting_document_intake_router
from .contacts import router as contacts_router
from .business_profiles import router as business_profiles_router
from .contracts import router as contracts_router
from .delete_user_database import router as delete_user_database_router
from .decision_callbacks import router as decision_callbacks_router
from .work_time import router as work_time_router
from .invoice import router as invoice_router
from .invoice_followup import router as invoice_followup_router
from .officeflow_attachment_router import router as officeflow_attachment_router
from .onboarding import router as onboarding_router
from .settings import router as settings_router
from .state_control import router as state_control_router
from .runtime_issue import router as runtime_issue_router
from .supplier import router as supplier_router
from .start import router as start_router
from .voice import router as voice_router

routers: list[Router] = [
    access_admin_router,
    start_router,
    state_control_router,
    runtime_issue_router,
    delete_user_database_router,
    business_profiles_router,
    voice_router,
    decision_callbacks_router,
    invoice_followup_router,
    onboarding_router,
    supplier_router,
    accounting_document_intake_router,
    accounting_documents_router,
    officeflow_attachment_router,
    contacts_router,
    contracts_router,
    work_time_router,
    invoice_router,
    settings_router,
]
