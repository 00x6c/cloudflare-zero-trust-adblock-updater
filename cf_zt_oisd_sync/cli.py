from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn
from rich.table import Table

from .cloudflare import CloudflareClient, CloudflareError
from .config import ConfigError, load_config
from .models import AppState
from .oisd import OISDError
from .state import StateError, delete_state, read_state
from .sync import collect_remote_managed, init_sync, is_managed_list, make_traffic_expression, plan, status_sync, update_sync

app = typer.Typer(help="cf-zt-oisd-sync — синхронизация OISD small с Cloudflare Zero Trust Gateway")
console = Console()


def _as_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False))


def _print_state_summary(state: AppState, state_file: str) -> None:
    console.print("Готово.")
    console.print(f"Списков: {len(state.chunks)}")
    console.print(f"Доменов: {state.domain_count}")
    console.print(f"State-файл: {state_file}")


def _update_available_text(info: dict) -> str:
    if info["source_check_error"]:
        return f"[red]не удалось проверить[/red] ({info['source_check_error']})"
    if info["update_available"] is None:
        return "[yellow]неизвестно[/yellow]"
    return "[yellow]доступно[/yellow]" if info["update_available"] else "[green]не требуется[/green]"


def _run_with_progress(operation):
    task_ids: dict[str, TaskID] = {}
    labels = {
        "lists": "Списки Cloudflare",
        "rule": "DNS Gateway rule",
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress_bar:

        def on_progress(kind: str, completed: int, total: int) -> None:
            if kind not in task_ids:
                task_ids[kind] = progress_bar.add_task(labels.get(kind, kind), total=max(total, 1))
            progress_bar.update(task_ids[kind], completed=completed, total=max(total, 1))

        return operation(on_progress)


@app.command("setup")
def setup_cmd() -> None:
    account = typer.prompt("Введите Cloudflare Account ID")
    token = typer.prompt("Введите Cloudflare API Token", hide_input=True)
    source = typer.prompt("Источник OISD small", default="https://small.oisd.nl")
    prefix = typer.prompt("Префикс списков", default="oisd-small-auto")
    rule_name = typer.prompt("Название правила", default="OISD Small Auto Block")
    chunk = typer.prompt("Размер части списка", default="1000")
    env = "\n".join(
        [
            f"CLOUDFLARE_ACCOUNT_ID={account}",
            f"CLOUDFLARE_API_TOKEN={token}",
            f"OISD_SOURCE_URL={source}",
            f"LIST_PREFIX={prefix}",
            f"RULE_NAME={rule_name}",
            f"CHUNK_SIZE={chunk}",
            "LIST_WORKERS=4",
            "RULE_PRECEDENCE=5000",
            "STATE_FILE=.cf-zt-oisd-state.json",
            "DRY_RUN=false",
            "LANGUAGE=en",
        ]
    )
    Path(".env").write_text(env + "\n", encoding="utf-8")
    console.print("[green][OK][/green] Файл .env создан.")
    console.print("Следующий шаг: cf-zt-oisd-sync check")


@app.command("menu")
def menu_cmd() -> None:
    """Запустить интерактивное меню с выбором действий по цифрам."""
    from .menu import start_menu

    start_menu()


@app.command("check")
def check_cmd(json_out: bool = typer.Option(False, "--json")) -> None:
    checks: list[tuple[str, bool]] = []
    checks.append((".env найден", Path(".env").exists()))

    try:
        cfg = load_config(require_cloudflare=True)
    except ConfigError as exc:
        if json_out:
            _as_json({"success": False, "command": "check", "error": str(exc), "exit_code": 2})
            raise typer.Exit(2)
        raise

    checks.append(("Cloudflare Account ID найден", bool(cfg.cloudflare_account_id)))
    checks.append(("API token найден", bool(cfg.cloudflare_api_token)))

    cf_err = None
    try:
        cf = CloudflareClient(cfg.cloudflare_api_token, cfg.cloudflare_account_id)
        try:
            cf.list_gateway_lists()
            checks.append(("Cloudflare API доступен", True))
            checks.append(("Доступ к Gateway Lists есть", True))
        finally:
            cf.close()
    except Exception as exc:  # noqa: BLE001
        cf_err = str(exc)
        checks.append(("Cloudflare API доступен", False))
        checks.append(("Доступ к Gateway Lists есть", False))

    try:
        domains, _, _ = plan(cfg)
        checks.append(("OISD small доступен", True))
        checks.append((f"Доменов после обработки: {len(domains)}", len(domains) >= 100))
    except OISDError:
        checks.append(("OISD small доступен", False))
        checks.append(("Доменов после обработки: 0", False))

    success = all(ok for _, ok in checks)
    if json_out:
        _as_json({"success": success, "command": "check", "checks": checks, "cloudflare_error": cf_err})
        raise typer.Exit(0 if success else 1)

    console.print("Проверка конфигурации")
    for text, ok in checks:
        marker = "[OK]" if ok else "[ERROR]"
        style = "green" if ok else "red"
        console.print(f"[{style}]{marker}[/{style}] {text}")


@app.command("dry-run")
def dry_run_cmd(json_out: bool = typer.Option(False, "--json")) -> None:
    cfg = load_config(require_cloudflare=True)
    cfg.dry_run = True

    domains, _, chunks = plan(cfg)
    cf = CloudflareClient(cfg.cloudflare_api_token, cfg.cloudflare_account_id, dry_run=False)
    try:
        remote_lists, remote_rules = collect_remote_managed(cfg, cf)
    finally:
        cf.close()

    plan_data = {
        "create_lists": max(len(chunks) - len(remote_lists), 0),
        "update_lists": min(len(chunks), len(remote_lists)),
        "delete_lists": max(len(remote_lists) - len(chunks), 0),
        "create_rule": 1 if not remote_rules else 0,
    }
    payload = {
        "success": True,
        "command": "dry-run",
        "source": cfg.oisd_source_url,
        "domain_count": len(domains),
        "chunk_count": len(chunks),
        "chunk_size": cfg.chunk_size,
        "plan": plan_data,
    }
    if json_out:
        _as_json(payload)
        return

    console.print("Предварительный просмотр изменений")
    console.print(f"Источник: {cfg.oisd_source_url}")
    console.print(f"Доменов после очистки: {len(domains)}")
    console.print(f"Размер части: {cfg.chunk_size}")
    console.print(f"Нужно списков Cloudflare: {len(chunks)}")
    console.print("План действий:")
    console.print(f"+ Создать списков: {plan_data['create_lists']}")
    console.print(f"~ Обновить списков: {plan_data['update_lists']}")
    console.print(f"- Удалить лишних списков: {plan_data['delete_lists']}")
    console.print(f"+ Создать DNS rule: {'да' if plan_data['create_rule'] else 'нет'}")
    console.print("Изменения НЕ будут применены.")


@app.command("init")
def init_cmd(
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    cfg = load_config(require_cloudflare=True)
    cfg.dry_run = dry_run or cfg.dry_run

    if not yes and not cfg.dry_run:
        typer.confirm("Будут созданы Cloudflare lists и DNS rule. Продолжить?", abort=True)

    if json_out:
        state = init_sync(cfg, yes=yes)
    else:
        state = _run_with_progress(lambda progress: init_sync(cfg, yes=yes, progress=progress))
    if json_out:
        _as_json({"success": True, "command": "init", "domain_count": state.domain_count, "chunk_count": len(state.chunks)})
        return
    _print_state_summary(state, cfg.state_file)


@app.command("update")
def update_cmd(
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    cfg = load_config(require_cloudflare=True)
    cfg.dry_run = dry_run or cfg.dry_run

    if not yes and not cfg.dry_run and not os.isatty(0):
        msg = "[ERROR] Требуется подтверждение, но программа запущена в неинтерактивном режиме. Добавьте --yes."
        if json_out:
            _as_json({"success": False, "command": "update", "error": msg, "exit_code": 6})
        raise typer.Exit(6)

    if json_out:
        state = update_sync(cfg)
    else:
        state = _run_with_progress(lambda progress: update_sync(cfg, progress=progress))
    if json_out:
        _as_json({"success": True, "command": "update", "domain_count": state.domain_count, "chunk_count": len(state.chunks)})
        return
    _print_state_summary(state, cfg.state_file)


@app.command("status")
def status_cmd(json_out: bool = typer.Option(False, "--json")) -> None:
    cfg = load_config(require_cloudflare=True)
    info = status_sync(cfg)
    state = info["state"]

    if json_out:
        _as_json(
            {
                "success": True,
                "command": "status",
                "domain_count": state.domain_count if state else 0,
                "chunk_count": len(state.chunks) if state else 0,
                "cloudflare_lists_found": info["managed_lists_count"],
                "rule_found": info["rule_found"],
                "rule_enabled": info["rule_enabled"],
                "state_ok": info["state_ok"],
                "update_available": info["update_available"],
                "latest_domain_count": info["latest_domain_count"],
                "source_check_error": info["source_check_error"],
                "missing_in_remote": info["missing_in_remote"],
                "extra_in_remote": info["extra_in_remote"],
            }
        )
        raise typer.Exit(0 if info["state_ok"] else 7)

    console.print("Статус cf-zt-oisd-sync")
    console.print("Конфигурация:")
    console.print(f"Источник OISD: {cfg.oisd_source_url}")
    console.print(f"Префикс списков: {cfg.list_prefix}")
    console.print(f"Название правила: {cfg.rule_name}")
    console.print(f"Размер части: {cfg.chunk_size}")

    if state:
        table = Table(title="Локальное состояние")
        table.add_column("Параметр")
        table.add_column("Значение")
        table.add_row("State-файл", "найден")
        table.add_row("Последняя синхронизация", str(state.last_sync_at))
        table.add_row("Доменов", str(state.domain_count))
        table.add_row("Списков в state", str(len(state.chunks)))
        table.add_row("Обновление списка", _update_available_text(info))
        if info["latest_domain_count"] is not None:
            table.add_row("Доменов в текущем OISD", str(info["latest_domain_count"]))
        console.print(table)
    else:
        console.print("[yellow][WARNING][/yellow] State-файл не найден")
        console.print(f"Обновление списка: {_update_available_text(info)}")

    console.print("Cloudflare:")
    console.print(f"Найдено managed lists: {info['managed_lists_count']}")
    console.print(f"DNS rule найдено: {'да' if info['rule_found'] else 'нет'}")
    console.print(f"DNS rule включено: {'да' if info['rule_enabled'] else 'нет'}")

    if info["state_ok"]:
        console.print("[green][OK][/green] Локальное состояние совпадает с Cloudflare")
    else:
        console.print("[yellow][WARNING][/yellow] Есть расхождение state и Cloudflare")
        if info["missing_in_remote"]:
            console.print(f"Отсутствуют в Cloudflare: {len(info['missing_in_remote'])}")
        if info["extra_in_remote"]:
            console.print(f"Лишние в Cloudflare: {len(info['extra_in_remote'])}")
        raise typer.Exit(7)


@app.command("delete")
def delete_cmd(yes: bool = typer.Option(False, "--yes"), json_out: bool = typer.Option(False, "--json")) -> None:
    cfg = load_config(require_cloudflare=True)
    state = read_state(cfg.state_file)
    state_list_ids = {c.cloudflare_list_id for c in state.chunks} if state else set()

    cf = CloudflareClient(cfg.cloudflare_api_token, cfg.cloudflare_account_id, dry_run=False)
    try:
        all_lists = cf.list_gateway_lists()
        all_rules = cf.list_gateway_rules()

        managed_lists = [
            x
            for x in all_lists
            if is_managed_list(x, cfg.list_prefix) or (x.get("id") in state_list_ids)
        ]
        managed_rules = [
            x
            for x in all_rules
            if (x.get("name") == cfg.rule_name and "Managed by cf-zt-oisd-sync" in str(x.get("description", "")))
            or (state and state.rule and x.get("id") == state.rule.cloudflare_rule_id)
        ]

        if not yes:
            console.print("Будут удалены:")
            console.print(f"DNS rules: {len(managed_rules)}")
            console.print(f"Cloudflare lists: {len(managed_lists)}")
            console.print("Это действие нельзя отменить.")
            val = typer.prompt("Type DELETE to confirm")
            if val != "DELETE":
                raise typer.Exit(6)

        for r in managed_rules:
            cf.delete_gateway_rule(r["id"])
        for l in managed_lists:
            cf.delete_gateway_list(l["id"])
    finally:
        cf.close()

    removed_state = delete_state(cfg.state_file)
    payload = {
        "success": True,
        "command": "delete",
        "rules_deleted": len(managed_rules),
        "lists_deleted": len(managed_lists),
        "state_deleted": removed_state,
    }
    if json_out:
        _as_json(payload)
        return

    console.print("Удаление завершено.")
    console.print(f"Удалено DNS rules: {len(managed_rules)}")
    console.print(f"Удалено Cloudflare lists: {len(managed_lists)}")
    console.print(f"State-файл удалён: {'да' if removed_state else 'нет'}")


@app.command("doctor")
def doctor_cmd(json_out: bool = typer.Option(False, "--json")) -> None:
    cfg = load_config(require_cloudflare=True)
    checks: list[tuple[str, str]] = []

    try:
        state = read_state(cfg.state_file)
    except StateError as exc:
        state = None
        checks.append(("ERROR", str(exc)))

    if state is None:
        checks.append(("WARNING", "State-файл не найден"))

    cf_err = None
    managed_lists: list[dict] = []
    managed_rules: list[dict] = []
    try:
        cf = CloudflareClient(cfg.cloudflare_api_token, cfg.cloudflare_account_id)
        try:
            managed_lists, managed_rules = collect_remote_managed(cfg, cf)
        finally:
            cf.close()
    except CloudflareError as exc:
        cf_err = str(exc)
        checks.append(("ERROR", f"Cloudflare API недоступен: {exc}"))

    if state and managed_lists:
        remote_ids = {x.get("id") for x in managed_lists}
        state_ids = {c.cloudflare_list_id for c in state.chunks}
        missing = state_ids - remote_ids
        extra = remote_ids - state_ids
        if missing:
            checks.append(("ERROR", f"Не найдены в Cloudflare списки из state: {len(missing)}"))
        else:
            checks.append(("OK", "Все списки из state найдены в Cloudflare"))
        if extra:
            checks.append(("WARNING", f"Найдены лишние managed lists: {len(extra)}"))

    if managed_rules:
        checks.append(("OK", "DNS rule найдено"))
        if not bool(managed_rules[0].get("enabled")):
            checks.append(("WARNING", "DNS rule выключено"))
        else:
            checks.append(("OK", "DNS rule включено"))
    elif cf_err is None:
        checks.append(("WARNING", "DNS rule не найдено"))

    success = not any(level == "ERROR" for level, _ in checks)

    if json_out:
        _as_json({"success": success, "command": "doctor", "checks": checks})
        raise typer.Exit(0 if success else 7)

    console.print("Диагностика")
    for level, msg in checks:
        color = {"OK": "green", "WARNING": "yellow", "ERROR": "red"}.get(level, "white")
        console.print(f"[{color}][{level}][/{color}] {msg}")

    if not success:
        console.print("Рекомендация: cf-zt-oisd-sync update --yes")
        raise typer.Exit(7)


@app.callback()
def main() -> None:
    pass
