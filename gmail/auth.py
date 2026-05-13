import json
import os
import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

import config

TOKEN_FILE = Path(__file__).parent.parent / "token.json"
logger = logging.getLogger(__name__)


def harden_token_permissions() -> None:
    """token.json が存在する場合、所有者のみ読み書き可能にする（起動時に呼ぶ）"""
    if not TOKEN_FILE.exists():
        return
    import platform, subprocess, stat
    if platform.system() == "Windows":
        try:
            username = subprocess.check_output(
                ["whoami"], text=True, stderr=subprocess.DEVNULL
            ).strip()
            subprocess.run(
                ["icacls", str(TOKEN_FILE), "/inheritance:r",
                 "/grant:r", f"{username}:(R,W)"],
                check=True, capture_output=True,
            )
            logger.info("[auth] token.json の権限を所有者のみに設定しました")
        except Exception as e:
            logger.warning(f"[auth] token.json の権限設定失敗: {e}")
    else:
        TOKEN_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)


def get_auth_url(state: str | None = None) -> str:
    flow = _create_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url


def exchange_code(code: str) -> Credentials:
    flow = _create_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    _save_token(creds)
    return creds


def load_credentials() -> Credentials | None:
    if not TOKEN_FILE.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), config.GOOGLE_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
        except Exception as e:
            logger.error(
                f"[auth] トークンのリフレッシュに失敗しました。再認証が必要です: {e}"
            )
            return None
    return creds if creds and creds.valid else None


def _create_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uris": [config.GOOGLE_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(client_config, scopes=config.GOOGLE_SCOPES,
                                   redirect_uri=config.GOOGLE_REDIRECT_URI)


def _save_token(creds: Credentials) -> None:
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    import stat
    import platform
    if platform.system() == "Windows":
        # Windows: icacls で現在ユーザーのみアクセス可能に設定
        import subprocess
        try:
            username = subprocess.check_output(
                ["whoami"], text=True, stderr=subprocess.DEVNULL
            ).strip()
            subprocess.run(
                ["icacls", str(TOKEN_FILE), "/inheritance:r",
                 "/grant:r", f"{username}:(R,W)"],
                check=True, capture_output=True,
            )
        except Exception:
            pass  # 失敗しても動作は継続（権限設定は best-effort）
    else:
        # Unix/Mac: 所有者のみ読み書き可能
        TOKEN_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
