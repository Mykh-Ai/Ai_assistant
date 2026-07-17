from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parent.parent

if (REPO_ROOT / 'faktura.env').exists():
    load_dotenv(REPO_ROOT / 'faktura.env')
else:
    load_dotenv(REPO_ROOT / '.env')


@dataclass(frozen=True)
class Config:
    bot_token: str
    openai_api_key: str | None
    openai_stt_model: str
    openai_llm_model: str
    debug_invoice_transparency: bool
    db_path: Path
    storage_dir: Path
    allowed_telegram_user_ids: frozenset[int] = frozenset()
    admin_telegram_user_ids: frozenset[int] = frozenset()
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str | None = None
    google_oauth_callback_host: str = '127.0.0.1'
    google_oauth_callback_port: int = 8080
    google_oauth_callback_use_fake_exchanger: bool = False
    google_token_crypto_secret: str | None = None
    google_drive_enabled: bool = False
    google_drive_mode: str = 'owner_oauth'
    google_drive_service_account_json_path: Path | None = None
    google_drive_owner_workspace_id: str = 'owner'
    google_drive_root_folder_id: str | None = None
    google_drive_root_folder_name: str = 'FakturaBot'
    google_drive_delete_local_receipt_original_after_upload: bool = True
    google_drive_delete_local_incoming_invoice_original_after_upload: bool = True
    google_drive_delete_local_invoice_pdf_after_upload: bool = False
    google_drive_archive_worker_interval_seconds: int = 60
    google_drive_archive_worker_batch_size: int = 5
    invoice_followup_scheduler_enabled: bool = True
    invoice_followup_check_interval_seconds: int = 86400
    invoice_followup_notification_cooldown_hours: int = 24
    contact_registry_lookup_enabled: bool = False
    contact_registry_pilot_workspace_ids: frozenset[str] = frozenset()
    contact_registry_timeout_seconds: int = 5
    contact_registry_max_results: int = 5


def ensure_storage_dirs(storage_dir: Path) -> None:
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / 'invoices').mkdir(parents=True, exist_ok=True)
    (storage_dir / 'contracts').mkdir(parents=True, exist_ok=True)
    (storage_dir / 'uploads').mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    bot_token = os.getenv('BOT_TOKEN', '').strip()
    if not bot_token:
        raise RuntimeError('BOT_TOKEN is required')

    openai_api_key = os.getenv('OPENAI_API_KEY', '').strip() or None
    openai_stt_model = os.getenv('OPENAI_STT_MODEL', '').strip() or 'whisper-1'
    openai_llm_model = os.getenv('OPENAI_LLM_MODEL', '').strip() or 'gpt-4o'
    debug_invoice_transparency = os.getenv('DEBUG_INVOICE_TRANSPARENCY', '').strip().lower() in {
        '1',
        'true',
        'yes',
        'on',
    }
    db_path = Path(os.getenv('DB_PATH', 'storage/fakturabot.db')).resolve()
    storage_dir = Path(os.getenv('STORAGE_DIR', 'storage')).resolve()
    allowed_telegram_user_ids = _parse_allowed_telegram_user_ids(
        os.getenv('ALLOWED_TELEGRAM_USER_IDS', '')
    )
    admin_telegram_user_ids = _parse_telegram_user_ids(
        os.getenv('ADMIN_TELEGRAM_USER_IDS', ''),
        env_name='ADMIN_TELEGRAM_USER_IDS',
    )
    google_oauth_client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '').strip() or None
    google_oauth_client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '').strip() or None
    google_oauth_redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '').strip() or None
    google_oauth_callback_host = os.getenv('GOOGLE_OAUTH_CALLBACK_HOST', '').strip() or '127.0.0.1'
    google_oauth_callback_port = _parse_positive_int(
        os.getenv('GOOGLE_OAUTH_CALLBACK_PORT', '8080'),
        env_name='GOOGLE_OAUTH_CALLBACK_PORT',
    )
    google_oauth_callback_use_fake_exchanger = _parse_bool(
        os.getenv('GOOGLE_OAUTH_CALLBACK_USE_FAKE_EXCHANGER', ''),
    )
    google_token_crypto_secret = os.getenv('GOOGLE_TOKEN_CRYPTO_SECRET', '').strip() or None
    google_drive_enabled = _parse_bool(os.getenv('GOOGLE_DRIVE_ENABLED', ''))
    google_drive_mode = os.getenv('GOOGLE_DRIVE_MODE', 'owner_oauth').strip() or 'owner_oauth'
    google_drive_service_account_json_path = _parse_optional_path(
        os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_PATH', '')
    )
    google_drive_owner_workspace_id = (
        os.getenv('GOOGLE_DRIVE_OWNER_WORKSPACE_ID', '').strip() or 'owner'
    )
    google_drive_root_folder_id = os.getenv('GOOGLE_DRIVE_ROOT_FOLDER_ID', '').strip() or None
    google_drive_root_folder_name = (
        os.getenv('GOOGLE_DRIVE_ROOT_FOLDER_NAME', '').strip() or 'FakturaBot'
    )
    google_drive_delete_local_receipt_original_after_upload = _parse_bool(
        os.getenv('GOOGLE_DRIVE_DELETE_LOCAL_RECEIPT_ORIGINAL_AFTER_UPLOAD', '1')
    )
    google_drive_delete_local_incoming_invoice_original_after_upload = _parse_bool(
        os.getenv('GOOGLE_DRIVE_DELETE_LOCAL_INCOMING_INVOICE_ORIGINAL_AFTER_UPLOAD', '1')
    )
    google_drive_delete_local_invoice_pdf_after_upload = _parse_bool(
        os.getenv('GOOGLE_DRIVE_DELETE_LOCAL_INVOICE_PDF_AFTER_UPLOAD', '')
    )
    google_drive_archive_worker_interval_seconds = _parse_positive_int(
        os.getenv('GOOGLE_DRIVE_ARCHIVE_WORKER_INTERVAL_SECONDS', '60'),
        env_name='GOOGLE_DRIVE_ARCHIVE_WORKER_INTERVAL_SECONDS',
    )
    google_drive_archive_worker_batch_size = _parse_positive_int(
        os.getenv('GOOGLE_DRIVE_ARCHIVE_WORKER_BATCH_SIZE', '5'),
        env_name='GOOGLE_DRIVE_ARCHIVE_WORKER_BATCH_SIZE',
    )
    invoice_followup_scheduler_enabled = not _parse_bool(
        os.getenv('DISABLE_INVOICE_FOLLOWUP_SCHEDULER', ''),
    )
    invoice_followup_check_interval_seconds = _parse_positive_int(
        os.getenv('INVOICE_FOLLOWUP_CHECK_INTERVAL_SECONDS', '86400'),
        env_name='INVOICE_FOLLOWUP_CHECK_INTERVAL_SECONDS',
    )
    invoice_followup_notification_cooldown_hours = _parse_positive_int(
        os.getenv('INVOICE_FOLLOWUP_NOTIFICATION_COOLDOWN_HOURS', '24'),
        env_name='INVOICE_FOLLOWUP_NOTIFICATION_COOLDOWN_HOURS',
    )
    contact_registry_lookup_enabled = _parse_bool(
        os.getenv('CONTACT_REGISTRY_LOOKUP_ENABLED', '')
    )
    contact_registry_pilot_workspace_ids = frozenset(
        value.strip()
        for value in os.getenv('CONTACT_REGISTRY_PILOT_WORKSPACE_IDS', '').split(',')
        if value.strip()
    )
    contact_registry_timeout_seconds = _parse_bounded_positive_int(
        os.getenv('CONTACT_REGISTRY_TIMEOUT_SECONDS', '5'),
        env_name='CONTACT_REGISTRY_TIMEOUT_SECONDS',
        maximum=30,
    )
    contact_registry_max_results = _parse_bounded_positive_int(
        os.getenv('CONTACT_REGISTRY_MAX_RESULTS', '5'),
        env_name='CONTACT_REGISTRY_MAX_RESULTS',
        maximum=10,
    )

    ensure_storage_dirs(storage_dir)

    return Config(
        bot_token=bot_token,
        openai_api_key=openai_api_key,
        openai_stt_model=openai_stt_model,
        openai_llm_model=openai_llm_model,
        debug_invoice_transparency=debug_invoice_transparency,
        db_path=db_path,
        storage_dir=storage_dir,
        allowed_telegram_user_ids=allowed_telegram_user_ids,
        admin_telegram_user_ids=admin_telegram_user_ids,
        google_oauth_client_id=google_oauth_client_id,
        google_oauth_client_secret=google_oauth_client_secret,
        google_oauth_redirect_uri=google_oauth_redirect_uri,
        google_oauth_callback_host=google_oauth_callback_host,
        google_oauth_callback_port=google_oauth_callback_port,
        google_oauth_callback_use_fake_exchanger=google_oauth_callback_use_fake_exchanger,
        google_token_crypto_secret=google_token_crypto_secret,
        google_drive_enabled=google_drive_enabled,
        google_drive_mode=google_drive_mode,
        google_drive_service_account_json_path=google_drive_service_account_json_path,
        google_drive_owner_workspace_id=google_drive_owner_workspace_id,
        google_drive_root_folder_id=google_drive_root_folder_id,
        google_drive_root_folder_name=google_drive_root_folder_name,
        google_drive_delete_local_receipt_original_after_upload=google_drive_delete_local_receipt_original_after_upload,
        google_drive_delete_local_incoming_invoice_original_after_upload=google_drive_delete_local_incoming_invoice_original_after_upload,
        google_drive_delete_local_invoice_pdf_after_upload=google_drive_delete_local_invoice_pdf_after_upload,
        google_drive_archive_worker_interval_seconds=google_drive_archive_worker_interval_seconds,
        google_drive_archive_worker_batch_size=google_drive_archive_worker_batch_size,
        invoice_followup_scheduler_enabled=invoice_followup_scheduler_enabled,
        invoice_followup_check_interval_seconds=invoice_followup_check_interval_seconds,
        invoice_followup_notification_cooldown_hours=invoice_followup_notification_cooldown_hours,
        contact_registry_lookup_enabled=contact_registry_lookup_enabled,
        contact_registry_pilot_workspace_ids=contact_registry_pilot_workspace_ids,
        contact_registry_timeout_seconds=contact_registry_timeout_seconds,
        contact_registry_max_results=contact_registry_max_results,
    )


def _parse_allowed_telegram_user_ids(raw_value: str) -> frozenset[int]:
    return _parse_telegram_user_ids(raw_value, env_name='ALLOWED_TELEGRAM_USER_IDS')


def _parse_telegram_user_ids(raw_value: str, *, env_name: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in raw_value.split(','):
        value = part.strip()
        if not value:
            continue
        try:
            parsed = int(value)
        except ValueError as exc:
            raise RuntimeError(f'{env_name} must contain comma-separated integers') from exc
        if parsed <= 0:
            raise RuntimeError(f'{env_name} must contain positive Telegram user ids')
        ids.add(parsed)
    return frozenset(ids)


def _parse_positive_int(raw_value: str, *, env_name: str) -> int:
    try:
        parsed = int(raw_value.strip())
    except ValueError as exc:
        raise RuntimeError(f'{env_name} must be a positive integer') from exc
    if parsed <= 0:
        raise RuntimeError(f'{env_name} must be a positive integer')
    return parsed


def _parse_bounded_positive_int(raw_value: str, *, env_name: str, maximum: int) -> int:
    parsed = _parse_positive_int(raw_value, env_name=env_name)
    if parsed > maximum:
        raise RuntimeError(f'{env_name} must be at most {maximum}')
    return parsed


def _parse_bool(raw_value: str) -> bool:
    return raw_value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _parse_optional_path(raw_value: str) -> Path | None:
    text = raw_value.strip()
    if not text:
        return None
    return Path(text).resolve()
