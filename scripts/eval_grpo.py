# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "torch>=2.1.0",
#   "transformers>=4.45.0",
#   "peft>=0.13.0",
#   "accelerate>=0.34.0",
#   "datasets>=3.0.0",
#   "bitsandbytes>=0.44.0",
#   "wandb>=0.18.0",
#   "unsloth",
# ]
# ///
"""
BOARDROOM — GRPO Evaluation Script (self-contained for HF Jobs)

Runs N episodes with the trained model as primary CEO vs heuristic rivals,
then N episodes with a pure heuristic baseline, and logs everything to W&B.

Usage (local):
    python scripts/eval_grpo.py --hub-model-id nothr/boardroom-grpo-lora

Usage (HF Jobs):
    hf jobs uv run --flavor l40sx1 \\
      --env WANDB_API_KEY=<key> --env HF_TOKEN=<token> \\
      scripts/eval_grpo.py --hub-model-id nothr/boardroom-grpo-lora
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4


# ------------------------------------------------------------------ #
# Inlined game logic (mirrors train_grpo.py)                          #
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

MARKET_SHARE_BASELINE: float = 100.0 / len(L2_COMPANIES)

STARTING_STATS = {
    "cash": 50_000_000.0,
    "market_share": MARKET_SHARE_BASELINE,
    "stock_price": 100.0,
    "reputation": 0.70,
}

PRIMARY_CEO = "Vermillion Capital"
MAX_TURNS   = 12


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

    partnership_proposals: Dict[str, str] = {}
    merger_proposals: Dict[str, str] = {}

    for name, action in actions.items():
        company = companies[name]
        if not company.alive:
            continue
        trait = SECTOR_TRAITS.get(company.sector)

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


def _final_rank(companies, ceo_id):
    company = companies.get(ceo_id)
    if not company or not company.alive:
        return len(companies)
    alive = [c for c in companies.values() if c.alive]
    ranked = sorted(alive, key=lambda c: c.stock_price * c.market_share, reverse=True)
    return next((i for i, c in enumerate(ranked) if c.name == ceo_id), len(ranked))


def _make_companies():
    companies = {}
    for defn in L2_COMPANIES:
        companies[defn["name"]] = CompanyState(
            name=defn["name"], sector=defn["sector"],
            cash=STARTING_STATS["cash"], market_share=STARTING_STATS["market_share"],
            stock_price=STARTING_STATS["stock_price"], reputation=STARTING_STATS["reputation"],
            starting_cash=STARTING_STATS["cash"],
        )
    return companies


def _heuristic_action(name, companies, rng):
    alive_others = [n for n, c in companies.items() if c.alive and n != name]
    r = rng.random()
    if r < 0.15:
        atype, target = "EARNINGS_CALL", None
    elif r < 0.35 and alive_others:
        atype, target = "SABOTAGE", rng.choice(alive_others)
    elif r < 0.45 and alive_others:
        atype, target = "PARTNERSHIP", rng.choice(alive_others)
    elif r < 0.52 and alive_others:
        atype, target = "PROPOSE_MERGER", rng.choice(alive_others)
    else:
        atype, target = "HOLD", None
    return TurnAction(company_name=name, private_emails=[], press_release=None,
                      action_type=atype, action_target=target)


# ------------------------------------------------------------------ #
# Prompt builder + action parser                                       #
# ------------------------------------------------------------------ #

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

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_JSON_RE   = re.compile(r"\{.*\}", re.DOTALL)

DEFAULT_HOLD = {"private_emails": [], "press_release": None, "action_type": "HOLD", "action_target": None}

VALID_ACTIONS = {"EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "PROPOSE_MERGER", "HOLD"}


def parse_completion(text: str):
    text = _THINK_RE.sub("", text).strip()
    match = _JSON_RE.search(text)
    if not match:
        return DEFAULT_HOLD.copy(), False
    try:
        data = json.loads(match.group())
        data.setdefault("private_emails", [])
        data.setdefault("press_release", None)
        data.setdefault("action_type", "HOLD")
        data.setdefault("action_target", None)
        data["action_type"] = str(data["action_type"]).upper()
        if data["action_type"] not in VALID_ACTIONS:
            data["action_type"] = "HOLD"
        return data, True
    except json.JSONDecodeError:
        return DEFAULT_HOLD.copy(), False


def build_prompt(companies, turn):
    primary = companies[PRIMARY_CEO]
    all_cos = list(companies.values())
    leaderboard = sorted(all_cos, key=lambda c: c.stock_price * c.market_share, reverse=True)

    lines = [
        f"=== BOARDROOM | Turn {turn + 1} / {MAX_TURNS} ===",
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
    for c in all_cos:
        if not c.alive:
            lines.append(f"  {c.name:30s} [BANKRUPT]")
        else:
            lines.append(f"  {c.name:30s} stock=${c.stock_price:.0f}  share={c.market_share:.1f}%  rep={c.reputation:.2f}")
    top3 = " > ".join(c.name for c in leaderboard[:3] if c.alive)
    lines += ["", f"LEADERBOARD: {top3}", "",
              "ACTIONS: EARNINGS_CALL | SABOTAGE <target> | PARTNERSHIP <target> | PROPOSE_MERGER <target> | HOLD",
              "Respond with ONLY valid JSON:"]
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Model loading                                                        #
# ------------------------------------------------------------------ #

def load_model(hub_model_id: str, base_model_id: str, use_fp16: bool = False):
    import torch
    dtype = torch.float16 if use_fp16 else torch.bfloat16

    try:
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name     = hub_model_id,
            max_seq_length = 2048,
            load_in_4bit   = True,
            dtype          = None,
        )
        FastLanguageModel.for_inference(model)
        print(f"[model] Unsloth — {hub_model_id}")
    except Exception as e:
        print(f"[model] Unsloth failed ({e}), using PEFT")
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        tokenizer = AutoTokenizer.from_pretrained(base_model_id)
        base = AutoModelForCausalLM.from_pretrained(
            base_model_id, torch_dtype=dtype, device_map="auto"
        )
        model = PeftModel.from_pretrained(base, hub_model_id)
        model.eval()
        print(f"[model] PEFT — {hub_model_id}")

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return model, tokenizer


# ------------------------------------------------------------------ #
# Episode runner                                                       #
# ------------------------------------------------------------------ #

def run_episode_model(model, tokenizer, seed: int, device) -> Dict:
    import torch
    rng = random.Random(seed)
    companies = _make_companies()
    total_reward = 0.0
    action_counts: Dict[str, int] = defaultdict(int)
    parse_fails = 0

    for turn in range(MAX_TURNS):
        primary = companies[PRIMARY_CEO]
        if not primary.alive:
            break

        prompt = build_prompt(companies, turn)
        messages = [
            {"role": "system",  "content": SYSTEM_PROMPT},
            {"role": "user",    "content": prompt},
        ]
        text = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False
        )
        enc = tokenizer(text=text, return_tensors="pt")
        input_ids      = enc.input_ids.to(device)
        attention_mask = torch.ones_like(input_ids)  # no padding; suppress pad==eos warning

        with torch.no_grad():
            out = model.generate(
                input_ids,
                attention_mask   = attention_mask,
                max_new_tokens   = 160,
                do_sample        = True,
                temperature      = 0.7,
                pad_token_id     = tokenizer.eos_token_id,
            )
        completion = tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True)

        action_dict, ok = parse_completion(completion)
        if not ok:
            parse_fails += 1

        atype  = action_dict["action_type"]
        target = action_dict.get("action_target")
        if target and (target not in companies or not companies[target].alive or target == PRIMARY_CEO):
            target = None
        if atype in ("SABOTAGE", "PARTNERSHIP", "PROPOSE_MERGER") and not target:
            atype = "HOLD"

        action_counts[atype] += 1
        primary_action = TurnAction(
            company_name   = PRIMARY_CEO,
            private_emails = action_dict.get("private_emails", [])[:2],
            press_release  = action_dict.get("press_release"),
            action_type    = atype,
            action_target  = target,
            parse_failed   = not ok,
        )

        all_actions = {PRIMARY_CEO: primary_action}
        for name, co in companies.items():
            if name != PRIMARY_CEO and co.alive:
                all_actions[name] = _heuristic_action(name, companies, rng)

        result = resolve_turn(companies, all_actions, rng)
        total_reward += result.rewards.get(PRIMARY_CEO, 0.0)

        alive = [c for c in companies.values() if c.alive]
        if len(alive) <= 1 or not primary.alive:
            break

    total_reward += compute_terminal_reward(companies, PRIMARY_CEO)
    rank = _final_rank(companies, PRIMARY_CEO)
    primary = companies[PRIMARY_CEO]

    return {
        "total_reward":  total_reward,
        "rank":          rank,
        "survived":      primary.alive,
        "won":           rank == 0,
        "final_cash":    primary.cash,
        "final_share":   primary.market_share,
        "final_stock":   primary.stock_price,
        "action_counts": dict(action_counts),
        "parse_fails":   parse_fails,
    }


def run_episode_heuristic(seed: int) -> Dict:
    rng = random.Random(seed)
    companies = _make_companies()
    total_reward = 0.0
    action_counts: Dict[str, int] = defaultdict(int)

    for turn in range(MAX_TURNS):
        primary = companies[PRIMARY_CEO]
        if not primary.alive:
            break

        all_actions = {}
        for name, co in companies.items():
            if co.alive:
                all_actions[name] = _heuristic_action(name, companies, rng)

        action_counts[all_actions[PRIMARY_CEO].action_type] += 1
        result = resolve_turn(companies, all_actions, rng)
        total_reward += result.rewards.get(PRIMARY_CEO, 0.0)

        alive = [c for c in companies.values() if c.alive]
        if len(alive) <= 1 or not primary.alive:
            break

    total_reward += compute_terminal_reward(companies, PRIMARY_CEO)
    rank = _final_rank(companies, PRIMARY_CEO)
    primary = companies[PRIMARY_CEO]

    return {
        "total_reward":  total_reward,
        "rank":          rank,
        "survived":      primary.alive,
        "won":           rank == 0,
        "final_cash":    primary.cash,
        "final_share":   primary.market_share,
        "final_stock":   primary.stock_price,
        "action_counts": dict(action_counts),
        "parse_fails":   0,
    }


# ------------------------------------------------------------------ #
# Aggregation                                                          #
# ------------------------------------------------------------------ #

def aggregate(results: List[Dict], prefix: str) -> Dict:
    n = len(results)
    agg = {
        f"{prefix}/win_rate":      sum(r["won"]      for r in results) / n,
        f"{prefix}/survival_rate": sum(r["survived"] for r in results) / n,
        f"{prefix}/avg_reward":    sum(r["total_reward"] for r in results) / n,
        f"{prefix}/avg_rank":      sum(r["rank"]     for r in results) / n,
        f"{prefix}/avg_cash_M":    sum(r["final_cash"] for r in results) / n / 1e6,
        f"{prefix}/avg_share":     sum(r["final_share"] for r in results) / n,
        f"{prefix}/avg_stock":     sum(r["final_stock"] for r in results) / n,
    }
    if any("parse_fails" in r for r in results):
        agg[f"{prefix}/parse_fail_rate"] = sum(r.get("parse_fails", 0) for r in results) / n

    # action distribution
    total_actions: Dict[str, int] = defaultdict(int)
    for r in results:
        for a, cnt in r.get("action_counts", {}).items():
            total_actions[a] += cnt
    total = sum(total_actions.values()) or 1
    for a, cnt in total_actions.items():
        agg[f"{prefix}/action_{a.lower()}"] = cnt / total

    return agg


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--hub-model-id",  required=True,
                   help="HF Hub repo with trained adapter, e.g. nothr/boardroom-grpo-lora")
    p.add_argument("--base-model-id", default="google/gemma-4-E2B-it")
    p.add_argument("--n-episodes",    type=int, default=50)
    p.add_argument("--seed",          type=int, default=0)
    p.add_argument("--run-name",      default="boardroom-eval")
    p.add_argument("--fp16",          action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[eval] device={device}  episodes={args.n_episodes}  model={args.hub_model_id}")

    import wandb
    wandb.init(project="boardroom", name=args.run_name, config=vars(args))

    # ── Heuristic baseline ──────────────────────────────────────────
    print(f"\n[baseline] running {args.n_episodes} heuristic episodes ...")
    baseline_results = [run_episode_heuristic(args.seed + i) for i in range(args.n_episodes)]
    baseline_metrics = aggregate(baseline_results, "baseline")
    print_table("BASELINE", baseline_metrics)
    wandb.log(baseline_metrics)

    # ── Trained model ───────────────────────────────────────────────
    print(f"\n[model] loading {args.hub_model_id} ...")
    model, tokenizer = load_model(args.hub_model_id, args.base_model_id, args.fp16)

    print(f"\n[model] running {args.n_episodes} episodes ...")
    model_results = []
    for i in range(args.n_episodes):
        r = run_episode_model(model, tokenizer, args.seed + i, device)
        model_results.append(r)
        print(f"  ep {i+1:>3}/{args.n_episodes}  reward={r['total_reward']:+.3f}  "
              f"rank={r['rank']+1}  {'WIN' if r['won'] else 'survived' if r['survived'] else 'bankrupt'}")

    model_metrics = aggregate(model_results, "model")
    print_table("MODEL", model_metrics)
    wandb.log(model_metrics)

    # ── Delta ────────────────────────────────────────────────────────
    delta = {
        "delta/win_rate":      model_metrics["model/win_rate"]      - baseline_metrics["baseline/win_rate"],
        "delta/survival_rate": model_metrics["model/survival_rate"] - baseline_metrics["baseline/survival_rate"],
        "delta/avg_reward":    model_metrics["model/avg_reward"]    - baseline_metrics["baseline/avg_reward"],
        "delta/avg_rank":      model_metrics["model/avg_rank"]      - baseline_metrics["baseline/avg_rank"],
    }
    wandb.log(delta)
    print("\n[delta vs baseline]")
    for k, v in delta.items():
        sign = "+" if v >= 0 else ""
        print(f"  {k:<30s} {sign}{v:.4f}")

    wandb.finish()


def print_table(label: str, metrics: Dict):
    print(f"\n{'─'*50}")
    print(f"  {label}")
    print(f"{'─'*50}")
    for k, v in sorted(metrics.items()):
        print(f"  {k:<40s} {v:.4f}")
    print(f"{'─'*50}")


if __name__ == "__main__":
    main()
