"""
Turn resolution, economy updates, and stock price formula for BOARDROOM.

All actions resolve simultaneously each turn (no ordering advantage).
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .companies import MARKET_SHARE_BASELINE, SECTOR_TRAITS


@dataclass
class CompanyState:
    name: str
    sector: str
    cash: float
    market_share: float
    stock_price: float
    reputation: float
    alive: bool = True
    starting_cash: float = 50_000_000.0

    # History needed for reward signals
    caught_lying_count: int = 0
    active_partnerships: List[str] = field(default_factory=list)
    partnership_turns_remaining: Dict[str, int] = field(default_factory=dict)

    # Per-turn flags, reset each turn
    was_sabotaged: bool = False
    press_caught_this_turn: bool = False
    partnership_formed_this_turn: List[str] = field(default_factory=list)


@dataclass
class TurnAction:
    company_name: str
    private_emails: List[Dict]
    press_release: Optional[Dict]
    action_type: str   # EARNINGS_CALL | SABOTAGE | PARTNERSHIP | PROPOSE_MERGER | HOLD
    action_target: Optional[str]
    parse_failed: bool = False


@dataclass
class TurnResult:
    rewards: Dict[str, float]
    press_wire: List[Dict]   # all press releases this turn (for observation)
    emails: Dict[str, List[Dict]]  # per-recipient emails


def resolve_turn(
    companies: Dict[str, CompanyState],
    actions: Dict[str, TurnAction],
    rng: random.Random,
) -> TurnResult:
    """Resolve all CEO actions simultaneously. Returns per-company rewards."""

    rewards = {name: 0.0 for name in companies}
    press_wire: List[Dict] = []
    emails: Dict[str, List[Dict]] = {name: [] for name in companies}

    # --- Reset per-turn flags ---
    for c in companies.values():
        c.was_sabotaged = False
        c.press_caught_this_turn = False
        c.partnership_formed_this_turn = []

    # --- Phase 1: Communications (emails + press releases) ---
    for name, action in actions.items():
        company = companies[name]
        if not company.alive:
            continue

        # Format penalty
        if action.parse_failed:
            rewards[name] -= 0.3

        # Deliver private emails
        for mail in action.private_emails:
            recipient = mail.get("to")
            if recipient and recipient in companies and companies[recipient].alive:
                emails[recipient].append({"from": name, "text": mail.get("text", "")})

        # Process press release
        if action.press_release:
            pr = action.press_release
            is_fake = not pr.get("marked_truthful", True)

            caught = is_fake and rng.random() < 0.30
            if caught:
                company.caught_lying_count += 1
                company.press_caught_this_turn = True
                company.reputation = max(0.0, company.reputation - 0.20)
                rewards[name] -= 0.6
            else:
                press_wire.append({
                    "from": name,
                    "claim": pr.get("claim", ""),
                    "is_fake": is_fake,
                    "caught": False,
                })
                rewards[name] += 0.2

    # --- Phase 2: Strategic actions (resolved simultaneously) ---
    partnership_proposals: Dict[str, str] = {}  # proposer → target
    merger_proposals: Dict[str, str] = {}        # proposer → target

    for name, action in actions.items():
        company = companies[name]
        if not company.alive:
            continue

        trait = SECTOR_TRAITS.get(company.sector)

        if action.action_type == "EARNINGS_CALL":
            # Truthful track record = big boost; liar history = diminished boost
            trust = max(0.0, 1.0 - 0.15 * company.caught_lying_count)
            company.stock_price *= (1.0 + 0.08 * trust)
            rewards[name] += 0.15 * trust

        elif action.action_type == "SABOTAGE" and action.action_target:
            target = companies.get(action.action_target)
            if target and target.alive:
                cost = 5_000_000 * (trait.sabotage_cost_multiplier if trait else 1.0)
                company.cash -= cost

                if rng.random() < 0.70:  # 70% success
                    target_trait = SECTOR_TRAITS.get(target.sector)
                    dmg_mult = target_trait.sabotage_damage_multiplier if target_trait else 1.0
                    cash_damage = 8_000_000 * dmg_mult
                    target.cash -= cash_damage
                    target.market_share = max(0.0, target.market_share - 1.5)
                    company.market_share += 0.5
                    target.was_sabotaged = True
                    rewards[name] += 0.3
                else:
                    # 30% fail — 50% chance reputation exposed
                    if rng.random() < 0.50:
                        company.reputation = max(0.0, company.reputation - 0.15)
                        rewards[name] -= 0.4

        elif action.action_type == "PARTNERSHIP" and action.action_target:
            partnership_proposals[name] = action.action_target

        elif action.action_type == "PROPOSE_MERGER" and action.action_target:
            t = action.action_target
            if t in companies and companies[t].alive and t != name:
                merger_proposals[name] = t

    # --- Resolve partnerships (mutual proposals auto-accept; NPC 50% accept) ---
    processed = set()
    for proposer, target_name in partnership_proposals.items():
        if proposer in processed:
            continue
        target = companies.get(target_name)
        if not target or not target.alive or target_name == proposer:
            continue

        mutual = partnership_proposals.get(target_name) == proposer
        accept = mutual or rng.random() < 0.50

        if accept and target_name not in companies[proposer].active_partnerships:
            companies[proposer].active_partnerships.append(target_name)
            companies[proposer].partnership_turns_remaining[target_name] = 3
            target.active_partnerships.append(proposer)
            target.partnership_turns_remaining[proposer] = 3
            companies[proposer].partnership_formed_this_turn.append(target_name)
            target.partnership_formed_this_turn.append(proposer)
            rewards[proposer] += 0.1
            rewards[target_name] += 0.1
            processed.add(proposer)
            processed.add(target_name)

    # --- Resolve merger proposals ---
    # Mutual: target absorbed (gains assets, target dies).
    # One-sided: heavy reputation loss for proposer, small boost for target.
    processed_mergers: set = set()
    for proposer, target_name in merger_proposals.items():
        if proposer in processed_mergers or target_name in processed_mergers:
            continue
        target = companies.get(target_name)
        if not target or not target.alive:
            continue

        mutual = merger_proposals.get(target_name) == proposer
        if mutual:
            proposer_co = companies[proposer]
            proposer_co.cash += target.cash
            proposer_co.market_share += target.market_share
            target.market_share = 0.0
            target.alive = False
            target.cash = 0.0
            rewards[proposer] += 1.0
            rewards[target_name] -= 0.5
            processed_mergers.add(proposer)
            processed_mergers.add(target_name)
        else:
            # Hostile / one-sided attempt
            companies[proposer].reputation = max(0.0, companies[proposer].reputation - 0.25)
            rewards[proposer] -= 0.5
            target.market_share += 1.0
            target.reputation = min(1.0, target.reputation + 0.05)
            rewards[target_name] += 0.15
            processed_mergers.add(target_name)

    # --- Tick down partnerships ---
    for company in companies.values():
        expired = [p for p, t in company.partnership_turns_remaining.items() if t <= 1]
        for partner in expired:
            if partner in company.active_partnerships:
                company.active_partnerships.remove(partner)
            company.partnership_turns_remaining.pop(partner, None)
        for partner in company.partnership_turns_remaining:
            company.partnership_turns_remaining[partner] -= 1

    # Active partnership bonus — only count alive partners
    for name, company in companies.items():
        alive_partners = [p for p in company.active_partnerships
                          if companies.get(p) and companies[p].alive]
        if alive_partners:
            rewards[name] += 0.1 * len(alive_partners)

    # --- Phase 3: Economy update ---
    for name, company in companies.items():
        if not company.alive:
            continue

        # Operational cash burn
        company.cash -= 1_000_000

        # Sector: Finance earns interest
        trait = SECTOR_TRAITS.get(company.sector)
        if trait and trait.cash_interest_multiplier != 1.0:
            company.cash += company.cash * (trait.cash_interest_multiplier - 1.0)

        # Market share → revenue
        company.cash += company.cash * 0.005 * (company.market_share / MARKET_SHARE_BASELINE)

        # Update stock price
        company.stock_price = _update_stock(company, press_wire, rng)

        # Dense per-turn reward signals
        rewards[name] += 0.001 * (company.cash / 1_000_000)
        rewards[name] += 0.05 * (company.market_share / 100.0)
        rewards[name] += 0.0005 * company.stock_price
        rewards[name] -= 0.05 * (1.0 - company.reputation)

        # Bankruptcy check
        if company.cash <= 0:
            company.alive = False
            rewards[name] -= 1.5
            _redistribute_market_share(company, companies)

    return TurnResult(rewards=rewards, press_wire=press_wire, emails=emails)


def _update_stock(company: CompanyState, press_wire: List[Dict], rng: random.Random) -> float:
    """Stock price formula from PLAN.md."""
    base = company.stock_price

    # Cash health (caps at 2× starting so stock can't grow unboundedly)
    cash_health = min(company.cash / company.starting_cash, 2.0)
    base *= 0.95 + 0.1 * cash_health

    # Market share momentum (baseline = 100% / num_companies)
    base *= 0.98 + 0.04 * (company.market_share / MARKET_SHARE_BASELINE)

    # Press release effects on this company
    for press in press_wire:
        if company.name in press.get("claim", "") and not press.get("caught"):
            if press.get("is_fake"):
                trait = SECTOR_TRAITS.get(press.get("from_sector", ""))
                mult = trait.press_impact_multiplier if trait else 1.0
                base *= 0.92 * mult
            else:
                base *= 1.05

    # Sabotage damage
    if company.was_sabotaged:
        base *= 0.85

    # Reputation drift
    base *= 0.95 + 0.1 * company.reputation

    # Random market noise
    base *= rng.uniform(0.97, 1.03)

    return max(1.0, base)


def _redistribute_market_share(bankrupt: CompanyState, companies: Dict[str, CompanyState]) -> None:
    alive = [c for c in companies.values() if c.alive and c.name != bankrupt.name]
    if not alive:
        return
    share_each = bankrupt.market_share / len(alive)
    for c in alive:
        c.market_share += share_each
    bankrupt.market_share = 0.0
