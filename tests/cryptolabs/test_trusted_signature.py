import base64
import hashlib
import hmac
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / 'backend' / 'open_webui' / 'services' / 'cryptolabs_sso.py'
spec = importlib.util.spec_from_file_location('cryptolabs_sso', MODULE_PATH)
cryptolabs_sso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cryptolabs_sso)


def test_verify_signature_accepts_wordpress_base64_hmac_for_string_secret():
    payload = base64.b64encode(b'{"email":"user@example.com"}').decode()
    secret = 'shared-wordpress-secret'
    signature = base64.b64encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()).decode()

    assert cryptolabs_sso.verify_trusted_signature(payload, signature, secret) is True


def test_verify_signature_rejects_bad_signature():
    assert cryptolabs_sso.verify_trusted_signature('payload', 'not-valid', 'shared-wordpress-secret') is False


def test_decode_trusted_payload_accepts_wordpress_base64_json():
    payload = base64.b64encode(b'{"email":"user@example.com","apiKey":"sk-user","keyVersion":7}').decode()

    decoded = cryptolabs_sso.decode_trusted_payload(payload)

    assert decoded['email'] == 'user@example.com'
    assert decoded['apiKey'] == 'sk-user'
    assert decoded['keyVersion'] == 7
