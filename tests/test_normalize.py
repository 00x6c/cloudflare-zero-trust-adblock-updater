from cf_zt_oisd_sync.normalize import chunk_domains, normalize_domain_line, normalize_domains
from cf_zt_oisd_sync.oisd import hash_text, normalize_raw


def test_parse_plain_domain() -> None:
    assert normalize_domain_line("example.com") == "example.com"


def test_parse_hosts_format() -> None:
    assert normalize_domain_line("0.0.0.0 ads.example.com") == "ads.example.com"


def test_parse_adblock_style() -> None:
    assert normalize_domain_line("||tracker.example.net^") == "tracker.example.net"


def test_ignore_comments() -> None:
    assert normalize_domain_line("# comment") is None


def test_remove_wildcard_prefix() -> None:
    assert normalize_domain_line("*.sub.example.org") == "sub.example.org"


def test_punycode() -> None:
    assert normalize_domain_line("пример.рф") == "xn--e1afmkfd.xn--p1ai"


def test_dedup_and_sort() -> None:
    out = normalize_domains(["b.com", "a.com", "a.com"])
    assert out == ["a.com", "b.com"]


def test_chunking() -> None:
    chunks = chunk_domains([str(i) + ".com" for i in range(2500)], 1000)
    assert [len(c) for c in chunks] == [1000, 1000, 500]


def test_normalize_raw_returns_digest() -> None:
    domains, digest = normalize_raw("b.com\na.com\na.com")
    assert domains == ["a.com", "b.com"]
    assert digest == hash_text("a.com\nb.com")
