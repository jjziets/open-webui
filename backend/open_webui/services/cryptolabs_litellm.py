from __future__ import annotations

from copy import deepcopy
from typing import Any

LITELLM_PROVIDER_SLUG = 'cryptolabs-litellm'


def _normalize_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return cleaned
    return cleaned.rstrip('/')


def _prepare_list(values: list[str], target_index: int) -> list[str]:
    items = list(values)
    while len(items) <= target_index:
        items.append('')
    return items


def build_litellm_connection_settings(
    *,
    settings: dict[str, Any] | None,
    api_key: str,
    base_url: str,
    default_model: str,
    key_version: int | str | None = None,
) -> dict[str, Any]:
    api_key_clean = api_key.strip() if api_key else ''
    base_url_clean = _normalize_url(base_url or '')
    if not api_key_clean or not base_url_clean:
        return deepcopy(settings or {})

    user_settings: dict[str, Any] = deepcopy(settings or {})
    ui_settings: dict[str, Any] = dict(user_settings.get('ui') or {})
    direct_connections: dict[str, Any] = dict(ui_settings.get('directConnections') or {})

    base_urls = list(direct_connections.get('OPENAI_API_BASE_URLS') or [])
    api_keys = list(direct_connections.get('OPENAI_API_KEYS') or [])
    raw_configs = direct_connections.get('OPENAI_API_CONFIGS') or {}
    configs: dict[str, dict[str, Any]] = {
        str(key): dict(value) if isinstance(value, dict) else {} for key, value in raw_configs.items()
    }

    target_index: int | None = None
    for idx_str, config in configs.items():
        if config.get('slug') == LITELLM_PROVIDER_SLUG:
            target_index = int(idx_str)
            break

    if target_index is None:
        for idx, existing_url in enumerate(base_urls):
            if _normalize_url(existing_url) == base_url_clean:
                target_index = idx
                break

    if target_index is None:
        target_index = len(base_urls)

    base_urls = _prepare_list(base_urls, target_index)
    api_keys = _prepare_list(api_keys, target_index)

    base_urls[target_index] = base_url_clean
    api_keys[target_index] = api_key_clean

    config_entry = dict(configs.get(str(target_index)) or {})
    config_entry.setdefault('connection_type', 'external')
    config_entry['enable'] = True
    config_entry['slug'] = LITELLM_PROVIDER_SLUG
    configs[str(target_index)] = config_entry

    ui_settings['directConnections'] = {
        'OPENAI_API_BASE_URLS': base_urls,
        'OPENAI_API_KEYS': api_keys,
        'OPENAI_API_CONFIGS': configs,
    }

    default_model_clean = default_model.strip() if default_model else ''
    if default_model_clean:
        models = list(ui_settings.get('models') or [])
        ui_settings['models'] = [default_model_clean] + [model for model in models if model != default_model_clean]

    user_settings['ui'] = ui_settings
    if key_version is not None:
        user_settings['cryptolabs_key_version'] = key_version

    return user_settings


async def upsert_trusted_litellm_connection(
    *,
    user_id: str,
    api_key: str,
    base_url: str,
    default_model: str,
    key_version: int | str | None = None,
    db=None,
) -> None:
    from open_webui.models.users import Users

    user = await Users.get_user_by_id(user_id, db=db)
    if not user:
        return

    current_settings = user.settings.model_dump() if hasattr(user.settings, 'model_dump') else dict(user.settings or {})
    updated_settings = build_litellm_connection_settings(
        settings=current_settings,
        api_key=api_key,
        base_url=base_url,
        default_model=default_model,
        key_version=key_version,
    )

    if updated_settings != current_settings:
        await Users.update_user_by_id(user_id, {'settings': updated_settings}, db=db)
