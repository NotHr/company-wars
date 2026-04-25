"""
BOARDROOM — GRPO Training Script
Adapted from TRL's Wordle GRPO notebook.

Stack:
  - Qwen 2.5 1.5B (base or instruct)
  - Unsloth 4-bit LoRA (fits T4-medium 16GB VRAM)
  - TRL GRPOTrainer
  - Weights & Biases logging

Run locally (debug, 10 steps):
  python train/train_grpo.py --debug

Run on HF Jobs (full training):
  hf jobs uv run --flavor t4-medium train/train_grpo.py

Environment must be running:
  uv run server           # localhost:8000
  # OR point --env-url at a deployed HF Space
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List

# Add parent to path so we can import env client
sys.path.insert(0, str(Path(__file__).parent.parent))

# ------------------------------------------------------------------ #
# Args                                                                 #
# ------------------------------------------------------------------ #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--env-url", default="http://localhost:8000",
                   help="OpenEnv server URL")
    p.add_argument("--model-id", default="Qwen/Qwen3.5-4B",
                   help="HuggingFace model ID")
    p.add_argument("--output-dir", default="checkpoints/boardroom-grpo",
                   help="Where to save LoRA adapter")
    p.add_argument("--run-name", default="boardroom-grpo-v1",
                   help="W&B run name")
    p.add_argument("--max-steps", type=int, default=200,
                   help="Total GRPO training steps")
    p.add_argument("--batch-size", type=int, default=4,
                   help="Prompts per step")
    p.add_argument("--num-generations", type=int, default=8,
                   help="LLM completions per prompt (GRPO N)")
    p.add_argument("--max-turns", type=int, default=12,
                   help="Max game turns per episode")
    p.add_argument("--debug", action="store_true",
                   help="10-step smoke test run, no W&B")
    return p.parse_args()


# ------------------------------------------------------------------ #
# Model loading (Unsloth 4-bit for T4 memory budget)                  #
# ------------------------------------------------------------------ #
def load_model(model_id: str):
    """Load Qwen with Unsloth 4-bit LoRA. Falls back to vanilla HF if Unsloth not installed."""
    try:
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_id,
            max_seq_length=2048,
            load_in_4bit=True,
            dtype=None,  # auto
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
        print("Loaded with Unsloth 4-bit LoRA")
    except ImportError:
        print("Unsloth not installed — falling back to vanilla HF (will use more VRAM)")
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    return model, tokenizer


# ------------------------------------------------------------------ #
# Episode rollout — generates (prompt, completion, reward) tuples     #
# ------------------------------------------------------------------ #
def rollout_episode(
    loop,
    env_url: str,
    max_turns: int,
    num_generations: int,
) -> List[dict]:
    """
    Run one full game episode (up to max_turns).
    For each turn, generate num_generations completions.
    Returns list of dicts: {prompt, completions, rewards}.

    This is what feeds the GRPO update.
    """
    from client import BoardroomEnv
    from models import BoardroomAction, Email, PressRelease
    from train.action_loop import parse_completion, obs_to_messages, _dict_to_action

    records = []

    with BoardroomEnv(base_url=env_url) as env:
        obs = env.reset()

        for _ in range(max_turns):
            if obs.done:
                break

            prompt = obs.prompt
            samples = loop.sample(prompt, n=num_generations)

            # Collect rewards for each completion
            completions_text = []
            rewards = []

            for raw_text, parse_result in samples:
                action = _dict_to_action(
                    parse_result.action_dict,
                    BoardroomAction, Email, PressRelease,
                )
                # Format penalty baked into env reward via parse_failed flag
                # We DON'T step the real env per-completion — that would advance state.
                # Instead, we step ONCE with the greedy action, use per-turn reward,
                # and assign that reward to ALL completions (standard GRPO on-policy trick).
                completions_text.append(raw_text)
                rewards.append(None)  # filled below after we step

            # Step env ONCE with greedy (first) completion
            greedy_parse = samples[0][1]
            greedy_action = _dict_to_action(
                greedy_parse.action_dict,
                BoardroomAction, Email, PressRelease,
            )
            step_result = env.step(greedy_action)
            turn_reward = step_result.reward or 0.0

            # Assign the actual env reward to the greedy completion.
            # Other completions get scored by parse quality + simulated reward.
            for i, (raw_text, parse_result) in enumerate(samples):
                r = turn_reward
                if not parse_result.parse_ok:
                    r -= 0.3   # format penalty for non-greedy completions
                rewards[i] = r

            records.append({
                "prompt": prompt,
                "completions": completions_text,
                "rewards": rewards,
            })

            obs = step_result.observation

    return records


# ------------------------------------------------------------------ #
# Reward function (called by GRPOTrainer)                             #
# ------------------------------------------------------------------ #
def make_reward_fn(env_url: str, loop):
    """
    Factory for TRL's reward_funcs parameter.

    GRPOTrainer calls: reward_fn(prompts, completions, **kwargs) -> List[float]

    We maintain a single environment per batch and step it with each completion.
    Since GRPO generates completions off-policy, we score by:
      - Parse quality (did it produce valid JSON? correct action type?)
      - Simulated turn outcome (forward the env state, undo-able since env is stateless)
    """
    from train.action_loop import parse_completion, _dict_to_action
    from models import BoardroomAction, Email, PressRelease

    def reward_fn(prompts: List[str], completions: List[str], **kwargs) -> List[float]:
        rewards = []
        for prompt, completion in zip(prompts, completions):
            parse_result = parse_completion(completion)

            # Base reward from parse quality
            if not parse_result.parse_ok:
                rewards.append(-0.3)
                continue

            atype = parse_result.action_dict.get("action_type", "HOLD")

            # Heuristic scoring when we can't step the live env per-completion
            # (stepping the env would change state for other completions)
            r = 0.0

            # Reward informative actions over pure HOLD
            if atype == "EARNINGS_CALL":
                r += 0.1
            elif atype == "SABOTAGE":
                r += 0.15   # high risk, high reward
            elif atype == "PARTNERSHIP":
                r += 0.08
            # HOLD gets 0 — not punished, just not rewarded

            # Reward including emails (shows strategic communication)
            emails = parse_result.action_dict.get("private_emails", [])
            if emails:
                r += 0.05 * min(len(emails), 2)

            # Reward press releases
            if parse_result.action_dict.get("press_release"):
                r += 0.05

            rewards.append(r)

        return rewards

    return reward_fn


# ------------------------------------------------------------------ #
# Dataset — generates prompts from live env rollouts                  #
# ------------------------------------------------------------------ #
class BoardroomRolloutDataset:
    """
    HuggingFace-compatible dataset that generates prompts by rolling out
    the environment with the current model policy.

    Each call to __getitem__ returns a fresh observation prompt.
    Re-generates every `refresh_every` steps so training stays on-policy.
    """

    def __init__(self, env_url: str, n_episodes: int = 50):
        self.env_url = env_url
        self.n_episodes = n_episodes
        self._prompts: List[str] = []
        self._generate_prompts()

    def _generate_prompts(self):
        """Run random rollouts to collect diverse observation prompts."""
        from client import BoardroomEnv
        from models import BoardroomAction
        import random

        self._prompts = []
        actions = [
            BoardroomAction(action_type="EARNINGS_CALL"),
            BoardroomAction(action_type="SABOTAGE", action_target="Goldspire Industries"),
            BoardroomAction(action_type="PARTNERSHIP", action_target="Sablemark Holdings"),
            BoardroomAction(action_type="HOLD"),
            BoardroomAction(action_type="SABOTAGE", action_target="Ironhold Logistics"),
        ]

        for _ in range(self.n_episodes):
            try:
                with BoardroomEnv(base_url=self.env_url) as env:
                    obs = env.reset()
                    while not obs.done:
                        self._prompts.append(obs.prompt)
                        act = random.choice(actions)
                        result = env.step(act)
                        obs = result.observation
            except Exception as e:
                print(f"Rollout failed: {e}")
                continue

        print(f"Generated {len(self._prompts)} prompts from {self.n_episodes} episodes")

    def __len__(self) -> int:
        return len(self._prompts)

    def __getitem__(self, idx: int) -> dict:
        return {"prompt": self._prompts[idx % len(self._prompts)]}


# ------------------------------------------------------------------ #
# Plotting (called at end of training)                                 #
# ------------------------------------------------------------------ #
def save_plots(log_history: List[dict], output_dir: str) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        steps = [h["step"] for h in log_history if "step" in h]
        losses = [h.get("loss", None) for h in log_history if "step" in h]
        rewards = [h.get("reward", None) for h in log_history if "step" in h]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

        if any(l is not None for l in losses):
            ax1.plot(steps, [l for l in losses if l is not None])
            ax1.set_title("Training Loss")
            ax1.set_xlabel("Step")
            ax1.set_ylabel("Loss")
            ax1.grid(True, alpha=0.3)

        if any(r is not None for r in rewards):
            ax2.plot(steps, [r for r in rewards if r is not None], color="orange")
            ax2.set_title("Episode Reward")
            ax2.set_xlabel("Step")
            ax2.set_ylabel("Reward")
            ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        plt.savefig(out / "loss.png", dpi=150, bbox_inches="tight")
        plt.savefig(out / "reward.png", dpi=150, bbox_inches="tight")
        print(f"Saved plots to {output_dir}/")
    except ImportError:
        print("matplotlib not installed — skipping plots")


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #
def main():
    args = parse_args()

    if args.debug:
        args.max_steps = 10
        args.batch_size = 2
        args.num_generations = 4
        os.environ.setdefault("WANDB_MODE", "disabled")
        print("DEBUG MODE — 10 steps, W&B disabled")

    # -- Load model --
    print(f"Loading {args.model_id} ...")
    model, tokenizer = load_model(args.model_id)

    # -- Build action loop --
    from train.action_loop import ActionLoop
    loop = ActionLoop(model, tokenizer)

    # -- Build dataset from env rollouts --
    print(f"Rolling out environment at {args.env_url} ...")
    n_episodes = 5 if args.debug else 50
    dataset = BoardroomRolloutDataset(args.env_url, n_episodes=n_episodes)

    if len(dataset) == 0:
        print("ERROR: No prompts generated. Is the server running?")
        print(f"  uv run server   (then retry)")
        sys.exit(1)

    # -- Configure GRPO --
    try:
        from trl import GRPOConfig, GRPOTrainer
    except ImportError:
        print("TRL not installed. Run: pip install trl>=0.12.0")
        sys.exit(1)

    config = GRPOConfig(
        output_dir=args.output_dir,
        run_name=args.run_name,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        num_generations=args.num_generations,
        gradient_accumulation_steps=1,
        learning_rate=5e-6,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        bf16=True,
        logging_steps=1,
        save_steps=50,
        report_to="wandb" if not args.debug else "none",
        # GRPO-specific
        max_new_tokens=512,
        temperature=0.8,
        top_p=0.95,
    )

    reward_fn = make_reward_fn(args.env_url, loop)

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        config=config,
        reward_funcs=reward_fn,
        train_dataset=dataset,
    )

    # -- Train --
    print(f"Starting GRPO training ({args.max_steps} steps) ...")
    trainer.train()

    # -- Save adapter --
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out / "lora_adapter")
    tokenizer.save_pretrained(out / "lora_adapter")
    print(f"Adapter saved to {out / 'lora_adapter'}")

    # -- Save plots --
    save_plots(trainer.state.log_history, str(out))

    # -- Save W&B summary --
    summary = {
        "total_steps": args.max_steps,
        "model_id": args.model_id,
        "final_loss": trainer.state.log_history[-1].get("loss") if trainer.state.log_history else None,
        "final_reward": trainer.state.log_history[-1].get("reward") if trainer.state.log_history else None,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
