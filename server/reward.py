"""Terminal reward computation for BOARDROOM (anti-hacking multi-component design)."""

from typing import Dict

from .game_logic import CompanyState


def compute_terminal_reward(companies: Dict[str, CompanyState], ceo_id: str) -> float:
    """
    Rank-based terminal reward. Called once when game ends.

    Dense per-turn rewards are handled inside resolve_turn().
    This only fires at episode end so the model has an incentive
    to actually WIN, not just survive or farm small bonuses.
    """
    company = companies.get(ceo_id)
    if not company:
        return 0.0

    if not company.alive:
        return -1.5  # bankruptcy elimination

    alive = [c for c in companies.values() if c.alive]
    ranked = sorted(alive, key=lambda c: c.stock_price * c.market_share, reverse=True)
    rank = next((i for i, c in enumerate(ranked) if c.name == ceo_id), len(ranked))

    if rank == 0:
        return 3.0   # winner
    elif rank == 1:
        return 1.0   # runner-up
    elif rank == 2:
        return 0.3   # third
    return 0.0
