"""Moyen terme (1 à 3 mois) : rotation sur le momentum relatif 6-1 mois.

Chaque jour on classe tout l'univers sur la perf de t-126 à t-21 séances (on saute le
dernier mois, qui a tendance à se retourner). On achète les `top_n` premiers s'ils sont
au-dessus de leur SMA200 et si le marché est sain ; on revend quand le titre sort du
top `exit_rank`, casse sa SMA100, ou quand le marché passe sous sa SMA200.
Le classement à la date t n'utilise que des données <= t (pas de biais d'anticipation).
"""
from __future__ import annotations

import pandas as pd
from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame

from common import add_regime, apply_env_params


class MomentumRotation(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1d"
    can_short = False
    minimal_roi = {"0": 100}
    stoploss = -0.20
    use_exit_signal = True
    process_only_new_candles = True
    startup_candle_count = 210

    top_n = IntParameter(3, 15, default=5, space="buy", optimize=False)
    exit_rank = IntParameter(5, 40, default=20, space="sell", optimize=False)
    _ranks: pd.DataFrame | None = None

    def _rank_table(self) -> pd.DataFrame:
        if self._ranks is None:
            mom = {}
            for p in self.dp.current_whitelist():
                d = self.dp.get_pair_dataframe(p, "1d")
                if d.empty:
                    continue
                s = d.set_index("date")["close"]
                mom[p] = s.shift(21) / s.shift(126) - 1
            m = pd.DataFrame(mom)
            self._ranks = m.rank(axis=1, ascending=False)
        return self._ranks

    def bot_start(self, **kwargs) -> None:
        apply_env_params(self)

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["sma200"] = df["close"].rolling(200).mean()
        df["sma100"] = df["close"].rolling(100).mean()
        r = self._rank_table()
        pair = metadata["pair"]
        if pair in r:
            df = df.merge(r[pair].rename("mom_rank"), left_on="date", right_index=True, how="left")
        else:
            df["mom_rank"] = 999
        df["mom_rank"] = df["mom_rank"].fillna(999)
        return add_regime(self, df, pair)

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        cond = ((df["mom_rank"] <= self.top_n.value) & (df["close"] > df["sma200"])
                & (df["regime_ok"] == 1) & (df["volume"] > 0))
        df.loc[cond, "enter_long"] = 1
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        cond = ((df["mom_rank"] > self.exit_rank.value) | (df["close"] < df["sma100"])
                | (df["regime_ok"] == 0))
        df.loc[cond, "exit_long"] = 1
        return df
