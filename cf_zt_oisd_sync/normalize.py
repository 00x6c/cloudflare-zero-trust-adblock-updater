from __future__ import annotations

import re

import idna

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")


class NormalizeError(RuntimeError):
    pass


def _strip_noise(raw: str) -> str:
    s = raw.strip()
    if not s:
        return ""
    if s.startswith(("#", "!", "[", "]", "@@", "||")):
        s = s.lstrip("|")
    s = s.replace("$important", "")
    s = s.replace("^", "")
    s = s.split("/")[0]
    if s.startswith("0.0.0.0 ") or s.startswith("127.0.0.1 "):
        s = s.split(maxsplit=1)[1]
    s = s.removeprefix("||")
    s = s.removeprefix("*.")
    s = s.strip().strip(".").lower()
    return s


def normalize_domain_line(raw: str) -> str | None:
    s = _strip_noise(raw)
    if not s:
        return None
    if any(token in s for token in [" ", "\t", "@", "["]):
        return None

    if s.isascii():
        ascii_domain = s
    else:
        try:
            ascii_domain = idna.encode(s).decode("ascii")
        except idna.IDNAError:
            return None

    if not DOMAIN_RE.match(ascii_domain):
        return None
    return ascii_domain


def normalize_domains(lines: list[str]) -> list[str]:
    out: set[str] = set()
    for line in lines:
        val = normalize_domain_line(line)
        if val:
            out.add(val)
    return sorted(out)


def chunk_domains(domains: list[str], chunk_size: int) -> list[list[str]]:
    if chunk_size <= 0:
        raise NormalizeError("chunk_size должен быть > 0")
    return [domains[i : i + chunk_size] for i in range(0, len(domains), chunk_size)]
