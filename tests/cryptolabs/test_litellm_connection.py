import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / 'backend' / 'open_webui' / 'services' / 'cryptolabs_litellm.py'
spec = importlib.util.spec_from_file_location('cryptolabs_litellm', MODULE_PATH)
cryptolabs_litellm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cryptolabs_litellm)
build_litellm_connection_settings = cryptolabs_litellm.build_litellm_connection_settings


def test_build_litellm_connection_settings_creates_default_connection():
    settings = {'ui': {'theme': 'dark'}}

    updated = build_litellm_connection_settings(
        settings=settings,
        api_key='  sk-user-key  ',
        base_url='https://api.ai.cryptolabs.co.za/v1/',
        default_model='qwen3.6-27b',
        key_version=42,
    )

    direct = updated['ui']['directConnections']

    assert updated['ui']['theme'] == 'dark'
    assert direct['OPENAI_API_BASE_URLS'] == ['https://api.ai.cryptolabs.co.za/v1']
    assert direct['OPENAI_API_KEYS'] == ['sk-user-key']
    assert direct['OPENAI_API_CONFIGS']['0']['slug'] == 'cryptolabs-litellm'
    assert direct['OPENAI_API_CONFIGS']['0']['enable'] is True
    assert updated['ui']['models'][0] == 'qwen3.6-27b'
    assert updated['cryptolabs_key_version'] == 42


def test_build_litellm_connection_settings_updates_existing_slug_without_duplicate():
    settings = {
        'ui': {
            'directConnections': {
                'OPENAI_API_BASE_URLS': ['https://old.example/v1'],
                'OPENAI_API_KEYS': ['sk-old'],
                'OPENAI_API_CONFIGS': {'0': {'slug': 'cryptolabs-litellm', 'enable': True}},
            },
            'models': ['old-model', 'qwen3.6-27b'],
        }
    }

    updated = build_litellm_connection_settings(
        settings=settings,
        api_key='sk-new',
        base_url='https://api.ai.cryptolabs.co.za/v1',
        default_model='qwen3.6-27b',
    )

    direct = updated['ui']['directConnections']

    assert direct['OPENAI_API_BASE_URLS'] == ['https://api.ai.cryptolabs.co.za/v1']
    assert direct['OPENAI_API_KEYS'] == ['sk-new']
    assert list(direct['OPENAI_API_CONFIGS'].keys()) == ['0']
    assert updated['ui']['models'] == ['qwen3.6-27b', 'old-model']


def test_build_litellm_connection_settings_ignores_missing_credentials():
    settings = {'ui': {'theme': 'dark'}}

    assert (
        build_litellm_connection_settings(
            settings=settings,
            api_key='',
            base_url='https://api.ai.cryptolabs.co.za/v1',
            default_model='qwen3.6-27b',
        )
        == settings
    )
