from __future__ import annotations

from bot.config import Config


def contextual_info_help_v2_enabled(config: Config, actor_telegram_id: int | None) -> bool:
    mode = str(getattr(config, 'infohelp_contextual_v2_rollout', 'disabled')).casefold()
    if mode == 'enabled':
        return actor_telegram_id is not None
    if mode == 'admin_pilot':
        return actor_telegram_id is not None and actor_telegram_id in config.admin_telegram_user_ids
    return False
