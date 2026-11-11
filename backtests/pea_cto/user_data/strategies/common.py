"""Briques communes : indicateurs en pandas pur + filtre de régime de marché."""
from __future__ import annotations

import pandas as pd



def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, 1e-12))


def add_regime(strategy, df: pd.DataFrame, pair: str, sma: int = 200) -> pd.DataFrame:
    """regime_ok = 1 si l'indice de référence clôture au-dessus de sa SMA `sma`.
    L'indice est la clé "regime_pair" de la config (CAC/EUR pour l'univers actions PEA) ;
    sans cette clé (backtest mono-indice NDX, CAC long), c'est la paire elle-même."""
    ref = None
    regime_pair = strategy.config.get("regime_pair")
    if regime_pair and strategy.dp and pair != regime_pair:
        ref = strategy.dp.get_pair_dataframe(regime_pair, "1d")
    if ref is None or ref.empty:
        df["regime_ok"] = (df["close"] > df["close"].rolling(sma).mean()).astype(int)
        return df
    r = ref[["date", "close"]].copy()
    r["regime_ok"] = (r["close"] > r["close"].rolling(sma).mean()).astype(int)
    df = df.merge(r[["date", "regime_ok"]], on="date", how="left")
    df["regime_ok"] = df["regime_ok"].ffill().fillna(0)
    return df


def apply_env_params(strategy) -> None:
    """Permet de surcharger les paramètres via FT_PARAMS='{"entry_n": 40}' (tests de robustesse)."""
    import json
    import os

    for k, v in json.loads(os.environ.get("FT_PARAMS", "{}")).items():
        getattr(strategy, k).value = v
