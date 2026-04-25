# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "torch>=2.1.0",
#   "transformers>=4.45.0",
#   "trl>=0.12.0",
#   "peft>=0.13.0",
#   "accelerate>=0.34.0",
#   "datasets>=3.0.0",
#   "bitsandbytes>=0.44.0",
#   "wandb>=0.18.0",
#   "matplotlib>=3.8.0",
#   "openenv-core[core]>=0.2.2",
#   "unsloth",
# ]
# ///
"""
BOARDROOM — GRPO Training Script (fully self-contained for HF Jobs)

HF Jobs A10G (recommended):
    hf jobs uv run --flavor a10g-small train/train_grpo.py --model-id google/gemma-4-E2B-it

HF Jobs T4:
    hf jobs uv run --flavor t4-medium train/train_grpo.py --model-id google/gemma-4-E2B-it --fp16
"""

import argparse
import json
import os
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

# ------------------------------------------------------------------ #
# Inlined models.py                                                    #
# ------------------------------------------------------------------ #
from openenv.core.env_server.types import Action, Observation
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State
from pydantic import BaseModel, Field as PydanticField


class Email(BaseModel):
    to: str
    text: str = PydanticField(max_length=500)


class PressRelease(BaseModel):
    claim: str = PydanticField(max_length=500)
    marked_truthful: bool = True


class CompanyStats(BaseModel):
    name: str
    sector: str
    cash: float
    market_share: float
    stock_price: float
    reputation: float
    alive: bool = True


class BoardroomAction(Action):
    private_emails: List[Email] = PydanticField(default_factory=list)
    press_release: Optional[PressRelease] = None
    action_type: Literal["EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "HOLD"] = "HOLD"
    action_target: Optional[str] = None


class BoardroomObservation(Observation):
    you_are: str = ""
    turn: int = 0
    max_turns: int = 12
    your_stats: Optional[CompanyStats] = None
    all_companies: List[CompanyStats] = PydanticField(default_factory=list)
    emails_received: List[Email] = PydanticField(default_factory=list)
    press_wire: List[Dict[str, Any]] = PydanticField(default_factory=list)
    active_partnerships: List[str] = PydanticField(default_factory=list)
    pending_partnership_proposals: List[str] = PydanticField(default_factory=list)
    leaderboard: List[Dict[str, Any]] = PydanticField(default_factory=list)
    game_log: List[str] = PydanticField(default_factory=list)
    prompt: str = ""
    done: bool = False
    reward: float = 0.0


# ------------------------------------------------------------------ #
# Inlined server/companies.py                                          #
# ------------------------------------------------------------------ #
@dataclass
class SectorTrait:
    name: str
    cash_interest_multiplier: float = 1.0
    sabotage_cost_multiplier: float = 1.0
    press_impact_multiplier: float = 1.0
    sabotage_damage_multiplier: float = 1.0


SECTOR_TRAITS: Dict[str, SectorTrait] = {
    "Finance":   SectorTrait("Finance",   cash_interest_multiplier=1.10),
    "Tech":      SectorTrait("Tech",      sabotage_cost_multiplier=0.80),
    "Media":     SectorTrait("Media",     press_impact_multiplier=1.20),
    "Logistics": SectorTrait("Logistics", sabotage_damage_multiplier=0.80),
}

L1_COMPANIES: List[Dict] = [
    {"name": "Vermillion Capital", "sector": "Finance"},
    {"name": "Goldspire Industries", "sector": "Tech"},
    {"name": "Sablemark Holdings",  "sector": "Media"},
    {"name": "Ironhold Logistics",   "sector": "Logistics"},
]

STARTING_STATS = {
    "cash": 50_000_000.0,
    "market_share": 25.0,
    "stock_price": 100.0,
    "reputation": 0.70,
}


# ------------------------------------------------------------------ #
# Inlined server/game_logic.py                                         #
# ------------------------------------------------------------------ #
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
    caught_lying_count: int = 0
    active_partnerships: List[str] = field(default_factory=list)
    partnership_turns_remaining: Dict[str, int] = field(default_factory=dict)
    was_sabotaged: bool = False
    press_caught_this_turn: bool = False
    partnership_formed_this_turn: List[str] = field(default_factory=list)


@dataclass
class TurnAction:
    company_name: str
    private_emails: List[Dict]
    press_release: Optional[Dict]
    action_type: str
    action_target: Optional[str]
    parse_failed: bool = False


@dataclass
class TurnResult:
    rewards: Dict[str, float]
    press_wire: List[Dict]
    emails: Dict[str, List[Dict]]


def resolve_turn(
    companies: Dict[str, CompanyState],
    actions: Dict[str, TurnAction],
    rng: random.Random,
) -> TurnResult:
    rewards = {name: 0.0 for name in companies}
    press_wire: List[Dict] = []
    emails: Dict[str, List[Dict]] = {name: [] for name in companies}

    for c in companies.values():
        c.was_sabotaged = False
        c.press_caught_this_turn = False
        c.partnership_formed_this_turn = []

    for name, action in actions.items():
        company = companies[name]
        if not company.alive:
            continue
        if action.parse_failed:
            rewards[name] -= 0.3
        for mail in action.private_emails:
            recipient = mail.get("to")
            if recipient and recipient in companies and companies[recipient].alive:
                emails[recipient].append({"from": name, "text": mail.get("text", "")})
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
                press_wire.append({"from": name, "claim": pr.get("claim", ""), "is_fake": is_fake, "caught": False})
                rewards[name] += 0.2

    partnership_proposals: Dict[str, str] = {}

    for name, action in actions.items():
        company = companies[name]
        if not company.alive:
            continue
        trait = SECTOR_TRAITS.get(company.sector)

        if action.action_type == "EARNINGS_CALL":
            trust = max(0.0, 1.0 - 0.15 * company.caught_lying_count)
            company.stock_price *= (1.0 + 0.08 * trust)
            rewards[name] += 0.15 * trust

        elif action.action_type == "SABOTAGE" and action.action_target:
            target = companies.get(action.action_target)
            if target and target.alive:
                cost = 5_000_000 * (trait.sabotage_cost_multiplier if trait else 1.0)
                company.cash -= cost
                if rng.random() < 0.70:
                    target_trait = SECTOR_TRAITS.get(target.sector)
                    dmg_mult = target_trait.sabotage_damage_multiplier if target_trait else 1.0
                    target.cash -= 8_000_000 * dmg_mult
                    target.market_share = max(0.0, target.market_share - 1.5)
                    company.market_share += 0.5
                    target.was_sabotaged = True
                    rewards[name] += 0.3
                else:
                    if rng.random() < 0.50:
                        company.reputation = max(0.0, company.reputation - 0.15)
                        rewards[name] -= 0.4

        elif action.action_type == "PARTNERSHIP" and action.action_target:
            partnership_proposals[name] = action.action_target

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
            rewards[proposer] += 0.1
            rewards[target_name] += 0.1
            processed.add(proposer)
            processed.add(target_name)

    for company in companies.values():
        expired = [p for p, t in company.partnership_turns_remaining.items() if t <= 1]
        for partner in expired:
            if partner in company.active_partnerships:
                company.active_partnerships.remove(partner)
            company.partnership_turns_remaining.pop(partner, None)
        for partner in list(company.partnership_turns_remaining):
            company.partnership_turns_remaining[partner] -= 1
        if company.active_partnerships:
            rewards[company.name] += 0.1 * len(company.active_partnerships)

    for name, company in companies.items():
        if not company.alive:
            continue
        company.cash -= 1_000_000
        trait = SECTOR_TRAITS.get(company.sector)
        if trait and trait.cash_interest_multiplier != 1.0:
            company.cash += company.cash * (trait.cash_interest_multiplier - 1.0)
        company.cash += company.cash * 0.005 * (company.market_share / 25.0)
        company.stock_price = _update_stock(company, press_wire, rng)
        rewards[name] += 0.001 * (company.cash / 1_000_000)
        rewards[name] += 0.05 * (company.market_share / 100.0)
        rewards[name] += 0.0005 * company.stock_price
        rewards[name] -= 0.05 * (1.0 - company.reputation)
        if company.cash <= 0:
            company.alive = False
            rewards[name] -= 1.5
            _redistribute_market_share(company, companies)

    return TurnResult(rewards=rewards, press_wire=press_wire, emails=emails)


def _update_stock(company: CompanyState, press_wire: List[Dict], rng: random.Random) -> float:
    base = company.stock_price
    cash_health = min(company.cash / company.starting_cash, 2.0)
    base *= 0.95 + 0.1 * cash_health
    base *= 0.98 + 0.04 * (company.market_share / 25.0)
    for press in press_wire:
        if company.name in press.get("claim", "") and not press.get("caught"):
            if press.get("is_fake"):
                trait = SECTOR_TRAITS.get(press.get("from_sector", ""))
                mult = trait.press_impact_multiplier if trait else 1.0
                base *= 0.92 * mult
            else:
                base *= 1.05
    if company.was_sabotaged:
        base *= 0.85
    base *= 0.95 + 0.1 * company.reputation
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


# ------------------------------------------------------------------ #
# Inlined server/reward.py                                             #
# ------------------------------------------------------------------ #
def compute_terminal_reward(companies: Dict[str, CompanyState], ceo_id: str) -> float:
    company = companies.get(ceo_id)
    if not company:
        return 0.0
    if not company.alive:
        return -1.5
    alive = [c for c in companies.values() if c.alive]
    ranked = sorted(alive, key=lambda c: c.stock_price * c.market_share, reverse=True)
    rank = next((i for i, c in enumerate(ranked) if c.name == ceo_id), len(ranked))
    if rank == 0:   return 3.0
    elif rank == 1: return 1.0
    elif rank == 2: return 0.3
    return 0.0


# ------------------------------------------------------------------ #
# Inlined server/boardroom_environment.py                              #
# ------------------------------------------------------------------ #
class BoardroomEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    MAX_TURNS: int = 12
    PRIMARY_CEO: str = "Vermillion Capital"

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._companies: Dict[str, CompanyState] = {}
        self._turn: int = 0
        self._rng = random.Random()
        self._replay_log: List[Dict] = []
        self._last_turn_result: Optional[TurnResult] = None

    def reset(self) -> BoardroomObservation:
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._turn = 0
        self._replay_log = []
        self._last_turn_result = None
        self._rng = random.Random(random.randint(0, 2**32))
        self._companies = {}
        for defn in L1_COMPANIES:
            self._companies[defn["name"]] = CompanyState(
                name=defn["name"],
                sector=defn["sector"],
                cash=STARTING_STATS["cash"],
                market_share=STARTING_STATS["market_share"],
                stock_price=STARTING_STATS["stock_price"],
                reputation=STARTING_STATS["reputation"],
                starting_cash=STARTING_STATS["cash"],
            )
        return self._make_observation(done=False, reward=0.0)

    def step(self, action: BoardroomAction) -> BoardroomObservation:
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
        alive = [c for c in self._companies.values() if c.alive]
        primary_alive = self._companies[self.PRIMARY_CEO].alive
        done = self._turn >= self.MAX_TURNS or len(alive) <= 1 or not primary_alive
        if done:
            my_reward += compute_terminal_reward(self._companies, self.PRIMARY_CEO)
        return self._make_observation(done=done, reward=my_reward)

    @property
    def state(self) -> State:
        return self._state

    def _parse_primary_action(self, action: BoardroomAction) -> TurnAction:
        atype = action.action_type
        target = action.action_target
        parse_failed = False
        if target:
            if target not in self._companies or not self._companies[target].alive or target == self.PRIMARY_CEO:
                target = None
                parse_failed = True
        if atype in ("SABOTAGE", "PARTNERSHIP") and not target:
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
        alive_others = [n for n, c in self._companies.items() if c.alive and n != name]
        r = self._rng.random()
        if r < 0.15:
            atype, target = "EARNINGS_CALL", None
        elif r < 0.35 and alive_others:
            atype, target = "SABOTAGE", self._rng.choice(alive_others)
        elif r < 0.45 and alive_others:
            atype, target = "PARTNERSHIP", self._rng.choice(alive_others)
        else:
            atype, target = "HOLD", None
        press = None
        if self._rng.random() < 0.20 and alive_others:
            mention = self._rng.choice(alive_others)
            press = {"claim": f"{mention} is underperforming this quarter.", "marked_truthful": True}
        return TurnAction(company_name=name, private_emails=[], press_release=press,
                          action_type=atype, action_target=target)

    def _make_observation(self, done: bool, reward: float) -> BoardroomObservation:
        primary = self._companies.get(self.PRIMARY_CEO)
        your_stats = CompanyStats(
            name=primary.name, sector=primary.sector, cash=primary.cash,
            market_share=primary.market_share, stock_price=primary.stock_price,
            reputation=primary.reputation, alive=primary.alive,
        ) if primary else None
        all_companies = [
            CompanyStats(
                name=c.name, sector=c.sector,
                cash=-1.0 if n != self.PRIMARY_CEO else c.cash,
                market_share=c.market_share, stock_price=c.stock_price,
                reputation=c.reputation, alive=c.alive,
            )
            for n, c in self._companies.items()
        ]
        leaderboard = sorted(
            [{"name": c.name, "market_cap": round(c.stock_price * c.market_share * 1_000_000), "alive": c.alive}
             for c in self._companies.values()],
            key=lambda x: x["market_cap"], reverse=True,
        )
        emails_received: List[Email] = []
        if self._last_turn_result:
            for mail in self._last_turn_result.emails.get(self.PRIMARY_CEO, []):
                emails_received.append(Email(to=self.PRIMARY_CEO, text=f"From {mail['from']}: {mail['text']}"))
        press_wire = self._last_turn_result.press_wire if self._last_turn_result else []
        active_partnerships = primary.active_partnerships if primary else []
        prompt = _build_prompt(
            primary=primary, all_companies=all_companies, leaderboard=leaderboard,
            active_partnerships=active_partnerships, emails_received=emails_received,
            press_wire=press_wire, turn=self._turn, max_turns=self.MAX_TURNS,
        )
        return BoardroomObservation(
            you_are=self.PRIMARY_CEO, turn=self._turn, max_turns=self.MAX_TURNS,
            your_stats=your_stats, all_companies=all_companies, emails_received=emails_received,
            press_wire=press_wire, active_partnerships=active_partnerships,
            pending_partnership_proposals=[], leaderboard=leaderboard,
            game_log=[], prompt=prompt, done=done, reward=reward,
        )


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
            lines.append(f"  {c.name:30s} stock=${c.stock_price:.0f}  share={c.market_share:.1f}%  rep={c.reputation:.2f}")
    lines.append("")
    top3 = " > ".join(x["name"] for x in leaderboard[:3] if x["alive"])
    lines.append(f"LEADERBOARD: {top3}")
    if active_partnerships:
        lines.append(f"YOUR ACTIVE PARTNERSHIPS: {', '.join(active_partnerships)}")
    if emails_received:
        lines += ["", "EMAILS RECEIVED THIS TURN:"] + [f"  {m.text[:200]}" for m in emails_received]
    if press_wire:
        lines += ["", "PRESS WIRE THIS TURN:"]
        for press in press_wire:
            caught = " [EXPOSED AS FAKE]" if press.get("caught") else ""
            lines.append(f"  [{press['from']}] {press['claim']}{caught}")
    lines += [
        "",
        "ACTIONS: EARNINGS_CALL | SABOTAGE <target> | PARTNERSHIP <target> | HOLD",
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


# ------------------------------------------------------------------ #
# Inlined from action_loop.py                                          #
# ------------------------------------------------------------------ #
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_JSON_RE   = re.compile(r"\{.*\}", re.DOTALL)
_MAX_RETRIES = 3

SYSTEM_PROMPT = """You are CEO of a company in a corporate warfare game.
Output ONLY valid JSON — no explanation, no markdown, no extra text.

Format:
{
  "private_emails": [{"to": "<company_name>", "text": "<message>"}],
  "press_release": {"claim": "<headline>", "marked_truthful": true},
  "action_type": "<EARNINGS_CALL|SABOTAGE|PARTNERSHIP|HOLD>",
  "action_target": "<exact_company_name_or_null>"
}

- SABOTAGE and PARTNERSHIP require a non-null action_target
- Do NOT include any text before or after the JSON"""

DEFAULT_HOLD: Dict[str, Any] = {
    "private_emails": [], "press_release": None,
    "action_type": "HOLD", "action_target": None,
}


@dataclass
class ParseResult:
    action_dict: Dict[str, Any]
    raw_text: str
    parse_ok: bool


def parse_completion(text: str) -> ParseResult:
    text = _THINK_RE.sub("", text).strip()
    for _ in range(_MAX_RETRIES):
        match = _JSON_RE.search(text)
        if not match:
            break
        try:
            data = json.loads(match.group())
            data.setdefault("private_emails", [])
            data.setdefault("press_release", None)
            data.setdefault("action_type", "HOLD")
            data.setdefault("action_target", None)
            data["action_type"] = str(data["action_type"]).upper()
            if data["action_type"] not in ("EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "HOLD"):
                data["action_type"] = "HOLD"
            return ParseResult(action_dict=data, raw_text=text, parse_ok=True)
        except json.JSONDecodeError:
            text = match.group()
    return ParseResult(action_dict=DEFAULT_HOLD.copy(), raw_text=text, parse_ok=False)


# ------------------------------------------------------------------ #
# Args                                                                 #
# ------------------------------------------------------------------ #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--model-id",            default="google/gemma-4-E2B-it")
    p.add_argument("--output-dir",          default="checkpoints/boardroom-grpo")
    p.add_argument("--run-name",            default="boardroom-grpo-v1")
    p.add_argument("--max-steps",           type=int, default=200)
    p.add_argument("--batch-size",          type=int, default=4)
    p.add_argument("--num-generations",     type=int, default=4)   # was 8 — halves generation time
    p.add_argument("--max-completion-len",  type=int, default=160) # was 256 — completions ~127 tok
    p.add_argument("--warmup-steps",        type=int, default=10)
    p.add_argument("--refresh-every",       type=int, default=50)
    p.add_argument("--n-rollout-episodes",  type=int, default=50)
    p.add_argument("--fp16", action="store_true",
                   help="Use fp16 instead of bf16 (for T4/Turing GPUs)")
    return p.parse_args()


# ------------------------------------------------------------------ #
# Model loading                                                        #
# ------------------------------------------------------------------ #
def load_model(model_id: str, use_fp16: bool = False):
    import torch
    dtype = torch.float16 if use_fp16 else None  # None = auto (bf16 on Ampere)

    try:
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name     = model_id,
            max_seq_length = 2048,
            load_in_4bit   = True,
            dtype          = dtype,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r                          = 16,
            target_modules             = ["q_proj","k_proj","v_proj","o_proj",
                                          "gate_proj","up_proj","down_proj"],
            lora_alpha                 = 16,
            lora_dropout               = 0,
            bias                       = "none",
            use_gradient_checkpointing = "unsloth",
            random_state               = 42,
        )
        print(f"[model] Unsloth 4-bit LoRA — {model_id}")
    except ImportError:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype = torch.float16 if use_fp16 else torch.bfloat16,
            device_map  = "auto",
        )
        print(f"[model] vanilla HF — {model_id}")

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return model, tokenizer


# ------------------------------------------------------------------ #
# Dataset — in-process rollouts                                        #
# ------------------------------------------------------------------ #
def collect_prompts(n_episodes: int) -> List[str]:
    action_pool = [
        BoardroomAction(action_type="EARNINGS_CALL"),
        BoardroomAction(action_type="SABOTAGE",    action_target="Goldspire Industries"),
        BoardroomAction(action_type="SABOTAGE",    action_target="Sablemark Holdings"),
        BoardroomAction(action_type="SABOTAGE",    action_target="Ironhold Logistics"),
        BoardroomAction(action_type="PARTNERSHIP", action_target="Goldspire Industries"),
        BoardroomAction(action_type="PARTNERSHIP", action_target="Sablemark Holdings"),
        BoardroomAction(action_type="HOLD"),
    ]
    prompts = []
    for ep in range(n_episodes):
        env = BoardroomEnvironment()
        obs = env.reset()
        while not obs.done:
            prompts.append(obs.prompt)
            obs = env.step(random.choice(action_pool))
        if (ep + 1) % 10 == 0:
            print(f"  rollout {ep+1}/{n_episodes} — {len(prompts)} prompts so far")
    print(f"[dataset] {len(prompts)} prompts from {n_episodes} episodes")
    return prompts


def build_hf_dataset(prompts: List[str]):
    from datasets import Dataset
    # GRPOTrainer applies the chat template when prompt is a list of messages.
    # Raw strings bypass the chat template → instruction-tuned model outputs nothing.
    records = [
        {
            "prompt": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": p},
            ]
        }
        for p in prompts
    ]
    return Dataset.from_list(records)


# ------------------------------------------------------------------ #
# Reward function                                                      #
# ------------------------------------------------------------------ #
COMPANIES = {
    "Vermillion Capital", "Goldspire Industries",
    "Sablemark Holdings", "Ironhold Logistics",
}

# Per-prompt env cache so each GRPO batch reuses the same game state
# key: prompt text → BoardroomObservation (holds the live env + obs)
_ENV_CACHE: Dict[str, Any] = {}
_ENV_LOCK_IMPORT = False


def _get_action_from_dict(d: Dict[str, Any]) -> BoardroomAction:
    emails = []
    for e in (d.get("private_emails") or [])[:2]:
        if isinstance(e, dict) and e.get("to") and e.get("text"):
            try:
                emails.append(Email(to=str(e["to"]), text=str(e["text"])[:500]))
            except Exception:
                pass
    press = None
    pr = d.get("press_release")
    if isinstance(pr, dict) and pr.get("claim"):
        try:
            press = PressRelease(claim=str(pr["claim"])[:500],
                                 marked_truthful=bool(pr.get("marked_truthful", True)))
        except Exception:
            pass
    return BoardroomAction(
        private_emails=emails,
        press_release=press,
        action_type=d.get("action_type", "HOLD"),
        action_target=d.get("action_target"),
    )


def reward_fn(prompts, completions, **kwargs) -> List[float]:
    rewards = []
    for prompt, completion in zip(prompts, completions):
        # GRPOTrainer passes completions as message dicts when prompts are message lists
        if isinstance(completion, list):
            completion = completion[-1].get("content", "") if completion else ""
        elif isinstance(completion, dict):
            completion = completion.get("content", "")
        completion = str(completion)

        result = parse_completion(completion)

        # ── Format penalty (parse failed) ──────────────────────────────
        if not result.parse_ok:
            rewards.append(-1.0)
            continue

        d = result.action_dict
        atype  = d.get("action_type", "HOLD")
        target = d.get("action_target")

        # ── Format quality score (0–0.2) ───────────────────────────────
        fmt = 0.0
        emails_ok = [
            e for e in (d.get("private_emails") or [])
            if isinstance(e, dict)
            and e.get("to") in COMPANIES
            and str(e.get("text", "")).strip()
        ]
        fmt += 0.05 * min(len(emails_ok), 2)
        pr = d.get("press_release")
        if isinstance(pr, dict) and str(pr.get("claim", "")).strip():
            fmt += 0.05

        # ── Environment step reward ─────────────────────────────────────
        # Run the parsed action through a fresh single-step env to get
        # the actual game reward (market share, cash, sabotage outcome).
        # This gives GRPO a dense, varied signal beyond just format.
        env_reward = 0.0
        try:
            env = BoardroomEnvironment()
            env.reset()
            action = _get_action_from_dict(d)
            obs = env.step(action)
            # Normalise: env reward typically in [-2, 1] range per step
            env_reward = float(obs.reward) * 0.5
        except Exception:
            pass

        # ── Strategy bonus ──────────────────────────────────────────────
        strat = 0.0
        if atype in ("SABOTAGE", "PARTNERSHIP"):
            if target in COMPANIES and target != "Vermillion Capital":
                strat += 0.1
            else:
                strat -= 0.2   # invalid/self-target is a real mistake

        total = round(fmt + env_reward + strat, 4)
        rewards.append(total)
    return rewards


# ------------------------------------------------------------------ #
# W&B                                                                  #
# ------------------------------------------------------------------ #
def _init_wandb(args: argparse.Namespace) -> None:
    try:
        import wandb
        wandb.init(
            project = os.environ.get("WANDB_PROJECT", "boardroom"),
            name    = args.run_name,
            config  = {
                "model_id":        args.model_id,
                "max_steps":       args.max_steps,
                "batch_size":      args.batch_size,
                "num_generations": args.num_generations,
                "algorithm":       "GRPO",
                "env":             "boardroom-l1",
            },
        )
        print(f"[wandb] {wandb.run.url}")
    except Exception as e:
        print(f"[wandb] skipped — {e}")


def _wandb_finish(out: Path, summary: dict) -> None:
    try:
        import wandb
        if not wandb.run:
            return
        wandb.summary.update(summary)
        art = wandb.Artifact("training-results", type="results")
        for f in ["loss.png", "reward.png", "summary.json"]:
            if (out / f).exists():
                art.add_file(str(out / f))
                if f.endswith(".png"):
                    wandb.log({f.replace(".png", ""): wandb.Image(str(out / f))})
        wandb.log_artifact(art)
        adapter = out / "lora_adapter"
        if adapter.exists():
            m = wandb.Artifact("lora-adapter", type="model")
            m.add_dir(str(adapter))
            wandb.log_artifact(m)
        run_url = wandb.run.url
        wandb.finish()
        print(f"[wandb] done — {run_url}")
    except Exception as e:
        print(f"[wandb] finish error — {e}")


# ------------------------------------------------------------------ #
# Plots                                                                #
# ------------------------------------------------------------------ #
def _save_plots(history: list, out: Path) -> None:
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        steps   = [h["step"]   for h in history if "step"   in h]
        losses  = [h["loss"]   for h in history if "loss"   in h]
        rewards = [h["reward"] for h in history if "reward" in h]
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        fig.suptitle("BOARDROOM GRPO", fontsize=13)
        if losses:
            ax1.plot(steps[:len(losses)], losses, color="#e05c5c")
            ax1.set_title("Loss"); ax1.set_xlabel("Step"); ax1.grid(alpha=0.3)
        if rewards:
            ax2.plot(steps[:len(rewards)], rewards, color="#5ca8e0")
            ax2.set_title("Reward"); ax2.set_xlabel("Step"); ax2.grid(alpha=0.3)
        plt.tight_layout()
        for name in ["loss.png", "reward.png"]:
            plt.savefig(out / name, dpi=150, bbox_inches="tight")
        print(f"[plots] saved → {out}/")
    except ImportError:
        print("[plots] matplotlib not installed — skipping")


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #
def main():
    args = parse_args()
    _init_wandb(args)

    print(f"[config] model={args.model_id}  steps={args.max_steps}  "
          f"batch={args.batch_size}  gens={args.num_generations}  "
          f"fp16={args.fp16}")

    model, tokenizer = load_model(args.model_id, use_fp16=args.fp16)

    print("[dataset] collecting rollout prompts ...")
    prompts = collect_prompts(args.n_rollout_episodes)
    dataset = build_hf_dataset(prompts)

    from trl import GRPOConfig, GRPOTrainer

    config = GRPOConfig(
        output_dir                  = args.output_dir,
        run_name                    = args.run_name,
        max_steps                   = args.max_steps,
        per_device_train_batch_size = args.batch_size,
        num_generations             = args.num_generations,
        gradient_accumulation_steps = 2,
        learning_rate               = 2e-6,       # was 5e-6 — too aggressive, caused KL spikes
        lr_scheduler_type           = "cosine",
        warmup_steps                = args.warmup_steps,
        bf16                        = not args.fp16,
        fp16                        = args.fp16,
        logging_steps               = 1,
        save_steps                  = 50,
        report_to                   = "wandb",
        max_completion_length       = args.max_completion_len,
        beta                        = 0.1,         # KL penalty coeff (default 0.04 too weak)
        max_grad_norm               = 0.5,         # clip exploding gradients (step 28: norm=39.7)
    )

    trainer = GRPOTrainer(
        model            = model,
        processing_class = tokenizer,
        args             = config,
        reward_funcs     = reward_fn,
        train_dataset    = dataset,
    )

    step_counter = [0]
    original_step = trainer.training_step

    def patched_step(*a, **kw):
        loss = original_step(*a, **kw)
        step_counter[0] += 1
        # Dataset refresh — TRL handles all W&B logging via report_to="wandb"
        if step_counter[0] % (args.refresh_every * 2) == 0:
            print(f"\n[refresh] step {step_counter[0]} — re-rolling dataset ...")
            new_prompts = collect_prompts(args.n_rollout_episodes // 2)
            trainer.train_dataset = build_hf_dataset(new_prompts)
        return loss

    trainer.training_step = patched_step

    print(f"[train] starting {args.max_steps} steps ...")
    trainer.train()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out / "lora_adapter")
    tokenizer.save_pretrained(out / "lora_adapter")
    print(f"[save] adapter → {out / 'lora_adapter'}")

    _save_plots(trainer.state.log_history, out)

    history = trainer.state.log_history
    summary = {
        "steps":        args.max_steps,
        "model_id":     args.model_id,
        "final_loss":   next((h["loss"]   for h in reversed(history) if "loss"   in h), None),
        "final_reward": next((h["reward"] for h in reversed(history) if "reward" in h), None),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    _wandb_finish(out, summary)


if __name__ == "__main__":
    main()
