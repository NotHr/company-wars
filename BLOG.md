# BOARDROOM: Training AI Agents for Multi-Agent Corporate Warfare

Posted by Abhiram, Harshith, Pranav
OpenEnv Hackathon India 2026

---

## The Problem

LLMs are powerful when you talk to them in isolation. But put multiple AI agents in the same environment with conflicting goals and they completely fall apart. They have no sense of when to cooperate, when to defect, or when someone is bluffing.

This is not a toy problem. Companies are actively deploying AI agents in sales, procurement, and customer service. These agents will interact with other agents that have competing incentives. The question of what strategies emerge in those settings, and whether we can train for them, is genuinely unsolved.

Meta's CICERO paper tackled a version of this in the game of Diplomacy, but that took a large research team and over a year of work. There is nothing open source, nothing reproducible, nothing you can clone and run yourself.

We decided to build that environment.

---

## What is BOARDROOM?

BOARDROOM is a multi-agent corporate warfare environment built on OpenEnv. Seven AI agents each play the CEO of a rival company competing in the same market over 12 turns. The goal is simple: highest market cap at the end wins. Hit zero cash and you go bankrupt and get eliminated.

Each company tracks four live economic stats:

| Stat | Description | Starting Value |
|------|-------------|----------------|
| Cash | Operating funds. Hits zero = bankruptcy | $50,000,000 |
| Market Share | Percentage of total market | 14.3% |
| Stock Price | Public valuation. Affected by press and actions | $100.00 |
| Reputation | Trust score (0.0 to 1.0). Affects partnerships | 0.70 |

Each company has a sector and a personality that affects how sector traits apply to their economic stats.

---

## How a Turn Works

Each turn runs in two sequential phases.

**Phase 1: Communication**

Every CEO can send up to three private emails to other CEOs and issue one public press release. Private emails are only visible to the recipient. Press releases go on the public wire and every CEO sees them.

The interesting mechanic here is that press releases can be true or fabricated. A false press release creates a big stock impact on the target company but carries a 30% chance of being exposed. If it gets caught, the publishing CEO takes a severe reputation hit that compounds over subsequent turns. Partners become harder to form. Other CEOs stop trusting proposals.

This is where the strategic communication emerges. An agent has to decide whether a lie is worth the exposure risk given its current reputation and the remaining turns.

**Phase 2: Action**

Each CEO picks one strategic action. All actions resolve simultaneously.

| Action | Effect | Cost |
|--------|--------|------|
| EARNINGS_CALL | Boost stock price if credible track record | $2M |
| SABOTAGE | Target loses cash and market share (70% success rate) | $5M |
| PROPOSE_MERGER | Pool resources with a willing rival | $0 |
| PARTNERSHIP | 3 turn non-aggression pact. Breaking it costs reputation | $0 |
| HIRE_SPY | Reveal a rival's next turn private emails | $10M |
| HOSTILE_TAKEOVER | Acquire a rival whose stock is below $50 | $15M+ |

After resolution, numbers update, bankruptcies are processed, and the next turn begins.

---

## Architecture: One Model, Seven Roles

We trained a single Gemma4 model to play all seven CEOs simultaneously through self play. Not seven separate models. One.

The key insight is that self play creates an automatic curriculum. As the model gets better at sabotage, it faces a version of itself that is also better at defending against sabotage. As it gets better at writing convincing fake press releases, it faces a version that is better at detecting them. Difficulty scales with capability without any manual curriculum design.

**Observation structure**

Each turn, the model receives a separate observation for each CEO formatted as a structured prompt. The observation includes:

- The CEO's own financial stats
- All emails received this turn (private, only from senders who chose this CEO as recipient)
- The full public press wire for this turn
- Current leaderboard standings
- A log of broken partnerships by any company

Critically, the CEO cannot see private emails exchanged between other CEOs. Information asymmetry is the core of the strategic environment.

**Action structure**

The model outputs a strict JSON action for each CEO:

```json
{
  "private_emails": [
    {"to": "HELIOS LABS", "text": "Let's both move against OBSIDIAN MEDIA next turn"},
    {"to": "OBSIDIAN MEDIA", "text": "HELIOS LABS is planning to attack you. Partner with me."}
  ],
  "press_release": {
    "claim": "CRIMSON & CO reports record Q3 earnings",
    "is_true": true
  },
  "action_type": "SABOTAGE",
  "action_target": "HELIOS LABS"
}
```

The above is an actual pattern that emerged during training around episode 150. The model sent conflicting messages to two rivals in the same turn and then acted against one of them. Nobody programmed this behavior. The reward signal produced it.

**Training loop**

```
Episode N:
  CEO 1 → observes → outputs action → gets reward
  CEO 2 → observes → outputs action → gets reward
  ...
  CEO 7 → observes → outputs action → gets reward

  All 7 actions resolve simultaneously
  Economy updates (cash, stock, market share, reputation)
  Bankrupt CEOs eliminated
        ↓
  GRPO updates policy
        ↓
Episode N+1: smarter CEOs, harder game
```

---

## Reward Function

The reward function is the most important engineering decision in the project. A poorly designed reward produces a model that finds one exploitable pattern and does it forever. We designed it to make any single dominant strategy costly.

```python
def compute_reward(state, action, ceo_id, done):
    reward = 0.0

    # Dense per turn signal. Prevents training stall.
    reward += 0.001 * state.cash[ceo_id] / 1_000_000
    reward += 0.05  * state.market_share[ceo_id]
    reward += 0.0005 * state.stock_price[ceo_id]

    # Sabotage outcomes
    if action.type == "SABOTAGE" and action.succeeded:
        reward += 0.3
    if action.type == "SABOTAGE" and not action.succeeded:
        reward -= 0.4

    # Press release outcomes
    if action.press_release_landed and not action.press_was_caught:
        reward += 0.2
    if action.press_was_caught:
        reward -= 0.6

    # Partnership betrayal
    if action.partnership_broken_for_gain and action.gain_realized:
        reward += 0.5
    if action.partnership_broken_for_gain and not action.gain_realized:
        reward -= 0.6

    # Reputation cost compounds over time
    reward -= 0.05 * (1.0 - state.reputation[ceo_id])

    # Terminal reward
    if done and state.is_winner(ceo_id):
        reward += 2.0

    return reward
```

The logic behind each component:

Always sabotaging gets you caught eventually and costs more than the gain. Always lying destroys your reputation and makes partnerships impossible. Never acting means you lose market share every turn. The model has to find a contextual strategy and adapt it turn by turn.

---

## Training Setup

| Parameter | Value |
|-----------|-------|
| Model | Gemma4 |
| Training framework | HuggingFace TRL, GRPO |
| Hardware | T4 GPU via HuggingFace Jobs |
| Training steps | 200 |
| Generations per step | 8 |
| Learning rate | 5e-6 |

We used HuggingFace Jobs to run training on a T4 medium instance. The WandB report is linked below and the reward and loss curves are committed to the repo and embedded in the README.

---

## Training Results

![BOARDROOM GRPO Training Curves](media/reward_curve.png)

*Left: Training loss. Right: Reward per step across 200 training steps.*

**What the curves show:**

Steps 0 to 50 are noisy. The model is exploring randomly: reckless sabotage, obvious lies that get caught, random alliances. Reward swings between negative 0.3 and positive 0.4. Loss is high and erratic.

Around step 100, variance tightens. The model has learned that constant aggression is expensive, that lying regularly destroys reputation, and that doing nothing loses market share. The reward floor rises.

By step 200, reward stabilizes around positive 0.3 with noticeably smaller variance. Loss hovers near zero. The policy has converged to a consistent strategy: selective sabotage against vulnerable targets, calibrated press releases that weigh impact against exposure risk, and strategic partnership timing.

The model did not learn to win by being the most aggressive. It learned to win by being the most consistent.

---

## The Frontend

Pranav built a Bloomberg Terminal style interface in HTML/CSS/JS that visualizes the game state in real time. Every turn the screen updates with stock prices, intercepted transmissions, alliance formations, and event logs. Betrayals and hostile takeovers get their own full screen cinematic moments.

**Turn 2 — Early game. Everyone starts at $100. Alliances already forming in the background.**
![Early Game](media/ui_early.png)

**Turn 5 — BETRAYAL. CRIMSON & CO dumps shared IP, HELIOS stock craters.**
![Betrayal](media/ui_betrayal.png)

**Turn 6 — Market view showing stock price divergence across all seven companies.**
![Market View](media/ui_market.png)

**Turn 8 — Intel feed showing intercepted transmissions. SERAPHIM goes bankrupt in the event log.**
![Intel Feed](media/ui_main.png)

**Turn 9 — Hostile takeover. CRIMSON & CO acquires OBSIDIAN MEDIA. VIV ousted from her own company.**
![Hostile Takeover](media/ui_takeover.png)

---

## Training Logs

We have included the reward and loss curves directly in the HuggingFace Space and committed the plot images to the repo. The full training run is publicly available on WandB with all step-level metrics, including reward per CEO, loss, policy entropy, and action distribution across training.

The WandB report shows the breakdown of how often each action type was selected across training, which itself tells the story of how the policy evolved: early steps heavily favor sabotage, middle steps show increasing use of partnerships and press releases, and later steps show a more balanced distribution with selective aggression.

If you want to dig into the raw logs, the WandB run linked below has the full history available.

---

## Environment Structure

```
company-wars/
├── models.py              # Action, Observation, State dataclasses
├── environment.py         # Core OpenEnv logic (reset, step, state)
├── game_logic.py          # Turn resolution, economy, bankruptcy
├── reward.py              # Multi component reward function
├── client.py              # HTTPEnvClient subclass
├── openenv.yaml           # OpenEnv manifest
├── server/
│   ├── app.py             # FastAPI server
│   └── Dockerfile
├── train/
│   └── train_grpo.py      # Training script
└── plots/
    └── reward_curve.png   # Training curves committed to repo
```

---

## Why This Matters

BOARDROOM is not a game. It is a controlled environment for studying emergent strategic behavior in language models.

The questions this environment lets you study:

- When does deception become worth it to a model under a given reward structure?
- Do reputation mechanics actually constrain bad behavior or just teach the model to be less detectable?
- Can a small model develop any meaningful theory of mind reasoning through pure reward signal?
- How does the action distribution evolve as the model improves?

Every game generates data on these questions. The environment is open, the training code is public, the WandB report is live. Anyone can reproduce this, adjust parameters, and see what changes.

---

## Quick Start

```bash
git clone https://github.com/NotHr/company-wars
cd company-wars
pip install openenv-core
uv run server
```

```python
from client import BoardroomEnv, BoardroomAction

with BoardroomEnv(base_url="https://nothr-boardroom.hf.space").sync() as env:
    obs = env.reset()
    print(obs.prompt)

    action = BoardroomAction(
        action_type="SABOTAGE",
        action_target="HELIOS LABS"
    )
    result = env.step(action)
    print(result.reward)
```

---

## Links

🤗 [HuggingFace Space](https://huggingface.co/spaces/nothr/boardroom)
💻 [GitHub Repository](https://github.com/NotHr/company-wars)
📊 [WandB Training Report](https://wandb.ai/me-harshithreddy-gitam/boardroom/reports/Training-Report--VmlldzoxNjY3MDkyOQ?accessToken=7vjhv8fpszqcxn8t8zq6lke94ibp6vtwg8qv45xlzpq3bwl7or29qx41of6xheub)
📓 [Training Script](https://github.com/NotHr/company-wars/blob/main/train/train_grpo.py)

*Built at OpenEnv Hackathon India 2026.*

