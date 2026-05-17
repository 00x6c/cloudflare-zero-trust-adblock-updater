from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


@dataclass
class Config:
    cloudflare_api_token: str
    cloudflare_account_id: str
    oisd_source_url: str = "https://small.oisd.nl"
    list_prefix: str = "oisd-small-auto"
    rule_name: str = "OISD Small Auto Block"
    chunk_size: int = 1000
    list_workers: int = 4
    rule_precedence: int = 5000
    state_file: str = ".cf-zt-oisd-state.json"
    dry_run: bool = False
    language: str = "en"


def _bool_env(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def load_config(require_cloudflare: bool = True) -> Config:
    load_dotenv()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "")
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    if require_cloudflare and not token:
        raise ConfigError("[ERROR] Не задан CLOUDFLARE_API_TOKEN")
    if require_cloudflare and not account:
        raise ConfigError("[ERROR] Не задан CLOUDFLARE_ACCOUNT_ID")

    chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
    if chunk_size <= 0:
        raise ConfigError("[ERROR] CHUNK_SIZE должен быть больше 0")
    list_workers = int(os.getenv("LIST_WORKERS", "4"))
    if list_workers <= 0:
        raise ConfigError("[ERROR] LIST_WORKERS должен быть больше 0")

    return Config(
        cloudflare_api_token=token,
        cloudflare_account_id=account,
        oisd_source_url=os.getenv("OISD_SOURCE_URL", "https://small.oisd.nl"),
        list_prefix=os.getenv("LIST_PREFIX", "oisd-small-auto"),
        rule_name=os.getenv("RULE_NAME", "OISD Small Auto Block"),
        chunk_size=chunk_size,
        list_workers=list_workers,
        rule_precedence=int(os.getenv("RULE_PRECEDENCE", "5000")),
        state_file=os.getenv("STATE_FILE", ".cf-zt-oisd-state.json"),
        dry_run=_bool_env("DRY_RUN", False),
        language=os.getenv("LANGUAGE", "en"),
    )
