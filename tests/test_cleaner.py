from cleaner import clean_html


SAMPLE_HTML = """<!doctype html>
<html><head><title>Mean Reversion on SPY</title></head>
<body>
<nav>site nav goes here</nav>
<article>
<h1>Mean Reversion on SPY</h1>
<p>This article describes a simple RSI(2) mean-reversion strategy on SPY. The rule is:
buy when RSI(2) is below 10 and close is above the 200-day simple moving average.
Exit when RSI(2) rises above 70. Stop loss three ATR below entry. Backtest from
2010 to 2020 produced a Sharpe ratio above 1.5 before costs, lower after realistic
transaction costs of five basis points round-trip. This works best in mean-reverting
regimes; underperforms in strong downtrends.</p>
<p>Position sizing is volatility-targeted at two percent portfolio risk per trade.</p>
</article>
<footer>copyright</footer>
</body></html>"""


def test_clean_html_extracts_article_body():
    text = clean_html(SAMPLE_HTML, url="https://example.com/x")
    assert text is not None
    assert "RSI(2)" in text
    assert "site nav" not in text
    assert "copyright" not in text


def test_clean_html_rejects_tiny_input():
    assert clean_html("<html><body>hi</body></html>") is None
