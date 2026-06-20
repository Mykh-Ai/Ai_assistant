from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

from bot.services.accounting_document_storage import WORKSPACE_KEY, workspace_key_for_supplier


class AccountingDocumentCategoryError(ValueError):
    pass


@dataclass(frozen=True)
class AccountingDocumentCategory:
    category_id: str
    label_sk: str
    label_user: str | None = None
    parent_id: str | None = None
    scope: str = 'system'
    workspace_key: str | None = None
    supplier_telegram_id: int | None = None
    is_active: bool = True
    created_by: str = 'system'
    created_at: str = 'system'
    updated_at: str | None = None
    description: str | None = None
    review_required: bool = False

    @property
    def display_label(self) -> str:
        return self.label_user or self.label_sk

    def to_allowed_payload(self) -> dict[str, Any]:
        return {
            'category_id': self.category_id,
            'label_sk': self.display_label,
            'description': self.description,
            'review_required': self.review_required,
        }


SYSTEM_CATEGORIES: tuple[AccountingDocumentCategory, ...] = (
    AccountingDocumentCategory('materials', 'Materiál', description='Stavebný, montážny alebo pracovný materiál.'),
    AccountingDocumentCategory('tools', 'Náradie', description='Ručné alebo elektrické náradie.'),
    AccountingDocumentCategory('small_equipment', 'Drobné vybavenie'),
    AccountingDocumentCategory('protective_equipment', 'Ochranné pomôcky'),
    AccountingDocumentCategory('consumables', 'Spotrebný materiál'),
    AccountingDocumentCategory('vehicle_fuel', 'Palivo'),
    AccountingDocumentCategory('vehicle_service_labor', 'Servis auta - práca'),
    AccountingDocumentCategory('vehicle_parts', 'Auto diely'),
    AccountingDocumentCategory('vehicle_consumables', 'Auto prevádzkové kvapaliny / spotrebný materiál'),
    AccountingDocumentCategory('vehicle_wash_parking_toll', 'Parkovanie / umývanie / diaľnica'),
    AccountingDocumentCategory('office_supplies', 'Kancelárske potreby'),
    AccountingDocumentCategory('software_subscriptions', 'Softvér / predplatné'),
    AccountingDocumentCategory('phone_internet', 'Telefón / internet'),
    AccountingDocumentCategory('travel_accommodation', 'Cestovanie / ubytovanie'),
    AccountingDocumentCategory(
        'food_refreshments',
        'Jedlo / voda / občerstvenie',
        description='Pracovná kategória pre jedlo, vodu, kávu, nápoje a občerstvenie; nie daňové posúdenie.',
    ),
    AccountingDocumentCategory('bank_fees', 'Bankové poplatky'),
    AccountingDocumentCategory('client_project_expense', 'Výdavok pre zákazku / klienta'),
    AccountingDocumentCategory('personal_or_non_business', 'Osobné alebo nefiremné', review_required=True),
    AccountingDocumentCategory('mixed_business_expense', 'Zmiešaný firemný výdavok'),
    AccountingDocumentCategory('unknown_review', 'Na kontrolu', review_required=True),
)


def resolve_workspace_key(*, supplier_telegram_id: int | None = None, workspace_key: str | None = None) -> str:
    if workspace_key:
        return workspace_key
    if supplier_telegram_id is not None:
        return workspace_key_for_supplier(supplier_telegram_id)
    return WORKSPACE_KEY


def list_active_categories(
    *,
    storage_dir: Path,
    supplier_telegram_id: int | None = None,
    workspace_key: str | None = None,
) -> tuple[AccountingDocumentCategory, ...]:
    resolved_workspace = resolve_workspace_key(supplier_telegram_id=supplier_telegram_id, workspace_key=workspace_key)
    return tuple(category for category in _all_categories(storage_dir, resolved_workspace) if category.is_active)


def get_category_by_id(
    *,
    storage_dir: Path,
    category_id: str,
    supplier_telegram_id: int | None = None,
    workspace_key: str | None = None,
    include_inactive: bool = False,
) -> AccountingDocumentCategory | None:
    resolved_workspace = resolve_workspace_key(supplier_telegram_id=supplier_telegram_id, workspace_key=workspace_key)
    for category in _all_categories(storage_dir, resolved_workspace):
        if category.category_id == category_id and (include_inactive or category.is_active):
            return category
    return None


def allowed_categories_payload(
    *,
    storage_dir: Path,
    supplier_telegram_id: int | None = None,
    workspace_key: str | None = None,
) -> list[dict[str, Any]]:
    return [
        category.to_allowed_payload()
        for category in list_active_categories(
            storage_dir=storage_dir,
            supplier_telegram_id=supplier_telegram_id,
            workspace_key=workspace_key,
        )
    ]


def find_similar_category(
    *,
    storage_dir: Path,
    label: str,
    supplier_telegram_id: int | None = None,
    workspace_key: str | None = None,
    include_inactive: bool = True,
) -> AccountingDocumentCategory | None:
    normalized = normalize_label(label)
    if not normalized:
        return None
    resolved_workspace = resolve_workspace_key(supplier_telegram_id=supplier_telegram_id, workspace_key=workspace_key)
    for category in _all_categories(storage_dir, resolved_workspace):
        if not include_inactive and not category.is_active:
            continue
        category_label = normalize_label(category.display_label)
        if category_label == normalized:
            return category
        if normalized in category_label or category_label in normalized:
            return category
    return None


def create_workspace_category(
    *,
    storage_dir: Path,
    label: str,
    supplier_telegram_id: int | None = None,
    workspace_key: str | None = None,
    created_by: str = 'user',
    allow_similar: bool = False,
) -> AccountingDocumentCategory:
    cleaned_label = normalize_category_label(label)
    resolved_workspace = resolve_workspace_key(supplier_telegram_id=supplier_telegram_id, workspace_key=workspace_key)
    similar = find_similar_category(
        storage_dir=storage_dir,
        label=cleaned_label,
        workspace_key=resolved_workspace,
        include_inactive=True,
    )
    if similar is not None and not allow_similar:
        raise AccountingDocumentCategoryError(f'similar_category_exists:{similar.category_id}')

    existing_ids = {category.category_id for category in _all_categories(storage_dir, resolved_workspace)}
    category_id = _unique_workspace_category_id(cleaned_label, existing_ids)
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    category = AccountingDocumentCategory(
        category_id=category_id,
        label_sk=cleaned_label,
        label_user=cleaned_label,
        scope='workspace',
        workspace_key=resolved_workspace,
        supplier_telegram_id=supplier_telegram_id,
        is_active=True,
        created_by=created_by,
        created_at=now,
    )
    categories = list(_load_workspace_categories(storage_dir, resolved_workspace))
    categories.append(category)
    _write_workspace_categories(storage_dir, resolved_workspace, categories)
    return category


def set_workspace_category_active(
    *,
    storage_dir: Path,
    category_id: str,
    is_active: bool,
    supplier_telegram_id: int | None = None,
    workspace_key: str | None = None,
) -> AccountingDocumentCategory:
    resolved_workspace = resolve_workspace_key(supplier_telegram_id=supplier_telegram_id, workspace_key=workspace_key)
    categories = list(_load_workspace_categories(storage_dir, resolved_workspace))
    updated: list[AccountingDocumentCategory] = []
    selected: AccountingDocumentCategory | None = None
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    for category in categories:
        if category.category_id == category_id:
            selected = AccountingDocumentCategory(**{**asdict(category), 'is_active': is_active, 'updated_at': now})
            updated.append(selected)
        else:
            updated.append(category)
    if selected is None:
        raise AccountingDocumentCategoryError('workspace_category_not_found')
    _write_workspace_categories(storage_dir, resolved_workspace, updated)
    return selected


def normalize_category_label(label: str) -> str:
    cleaned = re.sub(r'\s+', ' ', str(label).strip())
    if not cleaned:
        raise AccountingDocumentCategoryError('category_label_required')
    if len(cleaned) > 80:
        raise AccountingDocumentCategoryError('category_label_too_long')
    if any(ord(char) < 32 for char in cleaned):
        raise AccountingDocumentCategoryError('category_label_invalid')
    return cleaned


def normalize_label(label: str) -> str:
    normalized = unicodedata.normalize('NFKD', str(label).casefold().strip())
    without_diacritics = ''.join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', without_diacritics)).strip()


def _all_categories(storage_dir: Path, workspace_key: str) -> tuple[AccountingDocumentCategory, ...]:
    return SYSTEM_CATEGORIES + _load_workspace_categories(storage_dir, workspace_key)


def _category_registry_path(storage_dir: Path, workspace_key: str) -> Path:
    return storage_dir / 'workspaces' / workspace_key / 'master_data' / 'categories' / 'categories.json'


def _load_workspace_categories(storage_dir: Path, workspace_key: str) -> tuple[AccountingDocumentCategory, ...]:
    path = _category_registry_path(storage_dir, workspace_key)
    if not path.exists():
        return ()
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, list):
        return ()
    categories: list[AccountingDocumentCategory] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            category = AccountingDocumentCategory(
                category_id=str(item['category_id']),
                label_sk=str(item.get('label_sk') or item.get('label_user') or item['category_id']),
                label_user=item.get('label_user'),
                parent_id=item.get('parent_id'),
                scope='workspace',
                workspace_key=workspace_key,
                supplier_telegram_id=item.get('supplier_telegram_id'),
                is_active=bool(item.get('is_active', True)),
                created_by=str(item.get('created_by') or 'user'),
                created_at=str(item.get('created_at') or ''),
                updated_at=item.get('updated_at'),
                description=item.get('description'),
                review_required=bool(item.get('review_required', False)),
            )
        except (KeyError, TypeError, ValueError):
            continue
        categories.append(category)
    return tuple(categories)


def _write_workspace_categories(
    storage_dir: Path,
    workspace_key: str,
    categories: list[AccountingDocumentCategory],
) -> None:
    path = _category_registry_path(storage_dir, workspace_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace_payload = [
        {
            key: value
            for key, value in asdict(category).items()
            if key not in {'scope', 'workspace_key'} and value is not None
        }
        for category in categories
        if category.scope == 'workspace'
    ]
    path.write_text(json.dumps(workspace_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')


def _unique_workspace_category_id(label: str, existing_ids: set[str]) -> str:
    base = 'workspace_' + _slug(label)
    candidate = base
    index = 2
    while candidate in existing_ids:
        candidate = f'{base}_{index}'
        index += 1
    return candidate


def _slug(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value.casefold())
    ascii_text = ''.join(char for char in normalized if not unicodedata.combining(char)).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^a-z0-9]+', '_', ascii_text).strip('_')
    return slug or 'category'
