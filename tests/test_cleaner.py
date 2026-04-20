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
<p>Position sizing is volatility-targeted at two percent portfolio risk per trade.
We size each position so that the estimated daily dollar volatility of the trade
equals 0.5% of account equity, using a 20-day trailing standard deviation of daily
returns. This keeps total portfolio risk approximately constant as regimes shift.</p>
<p>Entry is only permitted when the VIX level is below 35. Above that level,
mean-reversion fails frequently and drawdowns compound. We also skip the first
thirty minutes of the trading day to avoid opening auction noise, though the
strategy trades end-of-day prices, so intraday timing is only used for filtering.</p>
<p>Backtests used survivorship-bias-adjusted data from CRSP. Transaction costs
modeled: 5 bps round-trip commission, 2 bps slippage. Sharpe of 1.62 in-sample,
1.31 out-of-sample 2018-2022, maximum drawdown 9.4%, annual turnover 4.2x.
The strategy loses money in strongly trending down markets (2008, 2020 Q1).</p>
<p>Failure modes: correlated crashes, VIX regime shifts, liquidity gaps, and
periods when the 200-day SMA filter yields no long signals for extended periods.
The signal also degrades in very-low-volatility regimes where bars rarely reach
the RSI(2) oversold threshold.</p>
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


def test_clean_html_rejects_thin_index_page():
    # Under MIN_CHARS — typical of a learning hub / category page.
    thin = "<html><body><article>" + ("one two three. " * 30) + "</article></body></html>"
    assert clean_html(thin) is None
