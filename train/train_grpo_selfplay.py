# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "torch>=2.1.0",
#   "transformers>=4.45.0",
#   "trl>=0.27.0",
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
BOARDROOM — Self-Play GRPO Training Script

All 7 companies use the same model. Primary company rotates randomly each
episode so the model learns a general strategy, not just one company's role.
GRPO loss is computed only on the primary company's completion; the other 6
completions are inference-only (no grad).

HF Jobs L40S:
    hf jobs uv run --flavor l40sx1 \\
      --env WANDB_API_KEY=... --env HF_TOKEN=... \\
      train/train_grpo_selfplay.py \\
      --hub-model-id nothr/boardroom-grpo-selfplay
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

from openenv.core.env_server.types import Action, Observation
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State
from pydantic import BaseModel, Field as PydanticField, field_validator


# ------------------------------------------------------------------ #
# Models (identical to train_grpo.py)                                  #
# ------------------------------------------------------------------ #
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
    action_type: Literal["EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "PROPOSE_MERGER", "HOLD"] = "HOLD"
    action_target: Optional[str] = None

    @field_validator("private_emails", mode="before")
    @classmethod
    def coerce_emails(cls, v):
        if isinstance(v, str):
            try:
                import json as _j; v = _j.loads(v)
            except Exception:
                return []
        return v if isinstance(v, list) else []


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
# Companies + sector traits (identical to train_grpo.py)              #
# ------------------------------------------------------------------ #
@dataclass
class SectorTrait:
    name: str
    cash_interest_multiplier: float = 1.0
    sabotage_cost_multiplier: float = 1.0
    press_impact_multiplier: float = 1.0
    sabotage_damage_multiplier: float = 1.0
    partnership_bonus_multiplier: float = 1.0


SECTOR_TRAITS: Dict[str, SectorTrait] = {
    "Finance":    SectorTrait("Finance",    cash_interest_multiplier=1.10),
    "Tech":       SectorTrait("Tech",       sabotage_cost_multiplier=0.80),
    "Media":      SectorTrait("Media",      press_impact_multiplier=1.20),
    "Logistics":  SectorTrait("Logistics",  sabotage_damage_multiplier=0.80),
    "Telecom":    SectorTrait("Telecom",    partnership_bonus_multiplier=1.25),
    "Energy":     SectorTrait("Energy",     cash_interest_multiplier=1.05),
    "Healthcare": SectorTrait("Healthcare", sabotage_damage_multiplier=0.75),
}

L2_COMPANIES: List[Dict] = [
    {"name": "Vermillion Capital",   "sector": "Finance"},
    {"name": "Goldspire Industries", "sector": "Tech"},
    {"name": "Sablemark Holdings",   "sector": "Media"},
    {"name": "Ironhold Logistics",   "sector": "Logistics"},
    {"name": "Nexbridge Telecom",    "sector": "Telecom"},
    {"name": "Solstice Energy",      "sector": "Energy"},
    {"name": "Medvault Health",      "sector": "Healthcare"},
]
ALL_COMPANY_NAMES = [c["name"] for c in L2_COMPANIES]

MARKET_SHARE_BASELINE: float = 100.0 / len(L2_COMPANIES)

STARTING_STATS = {
    "cash": 50_000_000.0,
    "market_share": MARKET_SHARE_BASELINE,
    "stock_price": 100.0,
    "reputation": 0.70,
}


# ------------------------------------------------------------------ #
# Game logic (identical to train_grpo.py)                             #
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


def resolve_turn(companies, actions, rng):
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
    merger_proposals: Dict[str, str] = {}

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

        elif action.action_type == "PROPOSE_MERGER" and action.action_target:
            t = action.action_target
            if t in companies and companies[t].alive and t != name:
                merger_proposals[name] = t

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
            companies[proposer].reputation = max(0.0, companies[proposer].reputation - 0.25)
            rewards[proposer] -= 0.5
            companies[proposer].market_share = max(0.0, companies[proposer].market_share - 1.0)
            target.market_share += 1.0
            target.reputation = min(1.0, target.reputation + 0.05)
            rewards[target_name] += 0.15
            processed_mergers.add(target_name)

    for company in companies.values():
        expired = [p for p, t in company.partnership_turns_remaining.items() if t <= 1]
        for partner in expired:
            if partner in company.active_partnerships:
                company.active_partnerships.remove(partner)
            company.partnership_turns_remaining.pop(partner, None)
        for partner in list(company.partnership_turns_remaining):
            company.partnership_turns_remaining[partner] -= 1
        alive_partners = [p for p in company.active_partnerships
                          if companies.get(p) and companies[p].alive]
        if alive_partners:
            trait = SECTOR_TRAITS.get(company.sector)
            bonus_mult = trait.partnership_bonus_multiplier if trait else 1.0
            rewards[company.name] += 0.1 * bonus_mult * len(alive_partners)

    for name, company in companies.items():
        if not company.alive:
            continue
        company.cash -= 1_000_000
        trait = SECTOR_TRAITS.get(company.sector)
        if trait and trait.cash_interest_multiplier != 1.0:
            company.cash += company.cash * (trait.cash_interest_multiplier - 1.0)
        company.cash += company.cash * 0.005 * (company.market_share / MARKET_SHARE_BASELINE)
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


def _update_stock(company, press_wire, rng):
    base = company.stock_price
    cash_health = min(company.cash / company.starting_cash, 2.0)
    base *= 0.95 + 0.1 * cash_health
    base *= 0.98 + 0.04 * (company.market_share / MARKET_SHARE_BASELINE)
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


def _redistribute_market_share(bankrupt, companies):
    alive = [c for c in companies.values() if c.alive and c.name != bankrupt.name]
    if not alive:
        return
    share_each = bankrupt.market_share / len(alive)
    for c in alive:
        c.market_share += share_each
    bankrupt.market_share = 0.0


def compute_terminal_reward(companies, ceo_id):
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
# Self-play environment — key difference from base env                #
# ------------------------------------------------------------------ #
class SelfPlayBoardroomEnvironment:
    """
    Thin game-state holder for one turn of self-play.
    All 7 companies are played by the model; this class just holds state
    and exposes per-company prompts + a multi-action step.
    """
    MAX_TURNS: int = 12

    def __init__(self):
        self._companies: Dict[str, CompanyState] = {}
        self._turn: int = 0
        self._rng = random.Random()
        self._last_result: Optional[TurnResult] = None
        self.primary_ceo: str = ALL_COMPANY_NAMES[0]

    def reset(self, primary_ceo: Optional[str] = None) -> None:
        self._rng = random.Random(random.randint(0, 2**32))
        self._turn = 0
        self._last_result = None
        self.primary_ceo = primary_ceo or random.choice(ALL_COMPANY_NAMES)
        self._companies = {
            defn["name"]: CompanyState(
                name=defn["name"], sector=defn["sector"],
                cash=STARTING_STATS["cash"], market_share=STARTING_STATS["market_share"],
                stock_price=STARTING_STATS["stock_price"], reputation=STARTING_STATS["reputation"],
                starting_cash=STARTING_STATS["cash"],
            )
            for defn in L2_COMPANIES
        }

    def get_company_prompt(self, company_name: str) -> str:
        """Return the text observation for any company (used to build model inputs)."""
        primary = self._companies.get(company_name)
        if not primary or not primary.alive:
            return "Game over."

        all_companies_stats = [
            CompanyStats(
                name=c.name, sector=c.sector,
                cash=c.cash if n == company_name else -1.0,
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
        emails_received = []
        if self._last_result:
            for mail in self._last_result.emails.get(company_name, []):
                emails_received.append(Email(to=company_name, text=f"From {mail['from']}: {mail['text']}"))
        press_wire = self._last_result.press_wire if self._last_result else []

        return _build_prompt(
            primary=primary, all_companies=all_companies_stats,
            leaderboard=leaderboard, active_partnerships=primary.active_partnerships,
            emails_received=emails_received, press_wire=press_wire,
            turn=self._turn, max_turns=self.MAX_TURNS,
        )

    def step_all_companies(self, actions: Dict[str, TurnAction]) -> Dict[str, float]:
        """Resolve one turn with all 7 companies' actions. Returns per-company rewards."""
        result = resolve_turn(self._companies, actions, self._rng)
        self._last_result = result
        self._turn += 1

        alive = [c for c in self._companies.values() if c.alive]
        done = self._turn >= self.MAX_TURNS or len(alive) <= 1

        rewards = dict(result.rewards)
        if done:
            for name in self._companies:
                rewards[name] = rewards.get(name, 0.0) + compute_terminal_reward(self._companies, name)

        return rewards

    def parse_action_for(self, action_dict: Dict[str, Any], company_name: str) -> TurnAction:
        """Validate and convert an action dict for a specific company."""
        atype = str(action_dict.get("action_type", "HOLD")).upper()
        target = action_dict.get("action_target")
        parse_failed = False

        if atype not in ("EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "PROPOSE_MERGER", "HOLD"):
            atype = "HOLD"
            parse_failed = True

        if target:
            if target not in self._companies or not self._companies[target].alive or target == company_name:
                target = None
                parse_failed = True

        if atype in ("SABOTAGE", "PARTNERSHIP", "PROPOSE_MERGER") and not target:
            atype = "HOLD"
            parse_failed = True

        emails = []
        for e in (action_dict.get("private_emails") or [])[:2]:
            if isinstance(e, dict) and e.get("to") and e.get("text"):
                try:
                    emails.append({"to": str(e["to"]), "text": str(e["text"])[:500]})
                except Exception:
                    pass

        press = None
        pr = action_dict.get("press_release")
        if isinstance(pr, dict) and pr.get("claim"):
            press = {"claim": str(pr["claim"])[:500], "marked_truthful": bool(pr.get("marked_truthful", True))}

        return TurnAction(
            company_name=company_name, private_emails=emails, press_release=press,
            action_type=atype, action_target=target, parse_failed=parse_failed,
        )


def _build_prompt(primary, all_companies, leaderboard, active_partnerships,
                  emails_received, press_wire, turn, max_turns):
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


# ------------------------------------------------------------------ #
# Parse helpers                                                        #
# ------------------------------------------------------------------ #
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_JSON_RE   = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = """You are CEO of a company in a corporate warfare game.
Output ONLY valid JSON — no explanation, no markdown, no extra text.

Format:
{
  "private_emails": [{"to": "<company_name>", "text": "<message>"}],
  "press_release": {"claim": "<headline>", "marked_truthful": true},
  "action_type": "<EARNINGS_CALL|SABOTAGE|PARTNERSHIP|PROPOSE_MERGER|HOLD>",
  "action_target": "<exact_company_name_or_null>"
}

- SABOTAGE, PARTNERSHIP, and PROPOSE_MERGER require a non-null action_target
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
    for _ in range(3):
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
            if data["action_type"] not in ("EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "PROPOSE_MERGER", "HOLD"):
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
    p.add_argument("--model-id",           default="google/gemma-4-E2B-it")
    p.add_argument("--output-dir",         default="checkpoints/boardroom-selfplay")
    p.add_argument("--run-name",           default="boardroom-selfplay-v1")
    p.add_argument("--max-steps",          type=int, default=200)
    p.add_argument("--batch-size",         type=int, default=4)
    p.add_argument("--num-generations",    type=int, default=4)
    p.add_argument("--max-completion-len", type=int, default=128)
    p.add_argument("--warmup-steps",       type=int, default=10)
    p.add_argument("--refresh-every",      type=int, default=50)
    p.add_argument("--n-seeds",            type=int, default=50)
    p.add_argument("--fp16",               action="store_true")
    p.add_argument("--hub-model-id",       default=None)
    return p.parse_args()


# ------------------------------------------------------------------ #
# Model loading (identical to train_grpo.py)                          #
# ------------------------------------------------------------------ #
def load_model(model_id: str, use_fp16: bool = False):
    import torch
    dtype = torch.float16 if use_fp16 else None

    try:
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_id, max_seq_length=2048, load_in_4bit=True, dtype=dtype,
        )
        model = FastLanguageModel.get_peft_model(
            model, r=16,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            lora_alpha=16, lora_dropout=0, bias="none",
            use_gradient_checkpointing="unsloth", random_state=42,
        )
        print(f"[model] Unsloth 4-bit LoRA — {model_id}")
    except ImportError:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if use_fp16 else torch.bfloat16,
            device_map="auto",
        )
        print(f"[model] vanilla HF — {model_id}")

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return model, tokenizer


# ------------------------------------------------------------------ #
# Dataset — one seed prompt per company per episode                   #
# ------------------------------------------------------------------ #
def build_seed_dataset(n_seeds: int):
    """
    Each record is one company's initial game prompt.
    n_seeds episodes × 7 companies = 7*n_seeds records total.
    The model learns to play any company, not just Vermillion.
    """
    from datasets import Dataset
    records = []
    for _ in range(n_seeds):
        env = SelfPlayBoardroomEnvironment()
        env.reset()
        for company_name in ALL_COMPANY_NAMES:
            records.append({
                "prompt":  env.get_company_prompt(company_name),
                "company": company_name,
            })
    return Dataset.from_list(records)


# ------------------------------------------------------------------ #
# Self-play rollout_func                                               #
# ------------------------------------------------------------------ #
def make_selfplay_rollout_func(tokenizer, use_fp16: bool):
    import torch
    import torch.nn.functional as F

    def _generate_one(model, tokenizer, prompt_text: str, device, max_new: int):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt_text},
        ]
        chat = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        enc = tokenizer(text=chat, return_tensors="pt")
        input_ids     = enc.input_ids.to(device)
        attention_mask = torch.ones_like(input_ids)

        with torch.no_grad():
            out = model.generate(
                input_ids,
                attention_mask          = attention_mask,
                max_new_tokens          = max_new,
                do_sample               = True,
                temperature             = 0.8,
                pad_token_id            = tokenizer.eos_token_id,
                return_dict_in_generate = True,
                output_scores           = True,
            )

        comp_ids    = out.sequences[0][input_ids.shape[1]:]
        comp_text   = tokenizer.decode(comp_ids, skip_special_tokens=True)
        logprobs    = [
            F.log_softmax(score[0], dim=-1)[comp_ids[i]].item()
            for i, score in enumerate(out.scores) if i < len(comp_ids)
        ]
        return input_ids[0].tolist(), comp_ids.tolist(), logprobs, comp_text

    def rollout_func(prompts: List[str], trainer) -> Dict[str, List]:
        model  = trainer.model
        device = next(model.parameters()).device
        max_new = 128

        all_prompt_ids:     List[List[int]]   = []
        all_completion_ids: List[List[int]]   = []
        all_logprobs:       List[List[float]] = []
        all_env_rewards:    List[float]       = []
        all_parse_ok:       List[float]       = []

        for prompt_text in prompts:
            # Identify which company this prompt is for
            m = re.search(r"You are CEO of: (.+?) \(", prompt_text)
            primary = m.group(1) if m else ALL_COMPANY_NAMES[0]

            # Fresh game state
            env = SelfPlayBoardroomEnvironment()
            env.reset(primary_ceo=primary)

            # Generate action for PRIMARY company (kept for GRPO)
            p_input_ids, p_comp_ids, p_logprobs, p_text = _generate_one(
                model, tokenizer, prompt_text, device, max_new
            )
            primary_result = parse_completion(p_text)

            # Generate actions for all OTHER companies (inference only, no grad needed)
            all_turn_actions: Dict[str, TurnAction] = {}
            for company in ALL_COMPANY_NAMES:
                if company == primary:
                    all_turn_actions[company] = env.parse_action_for(primary_result.action_dict, company)
                else:
                    _, _, _, opp_text = _generate_one(
                        model, tokenizer, env.get_company_prompt(company), device, max_new
                    )
                    opp_result = parse_completion(opp_text)
                    all_turn_actions[company] = env.parse_action_for(opp_result.action_dict, company)

            # Resolve turn, get primary company's reward
            rewards = env.step_all_companies(all_turn_actions)
            env_reward = float(rewards.get(primary, 0.0)) * 0.5

            all_prompt_ids.append(p_input_ids)
            all_completion_ids.append(p_comp_ids)
            all_logprobs.append(p_logprobs)
            all_env_rewards.append(env_reward)
            all_parse_ok.append(1.0 if primary_result.parse_ok else 0.0)

        return {
            "prompt_ids":     all_prompt_ids,
            "completion_ids": all_completion_ids,
            "logprobs":       all_logprobs,
            "env_reward":     all_env_rewards,
            "parse_ok":       all_parse_ok,
        }

    return rollout_func


# ------------------------------------------------------------------ #
# Reward function (extracts from rollout kwargs)                       #
# ------------------------------------------------------------------ #
def reward_fn(prompts, completions, **kwargs) -> List[float]:
    pre_env_rewards = kwargs.get("env_reward", [])
    pre_parse_ok    = kwargs.get("parse_ok",   [])
    using_rollout   = len(pre_env_rewards) == len(completions)

    rewards = []
    for i, completion in enumerate(completions):
        if using_rollout:
            rewards.append(-1.0 if pre_parse_ok[i] < 0.5 else float(pre_env_rewards[i]))
        else:
            if isinstance(completion, list):
                completion = completion[-1].get("content", "") if completion else ""
            elif isinstance(completion, dict):
                completion = completion.get("content", "")
            result = parse_completion(str(completion))
            rewards.append(-1.0 if not result.parse_ok else 0.0)
    return rewards


# ------------------------------------------------------------------ #
# W&B                                                                  #
# ------------------------------------------------------------------ #
def _init_wandb(args):
    try:
        import wandb
        wandb.init(
            project=os.environ.get("WANDB_PROJECT", "boardroom"),
            name=args.run_name,
            config={
                "model_id": args.model_id, "max_steps": args.max_steps,
                "batch_size": args.batch_size, "num_generations": args.num_generations,
                "algorithm": "GRPO", "env": "boardroom-l2-selfplay",
                "mode": "self_play_7company",
            },
        )
        print(f"[wandb] {wandb.run.url}")
    except Exception as e:
        print(f"[wandb] skipped — {e}")


def _wandb_finish(out, summary):
    try:
        import wandb
        if not wandb.run:
            return
        wandb.summary.update(summary)
        wandb.finish()
    except Exception:
        pass


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #
def main():
    args = parse_args()
    _init_wandb(args)

    print(f"[config] model={args.model_id}  steps={args.max_steps}  "
          f"batch={args.batch_size}  gens={args.num_generations}  "
          f"mode=SELF-PLAY (7 companies, rotating primary)")

    model, tokenizer = load_model(args.model_id, use_fp16=args.fp16)

    print("[dataset] building self-play seed dataset ...")
    dataset      = build_seed_dataset(args.n_seeds)
    rollout_func = make_selfplay_rollout_func(tokenizer, args.fp16)
    print(f"[dataset] {len(dataset)} records ({args.n_seeds} episodes × 7 companies)")

    from trl import GRPOConfig, GRPOTrainer

    config = GRPOConfig(
        output_dir                  = args.output_dir,
        run_name                    = args.run_name,
        max_steps                   = args.max_steps,
        per_device_train_batch_size = args.batch_size,
        num_generations             = args.num_generations,
        gradient_accumulation_steps = 2,
        learning_rate               = 2e-6,
        lr_scheduler_type           = "cosine",
        warmup_steps                = args.warmup_steps,
        bf16                        = not args.fp16,
        fp16                        = args.fp16,
        logging_steps               = 1,
        save_steps                  = 9999,
        report_to                   = "wandb",
        max_completion_length       = args.max_completion_len,
        beta                        = 0.1,
        max_grad_norm               = 0.5,
    )

    trainer_kwargs: Dict[str, Any] = dict(
        model=model, processing_class=tokenizer,
        args=config, reward_funcs=reward_fn, train_dataset=dataset,
    )
    try:
        import inspect
        if "rollout_func" in inspect.signature(GRPOTrainer.__init__).parameters:
            trainer_kwargs["rollout_func"] = rollout_func
            print("[rollout] custom self-play rollout_func wired")
        else:
            print("[rollout] GRPOTrainer has no rollout_func param — reward_fn fallback")
    except Exception:
        pass

    trainer = GRPOTrainer(**trainer_kwargs)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    step_counter = [0]
    best_reward  = [float("-inf")]
    best_dir     = out / "best_adapter"
    original_step = trainer.training_step

    if args.hub_model_id:
        from huggingface_hub import HfApi
        _hf_api = HfApi()
        _hf_api.create_repo(args.hub_model_id, repo_type="model", exist_ok=True)
    else:
        _hf_api = None

    def patched_step(*a, **kw):
        loss = original_step(*a, **kw)
        step_counter[0] += 1

        if step_counter[0] % (args.refresh_every * 2) == 0:
            print(f"\n[refresh] step {step_counter[0]} — re-rolling self-play dataset ...")
            trainer.train_dataset = build_seed_dataset(args.n_seeds // 2)

        log = trainer.state.log_history
        recent_rewards = [e["reward"] for e in log if "reward" in e]
        if recent_rewards:
            latest_reward = recent_rewards[-1]
            if latest_reward > best_reward[0]:
                best_reward[0] = latest_reward
                model.save_pretrained(best_dir)
                tokenizer.save_pretrained(best_dir)
                print(f"\n[best] step {step_counter[0]} reward={latest_reward:.4f} → saved")
                if _hf_api and args.hub_model_id:
                    try:
                        _hf_api.upload_folder(
                            folder_path=str(best_dir), repo_id=args.hub_model_id,
                            repo_type="model",
                            commit_message=f"best adapter step={step_counter[0]} reward={latest_reward:.4f}",
                        )
                        print(f"[hub] pushed → https://huggingface.co/{args.hub_model_id}")
                    except Exception as e:
                        print(f"[hub] upload failed: {e}")
        return loss

    trainer.training_step = patched_step

    print(f"[train] starting {args.max_steps} steps (self-play) ...")
    trainer.train()

    history = trainer.state.log_history
    summary = {
        "steps":        args.max_steps,
        "model_id":     args.model_id,
        "mode":         "self_play",
        "final_loss":   next((h["loss"]   for h in reversed(history) if "loss"   in h), None),
        "final_reward": next((h["reward"] for h in reversed(history) if "reward" in h), None),
        "best_reward":  best_reward[0],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    _wandb_finish(out, summary)


if __name__ == "__main__":
    main()
