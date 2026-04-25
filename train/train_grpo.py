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
BOARDROOM — GRPO Training Script

Environment runs in-process (no HTTP server needed).

HF Jobs A10G (recommended — bf16, fastest):
    hf jobs uv run --flavor a10g-small train/train_grpo.py --model-id Qwen/Qwen3.5-0.8B

HF Jobs T4:
    hf jobs uv run --flavor t4-medium train/train_grpo.py --model-id Qwen/Qwen3.5-0.8B --fp16
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

# HF Jobs copies script to // but sets cwd to the repo root.
# Use cwd first; fall back to walking up from __file__.
_CWD = Path.cwd()
if (_CWD / "models.py").exists():
    _REPO_DIR = _CWD
else:
    _SEARCH = Path(__file__).resolve().parent
    for _ in range(6):
        if (_SEARCH / "models.py").exists():
            break
        _SEARCH = _SEARCH.parent
    _REPO_DIR = _SEARCH

_TRAIN_DIR = _REPO_DIR / "train"
for _p in [str(_REPO_DIR), str(_TRAIN_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

print(f"[path] repo={_REPO_DIR}  cwd={_CWD}")

# ------------------------------------------------------------------ #
# Inlined from action_loop.py — self-contained for HF Jobs            #
# ------------------------------------------------------------------ #
_THINK_RE  = re.compile(r"<think>.*?</think>", re.DOTALL)
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
            if data["action_type"] not in ("EARNINGS_CALL","SABOTAGE","PARTNERSHIP","HOLD"):
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
    p.add_argument("--num-generations",     type=int, default=8)
    p.add_argument("--max-completion-len",  type=int, default=256)
    p.add_argument("--warmup-steps",        type=int, default=10)
    p.add_argument("--refresh-every",       type=int, default=50)
    p.add_argument("--n-rollout-episodes",  type=int, default=50)
    p.add_argument("--fp16",  action="store_true",
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
            r                        = 16,
            target_modules           = ["q_proj","k_proj","v_proj","o_proj",
                                        "gate_proj","up_proj","down_proj"],
            lora_alpha               = 16,
            lora_dropout             = 0,
            bias                     = "none",
            use_gradient_checkpointing = "unsloth",
            random_state             = 42,
        )
        print(f"[model] Unsloth 4-bit LoRA — {model_id}")
    except ImportError:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
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
# Dataset — in-process rollouts, no HTTP server                       #
# ------------------------------------------------------------------ #
def collect_prompts(n_episodes: int) -> List[str]:
    from server.boardroom_environment import BoardroomEnvironment
    from models import BoardroomAction
    import random

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
    return Dataset.from_list([{"prompt": p} for p in prompts])


# ------------------------------------------------------------------ #
# Reward function                                                      #
# ------------------------------------------------------------------ #
def reward_fn(prompts: List[str], completions: List[str], **kwargs) -> List[float]:
    # parse_completion is inlined at top of this file

    COMPANIES = {
        "Vermillion Capital", "Goldspire Industries",
        "Sablemark Holdings", "Ironhold Logistics",
    }

    rewards = []
    for prompt, completion in zip(prompts, completions):
        result = parse_completion(completion)

        if not result.parse_ok:
            rewards.append(-0.3)
            continue

        r  = 0.0
        d  = result.action_dict
        atype  = d.get("action_type", "HOLD")
        target = d.get("action_target")

        # Action type score
        if   atype == "SABOTAGE":     r += 0.20
        elif atype == "PARTNERSHIP":  r += 0.12
        elif atype == "EARNINGS_CALL":r += 0.10

        # Valid target bonus
        if atype in ("SABOTAGE", "PARTNERSHIP"):
            if target in COMPANIES and target != "Vermillion Capital":
                r += 0.10
            else:
                r -= 0.15

        # Communication bonus
        emails = [
            e for e in (d.get("private_emails") or [])
            if isinstance(e, dict)
            and e.get("to") in COMPANIES
            and str(e.get("text","")).strip()
        ]
        r += 0.05 * min(len(emails), 2)

        pr = d.get("press_release")
        if isinstance(pr, dict) and str(pr.get("claim","")).strip():
            r += 0.05

        rewards.append(round(r, 4))

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
                    wandb.log({f.replace(".png",""): wandb.Image(str(out / f))})
        wandb.log_artifact(art)
        adapter = out / "lora_adapter"
        if adapter.exists():
            m = wandb.Artifact("lora-adapter", type="model")
            m.add_dir(str(adapter))
            wandb.log_artifact(m)
        wandb.finish()
        print(f"[wandb] done — {wandb.run.url}")
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

    # Disable Qwen3 thinking tokens — JSON only, no <think> blocks
    # This cuts completion length ~5× and speeds up training significantly
    # SYSTEM_PROMPT already has /no_think (inlined at top of this file)

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
        learning_rate               = 5e-6,
        lr_scheduler_type           = "cosine",
        warmup_steps                = args.warmup_steps,  # not warmup_ratio
        bf16                        = not args.fp16,      # A10G/A100: bf16
        fp16                        = args.fp16,          # T4: fp16
        logging_steps               = 1,
        save_steps                  = 50,
        report_to                   = "wandb",
        max_completion_length       = args.max_completion_len,
    )

    trainer = GRPOTrainer(
        model            = model,
        processing_class = tokenizer,
        args             = config,        # args= not config=
        reward_funcs     = reward_fn,
        train_dataset    = dataset,
    )

    # Dataset refresh every N steps (keeps training on-policy)
    step_counter = [0]
    original_step = trainer.training_step

    def patched_step(*a, **kw):
        loss = original_step(*a, **kw)
        step_counter[0] += 1
        try:
            import wandb
            if wandb.run:
                log = {"train/loss": float(loss), "train/step": step_counter[0]}
                if trainer.state.log_history:
                    last = trainer.state.log_history[-1]
                    if "reward" in last:
                        log["train/reward"] = last["reward"]
                wandb.log(log, step=step_counter[0])
        except Exception:
            pass
        if step_counter[0] % args.refresh_every == 0:
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
