"""Company definitions and sector traits for BOARDROOM."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class SectorTrait:
    name: str
    cash_interest_multiplier: float = 1.0    # Finance: +10% interest; Energy: +5%
    sabotage_cost_multiplier: float = 1.0    # Tech: sabotage costs 20% less
    press_impact_multiplier: float = 1.0     # Media: press releases hit 20% harder
    sabotage_damage_multiplier: float = 1.0  # Logistics: 20% less; Healthcare: 25% less
    partnership_bonus_multiplier: float = 1.0  # Telecom: 25% more partnership rewards


SECTOR_TRAITS: Dict[str, SectorTrait] = {
    "Finance":    SectorTrait("Finance",    cash_interest_multiplier=1.10),
    "Tech":       SectorTrait("Tech",       sabotage_cost_multiplier=0.80),
    "Media":      SectorTrait("Media",      press_impact_multiplier=1.20),
    "Logistics":  SectorTrait("Logistics",  sabotage_damage_multiplier=0.80),
    "Telecom":    SectorTrait("Telecom",    partnership_bonus_multiplier=1.25),
    "Energy":     SectorTrait("Energy",     cash_interest_multiplier=1.05),
    "Healthcare": SectorTrait("Healthcare", sabotage_damage_multiplier=0.75),
}

# L1: 4 companies.
L1_COMPANIES: List[Dict] = [
    {"name": "Vermillion Capital", "sector": "Finance"},
    {"name": "Goldspire Industries", "sector": "Tech"},
    {"name": "Sablemark Holdings", "sector": "Media"},
    {"name": "Ironhold Logistics", "sector": "Logistics"},
]

# L2: 7 companies (L1 cast + Telecom, Energy, Healthcare).
L2_COMPANIES: List[Dict] = [
    {"name": "Vermillion Capital",  "sector": "Finance"},
    {"name": "Goldspire Industries","sector": "Tech"},
    {"name": "Sablemark Holdings",  "sector": "Media"},
    {"name": "Ironhold Logistics",  "sector": "Logistics"},
    {"name": "Nexbridge Telecom",   "sector": "Telecom"},
    {"name": "Solstice Energy",     "sector": "Energy"},
    {"name": "Medvault Health",     "sector": "Healthcare"},
]

L1_STARTING_STATS = {
    "cash": 50_000_000.0,
    "market_share": 100.0 / len(L1_COMPANIES),  # 25.0 for 4 companies
    "stock_price": 100.0,
    "reputation": 0.70,
}

L2_STARTING_STATS = {
    "cash": 50_000_000.0,
    "market_share": 100.0 / len(L2_COMPANIES),  # ≈14.2857 for 7 companies
    "stock_price": 100.0,
    "reputation": 0.70,
}

STARTING_STATS = L2_STARTING_STATS  # backward compat

# Used by game_logic formulas that normalise against starting share.
MARKET_SHARE_BASELINE: float = L2_STARTING_STATS["market_share"]
