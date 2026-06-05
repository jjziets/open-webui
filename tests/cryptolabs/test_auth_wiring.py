from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHS_PATH = REPO_ROOT / 'backend' / 'open_webui' / 'routers' / 'auths.py'
ENV_PATH = REPO_ROOT / 'backend' / 'open_webui' / 'env.py'
AUTH_UTILS_PATH = REPO_ROOT / 'backend' / 'open_webui' / 'utils' / 'auth.py'


def test_env_exposes_cryptolabs_webui_sso_and_litellm_settings():
    env = ENV_PATH.read_text()

    assert 'WEBUI_AUTH_TRUSTED_API_KEY_HEADER' in env
    assert 'WEBUI_AUTH_TRUSTED_LITELLM_URL_HEADER' in env
    assert 'WEBUI_LITELLM_DEFAULT_URL' in env
    assert 'WEBUI_LITELLM_DEFAULT_MODEL' in env
    assert 'ENABLE_SSO_SIGNUP' in env


def test_auth_router_wires_signed_login_and_per_user_litellm_provisioning():
    auths = AUTHS_PATH.read_text()

    assert "@router.get('/trusted/login')" in auths
    assert 'verify_trusted_signature(payload, sig, TRUSTED_SIGNATURE_KEY)' in auths
    assert 'decode_trusted_payload(payload)' in auths
    assert 'trusted_payload_is_fresh(data)' in auths
    assert 'upsert_trusted_litellm_connection(' in auths
    assert 'WEBUI_AUTH_TRUSTED_API_KEY_HEADER' in auths
    assert 'WEBUI_AUTH_TRUSTED_LITELLM_URL_HEADER' in auths
    signed_route = auths.split("@router.get('/trusted/login')", 1)[1].split('@router.', 1)[0]
    assert 'Auths.authenticate_user_by_email' not in signed_route
    assert 'user = await signup_handler(' in signed_route
    assert signed_route.count('Users.get_user_by_email(email, db=db)') == 1


def test_legacy_verify_signature_delegates_to_bytes_safe_helper():
    auth_utils = AUTH_UTILS_PATH.read_text()

    assert 'verify_trusted_signature(payload, signature, TRUSTED_SIGNATURE_KEY)' in auth_utils
