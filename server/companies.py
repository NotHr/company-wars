"""Company definitions and sector traits for BOARDROOM (L1: 4 companies)."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class SectorTrait:
    name: str
    cash_interest_multiplier: float = 1.0   # Finance: earns 10% interest on cash each turn
    sabotage_cost_multiplier: float = 1.0   # Tech: sabotage costs 20% less
    press_impact_multiplier: float = 1.0    # Media: press releases hit 20% harder
    sabotage_damage_multiplier: float = 1.0  # Logistics: 20% less damage from sabotage


SECTOR_TRAITS: Dict[str, SectorTrait] = {
    "Finance": SectorTrait("Finance", cash_interest_multiplier=1.10),
    "Tech": SectorTrait("Tech", sabotage_cost_multiplier=0.80),
    "Media": SectorTrait("Media", press_impact_multiplier=1.20),
    "Logistics": SectorTrait("Logistics", sabotage_damage_multiplier=0.80),
}

# L1: 4 companies. L2 expands to 7.
L1_COMPANIES: List[Dict] = [
    {"name": "Vermillion Capital", "sector": "Finance"},
    {"name": "Goldspire Industries", "sector": "Tech"},
    {"name": "Sablemark Holdings", "sector": "Media"},
    {"name": "Ironhold Logistics", "sector": "Logistics"},
]

STARTING_STATS = {
    "cash": 50_000_000.0,
    "market_share": 25.0,   # 100% / 4 companies
    "stock_price": 100.0,
    "reputation": 0.70,
}
