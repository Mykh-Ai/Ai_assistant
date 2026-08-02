from bot.config import load_config


def _base_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('BOT_TOKEN', 'token')
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'bot.db'))
    monkeypatch.setenv('STORAGE_DIR', str(tmp_path / 'storage'))
    monkeypatch.setenv('GOOGLE_OAUTH_CALLBACK_PORT', '8080')
    monkeypatch.setenv('GOOGLE_DRIVE_ARCHIVE_WORKER_INTERVAL_SECONDS', '60')
    monkeypatch.setenv('GOOGLE_DRIVE_ARCHIVE_WORKER_BATCH_SIZE', '5')
    monkeypatch.setenv('INVOICE_FOLLOWUP_CHECK_INTERVAL_SECONDS', '86400')
    monkeypatch.setenv('INVOICE_FOLLOWUP_NOTIFICATION_COOLDOWN_HOURS', '24')
    monkeypatch.setenv('CONTACT_REGISTRY_TIMEOUT_SECONDS', '5')
    monkeypatch.setenv('CONTACT_REGISTRY_MAX_RESULTS', '5')
    monkeypatch.setenv('CONTACT_REGISTRY_MONITOR_INTERVAL_DAYS', '14')
    monkeypatch.setenv('CONTACT_REGISTRY_MONITOR_BATCH_SIZE', '20')
    monkeypatch.setenv('CONTACT_REGISTRY_MONITOR_PROPOSAL_TTL_DAYS', '30')
    monkeypatch.setenv('FINANCNA_SPRAVA_TIMEOUT_SECONDS', '5')


def test_rollout_defaults_disabled(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.delenv('INFOHELP_CONTEXTUAL_V2_ROLLOUT', raising=False)
    assert load_config().infohelp_contextual_v2_rollout == 'disabled'


def test_rollout_accepts_only_bounded_values(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    for value in ('disabled', 'admin_pilot', 'enabled'):
        monkeypatch.setenv('INFOHELP_CONTEXTUAL_V2_ROLLOUT', value)
        assert load_config().infohelp_contextual_v2_rollout == value
    monkeypatch.setenv('INFOHELP_CONTEXTUAL_V2_ROLLOUT', 'force_everyone')
    assert load_config().infohelp_contextual_v2_rollout == 'disabled'
