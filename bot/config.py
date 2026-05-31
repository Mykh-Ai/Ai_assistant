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
    google_oauth_redirect_uri: str | None = None
    google_oauth_callback_host: str = '127.0.0.1'
    google_oauth_callback_port: int = 8080
    google_oauth_callback_use_fake_exchanger: bool = False


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
    google_oauth_redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '').strip() or None
    google_oauth_callback_host = os.getenv('GOOGLE_OAUTH_CALLBACK_HOST', '').strip() or '127.0.0.1'
    google_oauth_callback_port = _parse_positive_int(
        os.getenv('GOOGLE_OAUTH_CALLBACK_PORT', '8080'),
        env_name='GOOGLE_OAUTH_CALLBACK_PORT',
    )
    google_oauth_callback_use_fake_exchanger = _parse_bool(
        os.getenv('GOOGLE_OAUTH_CALLBACK_USE_FAKE_EXCHANGER', ''),
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
        google_oauth_redirect_uri=google_oauth_redirect_uri,
        google_oauth_callback_host=google_oauth_callback_host,
        google_oauth_callback_port=google_oauth_callback_port,
        google_oauth_callback_use_fake_exchanger=google_oauth_callback_use_fake_exchanger,
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


def _parse_bool(raw_value: str) -> bool:
    return raw_value.strip().lower() in {'1', 'true', 'yes', 'on'}
