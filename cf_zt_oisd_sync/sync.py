from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Callable

from .cloudflare import CloudflareClient
from .config import Config
from .models import AppState, ChunkState, RuleState
from .normalize import chunk_domains
from .oisd import OISDError, fetch_oisd_raw, hash_text, load_and_normalize, normalize_raw
from .state import read_state, write_state

MANAGED_MARKER = "Managed by cf-zt-oisd-sync"
ProgressCallback = Callable[[str, int, int], None]


def list_name(prefix: str, idx: int) -> str:
    return f"{prefix}-{idx:03d}"


def list_index(name: str, prefix: str) -> int | None:
    marker = f"{prefix}-"
    if not name.startswith(marker):
        return None
    suffix = name.removeprefix(marker)
    if not suffix.isdigit():
        return None
    return int(suffix)


def chunk_hash(items: list[str]) -> str:
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def make_traffic_expression(list_ids: list[str]) -> str:
    return " or ".join([f"any(dns.domains[*] in ${lid})" for lid in list_ids])


def is_managed_list(obj: dict, prefix: str) -> bool:
    name = str(obj.get("name", ""))
    desc = str(obj.get("description", ""))
    return name.startswith(prefix) and MANAGED_MARKER in desc


def is_managed_rule(obj: dict, rule_name: str) -> bool:
    name = str(obj.get("name", ""))
    desc = str(obj.get("description", ""))
    return name == rule_name and MANAGED_MARKER in desc


def plan(config: Config) -> tuple[list[str], str, list[list[str]]]:
    domains, source_hash = load_and_normalize(config.oisd_source_url)
    return domains, source_hash, chunk_domains(domains, config.chunk_size)


def plan_from_raw(config: Config, raw: str) -> tuple[list[str], str, str, list[list[str]]]:
    domains, source_hash = normalize_raw(raw)
    return domains, source_hash, hash_text(raw), chunk_domains(domains, config.chunk_size)


def fetch_plan(config: Config) -> tuple[list[str], str, str, list[list[str]]]:
    return plan_from_raw(config, fetch_oisd_raw(config.oisd_source_url))


def build_rule_payload(config: Config, list_ids: list[str]) -> dict:
    return {
        "name": config.rule_name,
        "description": "Blocks domains from OISD small. Managed by cf-zt-oisd-sync.",
        "precedence": config.rule_precedence,
        "enabled": True,
        "action": "block",
        "filters": ["dns"],
        "traffic": make_traffic_expression(list_ids),
    }


def collect_remote_managed(config: Config, cf: CloudflareClient) -> tuple[list[dict], list[dict]]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        lists_future = executor.submit(cf.list_gateway_lists)
        rules_future = executor.submit(cf.list_gateway_rules)
        lists = lists_future.result()
        rules = rules_future.result()
    managed_lists = [x for x in lists if is_managed_list(x, config.list_prefix)]
    managed_rules = [x for x in rules if is_managed_rule(x, config.rule_name)]
    return managed_lists, managed_rules


def state_from_remote(config: Config, managed_lists: list[dict], managed_rules: list[dict]) -> AppState:
    chunks: list[ChunkState] = []
    for item in sorted(managed_lists, key=lambda x: list_index(str(x.get("name", "")), config.list_prefix) or 0):
        idx = list_index(str(item.get("name", "")), config.list_prefix)
        if idx is None:
            continue
        chunks.append(
            ChunkState(
                index=idx,
                name=str(item.get("name", list_name(config.list_prefix, idx))),
                cloudflare_list_id=str(item.get("id", "")),
                item_count=0,
                chunk_hash="",
            )
        )

    rule = None
    if managed_rules:
        rule = RuleState(
            name=config.rule_name,
            cloudflare_rule_id=str(managed_rules[0].get("id", "")),
            precedence=int(managed_rules[0].get("precedence") or config.rule_precedence),
        )

    return AppState(
        list_prefix=config.list_prefix,
        rule_name=config.rule_name,
        source_url=config.oisd_source_url,
        chunk_size=config.chunk_size,
        chunks=chunks,
        rule=rule,
    )


def source_update_available(state: AppState | None, latest_source_hash: str | None) -> bool | None:
    if not state or latest_source_hash is None:
        return None
    if not state.source_hash:
        return True
    return state.source_hash != latest_source_hash


def init_sync(config: Config, yes: bool = False, progress: ProgressCallback | None = None) -> AppState:
    domains, source_hash, raw_source_hash, chunks = fetch_plan(config)
    cf = CloudflareClient(config.cloudflare_api_token, config.cloudflare_account_id, dry_run=config.dry_run)
    try:
        # Avoid silent duplicates on repeated init.
        remote_lists, remote_rules = collect_remote_managed(config, cf)
        if (remote_lists or remote_rules) and not config.dry_run:
            raise RuntimeError(
                "[WARNING] Похоже, программа уже была инициализирована. Используйте update/status/delete вместо повторного init."
            )

        new_state = AppState(
            list_prefix=config.list_prefix,
            rule_name=config.rule_name,
            source_url=config.oisd_source_url,
            chunk_size=config.chunk_size,
            source_hash=source_hash,
            raw_source_hash=raw_source_hash,
            domain_count=len(domains),
        )
        created_chunks: list[ChunkState] = []
        created_by_index: dict[int, ChunkState] = {}
        total = len(chunks)
        with ThreadPoolExecutor(max_workers=config.list_workers) as executor:
            futures = {}
            for i, chunk in enumerate(chunks, start=1):
                name = list_name(config.list_prefix, i)
                desc = f"{MANAGED_MARKER}. Source: OISD small. Chunk {i:03d}/{total:03d}. Do not edit manually."
                payload_items = [{"value": d} for d in chunk]
                futures[
                    executor.submit(cf.create_gateway_list, name=name, description=desc, items=payload_items)
                ] = (i, name, chunk)

            completed = 0
            if progress:
                progress("lists", completed, total)
            for future in as_completed(futures):
                i, name, chunk = futures[future]
                resp = future.result()
                lid = resp.get("id", f"dry-run-{i}")
                created_by_index[i] = ChunkState(
                    index=i,
                    name=name,
                    cloudflare_list_id=lid,
                    item_count=len(chunk),
                    chunk_hash=chunk_hash(chunk),
                )
                completed += 1
                if progress:
                    progress("lists", completed, total)

        created_chunks = [created_by_index[i] for i in sorted(created_by_index)]
        list_ids = [chunk.cloudflare_list_id for chunk in created_chunks]

        if progress:
            progress("rule", 0, 1)
        rule_resp = cf.create_gateway_rule(build_rule_payload(config, list_ids))
        if progress:
            progress("rule", 1, 1)
        rid = rule_resp.get("id", "dry-run-rule")
        new_state.rule = RuleState(name=config.rule_name, cloudflare_rule_id=rid, precedence=config.rule_precedence)
        new_state.chunks = created_chunks
        new_state.last_sync_at = AppState.now_utc_iso()
        if not config.dry_run:
            write_state(config.state_file, new_state)
        return new_state
    finally:
        cf.close()


def status_sync(config: Config) -> dict:
    state = read_state(config.state_file)
    latest_source_hash = None
    latest_domain_count = None
    source_check_error = None
    try:
        raw = fetch_oisd_raw(config.oisd_source_url)
        raw_source_hash = hash_text(raw)
        if state and state.raw_source_hash and state.raw_source_hash == raw_source_hash:
            latest_source_hash = state.source_hash
            latest_domain_count = state.domain_count
        else:
            domains, latest_source_hash, _, _ = plan_from_raw(config, raw)
            latest_domain_count = len(domains)
    except OISDError as exc:
        source_check_error = str(exc)

    cf = CloudflareClient(config.cloudflare_api_token, config.cloudflare_account_id, dry_run=False)
    try:
        managed_lists, managed_rules = collect_remote_managed(config, cf)
    finally:
        cf.close()

    remote_list_ids = {x.get("id") for x in managed_lists}
    state_list_ids = {c.cloudflare_list_id for c in state.chunks} if state else set()

    missing_in_remote = sorted([x for x in state_list_ids if x and x not in remote_list_ids])
    extra_in_remote = sorted([x for x in remote_list_ids if x and x not in state_list_ids]) if state else sorted(remote_list_ids)

    return {
        "state": state,
        "managed_lists": managed_lists,
        "managed_lists_count": len(managed_lists),
        "managed_rules": managed_rules,
        "rule_found": len(managed_rules) > 0,
        "rule_enabled": bool(managed_rules[0].get("enabled")) if managed_rules else False,
        "state_ok": bool(state)
        and len(missing_in_remote) == 0
        and len(extra_in_remote) == 0
        and (state.rule is None or any(r.get("id") == state.rule.cloudflare_rule_id for r in managed_rules)),
        "missing_in_remote": missing_in_remote,
        "extra_in_remote": extra_in_remote,
        "update_available": source_update_available(state, latest_source_hash),
        "latest_source_hash": latest_source_hash,
        "latest_domain_count": latest_domain_count,
        "source_check_error": source_check_error,
    }


def update_sync(config: Config, progress: ProgressCallback | None = None) -> AppState:
    current = read_state(config.state_file)
    if not current:
        cf = CloudflareClient(config.cloudflare_api_token, config.cloudflare_account_id, dry_run=config.dry_run)
        try:
            remote_lists, remote_rules = collect_remote_managed(config, cf)
        finally:
            cf.close()
        if not remote_lists and not remote_rules:
            return init_sync(config, progress=progress)
        current = state_from_remote(config, remote_lists, remote_rules)
    raw = fetch_oisd_raw(config.oisd_source_url)
    raw_source_hash = hash_text(raw)
    if current.raw_source_hash and current.raw_source_hash == raw_source_hash:
        return current

    domains, source_hash, _, chunks = plan_from_raw(config, raw)
    if current.source_hash == source_hash:
        current.raw_source_hash = raw_source_hash
        if not config.dry_run:
            write_state(config.state_file, current)
        return current

    cf = CloudflareClient(config.cloudflare_api_token, config.cloudflare_account_id, dry_run=config.dry_run)
    try:
        current_by_index = {chunk.index: chunk for chunk in current.chunks}
        prepared_chunks: list[tuple[int, str, list[str], str, ChunkState | None, str]] = []
        for i, chunk in enumerate(chunks, start=1):
            name = list_name(config.list_prefix, i)
            chash = chunk_hash(chunk)
            prev = current_by_index.get(i)
            desc = f"{MANAGED_MARKER}. Source: OISD small. Chunk {i:03d}/{len(chunks):03d}. Do not edit manually."
            prepared_chunks.append((i, name, chunk, chash, prev, desc))

        extras = [c for c in current.chunks if c.index > len(chunks)]
        list_results: dict[int, str] = {}
        list_futures = {}
        total_list_ops = sum(
            1 for _, _, _, chash, prev, _ in prepared_chunks if prev is None or prev.chunk_hash != chash
        ) + len(extras)
        done_list_ops = 0
        if progress:
            progress("lists", done_list_ops, total_list_ops)

        # Stage 1: Create and update active lists
        with ThreadPoolExecutor(max_workers=config.list_workers) as executor:
            for i, name, chunk, chash, prev, desc in prepared_chunks:
                if prev is None:
                    items = [{"value": d} for d in chunk]
                    future = executor.submit(cf.create_gateway_list, name=name, description=desc, items=items)
                    list_futures[future] = ("create", i, None)
                elif prev.chunk_hash != chash:
                    items = [{"value": d} for d in chunk]
                    future = executor.submit(
                        cf.update_gateway_list,
                        prev.cloudflare_list_id,
                        name=name,
                        description=desc,
                        items=items,
                    )
                    list_futures[future] = ("update", i, prev.cloudflare_list_id)
                else:
                    list_results[i] = prev.cloudflare_list_id

            if list_futures:
                for future in as_completed(list_futures):
                    operation, index, existing_id = list_futures[future]
                    result = future.result()
                    if operation == "create":
                        list_results[index] = result.get("id", f"dry-run-{index}")
                    elif operation == "update":
                        list_results[index] = str(existing_id)
                    done_list_ops += 1
                    if progress:
                        progress("lists", done_list_ops, total_list_ops)

        new_chunks: list[ChunkState] = []
        list_ids: list[str] = []
        for i, name, chunk, chash, prev, _ in prepared_chunks:
            lid = list_results.get(i) or (prev.cloudflare_list_id if prev else f"dry-run-{i}")
            new_chunks.append(
                ChunkState(index=i, name=name, cloudflare_list_id=lid, item_count=len(chunk), chunk_hash=chash)
            )
            list_ids.append(lid)

        # Stage 2: Update the Gateway Rule to use only active list IDs (removing references to extra lists)
        if progress:
            progress("rule", 0, 1)
        previous_list_ids = [chunk.cloudflare_list_id for chunk in sorted(current.chunks, key=lambda chunk: chunk.index)]
        rule_needs_update = previous_list_ids != list_ids or (
            current.rule is not None and current.rule.precedence != config.rule_precedence
        )
        if current.rule and rule_needs_update:
            cf.update_gateway_rule(current.rule.cloudflare_rule_id, build_rule_payload(config, list_ids))
            rule = RuleState(
                name=current.rule.name,
                cloudflare_rule_id=current.rule.cloudflare_rule_id,
                precedence=config.rule_precedence,
            )
        elif current.rule:
            rule = current.rule
        else:
            rule_resp = cf.create_gateway_rule(build_rule_payload(config, list_ids))
            rid = rule_resp.get("id", "dry-run-rule")
            rule = RuleState(name=config.rule_name, cloudflare_rule_id=rid, precedence=config.rule_precedence)
        if progress:
            progress("rule", 1, 1)

        # Stage 3: Delete extra lists (safe to delete now because the Gateway Rule no longer references them)
        if extras:
            delete_futures = {}
            with ThreadPoolExecutor(max_workers=config.list_workers) as executor:
                for extra in extras:
                    future = executor.submit(cf.delete_gateway_list, extra.cloudflare_list_id)
                    delete_futures[future] = extra.cloudflare_list_id

                for future in as_completed(delete_futures):
                    future.result()
                    done_list_ops += 1
                    if progress:
                        progress("lists", done_list_ops, total_list_ops)

        new_state = replace(current)
        new_state.source_hash = source_hash
        new_state.raw_source_hash = raw_source_hash
        new_state.domain_count = len(domains)
        new_state.chunk_size = config.chunk_size
        new_state.chunks = new_chunks
        new_state.rule = rule
        new_state.last_sync_at = AppState.now_utc_iso()
        if not config.dry_run:
            write_state(config.state_file, new_state)
        return new_state
    finally:
        cf.close()
