# 101 Formulaic Alphas — BRAIN Fast-Expression Syntax

Direct-paste-able versions of the Kakushadze 101 alphas already translated
into BRAIN's Fast Expression language. Original syntax (`stddev`,
`correlation`, `decay_linear`, `IndNeutralize`, `delta`, `delay`) replaced
with BRAIN equivalents (`ts_std_dev`, `ts_corr`, `ts_decay_linear`,
`group_neutralize`, `ts_delta`, `ts_delay`).

Source: jglazar/notes/quant_interview/alpha_ideas.md cross-checked with
github.com/RussellDash332/WQ-Brain/blob/main/commands.py (the
`from_arxiv()` generator). Both adapted from arXiv 1601.00991 and the
public 101alpha translation tables.

**Use these directly** as seed candidates in the synth/refine prompts.
Where the expression returns a 0/1 boolean, wrap with
`scale(group_neutralize(zscore(<expr>), subindustry))` before submission.

---

001. `(rank(ts_arg_max(signed_power(((returns < 0) ? ts_std_dev(returns, 20) : close), 2.), 5)) - 0.5)`
002. `(-1 * ts_corr(rank(ts_delta(log(volume), 2)), rank(((close - open) / open)), 6))`
003. `(-1 * ts_corr(rank(open), rank(volume), 10))`
004. `(-1 * ts_rank(rank(low), 9))`
005. `(rank((open - (ts_sum(vwap, 10) / 10))) * (-1 * abs(rank((close - vwap)))))`
006. `(-1 * ts_corr(open, volume, 10))`
007. `((ts_mean(volume,20) < volume) ? ((-1 * ts_rank(abs(ts_delta(close, 7)), 60)) * sign(ts_delta(close, 7))) : (-1 * 1))`
008. `(-1 * rank(((ts_sum(open, 5) * ts_sum(returns, 5)) - ts_delay((ts_sum(open, 5) * ts_sum(returns, 5)), 10))))`
009. `((0 < ts_min(ts_delta(close, 1), 5)) ? ts_delta(close, 1) : ((ts_max(ts_delta(close, 1), 5) < 0) ? ts_delta(close, 1) : (-1 * ts_delta(close, 1))))`
010. `rank(((0 < ts_min(ts_delta(close, 1), 4)) ? ts_delta(close, 1) : ((ts_max(ts_delta(close, 1), 4) < 0) ? ts_delta(close, 1) : (-1 * ts_delta(close, 1)))))`
011. `((rank(ts_max((vwap - close), 3)) + rank(ts_min((vwap - close), 3))) * rank(ts_delta(volume, 3)))`
012. `(sign(ts_delta(volume, 1)) * (-1 * ts_delta(close, 1)))`
013. `(-1 * rank(ts_covariance(rank(close), rank(volume), 5)))`
014. `((-1 * rank(ts_delta(returns, 3))) * ts_corr(open, volume, 10))`
015. `(-1 * ts_sum(rank(ts_corr(rank(high), rank(volume), 3)), 3))`
016. `(-1 * rank(ts_covariance(rank(high), rank(volume), 5)))`
017. `(((-1 * rank(ts_rank(close, 10))) * rank(ts_delta(ts_delta(close, 1), 1))) * rank(ts_rank((volume / ts_mean(volume,20)), 5)))`
018. `(-1 * rank(((ts_std_dev(abs((close - open)), 5) + (close - open)) + ts_corr(close, open, 10))))`
019. `((-1 * sign(((close - ts_delay(close, 7)) + ts_delta(close, 7)))) * (1 + rank((1 + ts_sum(returns, 250)))))`
020. `(((-1 * rank((open - ts_delay(high, 1)))) * rank((open - ts_delay(close, 1)))) * rank((open - ts_delay(low, 1))))`
021. `((((ts_sum(close, 8) / 8) + ts_std_dev(close, 8)) < (ts_sum(close, 2) / 2)) ? (-1 * 1) : (((ts_sum(close, 2) / 2) < ((ts_sum(close, 8) / 8) - ts_std_dev(close, 8))) ? 1 : (((1 < (volume / ts_mean(volume,20))) || ((volume / ts_mean(volume,20)) == 1)) ? 1 : (-1 * 1))))`
022. `(-1 * (ts_delta(ts_corr(high, volume, 5), 5) * rank(ts_std_dev(close, 20))))`
023. `(((ts_sum(high, 20) / 20) < high) ? (-1 * ts_delta(high, 2)) : 0)`
024. `((((ts_delta((ts_sum(close, 100) / 100), 100) / ts_delay(close, 100)) < 0.05) || ((ts_delta((ts_sum(close, 100) / 100), 100) / ts_delay(close, 100)) == 0.05)) ? (-1 * (close - ts_min(close, 100))) : (-1 * ts_delta(close, 3)))`
025. `rank(((((-1 * returns) * ts_mean(volume,20)) * vwap) * (high - close)))`
026. `(-1 * ts_max(ts_corr(ts_rank(volume, 5), ts_rank(high, 5), 5), 3))`
027. `((0.5 < rank((ts_sum(ts_corr(rank(volume), rank(vwap), 6), 2) / 2.0))) ? (-1 * 1) : 1)`
028. `scale(((ts_corr(ts_mean(volume,20), low, 5) + ((high + low) / 2)) - close))`
029. `(min(ts_product(rank(rank(scale(log(ts_sum(ts_min(rank(rank((-1 * rank(ts_delta((close - 1), 5))))), 2), 1))))), 1), 5) + ts_rank(ts_delay((-1 * returns), 6), 5))`
030. `(((1.0 - rank(((sign((close - ts_delay(close, 1))) + sign((ts_delay(close, 1) - ts_delay(close, 2)))) + sign((ts_delay(close, 2) - ts_delay(close, 3)))))) * ts_sum(volume, 5)) / ts_sum(volume, 20))`
031. `((rank(rank(rank(ts_decay_linear((-1 * rank(rank(ts_delta(close, 10)))), 10)))) + rank((-1 * ts_delta(close, 3)))) + sign(scale(ts_corr(ts_mean(volume,20), low, 12))))`
032. `(scale(((ts_sum(close, 7) / 7) - close)) + (20 * scale(ts_corr(vwap, ts_delay(close, 5), 230))))`
033. `rank((-1 * ((1 - (open / close))^1)))`
034. `rank(((1 - rank((ts_std_dev(returns, 2) / ts_std_dev(returns, 5)))) + (1 - rank(ts_delta(close, 1)))))`
035. `((ts_rank(volume, 32) * (1 - ts_rank(((close + high) - low), 16))) * (1 - ts_rank(returns, 32)))`
036. `(((((2.21 * rank(ts_corr((close - open), ts_delay(volume, 1), 15))) + (0.7 * rank((open - close)))) + (0.73 * rank(ts_rank(ts_delay((-1 * returns), 6), 5)))) + rank(abs(ts_corr(vwap, ts_mean(volume,20), 6)))) + (0.6 * rank((((ts_sum(close, 200) / 200) - open) * (close - open)))))`
037. `(rank(ts_corr(ts_delay((open - close), 1), close, 200)) + rank((open - close)))`
038. `((-1 * rank(ts_rank(close, 10))) * rank((close / open)))`
039. `((-1 * rank((ts_delta(close, 7) * (1 - rank(ts_decay_linear((volume / ts_mean(volume,20)), 9)))))) * (1 + rank(ts_sum(returns, 250))))`
040. `((-1 * rank(ts_std_dev(high, 10))) * ts_corr(high, volume, 10))`
041. `(((high * low)^0.5) - vwap)`
042. `(rank((vwap - close)) / rank((vwap + close)))`
043. `(ts_rank((volume / ts_mean(volume,20)), 20) * ts_rank((-1 * ts_delta(close, 7)), 8))`
044. `(-1 * ts_corr(high, rank(volume), 5))`
045. `(-1 * ((rank((ts_sum(ts_delay(close, 5), 20) / 20)) * ts_corr(close, volume, 2)) * rank(ts_corr(ts_sum(close, 5), ts_sum(close, 20), 2))))`
046. `((0.25 < (((ts_delay(close, 20) - ts_delay(close, 10)) / 10) - ((ts_delay(close, 10) - close) / 10))) ? (-1 * 1) : (((((ts_delay(close, 20) - ts_delay(close, 10)) / 10) - ((ts_delay(close, 10) - close) / 10)) < 0) ? 1 : ((-1 * 1) * (close - ts_delay(close, 1)))))`
047. `((((rank((1 / close)) * volume) / ts_mean(volume,20)) * ((high * rank((high - close))) / (ts_sum(high, 5) / 5))) - rank((vwap - ts_delay(vwap, 5))))`
048. `(group_neutralize(((ts_corr(ts_delta(close, 1), ts_delta(ts_delay(close, 1), 1), 250) * ts_delta(close, 1)) / close), subindustry) / ts_sum(((ts_delta(close, 1) / ts_delay(close, 1))^2), 250))`
049. `(((((ts_delay(close, 20) - ts_delay(close, 10)) / 10) - ((ts_delay(close, 10) - close) / 10)) < (-1 * 0.1)) ? 1 : ((-1 * 1) * (close - ts_delay(close, 1))))`
050. `(-1 * ts_max(rank(ts_corr(rank(volume), rank(vwap), 5)), 5))`
051. `(((((ts_delay(close, 20) - ts_delay(close, 10)) / 10) - ((ts_delay(close, 10) - close) / 10)) < (-1 * 0.05)) ? 1 : ((-1 * 1) * (close - ts_delay(close, 1))))`
052. `((((-1 * ts_min(low, 5)) + ts_delay(ts_min(low, 5), 5)) * rank(((ts_sum(returns, 240) - ts_sum(returns, 20)) / 220))) * ts_rank(volume, 5))`
053. `(-1 * ts_delta((((close - low) - (high - close)) / (close - low)), 9))`
054. `((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))`
055. `(-1 * ts_corr(rank(((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low, 12)))), rank(volume), 6))`
056. `(0 - (1 * (rank((ts_sum(returns, 10) / ts_sum(ts_sum(returns, 2), 3))) * rank((returns * cap)))))`
057. `(0 - (1 * ((close - vwap) / ts_decay_linear(rank(ts_arg_max(close, 30)), 2))))`
058. `(-1 * ts_rank(ts_decay_linear(ts_corr(group_neutralize(vwap, sector), volume, 4), 8), 6))`
059. `(-1 * ts_rank(ts_decay_linear(ts_corr(group_neutralize(((vwap * 0.728317) + (vwap * (1 - 0.728317))), industry), volume, 4), 16), 8))`
060. `(0 - (1 * ((2 * scale(rank(((((close - low) - (high - close)) / (high - low)) * volume)))) - scale(rank(ts_arg_max(close, 10))))))`
061. `(rank((vwap - ts_min(vwap, 16))) < rank(ts_corr(vwap, ts_mean(volume,180), 17)))`
062. `((rank(ts_corr(vwap, ts_sum(ts_mean(volume,20), 22), 10)) < rank(((rank(open) + rank(open)) < (rank(((high + low) / 2)) + rank(high))))) * -1)`
063. `((rank(ts_decay_linear(ts_delta(group_neutralize(close, industry), 2), 8)) - rank(ts_decay_linear(ts_corr(((vwap * 0.318108) + (open * (1 - 0.318108))), ts_sum(ts_mean(volume,180), 37), 14), 12))) * -1)`
064. `((rank(ts_corr(ts_sum(((open * 0.178404) + (low * (1 - 0.178404))), 13), ts_sum(ts_mean(volume,120), 13), 17)) < rank(ts_delta(((((high + low) / 2) * 0.178404) + (vwap * (1 - 0.178404))), 4))) * -1)`
065. `((rank(ts_corr(((open * 0.00817205) + (vwap * (1 - 0.00817205))), ts_sum(ts_mean(volume,60), 9), 6)) < rank((open - ts_min(open, 14)))) * -1)`
066. `((rank(ts_decay_linear(ts_delta(vwap, 4), 7)) + ts_rank(ts_decay_linear(((((low * 0.96633) + (low * (1 - 0.96633))) - vwap) / (open - ((high + low) / 2))), 11), 7)) * -1)`
067. `((rank((high - ts_min(high, 2)))^rank(ts_corr(group_neutralize(vwap, sector), group_neutralize(ts_mean(volume,20), subindustry), 6))) * -1)`
068. `((ts_rank(ts_corr(rank(high), rank(ts_mean(volume,15)), 9), 14) < rank(ts_delta(((close * 0.518371) + (low * (1 - 0.518371))), 1))) * -1)`
069. `((rank(ts_max(ts_delta(group_neutralize(vwap, industry), 3), 5))^ts_rank(ts_corr(((close * 0.490655) + (vwap * (1 - 0.490655))), ts_mean(volume,20), 5), 9)) * -1)`
070. `((rank(ts_delta(vwap, 1))^ts_rank(ts_corr(group_neutralize(close, industry), ts_mean(volume,50), 18), 18)) * -1)`
071. `max(ts_rank(ts_decay_linear(ts_corr(ts_rank(close, 3), ts_rank(ts_mean(volume,180), 12), 18), 4), 16), ts_rank(ts_decay_linear((rank(((low + open) - (vwap + vwap)))^2), 16), 4))`
072. `(rank(ts_decay_linear(ts_corr(((high + low) / 2), ts_mean(volume,40), 9), 10)) / rank(ts_decay_linear(ts_corr(ts_rank(vwap, 4), ts_rank(volume, 19), 7), 3)))`
073. `(max(rank(ts_decay_linear(ts_delta(vwap, 5), 3)), ts_rank(ts_decay_linear(((ts_delta(((open * 0.147155) + (low * (1 - 0.147155))), 2) / ((open * 0.147155) + (low * (1 - 0.147155)))) * -1), 3), 17)) * -1)`
074. `((rank(ts_corr(close, ts_sum(ts_mean(volume,30), 37), 15)) < rank(ts_corr(rank(((high * 0.0261661) + (vwap * (1 - 0.0261661)))), rank(volume), 11))) * -1)`
075. `(rank(ts_corr(vwap, volume, 4)) < rank(ts_corr(rank(low), rank(ts_mean(volume,50)), 12)))`
076. `(max(rank(ts_decay_linear(ts_delta(vwap, 1), 12)), ts_rank(ts_decay_linear(ts_rank(ts_corr(group_neutralize(low, sector), ts_mean(volume,81), 8), 20), 17), 19)) * -1)`
077. `min(rank(ts_decay_linear(((((high + low) / 2) + high) - (vwap + high)), 20)), rank(ts_decay_linear(ts_corr(((high + low) / 2), ts_mean(volume,40), 3), 6)))`
078. `(rank(ts_corr(ts_sum(((low * 0.352233) + (vwap * (1 - 0.352233))), 20), ts_sum(ts_mean(volume,40), 20), 7))^rank(ts_corr(rank(vwap), rank(volume), 6)))`
079. `(rank(ts_delta(group_neutralize(((close * 0.60733) + (open * (1 - 0.60733))), sector), 1)) < rank(ts_corr(ts_rank(vwap, 4), ts_rank(ts_mean(volume,150), 9), 15)))`
080. `((rank(sign(ts_delta(group_neutralize(((open * 0.868128) + (high * (1 - 0.868128))), industry), 4)))^ts_rank(ts_corr(high, ts_mean(volume,10), 5), 6)) * -1)`
081. `((rank(log(ts_product(rank((rank(ts_corr(vwap, ts_sum(ts_mean(volume,10), 50), 9))^4)), 15))) < rank(ts_corr(rank(vwap), rank(volume), 5))) * -1)`
082. `(min(rank(ts_decay_linear(ts_delta(open, 2), 15)), ts_rank(ts_decay_linear(ts_corr(group_neutralize(volume, sector), ((open * 0.634196) + (open * (1 - 0.634196))), 17), 7), 13)) * -1)`
083. `((rank(ts_delay(((high - low) / (ts_sum(close, 5) / 5)), 2)) * rank(rank(volume))) / (((high - low) / (ts_sum(close, 5) / 5)) / (vwap - close)))`
084. `signed_power(ts_rank((vwap - ts_max(vwap, 15)), 21), ts_delta(close, 5))`
085. `(rank(ts_corr(((high * 0.876703) + (close * (1 - 0.876703))), ts_mean(volume,30), 10))^rank(ts_corr(ts_rank(((high + low) / 2), 4), ts_rank(volume, 10), 7)))`
086. `((ts_rank(ts_corr(close, ts_sum(ts_mean(volume,20), 14), 6), 20) < rank(((open + close) - (vwap + open)))) * -1)`
087. `(max(rank(ts_decay_linear(ts_delta(((close * 0.369701) + (vwap * (1 - 0.369701))), 2), 3)), ts_rank(ts_decay_linear(abs(ts_corr(group_neutralize(ts_mean(volume,81), industry), close, 13)), 5), 14)) * -1)`
088. `min(rank(ts_decay_linear(((rank(open) + rank(low)) - (rank(high) + rank(close))), 8)), ts_rank(ts_decay_linear(ts_corr(ts_rank(close, 8), ts_rank(ts_mean(volume,60), 21), 8), 7), 3))`
089. `(ts_rank(ts_decay_linear(ts_corr(((low * 0.967285) + (low * (1 - 0.967285))), ts_mean(volume,10), 7), 6), 4) - ts_rank(ts_decay_linear(ts_delta(group_neutralize(vwap, industry), 3), 10), 15))`
090. `((rank((close - ts_max(close, 5)))^ts_rank(ts_corr(group_neutralize(ts_mean(volume,40), subindustry), low, 5), 3)) * -1)`
091. `((ts_rank(ts_decay_linear(ts_decay_linear(ts_corr(group_neutralize(close, industry), volume, 10), 16), 4), 5) - rank(ts_decay_linear(ts_corr(vwap, ts_mean(volume,30), 4), 3))) * -1)`
092. `min(ts_rank(ts_decay_linear(((((high + low) / 2) + close) < (low + open)), 15), 19), ts_rank(ts_decay_linear(ts_corr(rank(low), rank(ts_mean(volume,30)), 8), 7), 7))`
093. `(ts_rank(ts_decay_linear(ts_corr(group_neutralize(vwap, industry), ts_mean(volume,81), 17), 20), 8) / rank(ts_decay_linear(ts_delta(((close * 0.524434) + (vwap * (1 - 0.524434))), 3), 16)))`
094. `((rank((vwap - ts_min(vwap, 12)))^ts_rank(ts_corr(ts_rank(vwap, 20), ts_rank(ts_mean(volume,60), 4), 18), 3)) * -1)`
095. `(rank((open - ts_min(open, 12))) < ts_rank((rank(ts_corr(ts_sum(((high + low) / 2), 19), ts_sum(ts_mean(volume,40), 19), 13))^5), 12))`
096. `(max(ts_rank(ts_decay_linear(ts_corr(rank(vwap), rank(volume), 4), 4), 8), ts_rank(ts_decay_linear(ts_arg_max(ts_corr(ts_rank(close, 7), ts_rank(ts_mean(volume,60), 4), 4), 12), 14), 13)) * -1)`
097. `((rank(ts_decay_linear(ts_delta(group_neutralize(((low * 0.721001) + (vwap * (1 - 0.721001))), industry), 3), 20)) - ts_rank(ts_decay_linear(ts_rank(ts_corr(ts_rank(low, 8), ts_rank(ts_mean(volume,60), 17), 5), 19), 16), 7)) * -1)`
098. `(rank(ts_decay_linear(ts_corr(vwap, ts_sum(ts_mean(volume,5), 26), 5), 7)) - rank(ts_decay_linear(ts_rank(ts_arg_min(ts_corr(rank(open), rank(ts_mean(volume,15)), 21), 9), 7), 8)))`
099. `((rank(ts_corr(ts_sum(((high + low) / 2), 20), ts_sum(ts_mean(volume,60), 20), 9)) < rank(ts_corr(low, volume, 6))) * -1)`
100. `(0 - (1 * (((1.5 * scale(group_neutralize(group_neutralize(rank(((((close - low) - (high - close)) / (high - low)) * volume)), subindustry), subindustry))) - scale(group_neutralize((ts_corr(close, rank(ts_mean(volume,20)), 5) - rank(ts_arg_min(close, 30))), subindustry))) * (volume / ts_mean(volume,20)))))`
101. `((close - open) / ((high - low) + 0.001))`

## Strongest Pre-Wrapped Picks

When in doubt, start from one of these — already in the canonical pipeline:

```
# Alpha 33: simple, tunable
scale(group_neutralize(zscore(rank(-1 * ((1 - (open / close))^1))), subindustry))

# Alpha 101: clean candlestick
scale(group_neutralize(zscore((close - open) / ((high - low) + 0.001)), subindustry))

# Alpha 28: short-mean / liquidity correlate
scale(group_neutralize(zscore(((ts_corr(ts_mean(volume,20), low, 5) + ((high + low) / 2)) - close)), subindustry))
```
