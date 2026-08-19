from __future__ import annotations

from pathlib import Path
import re
import sqlite3

from bot.services.db import init_db
from bot.services.info_help import (
    build_product_truth_guidance,
    classify_info_help_capability,
)
from bot.services.product_truth import ProductTruthStatus, get_capability


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / 'android'
API_CLIENT = (
    ANDROID
    / 'app/src/main/java/sk/zevsflow/officeflow/network/OfficeFlowApiClient.kt'
)


def _android_text() -> str:
    return '\n'.join(
        path.read_text(encoding='utf-8')
        for path in sorted(ANDROID.rglob('*'))
        if path.is_file()
        and path.suffix in {'.kt', '.kts', '.xml', '.properties'}
    )


def test_android_api_client_contains_only_approved_stage_a_routes() -> None:
    source = API_CLIENT.read_text(encoding='utf-8')
    route_literals = set(re.findall(r'"(/v1/[^"?]*)"', source))

    assert route_literals == {
        '/v1/enrollment/exchange',
        '/v1/session/refresh',
        '/v1/session',
        '/v1/workspaces',
        '/v1/invoices',
        '/v1/invoices/$invoiceId',
        '/v1/invoices/$invoiceId/pdf',
        '/v1/contacts',
    }
    assert 'principal_id' not in source
    assert 'telegram_id' not in source
    assert 'supplier_telegram_id' not in source


def test_android_negative_space_has_no_business_mutation_or_ai_stack() -> None:
    source = _android_text().lower()

    for forbidden in (
        '/v1/action',
        'mark-paid',
        'active_workspace_selection',
        'retrofit',
        'roomdatabase',
        'firebase',
        'logginginterceptor',
        'com.openai',
        'speechrecognizer',
        'webview',
    ):
        assert forbidden not in source
    assert re.search(r'^import .*\b(llm|stt|lmm)\b', source, re.MULTILINE) is None
    api_source = API_CLIENT.read_text(encoding='utf-8').lower()
    assert api_source.count('.post(') == 1  # one builder used by enrollment/refresh
    assert len(re.findall(r'\.url\(url\("/v1/session"\)\)\s*\.delete\(\)', api_source)) == 1


def test_release_network_and_backup_policy_fail_closed() -> None:
    build = (ANDROID / 'app/build.gradle.kts').read_text(encoding='utf-8')
    main_manifest = (ANDROID / 'app/src/main/AndroidManifest.xml').read_text(
        encoding='utf-8'
    )
    debug_network = (
        ANDROID / 'app/src/debug/res/xml/network_security_config.xml'
    ).read_text(encoding='utf-8')

    assert 'uri.scheme == "https"' in build
    assert 'OFFICEFLOW_API_BASE_URL is required for release builds.' in build
    assert 'android:usesCleartextTraffic="false"' in main_manifest
    assert 'android:allowBackup="false"' in main_manifest
    assert '<domain includeSubdomains="false">10.0.2.2</domain>' in debug_network
    assert debug_network.count('<domain ') == 1


def test_secure_store_uses_keystore_no_backup_and_contains_no_plaintext_fallback() -> None:
    source = (
        ANDROID
        / 'app/src/main/java/sk/zevsflow/officeflow/security/SecureSessionStore.kt'
    ).read_text(encoding='utf-8')

    assert 'AndroidKeyStore' in source
    assert 'AES/GCM/NoPadding' in source
    assert 'noBackupFilesDir' in source
    assert 'ATOMIC_MOVE' in source
    assert 'SharedPreferences' not in source
    assert 'DataStore' not in source
    assert 'SQLite' not in source


def test_android_product_truth_and_slovak_infohelp_are_bounded_and_side_effect_free(
    tmp_path: Path,
) -> None:
    capability = get_capability('first_party_android_client')
    assert capability.product_status == ProductTruthStatus.PARTIAL
    assert capability.capability.requires_admin is True
    assert capability.capability.requires_setup is True
    assert classify_info_help_capability(
        user_input_text='Ako funguje OfficeFlow aplikácia pre Android?'
    ) == 'first_party_android_client'

    db_path = tmp_path / 'truth-no-effect.db'
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        before = '\n'.join(connection.iterdump())
    response = build_product_truth_guidance(
        user_input_text='Môžem v Android aplikácii vytvoriť faktúru?'
    )
    with sqlite3.connect(db_path) as connection:
        after = '\n'.join(connection.iterdump())

    assert response is not None
    assert 'čiastočné' in response
    assert 'Produkčný API endpoint ešte nie je nasadený' in response
    assert 'Nevytvára ani neupravuje faktúry' in response
    assert before == after


def test_forbidden_full_android_claims_are_absent_from_user_copy() -> None:
    response = build_product_truth_guidance(
        user_input_text='Čo vie OfficeFlow na Androide?'
    )
    assert response is not None
    for forbidden in (
        'Všetky funkcie OfficeFlow fungujú na Androide.',
        'Telegram už nie je potrebný.',
        'Android môže vytvárať faktúry.',
        'Aplikácia je už živá pre produkčných používateľov.',
    ):
        assert forbidden not in response
