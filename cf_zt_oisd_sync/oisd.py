from __future__ import annotations

import hashlib

import httpx

from .normalize import normalize_domains


class OISDError(RuntimeError):
    pass


def fetch_oisd_raw(url: str, timeout: float = 30.0) -> str:
    try:
        r = httpx.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        raise OISDError(f"[ERROR] Не удалось скачать OISD: {exc}") from exc

    if r.status_code != 200:
        raise OISDError(f"[ERROR] OISD вернул HTTP {r.status_code}")

    body = r.text.strip()
    if not body:
        raise OISDError("[ERROR] OISD вернул пустой список")
    return body


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_raw(raw: str) -> tuple[list[str], str]:
    lines = raw.splitlines()
    domains = normalize_domains(lines)
    if len(domains) < 1:
        raise OISDError("[ERROR] После обработки не осталось доменов")
    digest = hashlib.sha256("\n".join(domains).encode("utf-8")).hexdigest()
    return domains, digest


def load_and_normalize(url: str) -> tuple[list[str], str]:
    raw = fetch_oisd_raw(url)
    return normalize_raw(raw)
