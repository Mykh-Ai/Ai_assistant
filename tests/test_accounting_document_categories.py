from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.services.accounting_document_categories import (
    AccountingDocumentCategoryError,
    allowed_categories_payload,
    create_workspace_category,
    find_similar_category,
    get_category_by_id,
    list_active_categories,
    normalize_category_label,
    set_workspace_category_active,
)
from bot.services.accounting_document_storage import workspace_key_for_supplier


def test_system_categories_include_required_mvp_ids(tmp_path: Path) -> None:
    category_ids = {category.category_id for category in list_active_categories(storage_dir=tmp_path)}

    assert {
        'materials',
        'tools',
        'small_equipment',
        'protective_equipment',
        'consumables',
        'vehicle_fuel',
        'vehicle_service_labor',
        'vehicle_parts',
        'vehicle_consumables',
        'vehicle_wash_parking_toll',
        'office_supplies',
        'software_subscriptions',
        'phone_internet',
        'travel_accommodation',
        'food_refreshments',
        'bank_fees',
        'client_project_expense',
        'personal_or_non_business',
        'mixed_business_expense',
        'unknown_review',
    } <= category_ids


def test_allowed_payload_exposes_bounded_fields_only(tmp_path: Path) -> None:
    payload = allowed_categories_payload(storage_dir=tmp_path)

    assert payload
    assert {'category_id', 'label_sk', 'description', 'review_required'} == set(payload[0])
    assert 'db_id' not in payload[0]
    assert any(item['category_id'] == 'unknown_review' and item['review_required'] is True for item in payload)


def test_workspace_category_is_scoped_and_reused_in_allowed_payload(tmp_path: Path) -> None:
    category = create_workspace_category(
        storage_dir=tmp_path,
        label='Projekt klienta Alfa',
        supplier_telegram_id=111001,
    )

    assert category.category_id.startswith('workspace_projekt_klienta_alfa')
    assert category.scope == 'workspace'
    assert category.workspace_key == workspace_key_for_supplier(111001)
    assert get_category_by_id(
        storage_dir=tmp_path,
        category_id=category.category_id,
        supplier_telegram_id=111001,
    ) == category
    assert get_category_by_id(
        storage_dir=tmp_path,
        category_id=category.category_id,
        supplier_telegram_id=222002,
    ) is None
    assert any(
        item['category_id'] == category.category_id
        for item in allowed_categories_payload(storage_dir=tmp_path, supplier_telegram_id=111001)
    )


def test_duplicate_or_similar_label_requires_explicit_override(tmp_path: Path) -> None:
    category = create_workspace_category(storage_dir=tmp_path, label='Moje špeciálne nákupy', supplier_telegram_id=111001)

    similar = find_similar_category(storage_dir=tmp_path, label='moje specialne nakupy', supplier_telegram_id=111001)

    assert similar == category
    with pytest.raises(AccountingDocumentCategoryError, match='similar_category_exists'):
        create_workspace_category(storage_dir=tmp_path, label='Moje specialne nakupy', supplier_telegram_id=111001)

    second = create_workspace_category(
        storage_dir=tmp_path,
        label='Moje specialne nakupy',
        supplier_telegram_id=111001,
        allow_similar=True,
    )
    assert second.category_id != category.category_id


def test_inactive_workspace_category_is_hidden_from_allowed_payload(tmp_path: Path) -> None:
    category = create_workspace_category(storage_dir=tmp_path, label='Sezónne výdavky', supplier_telegram_id=111001)

    inactive = set_workspace_category_active(
        storage_dir=tmp_path,
        category_id=category.category_id,
        is_active=False,
        supplier_telegram_id=111001,
    )

    assert inactive.is_active is False
    assert get_category_by_id(
        storage_dir=tmp_path,
        category_id=category.category_id,
        supplier_telegram_id=111001,
    ) is None
    assert get_category_by_id(
        storage_dir=tmp_path,
        category_id=category.category_id,
        supplier_telegram_id=111001,
        include_inactive=True,
    ) is not None
    assert all(
        item['category_id'] != category.category_id
        for item in allowed_categories_payload(storage_dir=tmp_path, supplier_telegram_id=111001)
    )


def test_workspace_registry_file_contains_no_system_category_overwrite(tmp_path: Path) -> None:
    create_workspace_category(storage_dir=tmp_path, label='Lokálne nákupy', supplier_telegram_id=111001)

    registry_path = (
        tmp_path
        / 'workspaces'
        / workspace_key_for_supplier(111001)
        / 'master_data'
        / 'categories'
        / 'categories.json'
    )
    payload = json.loads(registry_path.read_text(encoding='utf-8'))

    assert len(payload) == 1
    assert 'scope' not in payload[0]
    assert 'workspace_key' not in payload[0]
    assert payload[0]['category_id'].startswith('workspace_')
    assert all(item['category_id'] != 'materials' for item in payload)


def test_category_label_validation_is_text_first_and_bounded() -> None:
    assert normalize_category_label('  Klientske  náklady  ') == 'Klientske náklady'
    with pytest.raises(AccountingDocumentCategoryError, match='category_label_required'):
        normalize_category_label('   ')
    with pytest.raises(AccountingDocumentCategoryError, match='category_label_too_long'):
        normalize_category_label('x' * 81)
