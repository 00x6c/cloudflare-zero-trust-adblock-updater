from __future__ import annotations

from typing import Any

import httpx


class CloudflareError(RuntimeError):
    pass


class CloudflareClient:
    def __init__(self, token: str, account_id: str, dry_run: bool = False) -> None:
        self.account_id = account_id
        self.dry_run = dry_run
        self.base = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/gateway"
        self.client = httpx.Client(
            timeout=45.0,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )

    def close(self) -> None:
        self.client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if self.dry_run and method in {"POST", "PUT", "PATCH", "DELETE"}:
            return {"result": None, "success": True, "dry_run": True}
        r = self.client.request(method, f"{self.base}{path}", **kwargs)
        data = r.json()
        if r.status_code >= 400 or not data.get("success", False):
            err = data.get("errors") or [{"message": r.text[:500]}]
            msg = err[0].get("message", "Unknown Cloudflare API error")
            raise CloudflareError(f"[ERROR] Cloudflare API: {msg} (HTTP {r.status_code})")
        return data

    def list_gateway_lists(self) -> list[dict[str, Any]]:
        return self._request("GET", "/lists").get("result", [])

    def create_gateway_list(self, name: str, description: str, items: list[dict[str, str]], type_: str = "DOMAIN") -> dict[str, Any]:
        payload = {"name": name, "description": description, "type": type_, "items": items}
        return self._request("POST", "/lists", json=payload).get("result", {})

    def update_gateway_list(self, list_id: str, name: str, description: str, items: list[dict[str, str]], type_: str = "DOMAIN") -> dict[str, Any]:
        payload = {"name": name, "description": description, "type": type_, "items": items}
        return self._request("PUT", f"/lists/{list_id}", json=payload).get("result", {})

    def delete_gateway_list(self, list_id: str) -> None:
        self._request("DELETE", f"/lists/{list_id}")

    def list_gateway_rules(self) -> list[dict[str, Any]]:
        return self._request("GET", "/rules").get("result", [])

    def create_gateway_rule(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/rules", json=payload).get("result", {})

    def update_gateway_rule(self, rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/rules/{rule_id}", json=payload).get("result", {})

    def delete_gateway_rule(self, rule_id: str) -> None:
        self._request("DELETE", f"/rules/{rule_id}")
