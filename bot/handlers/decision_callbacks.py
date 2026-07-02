from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.config import Config
from bot.handlers.access_admin import (
    CustomizationRequestAdminResponseStates,
    customization_request_response_preview_decision,
)
from bot.handlers.contacts import ContactStates, contact_confirm, process_contact_intake_confirm
from bot.handlers.invoice import (
    CustomizationRequestStates,
    InvoiceStates,
    customization_request_preview_decision,
    invoice_delete_existing_invoice_confirm,
    invoice_mark_existing_invoice_paid_confirm,
    process_invoice_customer_alias_confirm,
    process_invoice_preview_confirmation,
)
from bot.handlers.onboarding import (
    OnboardingStates,
    SupplierProfileEditStates,
    onboarding_confirm,
    supplier_profile_edit_confirm,
)
from bot.handlers.work_time import (
    WorkTimeStates,
    work_time_close_preview_confirm,
    work_time_delete_month_confirm,
    work_time_lunch_break_initial_choice,
    work_time_lunch_break_update_confirm,
    work_time_manual_range_confirm,
    work_time_missing_days_choice,
    work_time_open_day_conflict_choice,
)
from bot.keyboards.decision import (
    DECISION_APPROVE,
    DECISION_CALLBACK_PREFIX,
    DECISION_CANCEL,
    DECISION_CLOSE_DAY,
    DECISION_EDIT,
    DECISION_FILL,
    DECISION_FILL_TIME,
    DECISION_NO,
    DECISION_SKIP,
    DECISION_SKIP_DAY,
    DECISION_YES,
)


router = Router(name='decision_callbacks')

_STALE_DECISION_MESSAGE = 'Toto rozhodnutie už nie je dostupné. Pokračujte aktuálnym krokom v chate.'


class _CallbackMessageAdapter:
    def __init__(self, callback: CallbackQuery) -> None:
        self._callback = callback
        self.text = ''
        self.from_user = callback.from_user
        source_message = callback.message
        self.message_id = getattr(source_message, 'message_id', None)

    async def answer(self, text: str, **kwargs) -> None:
        source_message = self._callback.message
        if source_message is not None and hasattr(source_message, 'answer'):
            await source_message.answer(text, **kwargs)
            return
        await self._callback.answer(text, show_alert=True)

    async def answer_document(self, document, caption: str | None = None, **kwargs) -> None:
        source_message = self._callback.message
        if source_message is not None and hasattr(source_message, 'answer_document'):
            await source_message.answer_document(document, caption=caption, **kwargs)
            return
        await self._callback.answer('Dokument sa nepodarilo odoslat z tlacidla.', show_alert=True)


@router.callback_query(F.data.startswith(DECISION_CALLBACK_PREFIX))
async def decision_callback(callback: CallbackQuery, state: FSMContext, config: Config, bot: Bot | None = None) -> None:
    token = _parse_decision_token(callback.data)
    current_state = _state_name(await state.get_state())
    if token is None:
        await callback.answer(_STALE_DECISION_MESSAGE, show_alert=True)
        return

    adapter = _CallbackMessageAdapter(callback)
    handled = await _dispatch_decision_token(
        token=token,
        current_state=current_state,
        message=adapter,
        state=state,
        config=config,
        bot=bot,
    )
    if not handled:
        await callback.answer(_STALE_DECISION_MESSAGE, show_alert=True)
        return

    await _clear_inline_keyboard(callback)
    await callback.answer()


def _parse_decision_token(data: str | None) -> str | None:
    if not data or not data.startswith(DECISION_CALLBACK_PREFIX):
        return None
    token = data[len(DECISION_CALLBACK_PREFIX) :]
    allowed = {
        DECISION_YES,
        DECISION_NO,
        DECISION_APPROVE,
        DECISION_EDIT,
        DECISION_CANCEL,
        DECISION_CLOSE_DAY,
        DECISION_FILL_TIME,
        DECISION_SKIP_DAY,
        DECISION_FILL,
        DECISION_SKIP,
    }
    return token if token in allowed else None


def _state_name(value) -> str | None:
    if isinstance(value, str):
        return value
    state_value = getattr(value, 'state', None)
    return state_value if isinstance(state_value, str) else None


async def _dispatch_decision_token(
    *,
    token: str,
    current_state: str | None,
    message,
    state: FSMContext,
    config: Config,
    bot: Bot | None = None,
) -> bool:
    if current_state == InvoiceStates.waiting_confirm.state and token in {
        DECISION_APPROVE,
        DECISION_EDIT,
        DECISION_CANCEL,
    }:
        await process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='',
            canonical_decision=token,
        )
        return True

    if current_state == CustomizationRequestStates.waiting_preview_decision.state and token in {
        DECISION_APPROVE,
        DECISION_EDIT,
        DECISION_CANCEL,
    }:
        await customization_request_preview_decision(
            message=message,
            state=state,
            config=config,
            canonical_decision=token,
        )
        return True

    if current_state == CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state and token in {
        DECISION_APPROVE,
        DECISION_EDIT,
        DECISION_CANCEL,
    }:
        await customization_request_response_preview_decision(
            message=message,
            state=state,
            config=config,
            bot=bot,
            canonical_decision=token,
        )
        return True

    if current_state == InvoiceStates.waiting_customer_alias_confirm.state and token in {DECISION_YES, DECISION_NO}:
        await process_invoice_customer_alias_confirm(
            message=message,
            state=state,
            config=config,
            answer_text='',
            canonical_decision=token,
        )
        return True

    if current_state == InvoiceStates.waiting_delete_existing_invoice_confirm.state and token in {DECISION_YES, DECISION_NO}:
        await invoice_delete_existing_invoice_confirm(
            message=message,
            state=state,
            config=config,
            canonical_decision=token,
        )
        return True

    if current_state == InvoiceStates.waiting_mark_existing_invoice_paid_confirm.state and token in {DECISION_YES, DECISION_NO}:
        await invoice_mark_existing_invoice_paid_confirm(
            message=message,
            state=state,
            config=config,
            canonical_decision=token,
        )
        return True

    if current_state == WorkTimeStates.waiting_manual_range_confirm.state and token in {
        DECISION_APPROVE,
        DECISION_EDIT,
        DECISION_CANCEL,
    }:
        await work_time_manual_range_confirm(
            message=message,
            state=state,
            config=config,
            canonical_decision=token,
        )
        return True

    if current_state == WorkTimeStates.waiting_close_preview_confirm.state and token in {
        DECISION_APPROVE,
        DECISION_EDIT,
        DECISION_CANCEL,
    }:
        await work_time_close_preview_confirm(
            message=message,
            state=state,
            config=config,
            canonical_decision=token,
        )
        return True

    if current_state == WorkTimeStates.waiting_lunch_break_initial_choice.state and token in {DECISION_YES, DECISION_NO}:
        await work_time_lunch_break_initial_choice(
            message=message,
            state=state,
            config=config,
            canonical_decision=token,
        )
        return True

    if current_state == WorkTimeStates.waiting_lunch_break_update_confirm.state and token in {
        DECISION_APPROVE,
        DECISION_EDIT,
        DECISION_CANCEL,
    }:
        await work_time_lunch_break_update_confirm(
            message=message,
            state=state,
            config=config,
            canonical_decision=token,
        )
        return True

    if current_state == WorkTimeStates.waiting_delete_month_confirm.state and token in {DECISION_YES, DECISION_NO}:
        await work_time_delete_month_confirm(
            message=message,
            state=state,
            config=config,
            canonical_decision=token,
        )
        return True

    if current_state == WorkTimeStates.waiting_open_day_conflict_choice.state and token in {
        DECISION_CLOSE_DAY,
        DECISION_FILL_TIME,
        DECISION_SKIP_DAY,
        DECISION_CANCEL,
    }:
        await work_time_open_day_conflict_choice(
            message=message,
            state=state,
            config=config,
            canonical_decision={
                DECISION_CLOSE_DAY: 'close_day',
                DECISION_FILL_TIME: 'fill_time',
                DECISION_SKIP_DAY: 'skip_day',
                DECISION_CANCEL: 'cancel',
            }[token],
        )
        return True

    if current_state == WorkTimeStates.waiting_missing_days_choice.state and token in {
        DECISION_FILL,
        DECISION_SKIP,
        DECISION_CANCEL,
    }:
        await work_time_missing_days_choice(
            message=message,
            state=state,
            config=config,
            canonical_decision={
                DECISION_FILL: 'fill',
                DECISION_SKIP: 'skip',
                DECISION_CANCEL: 'cancel',
            }[token],
        )
        return True

    if current_state == ContactStates.intake_confirm.state and token in {DECISION_YES, DECISION_NO}:
        await process_contact_intake_confirm(
            message=message,
            state=state,
            config=config,
            answer_text='',
            canonical_decision=token,
        )
        return True

    if current_state == ContactStates.confirm.state and token in {DECISION_YES, DECISION_NO}:
        await contact_confirm(message=message, state=state, config=config, canonical_decision=token)
        return True

    if current_state == OnboardingStates.confirm.state and token in {DECISION_YES, DECISION_NO}:
        await onboarding_confirm(message=message, state=state, config=config, canonical_decision=token)
        return True

    if current_state == SupplierProfileEditStates.confirm.state and token in {DECISION_YES, DECISION_NO}:
        await supplier_profile_edit_confirm(message=message, state=state, config=config, canonical_decision=token)
        return True

    return False


async def _clear_inline_keyboard(callback: CallbackQuery) -> None:
    source_message = callback.message
    if source_message is None or not hasattr(source_message, 'edit_reply_markup'):
        return
    try:
        await source_message.edit_reply_markup(reply_markup=None)
    except Exception:
        return
