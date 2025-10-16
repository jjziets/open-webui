"""Utilities for updating user settings."""

from __future__ import annotations

from typing import Any, Dict, List

from open_webui.models.users import Users


_LITELLM_PROVIDER_SLUG = "cryptolabs-litellm"


def _normalize_url(url: str) -> str:
    """Normalize API base URLs to avoid duplicate entries."""
    cleaned = url.strip()
    if not cleaned:
        return cleaned
    # Remove trailing slashes for consistency
    return cleaned.rstrip("/")


def _prepare_list(values: List[str], target_index: int) -> List[str]:
    """Ensure the list is long enough to hold the target index."""
    items = list(values)
    while len(items) <= target_index:
        items.append("")
    return items


def upsert_trusted_litellm_connection(
    *, user_id: str, api_key: str, base_url: str, default_model: str
) -> None:
    """Create or update the trusted LiteLLM connection for a user."""

    api_key_clean = api_key.strip() if api_key else ""
    if not api_key_clean:
        return

    base_url_clean = _normalize_url(base_url or "")
    if not base_url_clean:
        return

    user = Users.get_user_by_id(user_id)
    if not user:
        return

    settings: Dict[str, Any] = user.settings.model_dump() if user.settings else {}
    ui_settings: Dict[str, Any] = dict(settings.get("ui") or {})

    direct_connections: Dict[str, Any] = dict(
        ui_settings.get("directConnections") or {}
    )

    base_urls: List[str] = list(direct_connections.get("OPENAI_API_BASE_URLS") or [])
    api_keys: List[str] = list(direct_connections.get("OPENAI_API_KEYS") or [])

    raw_configs = direct_connections.get("OPENAI_API_CONFIGS") or {}
    configs: Dict[str, Dict[str, Any]] = {
        str(key): dict(value) if isinstance(value, dict) else {}
        for key, value in raw_configs.items()
    }

    target_index = None
    for idx_str, config in configs.items():
        if config.get("slug") == _LITELLM_PROVIDER_SLUG:
            target_index = int(idx_str)
            break

    if target_index is None:
        for idx, existing_url in enumerate(base_urls):
            config = configs.get(str(idx)) or {}
            if config.get("slug") == _LITELLM_PROVIDER_SLUG:
                target_index = idx
                break
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
    config_entry.setdefault("connection_type", "external")
    config_entry["enable"] = True
    config_entry["slug"] = _LITELLM_PROVIDER_SLUG
    configs[str(target_index)] = config_entry

    direct_connections = {
        "OPENAI_API_BASE_URLS": base_urls,
        "OPENAI_API_KEYS": api_keys,
        "OPENAI_API_CONFIGS": configs,
    }

    ui_settings["directConnections"] = direct_connections

    models = list(ui_settings.get("models") or [])
    default_model_clean = default_model.strip() if default_model else ""
    if default_model_clean:
        if default_model_clean not in models:
            models.insert(0, default_model_clean)
        else:
            models = [default_model_clean] + [
                model for model in models if model != default_model_clean
            ]
        ui_settings["models"] = models

    settings["ui"] = ui_settings

    Users.update_user_by_id(user_id, {"settings": settings})
