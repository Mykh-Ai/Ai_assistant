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
APP_SOURCE = (
    ANDROID / 'app/src/main/java/sk/zevsflow/officeflow/ui/OfficeFlowApp.kt'
)
NAVIGATION_SOURCE = (
    ANDROID
    / 'app/src/main/java/sk/zevsflow/officeflow/ui/OfficeFlowNavigation.kt'
)
MODELS_SOURCE = (
    ANDROID / 'app/src/main/java/sk/zevsflow/officeflow/data/Models.kt'
)
ANDROID_WORKFLOW = ROOT / '.github/workflows/android-debug-apk.yml'


def _android_text() -> str:
    return '\n'.join(
        path.read_text(encoding='utf-8')
        for path in sorted(ANDROID.rglob('*'))
        if path.is_file()
        and 'build' not in path.parts
        and '.gradle' not in path.parts
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


def test_c1_home_uses_frozen_domains_without_flat_bottom_navigation() -> None:
    navigation = NAVIGATION_SOURCE.read_text(encoding='utf-8')
    app = APP_SOURCE.read_text(encoding='utf-8')

    domain_labels = re.findall(
        r'BusinessDomain\(\s*id = "[^"]+",\s*label = "([^"]+)"',
        navigation,
    )
    assert domain_labels == [
        'Faktúry',
        'Bločky',
        'Kontakty',
        'Pracovný čas',
        'Analytika',
        'InfoHelp',
    ]
    assert 'startDestination = HOME_ROUTE' in app
    assert 'NavigationBar' not in app
    assert 'VOICE_CHAT_LABEL = "Hlas / Chat"' in navigation
    assert 'label = "Doklady"' not in navigation
    assert 'label = "Bločky/Doklady"' not in navigation


def test_c1_unavailable_domains_have_no_network_owner_and_no_microphone_permission() -> None:
    navigation = NAVIGATION_SOURCE.read_text(encoding='utf-8')
    app = APP_SOURCE.read_text(encoding='utf-8')
    manifest = (ANDROID / 'app/src/main/AndroidManifest.xml').read_text(
        encoding='utf-8'
    )

    assert navigation.count('availability = C1Availability.EXISTING_INVOICES') == 1
    assert navigation.count('availability = C1Availability.EXISTING_CONTACTS') == 1
    assert 'RECORD_AUDIO' not in manifest
    assert 'C1Availability.UNAVAILABLE -> nav.navigate' in app
    assert 'Hlas a chat budú dostupné v ďalšej fáze.' in app


def test_c1_responsive_and_nullable_detail_boundaries_are_explicit() -> None:
    app = APP_SOURCE.read_text(encoding='utf-8')
    models = MODELS_SOURCE.read_text(encoding='utf-8')
    smoke = (
        ANDROID
        / 'app/src/androidTest/java/sk/zevsflow/officeflow/ResponsiveC1SmokeTest.kt'
    ).read_text(encoding='utf-8')

    assert 'val unit: String? = null' in models
    assert 'jednotka neuvedená' in app
    assert 'contentWindowInsets = ScaffoldDefaults.contentWindowInsets' in app
    assert '.consumeWindowInsets(padding)' in app
    assert 'assertHomeAtFontScale(1.3f)' in smoke
    assert 'assertHomeAtFontScale(1.5f)' in smoke
    assert 'assertHomeAtFontScale(2f)' in smoke
    assert 'longContactFieldsRemainReachableAtLargeFontScale' in smoke
    assert 'performScrollTo()' in smoke


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


def test_pilot_signing_is_isolated_from_pull_request_builds_and_pinned() -> None:
    workflow = ANDROID_WORKFLOW.read_text(encoding='utf-8')
    build = (ANDROID / 'app/build.gradle.kts').read_text(encoding='utf-8')

    debug_job, pilot_job = workflow.split('  android-pilot:', maxsplit=1)
    assert "if: github.event_name == 'pull_request'" in debug_job
    assert 'environment: android-pilot-signing' not in debug_job
    assert 'secrets.OFFICEFLOW_PILOT_' not in debug_job
    assert "if: github.event_name == 'workflow_dispatch'" in pilot_job
    assert 'environment: android-pilot-signing' in pilot_job
    assert 'OFFICEFLOW_PILOT_KEYSTORE_B64' in pilot_job
    assert 'OFFICEFLOW_PILOT_KEYSTORE_PASSWORD' in pilot_job
    assert 'OFFICEFLOW_PILOT_KEY_ALIAS' in pilot_job
    assert 'OFFICEFLOW_PILOT_KEY_PASSWORD' in pilot_job
    assert '${RUNNER_TEMP}/officeflow-pilot-signing.p12' in pilot_job
    assert 'if: always()' in pilot_job
    assert '3835035c2df22b22406a00c359cc1a03e54f61852c302ed7c6392702a9d8e6fe' in pilot_job
    assert 'observed_signing_certificate_sha256=%s' in pilot_job
    assert 'stable_pilot_signing_verified=true' in pilot_job

    for variable in (
        'OFFICEFLOW_PILOT_KEYSTORE_PATH',
        'OFFICEFLOW_PILOT_KEYSTORE_PASSWORD',
        'OFFICEFLOW_PILOT_KEY_ALIAS',
        'OFFICEFLOW_PILOT_KEY_PASSWORD',
    ):
        assert f'environmentVariable("{variable}")' in build
    assert 'pilotSigningInputCount == 0 ||' in build
    assert 'signingConfig = signingConfigs.getByName("pilot")' in build


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
    assert 'overené na jednom autorizovanom Samsung zariadení' in response
    assert 'nový APK ešte potrebuje reálne overenie' in response
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
