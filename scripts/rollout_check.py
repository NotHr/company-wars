"""12-turn random rollout to verify the BOARDROOM environment works end-to-end."""

import random
import sys
import os

# Allow running from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.boardroom_environment import BoardroomEnvironment
from server.companies import L2_COMPANIES
from models import BoardroomAction

COMPANIES = [c["name"] for c in L2_COMPANIES if c["name"] != "Vermillion Capital"]
ACTION_TYPES = ["EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "PROPOSE_MERGER", "HOLD"]

rng = random.Random(42)

def random_action() -> BoardroomAction:
    atype = rng.choice(ACTION_TYPES)
    target = None
    if atype in ("SABOTAGE", "PARTNERSHIP", "PROPOSE_MERGER"):
        target = rng.choice(COMPANIES)
    return BoardroomAction(action_type=atype, action_target=target)


def main():
    env = BoardroomEnvironment()
    obs = env.reset()
    print(f"[RESET] Turn {obs.turn}  |  you_are={obs.you_are}")
    print(f"        Cash=${obs.your_stats.cash:,.0f}  Share={obs.your_stats.market_share:.1f}%  "
          f"Stock=${obs.your_stats.stock_price:.2f}")
    print()

    total_reward = 0.0
    for step in range(12):
        action = random_action()
        obs = env.step(action)
        reward = obs.reward
        total_reward += reward
        alive_flag = "ALIVE" if obs.your_stats and obs.your_stats.alive else "BANKRUPT"
        print(
            f"[Turn {obs.turn:>2}]  action={action.action_type:<14} target={str(action.action_target):<25} "
            f"reward={reward:+.4f}  cumulative={total_reward:+.4f}  {alive_flag}"
        )
        if obs.done:
            print(f"\n[DONE]  Episode finished at turn {obs.turn}  |  total_reward={total_reward:+.4f}")
            break

    print("\n[OK] Rollout completed successfully.")


if __name__ == "__main__":
    main()
