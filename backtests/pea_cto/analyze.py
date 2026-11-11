"""Lance des backtests freqtrade et calcule des stats propres (equity mark-to-market journalière).

Pourquoi ne pas utiliser seulement le rapport freqtrade : sans bougies de week-end, ses
métriques "wallet" (Sharpe/drawdown journaliers) sont faussées ; on recalcule tout ici
à partir des trades exportés et des cours de clôture.

Usage : python analyze.py            -> lance la grille définie dans RUNS, écrit results/
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
DATA = ROOT / "user_data" / "data" / "binance"
RES = ROOT / "user_data" / "backtest_results"
OUT = ROOT / "results"
SPLIT = pd.Timestamp("2024-07-01", tz="UTC")   # in-sample avant / out-of-sample après
START = 10_000.0

FEE_STOCK = 0.0035  # par ordre : courtage ~0.1 % + spread ~0.05 % + TTF 0.4 % à l'achat lissée
FEE_ETF = 0.0015    # par ordre : courtage ~0.1 % + spread ~0.05 % (pas de TTF sur les ETF)


def close_px(pair: str) -> pd.Series:
    d = pd.read_feather(DATA / f"{pair.replace('/', '_')}-1d.feather")
    return d.set_index("date")["close"]


def run(strategy: str, config: str, fee: float, timerange: str, params: dict | None = None,
        tag: str = "") -> pd.DataFrame:
    env = dict(os.environ, FT_PARAMS=json.dumps(params or {}))
    name = f"{strategy}_{tag or 'base'}"
    cmd = [sys.executable, "ft.py", "backtesting", "--config", config, "--strategy", strategy,
           "--fee", str(fee), "--timerange", timerange, "--cache", "none", "--export", "trades",
           "--backtest-filename", name]
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stdout[-3000:] + p.stderr[-3000:])
    last = json.loads((RES / ".last_result.json").read_text())["latest_backtest"]
    z = zipfile.ZipFile(RES / last)
    js = [n for n in z.namelist() if n.endswith(".json") and "_config" not in n and "market" not in n]
    t = pd.DataFrame(json.loads(z.read(js[0]))["strategy"][strategy]["trades"])
    for c in ("open_date", "close_date"):
        t[c] = pd.to_datetime(t[c], utc=True)
    return t


def equity_curve(trades: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.Series:
    """Equity journalière = capital initial + P&L réalisé + P&L latent des positions ouvertes."""
    eq = pd.Series(START, index=calendar, dtype=float)
    if trades.empty:
        return eq
    realized = trades.set_index("close_date")["profit_abs"].groupby(level=0).sum()
    eq += realized.reindex(calendar, fill_value=0).cumsum()
    px_cache: dict[str, pd.Series] = {}
    for _, tr in trades.iterrows():
        px = px_cache.setdefault(tr.pair, close_px(tr.pair).reindex(calendar).ffill())
        live = (calendar >= tr.open_date) & (calendar < tr.close_date)
        eq[live] += tr.amount * px[live] - tr.stake_amount
    return eq


def stats(eq: pd.Series) -> dict:
    eq = eq.dropna()
    if len(eq) < 20:
        return dict.fromkeys(("CAGR %", "Total %", "MaxDD %", "Vol %", "Sharpe"), np.nan)
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    r = eq.pct_change().dropna()
    dd = eq / eq.cummax() - 1
    return {
        "CAGR %": 100 * ((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1) if yrs > 0 else np.nan,
        "Total %": 100 * (eq.iloc[-1] / eq.iloc[0] - 1),
        "MaxDD %": 100 * dd.min(),
        "Vol %": 100 * r.std() * np.sqrt(252),
        "Sharpe": r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan,
    }


def summarize(name: str, trades: pd.DataFrame, eq: pd.Series, split=SPLIT) -> dict:
    s = {"run": name, "Début": eq.index[0].date(), "Fin": eq.index[-1].date(), "Split": split.date(),
         **stats(eq)}
    s["IS CAGR %"] = stats(eq[eq.index < split])["CAGR %"]
    s["OOS CAGR %"] = stats(eq[eq.index >= split - pd.Timedelta(days=1)])["CAGR %"]
    s["IS MaxDD %"] = stats(eq[eq.index < split])["MaxDD %"]
    s["OOS MaxDD %"] = stats(eq[eq.index >= split - pd.Timedelta(days=1)])["MaxDD %"]
    if len(trades):
        inv = pd.Series(0.0, index=eq.index)
        for _, tr in trades.iterrows():
            inv[(eq.index >= tr.open_date) & (eq.index < tr.close_date)] += tr.stake_amount
        s["Expo %"] = 100 * (inv / eq).clip(upper=1).mean()
        dur = (trades.close_date - trades.open_date).dt.days
        s |= {"Trades": len(trades), "Win %": 100 * (trades.profit_ratio > 0).mean(),
              "Avg trade %": 100 * trades.profit_ratio.mean(), "Avg jours": dur.mean(),
              "Médiane jours": dur.median()}
    return s


def yearly(eq: pd.Series) -> pd.Series:
    e = eq.groupby(eq.index.year).last()
    first = eq.iloc[0]
    return 100 * (e / e.shift(1).fillna(first) - 1)


def benchmark(pairs: list[str], calendar: pd.DatetimeIndex) -> pd.Series:
    """Buy & hold équipondéré (prix ajustés dividendes pour les actions)."""
    px = pd.DataFrame({p: close_px(p) for p in pairs}).reindex(calendar).ffill().bfill()
    return START * (px / px.iloc[0]).mean(axis=1)


GRIDS = {
    "PullbackRSI2": [{"rsi_entry": r, "max_days": d} for r in (5, 10, 20) for d in (7, 14, 28)],
    "TrendBreakout": [{"entry_n": e, "exit_n": x} for e in (20, 55, 100) for x in (10, 20, 40)],
    "MomentumRotation": [{"top_n": n, "exit_rank": x} for n in (3, 5, 10) for x in (10, 20, 40)],
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rows, curves, years = [], {}, {}
    cfg = json.loads((ROOT / "config_pea.json").read_text())
    universe = [p for p in cfg["exchange"]["pair_whitelist"] if p not in cfg["exchange"]["pair_blacklist"]]
    cac = close_px("CAC/EUR")
    cal = cac.index[cac.index >= pd.Timestamp("2022-09-02", tz="UTC")]

    def record(name, trades, eq, keep=True, split=SPLIT):
        rows.append(summarize(name, trades, eq, split))
        if keep:
            curves[name] = eq
            years[name] = yearly(eq)
        print(f"{name:55s} CAGR {rows[-1]['CAGR %']:6.1f}%  DD {rows[-1]['MaxDD %']:6.1f}%  "
              f"IS {rows[-1]['IS CAGR %']:6.1f}%  OOS {rows[-1]['OOS CAGR %']:6.1f}%", flush=True)

    # ---- 1. Univers actions PEA (≈118 actions FR/UE), frais nets vs bruts
    conc = []
    for strat in GRIDS:
        for fee, lab in ((FEE_STOCK, "net"), (0.0, "brut")):
            t = run(strat, "config_pea.json", fee, "20220101-", tag=lab)
            record(f"PEA actions | {strat} | {lab}", t, equity_curve(t, cal), keep=lab == "net")
            if lab == "net":   # dépendance aux meilleurs titres : on retire les k meilleurs
                g = t.groupby("pair")["profit_abs"].sum().sort_values(ascending=False)
                for k in (0, 1, 3, 5):
                    tt = t[~t["pair"].isin(g.index[:k])]
                    conc.append({"strategie": strat, "sans_top_k_titres": k,
                                 "titres_retirés": ", ".join(g.index[:k]),
                                 "CAGR %": round(stats(equity_curve(tt, cal))["CAGR %"], 2)})
    pd.DataFrame(conc).to_csv(OUT / "concentration.csv", index=False)
    for name, eq in (("Bench | CAC 40 (indice prix)", START * cac.reindex(cal) / cac.reindex(cal).iloc[0]),
                     ("Bench | Buy&Hold équipondéré univers", benchmark(universe, cal))):
        record(name, pd.DataFrame(), eq)

    # ---- 2. Robustesse : grille de paramètres (frais nets)
    for strat, grid in GRIDS.items():
        for prm in grid:
            tag = "_".join(f"{k}{v}" for k, v in prm.items())
            t = run(strat, "config_pea.json", FEE_STOCK, "20220101-", prm, tag)
            record(f"GRID | {strat} | {tag}", t, equity_curve(t, cal), keep=False)

    # ---- 3. Historique long sur indices (proxy ETF PEA/CTO), frais ETF
    for pair, cfgf, tr, sp in (("NDX/USD", "config_ndx.json", "20010101-", "2013-01-01"),
                               ("CACLONG/EUR", "config_caclong.json", "19910101-", "2007-01-01")):
        sp = pd.Timestamp(sp, tz="UTC")
        px = close_px(pair)
        for strat in ("PullbackRSI2", "TrendBreakout", "IndexSMA200"):
            t = run(strat, cfgf, FEE_ETF, tr, tag=pair.split("/")[0])
            c = px.index[px.index >= t.open_date.min()] if len(t) else px.index
            record(f"{pair.split('/')[0]} | {strat} | net", t, equity_curve(t, c), split=sp)
        c = px.index[px.index >= pd.Timestamp(tr[:8], tz="UTC") + pd.Timedelta(days=300)]
        record(f"{pair.split('/')[0]} | Buy&Hold", pd.DataFrame(), START * px.reindex(c) / px.reindex(c).iloc[0],
               split=sp)

    df = pd.DataFrame(rows).round(2)
    df.to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame(years).round(1).to_csv(OUT / "yearly.csv")
    pd.DataFrame(curves).to_csv(OUT / "equity_curves.csv")
    print(df.to_string())


if __name__ == "__main__":
    main()
