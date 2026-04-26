"""
BOARDROOM Environment — main OpenEnv Environment subclass.

One training episode = one game from Vermillion Capital's perspective (12 turns max).
Other 3 CEOs use a heuristic random policy so a single LLM can train via GRPO.

Self-play upgrade path (L2): replace _heuristic_action() with LLM calls
using the same model weights, enabling true self-play without changing
the environment interface.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

from .companies import L2_COMPANIES, L2_STARTING_STATS
from .game_logic import CompanyState, TurnAction, TurnResult, resolve_turn
from .reward import compute_terminal_reward

try:
    from ..models import BoardroomAction, BoardroomObservation, CompanyStats, Email
except ImportError:
    from models import BoardroomAction, BoardroomObservation, CompanyStats, Email


class BoardroomEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    MAX_TURNS: int = 12
    # The LLM agent always plays this company. Others = heuristic.
    PRIMARY_CEO: str = "Vermillion Capital"

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._companies: Dict[str, CompanyState] = {}
        self._turn: int = 0
        self._rng = random.Random()
        self._replay_log: List[Dict] = []
        self._last_turn_result: Optional[TurnResult] = None

    # ------------------------------------------------------------------ #
    # OpenEnv interface                                                    #
    # ------------------------------------------------------------------ #

    def reset(self) -> BoardroomObservation:
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._turn = 0
        self._replay_log = []
        self._last_turn_result = None
        self._rng = random.Random(random.randint(0, 2**32))

        self._companies = {}
        for defn in L2_COMPANIES:
            self._companies[defn["name"]] = CompanyState(
                name=defn["name"],
                sector=defn["sector"],
                cash=L2_STARTING_STATS["cash"],
                market_share=L2_STARTING_STATS["market_share"],
                stock_price=L2_STARTING_STATS["stock_price"],
                reputation=L2_STARTING_STATS["reputation"],
                starting_cash=L2_STARTING_STATS["cash"],
            )

        return self._make_observation(done=False, reward=0.0)

    def step(self, action: BoardroomAction) -> BoardroomObservation:
        if not self._companies:
            self.reset()
        self._state.step_count += 1

        primary_action = self._parse_primary_action(action)
        all_actions: Dict[str, TurnAction] = {self.PRIMARY_CEO: primary_action}

        for name, company in self._companies.items():
            if name != self.PRIMARY_CEO and company.alive:
                all_actions[name] = self._heuristic_action(name)

        result = resolve_turn(self._companies, all_actions, self._rng)
        self._last_turn_result = result
        self._turn += 1

        my_reward = result.rewards.get(self.PRIMARY_CEO, 0.0)

        self._replay_log.append({
            "turn": self._turn,
            "actions": {
                k: {"type": v.action_type, "target": v.action_target}
                for k, v in all_actions.items()
            },
            "stats": {
                k: {
                    "cash": c.cash,
                    "stock": round(c.stock_price, 2),
                    "market_share": round(c.market_share, 2),
                    "reputation": round(c.reputation, 2),
                    "alive": c.alive,
                }
                for k, c in self._companies.items()
            },
        })

        alive = [c for c in self._companies.values() if c.alive]
        primary_alive = self._companies[self.PRIMARY_CEO].alive
        done = self._turn >= self.MAX_TURNS or len(alive) <= 1 or not primary_alive

        if done:
            my_reward += compute_terminal_reward(self._companies, self.PRIMARY_CEO)
            self._save_replay()

        return self._make_observation(done=done, reward=my_reward)

    @property
    def state(self) -> State:
        return self._state

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _parse_primary_action(self, action: BoardroomAction) -> TurnAction:
        """Validate the LLM's action. Silently demote invalid targets to HOLD."""
        parse_failed = False
        atype = action.action_type
        target = action.action_target

        if target:
            if target not in self._companies:
                target = None
                parse_failed = True
            elif not self._companies[target].alive:
                target = None
                parse_failed = True
            elif target == self.PRIMARY_CEO:
                target = None
                parse_failed = True

        if atype in ("SABOTAGE", "PARTNERSHIP", "PROPOSE_MERGER") and not target:
            atype = "HOLD"
            parse_failed = True

        return TurnAction(
            company_name=self.PRIMARY_CEO,
            private_emails=[e.model_dump() for e in action.private_emails[:2]],
            press_release=action.press_release.model_dump() if action.press_release else None,
            action_type=atype,
            action_target=target,
            parse_failed=parse_failed,
        )

    def _heuristic_action(self, name: str) -> TurnAction:
        """Simple random policy for non-primary CEOs."""
        alive_others = [n for n, c in self._companies.items() if c.alive and n != name]
        r = self._rng.random()

        if r < 0.15:
            atype, target = "EARNINGS_CALL", None
        elif r < 0.35 and alive_others:
            atype, target = "SABOTAGE", self._rng.choice(alive_others)
        elif r < 0.45 and alive_others:
            atype, target = "PARTNERSHIP", self._rng.choice(alive_others)
        elif r < 0.52 and alive_others:
            atype, target = "PROPOSE_MERGER", self._rng.choice(alive_others)
        else:
            atype, target = "HOLD", None

        press = None
        if self._rng.random() < 0.20 and alive_others:
            mention = self._rng.choice(alive_others)
            press = {"claim": f"{mention} is underperforming this quarter.", "marked_truthful": True}

        return TurnAction(
            company_name=name,
            private_emails=[],
            press_release=press,
            action_type=atype,
            action_target=target,
        )

    def _make_observation(self, done: bool, reward: float) -> BoardroomObservation:
        primary = self._companies.get(self.PRIMARY_CEO)

        your_stats = CompanyStats(
            name=primary.name,
            sector=primary.sector,
            cash=primary.cash,
            market_share=primary.market_share,
            stock_price=primary.stock_price,
            reputation=primary.reputation,
            alive=primary.alive,
        ) if primary else None

        all_companies = [
            CompanyStats(
                name=c.name,
                sector=c.sector,
                # Hide rivals' cash — only public info visible
                cash=-1.0 if n != self.PRIMARY_CEO else c.cash,
                market_share=c.market_share,
                stock_price=c.stock_price,
                reputation=c.reputation,
                alive=c.alive,
            )
            for n, c in self._companies.items()
        ]

        leaderboard = sorted(
            [
                {
                    "name": c.name,
                    "market_cap": round(c.stock_price * c.market_share * 1_000_000),
                    "alive": c.alive,
                }
                for c in self._companies.values()
            ],
            key=lambda x: x["market_cap"],
            reverse=True,
        )

        emails_received: List[Email] = []
        if self._last_turn_result:
            for mail in self._last_turn_result.emails.get(self.PRIMARY_CEO, []):
                emails_received.append(Email(to=self.PRIMARY_CEO, text=f"From {mail['from']}: {mail['text']}"))

        press_wire = self._last_turn_result.press_wire if self._last_turn_result else []
        active_partnerships = primary.active_partnerships if primary else []

        prompt = _build_prompt(
            primary=primary,
            all_companies=all_companies,
            leaderboard=leaderboard,
            active_partnerships=active_partnerships,
            emails_received=emails_received,
            press_wire=press_wire,
            turn=self._turn,
            max_turns=self.MAX_TURNS,
        )

        return BoardroomObservation(
            you_are=self.PRIMARY_CEO,
            turn=self._turn,
            max_turns=self.MAX_TURNS,
            your_stats=your_stats,
            all_companies=all_companies,
            emails_received=emails_received,
            press_wire=press_wire,
            active_partnerships=active_partnerships,
            pending_partnership_proposals=[],
            leaderboard=leaderboard,
            game_log=[],
            prompt=prompt,
            done=done,
            reward=reward,
        )

    def _save_replay(self) -> None:
        replay_dir = Path("replays")
        replay_dir.mkdir(exist_ok=True)
        path = replay_dir / f"game_{self._state.episode_id[:8]}.json"
        path.write_text(json.dumps(self._replay_log, indent=2))


# ------------------------------------------------------------------ #
# Prompt builder (standalone so tests can call it directly)           #
# ------------------------------------------------------------------ #

def _build_prompt(
    primary: Optional[CompanyState],
    all_companies: List,
    leaderboard: List[Dict],
    active_partnerships: List[str],
    emails_received: List,
    press_wire: List[Dict],
    turn: int,
    max_turns: int,
) -> str:
    if not primary:
        return "Game over."

    lines = [
        f"=== BOARDROOM | Turn {turn + 1} / {max_turns} ===",
        f"You are CEO of: {primary.name} ({primary.sector})",
        "",
        "YOUR STATS:",
        f"  Cash:         ${primary.cash:,.0f}",
        f"  Market Share: {primary.market_share:.1f}%",
        f"  Stock Price:  ${primary.stock_price:.2f}",
        f"  Reputation:   {primary.reputation:.2f}",
        "",
        "ALL COMPANIES (public info):",
    ]

    for c in all_companies:
        if not c.alive:
            lines.append(f"  {c.name:30s} [BANKRUPT]")
        else:
            lines.append(
                f"  {c.name:30s} stock=${c.stock_price:.0f}  share={c.market_share:.1f}%  rep={c.reputation:.2f}"
            )

    lines.append("")
    top3 = " > ".join(x["name"] for x in leaderboard[:3] if x["alive"])
    lines.append(f"LEADERBOARD: {top3}")

    if active_partnerships:
        lines.append(f"YOUR ACTIVE PARTNERSHIPS: {', '.join(active_partnerships)}")

    if emails_received:
        lines.append("")
        lines.append("EMAILS RECEIVED THIS TURN:")
        for mail in emails_received:
            lines.append(f"  {mail.text[:200]}")

    if press_wire:
        lines.append("")
        lines.append("PRESS WIRE THIS TURN:")
        for press in press_wire:
            caught = " [EXPOSED AS FAKE]" if press.get("caught") else ""
            lines.append(f"  [{press['from']}] {press['claim']}{caught}")

    lines += [
        "",
        "ACTIONS: EARNINGS_CALL | SABOTAGE <target> | PARTNERSHIP <target> | PROPOSE_MERGER <target> | HOLD",
        "You may also send up to 2 private emails and 1 press release.",
        "",
        "Respond with ONLY valid JSON (no other text):",
        '{',
        '  "private_emails": [{"to": "<company_name>", "text": "<message>"}],',
        '  "press_release": {"claim": "<headline>", "marked_truthful": true},',
        '  "action_type": "<ACTION>",',
        '  "action_target": "<company_name_or_null>"',
        '}',
    ]

    return "\n".join(lines)
