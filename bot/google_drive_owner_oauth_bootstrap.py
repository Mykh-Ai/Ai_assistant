from __future__ import annotations

import argparse
from datetime import UTC, datetime
import logging

from bot.config import Config, load_config
from bot.google_drive_oauth_callback_app import OAUTH_CALLBACK_PATH
from bot.services.google_drive_connection_service import (
    GOOGLE_DRIVE_STATUS_CONNECTED,
    GoogleDriveConnectionService,
)
from bot.services.google_drive_oauth_state_service import GoogleDriveOAuthStateService
from bot.services.google_drive_owner_oauth import (
    OWNER_GOOGLE_DRIVE_OAUTH_SCOPES,
    build_google_token_crypto_provider,
    serialize_google_oauth_token_bundle,
)
from bot.services.google_oauth_token_exchanger import GoogleOAuthTokenExchanger


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    if args.command == "authorize":
        _run_authorize(config, args)
        return
    if args.command == "exchange":
        _run_exchange(config, args)
        return
    parser.error("unknown command")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bot.google_drive_owner_oauth_bootstrap",
        description="One-time owner OAuth bootstrap for FakturaBot Google Drive archive.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    authorize = subparsers.add_parser("authorize", help="Generate the owner consent URL.")
    authorize.add_argument("--telegram-id", type=int, required=True, help="Owner/admin Telegram id for audit metadata.")
    authorize.add_argument("--workspace-id", default=None, help="Owner OAuth workspace id. Defaults to GOOGLE_DRIVE_OWNER_WORKSPACE_ID.")
    authorize.add_argument("--redirect-uri", default=None, help="OAuth redirect URI. Defaults to env or localhost callback path.")

    exchange = subparsers.add_parser("exchange", help="Exchange a returned OAuth code and store encrypted token.")
    exchange.add_argument("--state-token", required=True, help="Raw state token printed by authorize.")
    exchange.add_argument("--code", required=True, help="Authorization code copied from the redirect URL.")
    exchange.add_argument("--root-folder-id", default=None, help="Owner My Drive root folder id for FakturaBot archive.")

    return parser


def _run_authorize(config: Config, args: argparse.Namespace) -> None:
    _require_oauth_client(config)
    workspace_id = _workspace_id(config, args.workspace_id)
    redirect_uri = _redirect_uri(config, args.redirect_uri)
    state_service = GoogleDriveOAuthStateService(config.db_path)
    result = state_service.create_oauth_state(
        workspace_id=workspace_id,
        telegram_id=args.telegram_id,
        scopes=OWNER_GOOGLE_DRIVE_OAUTH_SCOPES,
        redirect_uri=redirect_uri,
    )
    authorization_url = state_service.build_authorization_url(
        client_id=str(config.google_oauth_client_id),
        redirect_uri=redirect_uri,
        scopes=OWNER_GOOGLE_DRIVE_OAUTH_SCOPES,
        state_token=result.raw_state_token,
        prompt_consent=True,
    )
    print("Open this URL as the Google Drive owner:")
    print(authorization_url)
    print()
    print("After consent, copy the code from the redirected URL and run:")
    print(
        "python -m bot.google_drive_owner_oauth_bootstrap exchange "
        f"--state-token {result.raw_state_token} --code <returned-code> --root-folder-id <folder-id>"
    )


def _run_exchange(config: Config, args: argparse.Namespace) -> None:
    _require_oauth_client(config)
    crypto_provider = build_google_token_crypto_provider(config)
    root_folder_id = (args.root_folder_id or config.google_drive_root_folder_id or "").strip()
    if not root_folder_id:
        raise SystemExit("GOOGLE_DRIVE_ROOT_FOLDER_ID or --root-folder-id is required")
    state_service = GoogleDriveOAuthStateService(config.db_path)
    consumed = state_service.consume_oauth_state(raw_state_token=args.state_token)
    exchanger = GoogleOAuthTokenExchanger(
        client_id=str(config.google_oauth_client_id),
        client_secret=str(config.google_oauth_client_secret),
        required_scopes=OWNER_GOOGLE_DRIVE_OAUTH_SCOPES,
    )
    token_bundle = exchanger.exchange_code(
        code=args.code,
        redirect_uri=consumed.redirect_uri,
        scopes=consumed.scopes_requested,
    )
    connection_service = GoogleDriveConnectionService(config.db_path, crypto_provider)
    record = connection_service.create_or_update_connection(
        workspace_id=consumed.workspace_id,
        telegram_id=consumed.telegram_id,
        scopes_granted=token_bundle.scope,
        token_plaintext=serialize_google_oauth_token_bundle(token_bundle),
        status=GOOGLE_DRIVE_STATUS_CONNECTED,
        google_subject=token_bundle.google_subject,
        google_email=token_bundle.google_email,
        root_folder_id=root_folder_id,
        root_folder_path=config.google_drive_root_folder_name,
        now=datetime.now(UTC),
    )
    print("OWNER_OAUTH_CONNECTED")
    print("workspace_id=" + record.workspace_id)
    print("google_email=" + str(record.google_email or "unknown"))
    print("root_folder_id=" + _mask_folder_id(str(record.root_folder_id or "")))


def _require_oauth_client(config: Config) -> None:
    if not config.google_oauth_client_id or not config.google_oauth_client_secret:
        raise SystemExit("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are required")
    if not config.google_token_crypto_secret:
        raise SystemExit("GOOGLE_TOKEN_CRYPTO_SECRET is required before storing owner OAuth tokens")


def _workspace_id(config: Config, explicit: str | None) -> str:
    workspace_id = (explicit or config.google_drive_owner_workspace_id or "").strip()
    if not workspace_id:
        raise SystemExit("owner workspace id is required")
    return workspace_id


def _redirect_uri(config: Config, explicit: str | None) -> str:
    value = (explicit or config.google_oauth_redirect_uri or "").strip()
    if value:
        return value
    return f"http://localhost:{config.google_oauth_callback_port}{OAUTH_CALLBACK_PATH}"


def _mask_folder_id(value: str) -> str:
    if len(value) <= 10:
        return "***" if value else ""
    return value[:6] + "..." + value[-4:]


if __name__ == "__main__":
    main()
