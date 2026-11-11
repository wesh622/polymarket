"""Moyen terme sur ETF indiciel : être investi quand l'indice est au-dessus de sa SMA200.

Entrée : clôture > SMA200 * (1 + band). Sortie : clôture < SMA200 * (1 - band).
La bande évite les allers-retours quand le prix colle à la moyenne. Sortie et entrée à
l'ouverture suivante. Pensé pour un ETF (CAC 40, S&P 500, Nasdaq-100 éligibles PEA).
"""
from __future__ import annotations

from freqtrade.strategy import DecimalParameter, IStrategy, IntParameter
from pandas import DataFrame

from common import apply_env_params


class IndexSMA200(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1d"
    can_short = False
    minimal_roi = {"0": 100}
    stoploss = -0.99
    use_exit_signal = True
    process_only_new_candles = True
    startup_candle_count = 210

    sma_n = IntParameter(100, 250, default=200, space="buy", optimize=False)
    band = DecimalParameter(0.0, 0.05, default=0.02, decimals=3, space="buy", optimize=False)

    def bot_start(self, **kwargs) -> None:
        apply_env_params(self)

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["sma"] = df["close"].rolling(self.sma_n.value).mean()
        return df

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df.loc[df["close"] > df["sma"] * (1 + self.band.value), "enter_long"] = 1
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df.loc[df["close"] < df["sma"] * (1 - self.band.value), "exit_long"] = 1
        return df
