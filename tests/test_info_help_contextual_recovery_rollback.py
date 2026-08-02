from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers import routers
from bot.handlers.decision_callbacks import router as decision_callbacks_router
from bot.handlers.invoice import process_invoice_text
from bot.handlers.invoice import router as invoice_router
from bot.handlers.start import router as start_router
from bot.services.info_help import InfoHelpTriageResult
from bot.services.product_truth import ProductTruthStatus, get_capability


REPO_ROOT = Path(__file__).resolve().parents[1]


class _Message:
    def __init__(self, text: str) -> None:
        self.text = text
        self.message_id = 1
        self.update_id = 1
        self.from_user = type("_User", (), {"id": 111})()
        self.answers: list[tuple[str, dict[str, object]]] = []

    async def answer(self, text: str, **kwargs: object) -> None:
        self.answers.append((text, kwargs))


class _State:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True

    async def get_state(self) -> None:
        return None


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token="token",
        openai_api_key=None,
        openai_stt_model="whisper-1",
        openai_llm_model="gpt-4o",
        debug_invoice_transparency=False,
        db_path=tmp_path / "test.db",
        storage_dir=tmp_path,
    )


def test_pr63_runtime_owners_and_callback_routes_are_absent() -> None:
    removed_paths = (
        REPO_ROOT / "bot/handlers/info_help_recovery.py",
        REPO_ROOT / "bot/services/active_fsm_state_descriptors.py",
        REPO_ROOT / "bot/services/contextual_info_help_recovery.py",
        REPO_ROOT / "bot/services/conversation_context.py",
    )
    assert all(not path.exists() for path in removed_paths)

    handler_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((REPO_ROOT / "bot/handlers").glob("*.py"))
    )
    main_source = (REPO_ROOT / "bot/main.py").read_text(encoding="utf-8")
    voice_source = (REPO_ROOT / "bot/handlers/voice.py").read_text(encoding="utf-8")

    assert "infohelp:" not in handler_source
    assert "navigation:show_main_menu" not in handler_source
    assert "dispatch_recovery_action" not in handler_source
    assert "ConversationContextInboundMiddleware" not in main_source
    assert "ConversationContextOutgoingMiddleware" not in main_source
    assert "remember_user_text" not in voice_source


def test_known_command_and_decision_owners_remain_registered() -> None:
    assert start_router in routers
    assert invoice_router in routers
    assert decision_callbacks_router in routers
    assert all(router.name != "info_help_recovery" for router in routers)


@pytest.mark.parametrize("user_input", ["Видалити чек", "/kontakt"])
def test_unknown_input_restores_prior_infohelp_without_recovery_buttons(
    user_input: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _unknown_action(**kwargs: object) -> str:
        return "unknown"

    async def _unknown_triage(**kwargs: object) -> InfoHelpTriageResult:
        return InfoHelpTriageResult()

    monkeypatch.setattr("bot.handlers.invoice.resolve_semantic_action", _unknown_action)
    monkeypatch.setattr(
        "bot.handlers.invoice.resolve_info_help_triage_result_with_llm",
        _unknown_triage,
    )

    message = _Message(user_input)
    state = _State()
    config = _config(tmp_path)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text=user_input,
        )
    )

    assert state.cleared is True
    assert len(message.answers) == 1
    answer, kwargs = message.answers[0]
    assert "Nerozumiem, čo chcete spraviť." in answer
    assert kwargs == {}
    assert "Vymazať existujúcu faktúru" not in answer
    assert "Vymazať databázu" not in answer
    assert not config.db_path.exists()


def test_preexisting_product_truth_remains_partial_after_v1_rollback() -> None:
    truth = get_capability("info_help")

    assert truth.product_status == ProductTruthStatus.PARTIAL
    assert "bounded Unknown / Discovery / Triage v1" in truth.capability.summary_for_user
    assert "contextual recovery" not in truth.capability.summary_for_user.casefold()
