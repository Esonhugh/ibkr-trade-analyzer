"""IBKR trade analyzers subpackage.

Each analyzer lives in its own module:
  analyzers/trade.py          — TradeAnalyzer
  analyzers/pnl.py            — PnLAnalyzer
  analyzers/portfolio.py      — PortfolioAnalyzer
  analyzers/cost.py           — CostAnalyzer
  analyzers/price.py          — PriceAnalyzer
  analyzers/fx.py             — FxAnalyzer
  analyzers/diluted_cost.py   — DilutedCostAnalyzer (摊薄成本价/保本价)
  analyzers/lifo.py           — LifoAnalyzer (LIFO lot matching)
"""

from .china_tax import ChinaTaxAnalyzer, ChinaTaxConfig, MissingFxRateError
from .cost import CostAnalyzer
from .diluted_cost import DilutedCostAnalyzer
from .fx import FxAnalyzer
from .lifo import LifoAnalyzer
from .pnl import PnLAnalyzer
from .portfolio import PortfolioAnalyzer
from .price import PriceAnalyzer
from .trade import TradeAnalyzer

__all__ = [
    "ChinaTaxAnalyzer",
    "ChinaTaxConfig",
    "CostAnalyzer",
    "DilutedCostAnalyzer",
    "FxAnalyzer",
    "LifoAnalyzer",
    "MissingFxRateError",
    "PnLAnalyzer",
    "PortfolioAnalyzer",
    "PriceAnalyzer",
    "TradeAnalyzer",
]
