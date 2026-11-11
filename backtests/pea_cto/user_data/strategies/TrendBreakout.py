"""Moyen terme (quelques semaines à ~3 mois) : cassure de plus haut 55 jours.

Entrée : clôture au plus haut des `entry_n` dernières séances, titre > SMA200, marché sain.
Sortie : clôture sous le plus bas des `exit_n` dernières séances (canal de Donchian,
type "Turtle"), ou stop catastrophe. On laisse courir les gagnants.
"""
from __future__ import annotations

from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame

from common import add_regime, apply_env_params


class TrendBreakout(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1d"
    can_short = False
    minimal_roi = {"0": 100}
    stoploss = -0.20
    use_exit_signal = True
    process_only_new_candles = True
    startup_candle_count = 210

    entry_n = IntParameter(20, 100, default=55, space="buy", optimize=False)
    exit_n = IntParameter(10, 50, default=20, space="sell", optimize=False)
    use_regime = True

    def bot_start(self, **kwargs) -> None:
        apply_env_params(self)

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["sma200"] = df["close"].rolling(200).mean()
        df["hh"] = df["close"].shift(1).rolling(self.entry_n.value).max()
        df["ll"] = df["close"].shift(1).rolling(self.exit_n.value).min()
        return add_regime(self, df, metadata["pair"])

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        cond = (df["close"] > df["hh"]) & (df["close"] > df["sma200"]) & (df["volume"] > 0)
        if self.use_regime:
            cond &= df["regime_ok"] == 1
        df.loc[cond, "enter_long"] = 1
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df.loc[df["close"] < df["ll"], "exit_long"] = 1
        return df
