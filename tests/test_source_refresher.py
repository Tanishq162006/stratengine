"""source_refresher — pure unit tests for the parsing helpers. Network paths
are not exercised here; the full refresh loop is covered indirectly via the
crawler reuse."""
from source_refresher import _match_patterns, _parse_arxiv_listing, _parse_sitemap


def test_parse_sitemap_extracts_loc():
    xml = """
    <?xml version="1.0" encoding="UTF-8"?>
    <urlset>
      <url><loc>https://example.com/a</loc></url>
      <url><loc>https://example.com/b</loc></url>
    </urlset>
    """
    assert _parse_sitemap(xml) == ["https://example.com/a", "https://example.com/b"]


def test_match_patterns_all_when_empty():
    assert _match_patterns("https://x.com/anything", []) is True
    assert _match_patterns("https://x.com/articles/foo", ["/articles/"]) is True
    assert _match_patterns("https://x.com/blog/foo", ["/articles/"]) is False


def test_parse_arxiv_listing():
    html = '<a href="/abs/2401.12345">paper 1</a><a href="/abs/2401.67890">p2</a>'
    urls = _parse_arxiv_listing(html)
    assert "https://arxiv.org/abs/2401.12345" in urls
    assert "https://arxiv.org/abs/2401.67890" in urls
