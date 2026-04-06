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
    db_path: Path
    storage_dir: Path


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
    db_path = Path(os.getenv('DB_PATH', 'storage/fakturabot.db')).resolve()
    storage_dir = Path(os.getenv('STORAGE_DIR', 'storage')).resolve()
    ensure_storage_dirs(storage_dir)

    return Config(
        bot_token=bot_token,
        openai_api_key=openai_api_key,
        openai_stt_model=openai_stt_model,
        openai_llm_model=openai_llm_model,
        db_path=db_path,
        storage_dir=storage_dir,
    )
