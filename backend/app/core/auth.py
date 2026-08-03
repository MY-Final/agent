"""轻量认证体系：PBKDF2 密码哈希 + JWT 令牌 + auth.json 持久化。

- 密码仅存 PBKDF2-HMAC-SHA256 摘要，不落明文；
- 认证状态持久化到 AUTH_FILE（默认 data/auth.json），Docker 部署时挂载命名卷；
- 首次启动自动创建 AUTH_USERNAME / AUTH_PASSWORD 默认账号，
  并标记 must_change_password=True，首次登录强制修改密码。
"""

import hashlib
import hmac
import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

from app.core.config import settings
from app.core.exceptions import AppException

PBKDF2_ITERATIONS = 200_000
JWT_ALGORITHM = "HS256"
AUTH_STORE_VERSION = 1

_lock = threading.Lock()


def _auth_file_path() -> Path:
    path = Path(settings.auth_file)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _derive_secret() -> str:
    """JWT 签名密钥：优先 AUTH_SECRET，未配置时从 AUTH_PASSWORD 稳定派生。"""

    if settings.auth_secret and settings.auth_secret.get_secret_value():
        return settings.auth_secret.get_secret_value()
    return hashlib.sha256(
        f"tender-analysis-auth:{settings.auth_password.get_secret_value()}".encode(),
    ).hexdigest()


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str, int]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return digest.hex(), salt.hex(), PBKDF2_ITERATIONS


def _verify_password(
    password: str,
    salt_hex: str,
    expected_hex: str,
    iterations: int,
) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(digest.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


def _load_store() -> dict:
    path = _auth_file_path()
    if not path.exists():
        return {"version": AUTH_STORE_VERSION, "users": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": AUTH_STORE_VERSION, "users": {}}
    if not isinstance(data, dict):
        return {"version": AUTH_STORE_VERSION, "users": {}}
    data.setdefault("users", {})
    return data


def _save_store(store: dict) -> None:
    path = _auth_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def ensure_initialized() -> None:
    """首次启动时创建默认账号；已存在则保持原样，不覆盖用户改过的密码。"""

    with _lock:
        store = _load_store()
        username = settings.auth_username.strip() or "admin"
        if username not in store["users"]:
            password_hash, salt, iterations = _hash_password(
                settings.auth_password.get_secret_value(),
            )
            store["users"][username] = {
                "salt": salt,
                "password_hash": password_hash,
                "iterations": iterations,
                "must_change_password": True,
            }
            _save_store(store)


def verify_login(username: str, password: str) -> dict | None:
    """校验账号密码，成功返回用户信息（含是否需强制改密），失败返回 None。"""

    store = _load_store()
    user = store["users"].get(username)
    if not user:
        return None
    iterations = int(user.get("iterations", PBKDF2_ITERATIONS))
    if not _verify_password(password, user["salt"], user["password_hash"], iterations):
        return None
    return {
        "username": username,
        "must_change_password": bool(user.get("must_change_password", False)),
    }


def change_password(username: str, old_password: str, new_password: str) -> None:
    """校验旧密码并更新为新密码；成功后清除强制改密标记并持久化。"""

    if len(new_password) < 6:
        raise AppException("新密码长度至少 6 位")
    with _lock:
        store = _load_store()
        user = store["users"].get(username)
        if not user:
            raise AppException("账号不存在", code=40100, status_code=401)
        iterations = int(user.get("iterations", PBKDF2_ITERATIONS))
        if not _verify_password(
            old_password,
            user["salt"],
            user["password_hash"],
            iterations,
        ):
            raise AppException("旧密码不正确")
        password_hash, salt, new_iterations = _hash_password(new_password)
        user["salt"] = salt
        user["password_hash"] = password_hash
        user["iterations"] = new_iterations
        user["must_change_password"] = False
        _save_store(store)


def create_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(hours=settings.auth_token_ttl_hours),
    }
    return jwt.encode(payload, _derive_secret(), algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> str | None:
    """校验 JWT，成功返回用户名，失败或过期返回 None。"""

    try:
        payload = jwt.decode(token, _derive_secret(), algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        return str(sub) if isinstance(sub, str) and sub else None
    except jwt.PyJWTError:
        return None
