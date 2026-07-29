# Pattern Definitions (code-aligned)

## Swing High / Low
Candle `i` is swing high if high[i] > highs of `N` bars left and right (`N=3` default).

## BOS
Close beyond last confirmed swing high (bullish) or swing low (bearish).  
Strength ≈ `(distance/ATR) * volume_factor`.

## CHoCH
BOS against prior trend (HH/HL vs LH/LL).

## Liquidity Sweep
Pierce swing level by ≥ pierce%, close back inside, preferably elevated volume.

## Equal High / Low
Two+ swing highs/lows within `0.15%` price distance.

## Bullish FVG
`low[i] > high[i-2]` after impulse candle `i-1`.

## Bullish Order Block
Last bearish candle before bullish BOS impulse.

## Premium / Discount
Above/below 50% of recent swing range.

## Pump score
Compression + volume increase + breakout + OI + liquidity/accumulation + mcap + momentum.
