"""
BOARDROOM — GRPO Training Script (T4-ready, no HTTP server needed)

The environment runs in-process — no `uv run server` needed.
BoardroomEnvironment is imported directly and called as a Python object.

Run on HF Jobs T4:
    hf jobs uv run --flavor t4-medium train/train_grpo.py

Override model or steps:
    hf jobs uv run --flavor t4-medium train/train_grpo.py \\
        --model-id Qwen/Qwen3.5-4B \\
        --max-steps 200
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))


# ------------------------------------------------------------------ #
# Args                                                                 #
# ------------------------------------------------------------------ #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--model-id", default="Qwen/Qwen3.5-4B")
    p.add_argument("--output-dir", default="checkpoints/boardroom-grpo")
    p.add_argument("--run-name", default="boardroom-grpo-v1")
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--num-generations", type=int, default=8)
    p.add_argument("--refresh-every", type=int, default=50,
                   help="Re-roll dataset with updated model every N steps")
    p.add_argument("--n-rollout-episodes", type=int, default=50,
                   help="Episodes to collect for initial prompt dataset")
    return p.parse_args()


# ------------------------------------------------------------------ #
# Model loading (Unsloth 4-bit → vanilla HF fallback)                 #
# ------------------------------------------------------------------ #
def load_model(model_id: str):
    try:
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_id,
            max_seq_length=2048,
            load_in_4bit=True,
            dtype=None,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=16,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            lora_alpha=16,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=42,
        )
        print(f"[model] Unsloth 4-bit LoRA: {model_id}")
    except ImportError:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        print(f"[model] vanilla HF bfloat16: {model_id}")

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    return model, tokenizer


# ------------------------------------------------------------------ #
# Prompt dataset — rollouts via in-process env (no HTTP)              #
# ------------------------------------------------------------------ #
def collect_prompts(n_episodes: int) -> List[str]:
    """
    Run random episodes with BoardroomEnvironment directly.
    Returns a flat list of observation prompt strings.
    Each episode produces ~12 prompts (one per turn).
    """
    from server.boardroom_environment import BoardroomEnvironment
    from models import BoardroomAction
    import random

    action_pool = [
        BoardroomAction(action_type="EARNINGS_CALL"),
        BoardroomAction(action_type="SABOTAGE", action_target="Goldspire Industries"),
        BoardroomAction(action_type="SABOTAGE", action_target="Sablemark Holdings"),
        BoardroomAction(action_type="SABOTAGE", action_target="Ironhold Logistics"),
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
            act = random.choice(action_pool)
            obs = env.step(act)   # direct env returns obs, not StepResult
        if (ep + 1) % 10 == 0:
            print(f"  rollout {ep + 1}/{n_episodes} — {len(prompts)} prompts so far")

    print(f"[dataset] {len(prompts)} prompts from {n_episodes} episodes")
    return prompts


def build_hf_dataset(prompts: List[str]):
    from datasets import Dataset
    return Dataset.from_list([{"prompt": p} for p in prompts])


# ------------------------------------------------------------------ #
# Reward function                                                      #
# ------------------------------------------------------------------ #
def reward_fn(prompts: List[str], completions: List[str], **kwargs) -> List[float]:
    """
    Score each (prompt, completion) pair.

    Called by GRPOTrainer every step. We can't step the live env per
    completion (would advance state for all 8 candidates), so we use
    a fast heuristic that strongly rewards:
      - Valid JSON output
      - Non-HOLD actions (engagement)
      - Correct target company name
      - Strategic communication (emails + press)
    """
    from train.action_loop import parse_completion

    # Extract known company names from the first prompt (they don't change)
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

        r = 0.0
        d = result.action_dict

        # --- Action type ---
        atype = d.get("action_type", "HOLD")
        if atype == "EARNINGS_CALL":
            r += 0.10
        elif atype == "SABOTAGE":
            r += 0.20   # high stakes → high signal
        elif atype == "PARTNERSHIP":
            r += 0.12
        # HOLD = 0 (not penalised, just not rewarded — forces model to prefer action)

        # --- Target validity ---
        target = d.get("action_target")
        if atype in ("SABOTAGE", "PARTNERSHIP"):
            if target in COMPANIES and target != "Vermillion Capital":
                r += 0.10  # correct target
            else:
                r -= 0.15  # invalid or self-target

        # --- Communication ---
        emails = d.get("private_emails") or []
        valid_emails = [
            e for e in emails
            if isinstance(e, dict)
            and e.get("to") in COMPANIES
            and e.get("text", "").strip()
        ]
        r += 0.05 * min(len(valid_emails), 2)

        pr = d.get("press_release")
        if isinstance(pr, dict) and pr.get("claim", "").strip():
            r += 0.05

        rewards.append(round(r, 4))

    return rewards


# ------------------------------------------------------------------ #
# Training                                                             #
# ------------------------------------------------------------------ #
def main():
    args = parse_args()

    # -- W&B init --
    # HF Jobs: set WANDB_API_KEY via `hf jobs secrets set WANDB_API_KEY <key>`
    # Local: `wandb login` or export WANDB_API_KEY=...
    _init_wandb(args)

    print(f"[config] model={args.model_id} steps={args.max_steps} "
          f"batch={args.batch_size} gens={args.num_generations}")

    # -- Model --
    model, tokenizer = load_model(args.model_id)

    # -- Initial dataset --
    print("[dataset] collecting rollout prompts ...")
    prompts = collect_prompts(args.n_rollout_episodes)
    dataset = build_hf_dataset(prompts)

    # -- GRPO config --
    try:
        from trl import GRPOConfig, GRPOTrainer
    except ImportError:
        print("ERROR: trl not installed. Check pyproject.toml [train] deps.")
        sys.exit(1)

    config = GRPOConfig(
        output_dir=args.output_dir,
        run_name=args.run_name,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        num_generations=args.num_generations,
        gradient_accumulation_steps=2,
        learning_rate=5e-6,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        bf16=True,
        logging_steps=1,
        save_steps=50,
        report_to="wandb",
        max_completion_length=512,
        temperature=0.8,
        top_p=0.95,
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        config=config,
        reward_funcs=reward_fn,
        train_dataset=dataset,
    )

    # -- Dataset refresh callback --
    # Every `refresh_every` steps: re-roll with updated model policy
    # so training stays on-policy as the model improves
    original_step = trainer.training_step

    step_counter = [0]

    def patched_step(*a, **kw):
        loss = original_step(*a, **kw)
        step_counter[0] += 1

        # Log to W&B directly (GRPOTrainer logs loss but not always reward)
        try:
            import wandb
            if wandb.run:
                log = {"train/step": step_counter[0], "train/loss": float(loss)}
                history = trainer.state.log_history
                if history:
                    last = history[-1]
                    if "reward" in last:
                        log["train/reward"] = last["reward"]
                wandb.log(log, step=step_counter[0])
        except Exception:
            pass

        if step_counter[0] % args.refresh_every == 0:
            print(f"\n[refresh] step {step_counter[0]} — re-rolling dataset ...")
            new_prompts = collect_prompts(args.n_rollout_episodes // 2)
            trainer.train_dataset = build_hf_dataset(new_prompts)
            print(f"[refresh] done — {len(new_prompts)} new prompts\n")
        return loss

    trainer.training_step = patched_step

    # -- Train --
    print(f"[train] starting {args.max_steps} steps ...")
    trainer.train()

    # -- Save --
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out / "lora_adapter")
    tokenizer.save_pretrained(out / "lora_adapter")
    print(f"[save] adapter → {out / 'lora_adapter'}")

    # -- Plots --
    _save_plots(trainer.state.log_history, out)

    # -- Summary --
    history = trainer.state.log_history
    summary = {
        "steps": args.max_steps,
        "model_id": args.model_id,
        "final_loss": next((h["loss"] for h in reversed(history) if "loss" in h), None),
        "final_reward": next((h.get("reward") for h in reversed(history) if "reward" in h), None),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    # -- Upload plots to W&B --
    _wandb_finish(out, summary)


# ------------------------------------------------------------------ #
# W&B helpers                                                          #
# ------------------------------------------------------------------ #
def _init_wandb(args: argparse.Namespace) -> None:
    try:
        import wandb
        wandb.init(
            project=os.environ.get("WANDB_PROJECT", "boardroom"),
            name=args.run_name,
            config={
                "model_id": args.model_id,
                "max_steps": args.max_steps,
                "batch_size": args.batch_size,
                "num_generations": args.num_generations,
                "refresh_every": args.refresh_every,
                "n_rollout_episodes": args.n_rollout_episodes,
                "env": "boardroom-l1",
                "companies": 4,
                "max_turns": 12,
                "algorithm": "GRPO",
            },
        )
        print(f"[wandb] run: {wandb.run.url}")
    except ImportError:
        print("[wandb] not installed — skipping")
    except Exception as e:
        print(f"[wandb] init failed ({e}) — training continues without W&B")


def _wandb_finish(out: Path, summary: dict) -> None:
    try:
        import wandb
        if wandb.run is None:
            return

        # Log final metrics
        wandb.summary.update(summary)

        # Upload plot PNGs as W&B artifacts
        artifact = wandb.Artifact("training-plots", type="results")
        for png in ["loss.png", "reward.png"]:
            p = out / png
            if p.exists():
                artifact.add_file(str(p))
                wandb.log({png.replace(".png", ""): wandb.Image(str(p))})
        wandb.log_artifact(artifact)

        # Upload adapter as artifact
        adapter_dir = out / "lora_adapter"
        if adapter_dir.exists():
            model_artifact = wandb.Artifact("lora-adapter", type="model")
            model_artifact.add_dir(str(adapter_dir))
            wandb.log_artifact(model_artifact)

        wandb.finish()
        print(f"[wandb] finished — {wandb.run.url}")
    except Exception as e:
        print(f"[wandb] finish failed: {e}")


# ------------------------------------------------------------------ #
# Plots                                                                #
# ------------------------------------------------------------------ #
def _save_plots(history: list, out: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        steps   = [h["step"] for h in history if "step" in h]
        losses  = [h["loss"] for h in history if "loss" in h]
        rewards = [h["reward"] for h in history if "reward" in h]

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        fig.suptitle("BOARDROOM GRPO Training", fontsize=13)

        if losses:
            axes[0].plot(steps[:len(losses)], losses, color="#e05c5c")
            axes[0].set_title("Loss")
            axes[0].set_xlabel("Step")
            axes[0].grid(alpha=0.3)

        if rewards:
            axes[1].plot(steps[:len(rewards)], rewards, color="#5ca8e0")
            axes[1].set_title("Reward")
            axes[1].set_xlabel("Step")
            axes[1].grid(alpha=0.3)

        plt.tight_layout()
        plt.savefig(out / "loss.png", dpi=150, bbox_inches="tight")
        plt.savefig(out / "reward.png", dpi=150, bbox_inches="tight")
        print(f"[plots] saved to {out}/")
    except ImportError:
        print("[plots] matplotlib not available — skipping")


if __name__ == "__main__":
    main()
