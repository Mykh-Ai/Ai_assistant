from aiogram import Router

from .contacts import router as contacts_router
from .contracts import router as contracts_router
from .invoice import router as invoice_router
from .onboarding import router as onboarding_router
from .settings import router as settings_router
from .start import router as start_router
from .voice import router as voice_router

routers: list[Router] = [
    start_router,
    voice_router,
    onboarding_router,
    contacts_router,
    contracts_router,
    invoice_router,
    settings_router,
]
