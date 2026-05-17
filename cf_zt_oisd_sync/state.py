from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import AppState, ChunkState, RuleState


class StateError(RuntimeError):
    pass


def read_state(path: str) -> AppState | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateError("[ERROR] State-файл повреждён или не является корректным JSON") from exc

    chunks = [ChunkState(**c) for c in data.get("chunks", [])]
    rule_raw = data.get("rule")
    rule = RuleState(**rule_raw) if rule_raw else None
    return AppState(
        managed_by=data.get("managed_by", "cf-zt-oisd-sync"),
        list_prefix=data.get("list_prefix", "oisd-small-auto"),
        rule_name=data.get("rule_name", "OISD Small Auto Block"),
        source_url=data.get("source_url", "https://small.oisd.nl"),
        chunk_size=int(data.get("chunk_size", 1000)),
        last_sync_at=data.get("last_sync_at"),
        source_hash=data.get("source_hash"),
        raw_source_hash=data.get("raw_source_hash"),
        domain_count=int(data.get("domain_count", 0)),
        chunks=chunks,
        rule=rule,
    )


def write_state(path: str, state: AppState) -> None:
    p = Path(path)
    p.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")


def delete_state(path: str) -> bool:
    p = Path(path)
    if not p.exists():
        return False
    p.unlink()
    return True
