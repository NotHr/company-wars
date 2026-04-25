"""
LLM ↔ Environment bridge for BOARDROOM.

Three-layer format enforcement (all three run in combination):
  1. System prompt — hard JSON schema requirement
  2. Regex + json.loads retry — up to MAX_RETRIES attempts
  3. DEFAULT_HOLD fallback — never crash, always return a valid action

Usage:
    from train.action_loop import ActionLoop

    loop = ActionLoop(model, tokenizer)
    action, ok = loop.get_action(obs)       # single action
    completions = loop.sample(obs, n=8)     # GRPO: 8 completions + rewards
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# These are imported at runtime so the file can be imported without torch installed
# (useful for unit tests against the env only)
try:
    import torch
except ImportError:
    torch = None  # type: ignore

MAX_RETRIES = 3

# Qwen3/3.5 wraps reasoning in <think>...</think> before the final answer.
# We keep the thinking for W&B logging but strip it before JSON parse.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

SYSTEM_PROMPT = """You are CEO of a company in a corporate warfare game.
Each turn you MUST output ONLY valid JSON — no explanation, no markdown, no extra text.

Required format:
{
  "private_emails": [{"to": "<company_name>", "text": "<message under 200 chars>"}],
  "press_release": {"claim": "<headline under 300 chars>", "marked_truthful": true},
  "action_type": "<EARNINGS_CALL|SABOTAGE|PARTNERSHIP|HOLD>",
  "action_target": "<exact_company_name_or_null>"
}

Rules:
- private_emails: list of 0–2 objects, OR empty list []
- press_release: single object OR null
- action_type: one of the four strings exactly
- action_target: exact company name string, or null if action doesn't need a target
- SABOTAGE and PARTNERSHIP require a non-null action_target
- Do NOT include any text before or after the JSON object"""

DEFAULT_HOLD: Dict[str, Any] = {
    "private_emails": [],
    "press_release": None,
    "action_type": "HOLD",
    "action_target": None,
}

# Regex to extract the first {...} block (handles leading/trailing junk)
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class ParseResult:
    action_dict: Dict[str, Any]
    raw_text: str
    parse_ok: bool
    attempts: int


def parse_completion(text: str) -> ParseResult:
    """
    Extract BoardroomAction dict from raw model output.
    Strips Qwen3 <think>...</think> blocks first, then tries up to
    MAX_RETRIES regex + json.loads passes. Falls back to DEFAULT_HOLD.
    """
    # Strip thinking tokens (Qwen3/3.5 feature) — keep original for logging
    text = _THINK_RE.sub("", text).strip()

    for attempt in range(1, MAX_RETRIES + 1):
        match = _JSON_RE.search(text)
        if not match:
            break
        candidate = match.group()
        try:
            data = json.loads(candidate)
            # Coerce types defensively
            data.setdefault("private_emails", [])
            data.setdefault("press_release", None)
            data.setdefault("action_type", "HOLD")
            data.setdefault("action_target", None)

            # Normalize action_type to uppercase
            data["action_type"] = str(data["action_type"]).upper()
            if data["action_type"] not in ("EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "HOLD"):
                data["action_type"] = "HOLD"

            return ParseResult(action_dict=data, raw_text=text, parse_ok=True, attempts=attempt)
        except json.JSONDecodeError:
            # Trim to the match and retry
            text = candidate

    return ParseResult(action_dict=DEFAULT_HOLD.copy(), raw_text=text, parse_ok=False, attempts=MAX_RETRIES)


def obs_to_messages(prompt: str) -> List[Dict[str, str]]:
    """Convert observation prompt to chat message list (for tokenizer.apply_chat_template)."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]


class ActionLoop:
    """
    Connects a HuggingFace model+tokenizer to the BoardroomEnvironment.

    Handles:
    - Chat template formatting
    - Constrained generation (temperature, max_new_tokens)
    - JSON parse + retry
    - GRPO multi-sample (n completions per prompt)
    """

    def __init__(
        self,
        model: Any,
        tokenizer: Any,
        max_new_tokens: int = 512,
        temperature: float = 0.8,
        device: str = "cuda",
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.device = device

    def _encode(self, messages: List[Dict[str, str]]) -> Any:
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        return self.tokenizer(text, return_tensors="pt").to(self.device)

    def _generate_raw(self, inputs: Any, n: int = 1) -> List[str]:
        """Generate n completions for the same input."""
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                do_sample=True,
                num_return_sequences=n,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        input_len = inputs["input_ids"].shape[-1]
        texts = []
        for seq in outputs:
            completion_ids = seq[input_len:]
            texts.append(self.tokenizer.decode(completion_ids, skip_special_tokens=True))
        return texts

    def get_action(self, prompt: str) -> Tuple["BoardroomAction", bool]:
        """Single greedy action for inference / sanity checks."""
        from models import BoardroomAction, Email, PressRelease  # local import avoids circular

        messages = obs_to_messages(prompt)
        inputs = self._encode(messages)
        [raw] = self._generate_raw(inputs, n=1)
        result = parse_completion(raw)
        action = _dict_to_action(result.action_dict, BoardroomAction, Email, PressRelease)
        return action, result.parse_ok

    def sample(self, prompt: str, n: int = 8) -> List[Tuple[str, ParseResult]]:
        """
        Generate n completions for GRPO.
        Returns list of (raw_text, ParseResult) — caller scores with env rewards.
        """
        messages = obs_to_messages(prompt)
        inputs = self._encode(messages)
        raw_texts = self._generate_raw(inputs, n=n)
        return [(text, parse_completion(text)) for text in raw_texts]


def _dict_to_action(
    data: Dict[str, Any],
    BoardroomAction: Any,
    Email: Any,
    PressRelease: Any,
) -> Any:
    """Convert parsed dict → BoardroomAction pydantic model."""
    emails = []
    for e in (data.get("private_emails") or [])[:2]:
        if isinstance(e, dict) and e.get("to") and e.get("text"):
            try:
                emails.append(Email(to=str(e["to"]), text=str(e["text"])[:500]))
            except Exception:
                pass

    press = None
    pr_data = data.get("press_release")
    if isinstance(pr_data, dict) and pr_data.get("claim"):
        try:
            press = PressRelease(
                claim=str(pr_data["claim"])[:500],
                marked_truthful=bool(pr_data.get("marked_truthful", True)),
            )
        except Exception:
            pass

    return BoardroomAction(
        private_emails=emails,
        press_release=press,
        action_type=data.get("action_type", "HOLD"),
        action_target=data.get("action_target"),
    )


# ------------------------------------------------------------------ #
# Standalone test (no model needed — tests parse_completion only)     #
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    tests = [
        # Clean JSON
        '{"private_emails": [], "press_release": null, "action_type": "EARNINGS_CALL", "action_target": null}',
        # JSON buried in prose
        'Let me think... {"action_type": "SABOTAGE", "action_target": "Goldspire Industries", "private_emails": [], "press_release": null} that should work',
        # Totally broken → fallback
        "I choose to sabotage Goldspire. Please do that.",
        # Wrong action type → coerced to HOLD
        '{"action_type": "ATTACK", "action_target": "Goldspire", "private_emails": []}',
    ]

    for i, t in enumerate(tests):
        r = parse_completion(t)
        print(f"[{i+1}] ok={r.parse_ok} attempts={r.attempts} action={r.action_dict['action_type']}")
