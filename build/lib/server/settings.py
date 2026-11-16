"""服务器配置，全部来自环境变量（部署时写在 .env 里）。"""

from __future__ import annotations

import os
import secrets
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.username = os.environ.get("APP_USERNAME", "admin")
        self.password = os.environ.get("APP_PASSWORD", "")  # 未设置时无法登录
        self.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
        self.data_dir = Path(os.environ.get("DATA_DIR", "data"))
        self.public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/")
        self.retry_wait = int(os.environ.get("RETRY_WAIT", "300"))
        self.max_workers = int(os.environ.get("SCAN_WORKERS", "2"))
        self.enable_scheduler = os.environ.get("ENABLE_SCHEDULER", "1") == "1"
        self.https_only = os.environ.get("COOKIE_SECURE", "0") == "1"
        # KakaoTalk：Kakao Developers 应用的 REST API 키（必填）和 Client Secret（若启用）
        self.kakao_rest_key = os.environ.get("KAKAO_REST_API_KEY", "")
        self.kakao_client_secret = os.environ.get("KAKAO_CLIENT_SECRET", "")
        self.notify_lang = os.environ.get("NOTIFY_LANG", "zh")  # zh / ko

    @property
    def kakao_redirect_uri(self) -> str:
        return f"{self.public_url}/api/kakao/callback"

    @property
    def cache_dir(self) -> str:
        return str(self.data_dir / "cache")

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'screener.db'}"


settings = Settings()
