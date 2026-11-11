"""Lance freqtrade hors-ligne sur des actions/ETF.

freqtrade ne connaît que les exchanges crypto : on garde l'exchange 'binance' comme
coquille et on remplace le chargement des marchés (appel réseau) par des marchés
synthétiques construits à partir des fichiers présents dans user_data/data/binance.
Usage : python ft.py backtesting --config config_pea.json --strategy ... [args freqtrade]
"""
from __future__ import annotations

import sys
from pathlib import Path

from freqtrade.exchange.exchange import Exchange

DATA = Path(__file__).parent / "user_data" / "data" / "binance"


def _markets() -> list[dict]:
    out = []
    for f in DATA.glob("*-1d.feather"):
        base, quote = f.name.split("-")[0].split("_")
        out.append({
            "id": base + quote, "symbol": f"{base}/{quote}", "base": base, "quote": quote,
            "baseId": base, "quoteId": quote, "settle": None, "settleId": None,
            "type": "spot", "spot": True, "margin": False, "swap": False, "future": False,
            "option": False, "contract": False, "active": True, "linear": None, "inverse": None,
            "contractSize": None, "taker": 0.0, "maker": 0.0,
            "precision": {"amount": 0.0001, "price": 0.0001},   # fractions d'action tolérées
            "limits": {"amount": {"min": None, "max": None}, "price": {"min": None, "max": None},
                       "cost": {"min": None, "max": None}, "leverage": {"min": None, "max": None}},
            "info": {},
        })
    return out


def _offline_load(self, reload: bool = False) -> None:  # noqa: ARG001
    m = _markets()
    self._api_async.set_markets(m)


Exchange._load_async_markets = _offline_load

# freqtrade "remplit" les bougies manquantes (pensé pour la crypto 24/7) : sur actions
# cela crée des samedis/dimanches fictifs qui faussent SMA/RSI et les prix d'exécution.
# On désactive ce remplissage : une bougie = une séance de bourse réelle.
import freqtrade.data.converter.converter as _conv  # noqa: E402

_conv.ohlcv_fill_up_missing_data = lambda df, *a, **k: df
Exchange.fetch_trading_fees = lambda self: {}

if __name__ == "__main__":
    from freqtrade.main import main
    main(sys.argv[1:])
