"""Court terme (2 à ~10 jours) : achat de repli dans une tendance haussière.

Idée (type Connors) : dans un titre en tendance (clôture > SMA200) et un marché sain
(indice > SMA200), un excès de vente à très court terme (RSI(2) < seuil) tend à être
rattrapé en quelques séances. Sortie dès que le prix repasse au-dessus de sa SMA5,
ou au bout de `max_days` séances, ou stop catastrophe.
"""
from __future__ import annotations

from datetime import datetime

from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame

from common import add_regime, apply_env_params, rsi


class PullbackRSI2(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1d"
    can_short = False
    minimal_roi = {"0": 100}          # pas de take-profit fixe
    stoploss = -0.15                  # stop catastrophe
    use_exit_signal = True
    exit_profit_only = False
    process_only_new_candles = True
    startup_candle_count = 210

    rsi_entry = IntParameter(3, 20, default=10, space="buy", optimize=False)
    max_days = IntParameter(3, 30, default=14, space="sell", optimize=False)
    use_regime = True

    def bot_start(self, **kwargs) -> None:
        apply_env_params(self)

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["sma200"] = df["close"].rolling(200).mean()
        df["sma5"] = df["close"].rolling(5).mean()
        df["rsi2"] = rsi(df["close"], 2)
        return add_regime(self, df, metadata["pair"])

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        cond = (df["close"] > df["sma200"]) & (df["rsi2"] < self.rsi_entry.value) & (df["volume"] > 0)
        if self.use_regime:
            cond &= df["regime_ok"] == 1
        df.loc[cond, "enter_long"] = 1
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df.loc[df["close"] > df["sma5"], "exit_long"] = 1
        return df

    def custom_exit(self, pair: str, trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs):
        if (current_time - trade.open_date_utc).days >= self.max_days.value:
            return "time_exit"
        return None


class PullbackRSI2NoRegime(PullbackRSI2):
    use_regime = False
