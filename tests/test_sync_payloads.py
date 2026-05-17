from cf_zt_oisd_sync.config import Config
from cf_zt_oisd_sync.models import AppState
from cf_zt_oisd_sync.sync import (
    build_rule_payload,
    is_managed_list,
    is_managed_rule,
    make_traffic_expression,
    source_update_available,
)


def test_traffic_expression() -> None:
    expr = make_traffic_expression(["L1", "L2"])
    assert "in $L1" in expr and "in $L2" in expr


def test_rule_payload() -> None:
    cfg = Config(cloudflare_api_token="t", cloudflare_account_id="a")
    payload = build_rule_payload(cfg, ["L1"])
    assert payload["action"] == "block"
    assert payload["filters"] == ["dns"]


def test_managed_list_filter() -> None:
    obj = {
        "name": "oisd-small-auto-001",
        "description": "Managed by cf-zt-oisd-sync. Source: OISD small.",
    }
    assert is_managed_list(obj, "oisd-small-auto")


def test_managed_rule_filter() -> None:
    obj = {
        "name": "OISD Small Auto Block",
        "description": "Blocks domains from OISD small. Managed by cf-zt-oisd-sync.",
    }
    assert is_managed_rule(obj, "OISD Small Auto Block")


def test_source_update_available() -> None:
    assert source_update_available(None, "new") is None
    assert source_update_available(AppState(source_hash="same"), None) is None
    assert source_update_available(AppState(source_hash="same"), "same") is False
    assert source_update_available(AppState(source_hash="old"), "new") is True
    assert source_update_available(AppState(source_hash=None), "new") is True
