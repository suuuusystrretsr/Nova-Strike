import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any

from .paths import AppPaths


DEV_KEY_FILE = "developer_authorization.key"


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign_payload(payload: Any, secret: str) -> str:
    raw = canonical_json(payload).encode("utf-8")
    key = secret.encode("utf-8")
    return hmac.new(key, raw, hashlib.sha256).hexdigest()


def verify_signature(payload: Any, signature: str, secret: str) -> bool:
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, str(signature or "").strip().lower())


def extract_signed_payload(envelope: dict[str, Any], secret: str) -> tuple[bool, dict[str, Any] | None]:
    payload = envelope.get("payload")
    signature = str(envelope.get("signature", "")).strip().lower()
    if not isinstance(payload, dict) or not signature:
        return False, None
    return verify_signature(payload, signature, secret), payload


def dev_key_path(paths: AppPaths) -> Path:
    return paths.security_dir / DEV_KEY_FILE


def ensure_developer_key(paths: AppPaths) -> str:
    key_file = dev_key_path(paths)
    if key_file.exists():
        try:
            value = key_file.read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            pass
    value = secrets.token_hex(32)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(value, encoding="utf-8")
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        pass
    return value
