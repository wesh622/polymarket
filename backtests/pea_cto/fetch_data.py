"""Télécharge les historiques journaliers et les convertit au format freqtrade (feather).

Sources (Yahoo/Stooq étant inaccessibles depuis l'environnement, on passe par des
CSV Yahoo Finance publiés sur GitHub) :
  - ~120 actions françaises/UE éligibles PEA, 2021-11 -> 2026-11, avec "Adj Close"
    (dividendes réinvestis)  : github.com/Mric006-44/Veille-Bourse
  - Nasdaq-100 2000-2018 + 2018-2026 (OHLC) : kowaalczyk/quant-invest + Lenoisalive/...
  - CAC 40 1990-2023 (clôtures seules)      : bashog/EconomicScenariosGenerator

Les prix des actions sont ajustés dividendes (facteur Adj Close / Close appliqué à OHLC).
Les indices sont des indices *prix* (sans dividendes) -> légèrement pessimiste pour du long.
"""
from __future__ import annotations

import io
import subprocess
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
RAW = ROOT / "raw"
OUT = ROOT / "user_data" / "data" / "binance"   # nom d'exchange factice (cf. ft.py)
RAW_GH = "https://raw.githubusercontent.com/"


def get(url: str) -> pd.DataFrame:
    with urllib.request.urlopen(url, timeout=60) as r:
        return pd.read_csv(io.BytesIO(r.read()))


def to_feather(df: pd.DataFrame, pair: str) -> None:
    df = df.dropna(subset=["close"]).copy()
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.normalize()
    df = df.drop_duplicates("date", keep="last").sort_values("date")
    df = df[(df["close"] > 0)]
    for c in ("open", "high", "low"):
        df[c] = df[c].where(df[c] > 0, df["close"])
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    df["volume"] = df.get("volume", 0).fillna(0) if "volume" in df else 1.0
    df = df[["date", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_feather(OUT / f"{pair.replace('/', '_')}-1d.feather", compression_level=9, compression="lz4")


def stocks() -> list[str]:
    repo = RAW / "Veille-Bourse"
    if not repo.exists():
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse",
                        "https://github.com/Mric006-44/Veille-Bourse", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "sparse-checkout", "set", "data/historique_long"], check=True)
    pairs = []
    for f in sorted((repo / "data" / "historique_long").glob("*.csv")):
        tick = f.stem
        d = pd.read_csv(f)
        d.columns = [c.lower().replace(" ", "_") for c in d.columns]
        if tick == "^FCHI":
            pair = "CAC/EUR"
        else:
            adj = d["adj_close"] / d["close"]
            for c in ("open", "high", "low", "close"):
                d[c] = d[c] * adj
            pair = f"{tick.split('.')[0].replace('-', '')}/EUR"
        to_feather(d, pair)
        pairs.append(pair)
    return pairs


def indices() -> None:
    # Nasdaq-100 : raccord 2000-2018 (colonnes en polonais) + 2018-2026
    a = get(RAW_GH + "kowaalczyk/quant-invest/HEAD/input/indices/%5Endx.csv")
    a.columns = ["date", "open", "high", "low", "close", "volume"]
    b = get(RAW_GH + "Lenoisalive/NVDA_Time_Series_Analysis/HEAD/%5ENDX.csv")
    b.columns = [c.lower().replace(" ", "_") for c in b.columns]
    a = a[pd.to_datetime(a["date"]) < pd.to_datetime(b["date"]).min()]
    to_feather(pd.concat([a, b[a.columns]]), "NDX/USD")
    # CAC 40 1990-2023 : clôtures seules -> open = clôture veille (approximation)
    c = get(RAW_GH + "bashog/EconomicScenariosGenerator/HEAD/datas/%5EFCHI.csv")
    c.columns = ["date", "close"]
    c["date"] = c["date"].str[:10]
    c["open"] = c["close"].shift(1)
    c["high"] = c[["open", "close"]].max(axis=1)
    c["low"] = c[["open", "close"]].min(axis=1)
    to_feather(c.iloc[1:], "CACLONG/EUR")


if __name__ == "__main__":
    RAW.mkdir(exist_ok=True)
    p = stocks()
    indices()
    print(f"{len(p)} actions/indices + NDX/USD + CACLONG/EUR écrits dans {OUT}")
    if "-v" in sys.argv:
        print(p)
